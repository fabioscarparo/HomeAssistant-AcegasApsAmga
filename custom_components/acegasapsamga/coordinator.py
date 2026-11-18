"""Coordinator: downloads the data of each contract and writes the statistics.

For each contract it reads the whole archive, the billing periods, the
self-reading window and the bills. Everything is kept in the integration's
store, so the sensors have values right after a restart and while the portal
is down.

Tokens stay in memory: when they expire the coordinator logs in again with
the stored email and password.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import bollette as bl
from . import letture as lt
from .api import ApiClient, ApiError, TokenScaduto
from .auth import (
    AuthClient,
    AuthError,
    CredenzialiNonValide,
    ErroreRete,
    PassaggioInatteso,
    Token,
    TokenNonValido,
    nuovo_cookie_jar,
)
from .const import CONF_CONTRATTI, DOMAIN, INTERVALLO_AGGIORNAMENTO_ORE
from .statistics import async_scrivi_serie, async_ultima_ora, statistic_id
from .testi import testo

_LOGGER = logging.getLogger(__name__)

VERSIONE_STORE = 1
INTERVALLO_NORMALE = timedelta(hours=INTERVALLO_AGGIORNAMENTO_ORE)
INTERVALLO_DOPO_ERRORE = timedelta(minutes=30)


@dataclass
class DatiContratto:
    letture: list[lt.Lettura] = field(default_factory=list)
    consumi: list[dict[str, Any]] = field(default_factory=list)
    finestra: dict[str, Any] | None = None
    bollette: list[bl.Bolletta] = field(default_factory=list)

    def come_dict(self) -> dict[str, Any]:
        return {
            "letture": [lettura.come_dict() for lettura in self.letture],
            "consumi": self.consumi,
            "finestra": self.finestra,
            "bollette": [bolletta.come_dict() for bolletta in self.bollette],
        }

    @classmethod
    def da_dict(cls, dati: dict[str, Any]) -> DatiContratto:
        letture = []
        for grezza in dati.get("letture") or []:
            try:
                letture.append(lt.Lettura.da_dict(grezza))
            except (KeyError, TypeError, ValueError):
                _LOGGER.debug("Lettura salvata non valida, ignorata: %r", grezza)
        bollette = []
        for grezza in dati.get("bollette") or []:
            try:
                bollette.append(bl.Bolletta.da_dict(grezza))
            except (KeyError, TypeError, ValueError):
                _LOGGER.debug("Bolletta salvata non valida, ignorata: %r", grezza)
        return cls(
            letture=lt.ordina(letture),
            consumi=list(dati.get("consumi") or []),
            finestra=dati.get("finestra"),
            bollette=bl.ordina(bollette),
        )


def _giorno_iso(valore: Any) -> str | None:
    giorno = lt.giorno_da_ms(valore)
    return giorno.isoformat() if giorno else None


def consumi_da_api(grezzi: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Billing periods with ISO dates, newest first."""
    periodi = []
    for periodo in grezzi:
        dal, al = _giorno_iso(periodo.get("usageFromDate")), _giorno_iso(periodo.get("usageToDate"))
        try:
            consumo = float(periodo.get("totalUsage"))
        except (TypeError, ValueError):
            continue
        if dal is None or al is None:
            continue
        giorni = (date.fromisoformat(al) - date.fromisoformat(dal)).days + 1
        periodi.append(
            {
                "dal": dal,
                "al": al,
                "consumo": round(consumo, 3),
                "media_giornaliera": round(consumo / giorni, 4) if giorni > 0 else None,
                "tipo": periodo.get("readType"),
            }
        )
    return sorted(periodi, key=lambda p: p["al"], reverse=True)


def finestra_da_api(grezza: dict[str, Any] | None) -> dict[str, Any] | None:
    """Self-reading window: first and last day, and whether it is open now."""
    if not grezza:
        return None
    inizio, fine = _giorno_iso(grezza.get("startDate")), _giorno_iso(grezza.get("endDate"))
    if inizio is None:
        return None
    return {"inizio": inizio, "fine": fine, "aperta": bool(grezza.get("insideTimeFrame"))}


def firma(letture: list[lt.Lettura]) -> str:
    """Fingerprint of the real readings, to rewrite the series only when they change."""
    grezzo = json.dumps([lettura.come_dict() for lettura in lt.ancore(letture)], sort_keys=True)
    return hashlib.sha256(grezzo.encode()).hexdigest()[:16]


