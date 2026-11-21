"""Login to AcegasApsAmga with email and password (Azure AD B2C).

The same four steps the browser goes through:

1. GET the authorize page: it holds the CSRF token and the transaction id.
2. POST email and password to SelfAsserted.
3. GET "confirmed": B2C redirects to the portal with the authorization code.
4. POST the code to the token endpoint, with the PKCE verifier.

B2C gives single-page apps refresh tokens that last at most 24 hours, so the
integration logs in again with the password about once a day.

No Home Assistant imports: this module only needs an aiohttp session created
with nuovo_cookie_jar().
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import math
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import aiohttp

from .const import (
    B2C_AUTHORIZE_URL,
    B2C_CLIENT_ID,
    B2C_HOST,
    B2C_REDIRECT_URI,
    B2C_REFERRER,
    B2C_SCOPE,
    B2C_TOKEN_URL,
    PORTALE_ORIGIN,
)

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=30)
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36"
)
MAX_REDIRECT = 8

_RE_SETTINGS = re.compile(r"var\s+SETTINGS\s*=\s*")
_REDIRECT_PARTI = urlsplit(B2C_REDIRECT_URI)
_ERRORI_TRANSITORI_OAUTH = frozenset({"server_error", "temporarily_unavailable"})


def _e_redirect_portale(location: str) -> bool:
    parti = urlsplit(location)
    return (parti.scheme, parti.netloc, parti.path) == (
        _REDIRECT_PARTI.scheme,
        _REDIRECT_PARTI.netloc,
        _REDIRECT_PARTI.path,
    )


def nuovo_cookie_jar() -> aiohttp.CookieJar:
    """Cookie jar for the login session.

    B2C's cookies must go back exactly as received. By default aiohttp puts
    some of them in quotes, and B2C then answers HTTP 400 to the password.
    """
    return aiohttp.CookieJar(quote_cookie=False)


class AuthError(Exception):
    """Login failed."""


class CredenzialiNonValide(AuthError):
    """B2C rejected email or password. The message is B2C's own."""


class PassaggioInatteso(AuthError):
    """B2C asked for another step (new terms, password change...): it has to
    be done once on the website."""


class RispostaInattesa(AuthError):
    """B2C answered with something unknown: the page or the protocol changed."""


class ErroreRete(AuthError):
    """B2C could not be reached."""


class TokenNonValido(AuthError):
    """The refresh token is expired or revoked."""


@dataclass
class Token:
    access_token: str
    refresh_token: str | None
    scadenza: float  # epoch seconds
    id_utente: str | None

    def valido(self, margine: float = 120) -> bool:
        return time.time() < self.scadenza - margine


def _base64url(dati: bytes) -> str:
    return base64.urlsafe_b64encode(dati).rstrip(b"=").decode("ascii")


def pkce() -> tuple[str, str]:
    """(verifier, S256 challenge)."""
    verifier = _base64url(secrets.token_bytes(48))
    return verifier, _base64url(hashlib.sha256(verifier.encode("ascii")).digest())


def id_utente_da_token(access_token: str) -> str | None:
    """The token's 'sub' claim, read without verifying the signature: only
    used as a stable account id."""
    try:
        payload = access_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError):
        return None
    return claims.get("sub") or claims.get("oid")


def estrai_settings(html: str) -> dict[str, Any]:
    """The SETTINGS object of a B2C page (csrf, transId, hosts, api)."""
    corrispondenza = _RE_SETTINGS.search(html)
    if corrispondenza is None:
        raise RispostaInattesa("pagina di accesso senza SETTINGS")
    try:
        settings, _ = json.JSONDecoder().raw_decode(html, corrispondenza.end())
    except ValueError as err:
        raise RispostaInattesa(f"SETTINGS non interpretabile: {err}") from err
    if not isinstance(settings, dict):
        raise RispostaInattesa("SETTINGS non è un oggetto JSON")
    for chiave in ("csrf", "transId"):
        if not settings.get(chiave):
            raise RispostaInattesa(f"SETTINGS senza {chiave}")
    return settings


