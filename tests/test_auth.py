"""B2C login with a simulated server: the four steps and their errors."""
from __future__ import annotations

import base64
import json
from urllib.parse import parse_qs, urlsplit

import aiohttp
import pytest

from custom_components.acegasapsamga import auth
from custom_components.acegasapsamga.const import B2C_AUTHORIZE_URL, B2C_REDIRECT_URI, B2C_TOKEN_URL

from .conftest import RispostaFinta, SessioneFinta

TENANT_URL = "https://login.acegasapsamga.it/myheraapp.onmicrosoft.com/B2C_1A_SignIn_Web"
PAGINA = """<html><script>
var SETTINGS = {
  "csrf": "CSRF1",
  "transId": "StateProperties=abc",
  "api": "CombinedSigninAndSignup",
  "trimSpacesInPassword": true,
  "hosts": {"tenant": "/myheraapp.onmicrosoft.com/B2C_1A_SignIn_Web", "policy": "B2C_1A_SignIn_Web"}
};
</script></html>"""


def _jwt(claims: dict) -> str:
    corpo = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"eyJhbGciOiJub25lIn0.{corpo}.firma"


ACCESS_TOKEN = _jwt({"sub": "utente-1", "aud": "x"})


class Redirect:
    """Redirect to the portal carrying the state the client sent."""

    def __init__(self, sessione: SessioneFinta, **extra: str):
        self.sessione = sessione
        self.extra = extra

    def risposta(self) -> RispostaFinta:
        authorize = next(r for r in self.sessione.richieste if r["url"].startswith(B2C_AUTHORIZE_URL))
        state = parse_qs(urlsplit(authorize["url"]).query)["state"][0]
        parametri = {"state": state, "code": "CODICE", **self.extra}
        query = "&".join(f"{k}={v}" for k, v in parametri.items())
        return RispostaFinta(302, "", {"Location": f"{B2C_REDIRECT_URI}?{query}"})


class SessioneB2C(SessioneFinta):
    """Answers like B2C; 'confermato' builds the redirect when it is called."""

    def __init__(self, esito_password=None, conferma=None, token=None, errore=None):
        super().__init__()
        self._extra = errore or {}
        self.aggiungi("GET", B2C_AUTHORIZE_URL, RispostaFinta(200, PAGINA))
        self.aggiungi("POST", f"{TENANT_URL}/SelfAsserted", esito_password or RispostaFinta(200, {"status": "200"}))
        self._conferma = conferma
        self.aggiungi(
            "POST",
            B2C_TOKEN_URL,
            token
            or RispostaFinta(
                200, {"access_token": ACCESS_TOKEN, "refresh_token": "RT1", "expires_in": 3600}
            ),
        )

    def get(self, url, **kwargs):
        if url.startswith(f"{TENANT_URL}/api/CombinedSigninAndSignup/confirmed"):
            self.richieste.append({"metodo": "GET", "url": url, **kwargs})
            return self._conferma or Redirect(self, **self._extra).risposta()
        return super().get(url, **kwargs)


async def test_login_completo():
    sessione = SessioneB2C()
    token = await auth.AuthClient(sessione).async_login(" utente@example.com ", " segreta ")

    assert token.access_token == ACCESS_TOKEN
    assert token.refresh_token == "RT1"
    assert token.id_utente == "utente-1"
    assert token.valido()
    assert sessione.cookie_jar.pulito == ["login.acegasapsamga.it"]

    authorize, password, conferma, richiesta_token = sessione.richieste
    parametri = parse_qs(urlsplit(authorize["url"]).query)
    assert parametri["code_challenge_method"] == ["S256"]
    assert parametri["redirect_uri"] == [B2C_REDIRECT_URI]
    assert password["data"] == {
        "request_type": "RESPONSE",
        "signInName": "utente@example.com",
        "password": "segreta",
    }
    assert password["headers"]["X-CSRF-TOKEN"] == "CSRF1"
    assert "csrf_token=CSRF1" in conferma["url"]
    assert richiesta_token["data"]["code"] == "CODICE"
    assert richiesta_token["data"]["code_verifier"]
    assert richiesta_token["headers"]["Origin"] == "https://servizionline.acegasapsamga.it"


async def test_credenziali_rifiutate():
    sessione = SessioneB2C(
        esito_password=RispostaFinta(200, {"status": "400", "message": "Credenziali non valide."})
    )
    with pytest.raises(auth.CredenzialiNonValide, match="Credenziali non valide"):
        await auth.AuthClient(sessione).async_login("utente@example.com", "sbagliata")


async def test_passaggio_in_piu_dopo_la_password():
    pagina = PAGINA.replace("CombinedSigninAndSignup", "SelfAsserted")
    sessione = SessioneB2C(conferma=RispostaFinta(200, pagina))
    with pytest.raises(auth.PassaggioInatteso, match="SelfAsserted"):
        await auth.AuthClient(sessione).async_login("utente@example.com", "segreta")


async def test_errore_nel_redirect():
    sessione = SessioneB2C(errore={"error": "access_denied", "error_description": "AADB2C90091"})
    with pytest.raises(auth.PassaggioInatteso, match="AADB2C90091"):
        await auth.AuthClient(sessione).async_login("utente@example.com", "segreta")


async def test_pagina_senza_settings():
    sessione = SessioneB2C()
    sessione.rotte[0] = ("GET", B2C_AUTHORIZE_URL, RispostaFinta(200, "<html>manutenzione</html>"))
    with pytest.raises(auth.RispostaInattesa):
        await auth.AuthClient(sessione).async_login("utente@example.com", "segreta")


async def test_rete_non_raggiungibile():
    sessione = SessioneFinta()
    sessione.aggiungi("GET", B2C_AUTHORIZE_URL, aiohttp.ClientConnectionError("dns"))
    with pytest.raises(auth.ErroreRete):
        await auth.AuthClient(sessione).async_login("utente@example.com", "segreta")


async def test_refresh():
    sessione = SessioneFinta()
    sessione.aggiungi(
        "POST",
        B2C_TOKEN_URL,
        RispostaFinta(200, {"access_token": ACCESS_TOKEN, "refresh_token": "RT2", "expires_in": 3600}),
    )
    token = await auth.AuthClient(sessione).async_refresh("RT1")
    assert token.refresh_token == "RT2"
    assert sessione.richieste[0]["data"]["grant_type"] == "refresh_token"


async def test_refresh_scaduto():
    sessione = SessioneFinta()
    sessione.aggiungi(
        "POST",
        B2C_TOKEN_URL,
        RispostaFinta(400, {"error": "invalid_grant", "error_description": "AADB2C90080: expired"}),
    )
    with pytest.raises(auth.TokenNonValido):
        await auth.AuthClient(sessione).async_refresh("RT1")


def test_id_utente_da_token_non_valido():
    assert auth.id_utente_da_token("non-un-jwt") is None


async def test_cookie_jar_senza_virgolette():
    # B2C answers 400 to the password if its cookies come back quoted.
    assert auth.nuovo_cookie_jar()._quote_cookie is False