class AcegasCoordinator(DataUpdateCoordinator[dict[str, DatiContratto]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({entry.title})",
            update_interval=INTERVALLO_NORMALE,
            config_entry=entry,
        )
        self.entry = entry
        # A session of its own, so B2C's cookies stay out of the shared one.
        # Home Assistant releases it when the entry is unloaded.
        session = async_create_clientsession(hass, cookie_jar=nuovo_cookie_jar())
        self._auth = AuthClient(session)
        self._api = ApiClient(session)
        self._token: Token | None = None
        self._store: Store[dict[str, Any]] = Store(
            hass, VERSIONE_STORE, f"{DOMAIN}.{entry.entry_id}"
        )
        self._firme: dict[str, str] = {}
        # billGroupType of each profile: it does not change, one call is enough.
        self._raggruppamenti: dict[str, str | None] = {}
        # Shown in the diagnostics.
        self.ultimo_accesso: str | None = None
        self.ultimo_errore: str | None = None
        self.serie_scritte: dict[str, str] = {}

    @property
    def contratti(self) -> list[dict[str, Any]]:
        return list(self.entry.data.get(CONF_CONTRATTI) or [])

    @property
    def lingua(self) -> str:
        return self.hass.config.language

    @staticmethod
    def codice(contratto: dict[str, Any]) -> str:
        """Supply point code, or the contract number if missing."""
        return str(contratto.get("pod") or contratto["contratto"])

    def statistic_id(self, contratto: dict[str, Any]) -> str:
        return statistic_id(contratto["servizio"], self.codice(contratto))

    def nome_serie(self, contratto: dict[str, Any]) -> str:
        servizio = testo(self.lingua, f"servizio_{contratto['servizio']}").lower()
        return testo(self.lingua, "statistica", servizio=servizio, codice=self.codice(contratto))

    # --- Store ---------------------------------------------------------------

    async def async_carica_cache(self) -> bool:
        """Load the data of the last update. True if there was any."""
        salvati = await self._store.async_load() or {}
        per_contratto = salvati.get("contratti") or {}
        self._firme = dict(salvati.get("firme") or {})
        dati = {
            c["contratto"]: DatiContratto.da_dict(per_contratto[c["contratto"]])
            for c in self.contratti
            if c["contratto"] in per_contratto
        }
        if dati:
            self.data = dati
        return bool(dati)

    async def _async_salva(self, dati: dict[str, DatiContratto]) -> None:
        await self._store.async_save(
            {
                "contratti": {numero: valori.come_dict() for numero, valori in dati.items()},
                "firme": self._firme,
            }
        )

    # --- Login ---------------------------------------------------------------

    async def _async_assicura_token(self, *, forza: bool = False) -> None:
        if self._token is not None and self._token.valido() and not forza:
            return
        token: Token | None = None
        if self._token is not None and self._token.refresh_token:
            try:
                token = await self._auth.async_refresh(self._token.refresh_token)
            except ErroreRete as err:
                raise UpdateFailed(f"AcegasApsAmga non raggiungibile: {err}") from err
            except (TokenNonValido, AuthError) as err:
                _LOGGER.debug("Rinnovo del token non riuscito (%s): nuovo accesso", err)
        if token is None:
            try:
                token = await self._auth.async_login(
                    self.entry.data[CONF_EMAIL], self.entry.data[CONF_PASSWORD]
                )
            except (CredenzialiNonValide, PassaggioInatteso) as err:
                self.ultimo_errore = f"{type(err).__name__}: {err}"
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="accesso_rifiutato",
                    translation_placeholders={"messaggio": str(err)},
                ) from err
            except AuthError as err:
                raise UpdateFailed(f"Accesso ad AcegasApsAmga non riuscito: {err}") from err
            self.ultimo_accesso = dt_util.utcnow().isoformat()
        self._token = token
        self._api.access_token = token.access_token

    async def _chiama(self, metodo, *argomenti):
        """Call the API; if the token is refused, log in again and retry once."""
        try:
            return await metodo(*argomenti)
        except TokenScaduto:
            await self._async_assicura_token(forza=True)
            return await metodo(*argomenti)

    # --- Update --------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, DatiContratto]:
        precedenti = self.data or {}
        try:
            await self._async_assicura_token()
            # Bills belong to the profile: one call for all its contracts.
            bollette = {
                profilo: await self._async_bollette(profilo)
                for profilo in dict.fromkeys(c["profilo"] for c in self.contratti)
            }
            dati = {
                c["contratto"]: await self._async_aggiorna_contratto(
                    c, precedenti.get(c["contratto"]), bollette[c["profilo"]]
                )
                for c in self.contratti
            }
        except (ApiError, UpdateFailed) as err:
            self.ultimo_errore = f"{type(err).__name__}: {err}"
            self.update_interval = INTERVALLO_DOPO_ERRORE
            if isinstance(err, UpdateFailed):
                raise
            raise UpdateFailed(f"Errore dal portale AcegasApsAmga: {err}") from err
        self.update_interval = INTERVALLO_NORMALE
        self.ultimo_errore = None

        for contratto in self.contratti:
            try:
                await self._async_aggiorna_statistiche(contratto, dati[contratto["contratto"]])
            except Exception:  # noqa: BLE001 - the sensors must update anyway
                _LOGGER.exception(
                    "Contratto %s: scrittura delle statistiche non riuscita", contratto["contratto"]
                )
        await self._async_salva(dati)
        return dati

    async def _async_bollette(self, profilo: str) -> list[bl.Bolletta] | None:
        """Bills of a profile, or None if they cannot be read: then each
        contract keeps the ones it had."""
        try:
            if profilo not in self._raggruppamenti:
                self._raggruppamenti[profilo] = await self._chiama(
                    self._api.async_raggruppamento_bollette, profilo
                )
            grezze = await self._chiama(self._api.async_bollette, profilo, self._raggruppamenti[profilo])
        except TokenScaduto:
            raise
        except ApiError as err:
            _LOGGER.debug("Profilo %s: bollette non disponibili (%s)", profilo, err)
            return None
        return bl.estrai_bollette(grezze)

    async def _async_aggiorna_contratto(
        self,
        contratto: dict[str, Any],
        precedenti: DatiContratto | None,
        bollette: list[bl.Bolletta] | None = None,
    ) -> DatiContratto:
        profilo, numero = contratto["profilo"], contratto["contratto"]
        precedenti = precedenti or DatiContratto()

        grezze = await self._chiama(self._api.async_letture, profilo, contratto["servizio"], numero)
        nuove = lt.estrai_letture(grezze)
        if grezze and not nuove:
            _LOGGER.warning(
                "Contratto %s: nessuna lettura interpretabile, formato cambiato? %r",
                numero,
                grezze[:3],
            )
        dati = DatiContratto(
            letture=lt.unisci(precedenti.letture, nuove),
            consumi=precedenti.consumi,
            finestra=precedenti.finestra,
            bollette=(
                bl.del_contratto(bollette, numero) if bollette is not None else precedenti.bollette
            ),
        )

        # Billing periods and self-reading window are extras: if they fail,
        # the previous values stay.
        try:
            dati.consumi = consumi_da_api(await self._chiama(self._api.async_consumi, profilo, numero))
        except TokenScaduto:
            raise
        except ApiError as err:
            _LOGGER.debug("Contratto %s: consumi non disponibili (%s)", numero, err)
        try:
            dati.finestra = finestra_da_api(
                await self._chiama(self._api.async_finestra_autolettura, profilo, numero)
            )
        except TokenScaduto:
            raise
        except ApiError as err:
            _LOGGER.debug("Contratto %s: finestra di autolettura non disponibile (%s)", numero, err)
        return dati

    async def _async_aggiorna_statistiche(
        self, contratto: dict[str, Any], dati: DatiContratto
    ) -> None:
        sid = self.statistic_id(contratto)
        righe = lt.serie_oraria(dati.letture, dt_util.utcnow())
        if not righe:
            _LOGGER.debug("%s: servono almeno due letture reali", sid)
            return
        ultima_scritta = await async_ultima_ora(self.hass, sid)
        nuova_firma = firma(dati.letture)
        # Nothing changed: skip the write.
        if ultima_scritta == righe[-1]["start"] and self._firme.get(sid) == nuova_firma:
            return
        await async_scrivi_serie(
            self.hass, sid, self.nome_serie(contratto), righe, ultima_ora_scritta=ultima_scritta
        )
        self._firme[sid] = nuova_firma
        self.serie_scritte[sid] = righe[-1]["start"].isoformat()