def codice_da_redirect(location: str, state: str) -> str:
    """Authorization code from the redirect to the portal."""
    parti = urlsplit(location)
    parametri = {**parse_qs(parti.query), **parse_qs(parti.fragment)}
    if "error" in parametri:
        errore = parametri["error"][0]
        descrizione = (parametri.get("error_description") or parametri["error"])[0]
        if errore in _ERRORI_TRANSITORI_OAUTH:
            raise RispostaInattesa(descrizione)
        # For example "forgot password" or a cancelled login.
        raise PassaggioInatteso(descrizione)
    stato_ricevuto = parametri.get("state", [None])[0]
    if not stato_ricevuto or not secrets.compare_digest(stato_ricevuto, state):
        raise RispostaInattesa("redirect con uno state diverso da quello inviato")
    codice = parametri.get("code", [None])[0]
    if not codice:
        raise RispostaInattesa("redirect senza codice di autorizzazione")
    return codice


def _token_da_risposta(
    dati: dict[str, Any], *, refresh_precedente: str | None = None
) -> Token:
    access_token = dati.get("access_token")
    if not access_token:
        raise RispostaInattesa("risposta del token senza access_token")
    grezza_durata = dati.get("expires_in")
    durata = 3600.0
    if not isinstance(grezza_durata, bool):
        try:
            candidata = float(grezza_durata)
        except (TypeError, ValueError):
            candidata = 0.0
        if math.isfinite(candidata) and candidata > 0:
            durata = candidata
    return Token(
        access_token=access_token,
        refresh_token=dati.get("refresh_token") or refresh_precedente,
        scadenza=time.time() + durata,
        id_utente=id_utente_da_token(access_token),
    )


class AuthClient:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def async_login(self, email: str, password: str) -> Token:
        # Clear all session cookies (including parent-domain .acegasapsamga.it
        # cookies) so B2C's SSO never skips the form or reuses a previous account.
        self._session.cookie_jar.clear()

        verifier, challenge = pkce()
        state = secrets.token_urlsafe(16)
        parametri = {
            "client_id": B2C_CLIENT_ID,
            "redirect_uri": B2C_REDIRECT_URI,
            "response_type": "code",
            "response_mode": "query",
            "scope": B2C_SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "nonce": secrets.token_urlsafe(16),
            "referrer": B2C_REFERRER,
            "env": "prod",
        }
        url_authorize = f"{B2C_AUTHORIZE_URL}?{urlencode(parametri)}"
        stato, html, location = await self._get(url_authorize)
        if location is not None and _e_redirect_portale(location):
            codice = codice_da_redirect(location, state)
        else:
            if stato != 200:
                raise RispostaInattesa(f"pagina di accesso: HTTP {stato}")
            settings = estrai_settings(html)
            await self._invia_credenziali(settings, url_authorize, email, password)
            codice = await self._conferma(settings, state)
        return await self._richiedi_token(
            {
                "grant_type": "authorization_code",
                "client_id": B2C_CLIENT_ID,
                "scope": B2C_SCOPE,
                "code": codice,
                "redirect_uri": B2C_REDIRECT_URI,
                "code_verifier": verifier,
            }
        )

    async def async_refresh(self, refresh_token: str) -> Token:
        return await self._richiedi_token(
            {
                "grant_type": "refresh_token",
                "client_id": B2C_CLIENT_ID,
                "scope": B2C_SCOPE,
                "refresh_token": refresh_token,
            },
            refresh=True,
            refresh_precedente=refresh_token,
        )

    async def _get(self, url: str) -> tuple[int, str, str | None]:
        """(status, body, absolute Location) of a GET without redirects."""
        try:
            async with self._session.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "it-IT,it;q=0.9"},
                allow_redirects=False,
                timeout=TIMEOUT,
            ) as risposta:
                location = risposta.headers.get("Location")
                if location is not None:
                    location = urljoin(url, location)
                return risposta.status, await risposta.text(), location
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ErroreRete(str(err) or type(err).__name__) from err

    def _url_b2c(self, settings: dict[str, Any], percorso: str) -> str:
        hosts = settings.get("hosts") or {}
        tenant = hosts.get("tenant") or "/myheraapp.onmicrosoft.com/B2C_1A_SignIn_Web"
        policy = hosts.get("policy") or "B2C_1A_SignIn_Web"
        query = urlencode({"tx": settings["transId"], "p": policy})
        return f"https://{B2C_HOST}{tenant}/{percorso}?{query}"

    async def _invia_credenziali(
        self, settings: dict[str, Any], referer: str, email: str, password: str
    ) -> None:
        if settings.get("trimSpacesInPassword", True):
            password = password.strip()
        try:
            async with self._session.post(
                self._url_b2c(settings, "SelfAsserted"),
                data={"request_type": "RESPONSE", "signInName": email.strip(), "password": password},
                headers={
                    "User-Agent": USER_AGENT,
                    "X-CSRF-TOKEN": settings["csrf"],
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": f"https://{B2C_HOST}",
                    "Referer": referer,
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                },
                allow_redirects=False,
                timeout=TIMEOUT,
            ) as risposta:
                stato_http = risposta.status
                testo = await risposta.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ErroreRete(str(err) or type(err).__name__) from err

        try:
            esito = json.loads(testo)
        except ValueError as err:
            raise RispostaInattesa(f"SelfAsserted: HTTP {stato_http}, risposta non JSON") from err
        if stato_http >= 500 or not isinstance(esito, dict):
            raise RispostaInattesa(f"SelfAsserted: HTTP {stato_http}")
        stato = str(esito.get("status"))
        if stato == "200":
            return
        messaggio = esito.get("message") or esito.get("errorCode") or "credenziali rifiutate"
        if stato == "400":
            raise CredenzialiNonValide(messaggio)
        raise RispostaInattesa(f"SelfAsserted: {messaggio}")

    async def _conferma(self, settings: dict[str, Any], state: str) -> str:
        api = settings.get("api") or "CombinedSigninAndSignup"
        url = self._url_b2c(settings, f"api/{api}/confirmed")
        url += "&" + urlencode({"rememberMe": "false", "csrf_token": settings["csrf"]})
        for _ in range(MAX_REDIRECT):
            stato, html, location = await self._get(url)
            if location is None:
                if stato != 200:
                    raise RispostaInattesa(f"conferma: HTTP {stato}")
                # A page instead of a redirect: B2C wants another step.
                try:
                    passo = estrai_settings(html).get("api")
                except RispostaInattesa:
                    passo = None
                raise PassaggioInatteso(passo or f"HTTP {stato}")
            if _e_redirect_portale(location):
                return codice_da_redirect(location, state)
            url = location
        raise RispostaInattesa("troppi redirect dopo la password")

    async def _richiedi_token(
        self,
        dati: dict[str, str],
        *,
        refresh: bool = False,
        refresh_precedente: str | None = None,
    ) -> Token:
        try:
            async with self._session.post(
                B2C_TOKEN_URL,
                data=dati,
                # The Origin header is required for single-page apps.
                headers={"User-Agent": USER_AGENT, "Origin": PORTALE_ORIGIN, "Accept": "application/json"},
                timeout=TIMEOUT,
            ) as risposta:
                stato = risposta.status
                testo = await risposta.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ErroreRete(str(err) or type(err).__name__) from err

        try:
            corpo = json.loads(testo)
        except ValueError as err:
            raise RispostaInattesa(f"token: HTTP {stato}, risposta non JSON") from err
        if not isinstance(corpo, dict):
            raise RispostaInattesa(f"token: HTTP {stato}, risposta inattesa")
        if stato == 200:
            return _token_da_risposta(corpo, refresh_precedente=refresh_precedente)
        descrizione = corpo.get("error_description") or corpo.get("error") or f"HTTP {stato}"
        if refresh and corpo.get("error") in ("invalid_grant", "invalid_request"):
            raise TokenNonValido(descrizione)
        raise RispostaInattesa(f"token: {descrizione}")
