"""Coordinator: downloads the data of each contract and writes the statistics.

For each contract it reads the whole archive, the billing periods, the
self-reading window and the bills. Everything is kept in the integration's
store, so the sensors have values right after a restart and while the portal
is down.

Tokens stay in memory: when they expire the coordinator logs in again with
the stored email and password.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from functools import cached_property
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import bollette as bl
from . import letture as lt
from .api import ApiClient, ApiError, TokenScaduto, contratto_da_api
from .auth import (
    AuthClient,
    AuthError,
    CredenzialiNonValide,
    ErroreRete,
    PassaggioInatteso,
    Token,
    nuovo_cookie_jar,
)
from .const import CONF_CONTRATTI, DOMAIN, INTERVALLO_AGGIORNAMENTO_ORE
from .statistics import async_cancella_serie, async_scrivi_serie, async_ultima_ora, statistic_id
from .testi import testo

_LOGGER = logging.getLogger(__name__)

VERSIONE_STORE = 1
INTERVALLO_NORMALE = timedelta(hours=INTERVALLO_AGGIORNAMENTO_ORE)
INTERVALLO_DOPO_ERRORE = timedelta(minutes=30)
_FINESTRA_MANCANTE: Any = object()


@dataclass
class DatiContratto:
    letture: list[lt.Lettura] = field(default_factory=list)
    finestra: dict[str, Any] | None = None
    bollette: list[bl.Bolletta] = field(default_factory=list)

    @cached_property
    def ancore(self) -> list[lt.Lettura]:
        return lt.ancore(self.letture)

    @cached_property
    def ultima_reale(self) -> lt.Lettura | None:
        return self.ancore[-1] if self.ancore else None

    @cached_property
    def periodi(self) -> list[dict[str, Any]]:
        return lt.periodi(self.ancore)

    @cached_property
    def ultimo_periodo(self) -> dict[str, Any] | None:
        return self.periodi[-1] if self.periodi else None

    def come_dict(self) -> dict[str, Any]:
        return {
            "letture": [lettura.come_dict() for lettura in self.letture],
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
            finestra=dati.get("finestra"),
            bollette=bl.ordina(bollette),
        )


def _giorno_iso(valore: Any) -> str | None:
    giorno = lt.giorno_da_ms(valore)
    return giorno.isoformat() if giorno else None


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
        self._lock_token = asyncio.Lock()
        self._store: Store[dict[str, Any]] = Store(
            hass, VERSIONE_STORE, f"{DOMAIN}.{entry.entry_id}"
        )
        self._firme: dict[str, str] = {}
        # billGroupType of each profile: it does not change, one call is enough.
        self._raggruppamenti: dict[str, str] = {}
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

    @property
    def ha_token_valido(self) -> bool:
        return self._token is not None and self._token.valido()

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
        sid_attivi = {self.statistic_id(c) for c in self.contratti}
        self._firme = {
            sid: valore
            for sid, valore in (salvati.get("firme") or {}).items()
            if sid in sid_attivi
        }
        dati = {
            c["contratto"]: DatiContratto.da_dict(per_contratto[c["contratto"]])
            for c in self.contratti
            if c["contratto"] in per_contratto
        }
        if dati:
            self.data = dati
        return bool(dati)

    async def _async_salva(self, dati: dict[str, DatiContratto]) -> None:
        sid_attivi = {self.statistic_id(c) for c in self.contratti}
        self._firme = {sid: v for sid, v in self._firme.items() if sid in sid_attivi}
        await self._store.async_save(
            {
                "contratti": {numero: valori.come_dict() for numero, valori in dati.items()},
                "firme": self._firme,
            }
        )

    # --- Login ---------------------------------------------------------------

    async def _async_assicura_token(
        self, *, forza: bool = False, token_rifiutato: str | None = None
    ) -> None:
        async with self._lock_token:
            if (
                token_rifiutato is not None
                and self._api.access_token
                and self._api.access_token != token_rifiutato
                and self._token is not None
                and self._token.valido()
            ):
                return
            if self._token is not None and self._token.valido() and not forza:
                return
            token: Token | None = None
            if self._token is not None and self._token.refresh_token:
                try:
                    token = await self._auth.async_refresh(self._token.refresh_token)
                except ErroreRete as err:
                    raise UpdateFailed(f"AcegasApsAmga non raggiungibile: {err}") from err
                except AuthError as err:
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
        """Call the API; if the token is refused, refresh/log in once and retry."""
        token_usato = self._api.access_token
        try:
            return await metodo(*argomenti)
        except TokenScaduto:
            await self._async_assicura_token(forza=True, token_rifiutato=token_usato)
            return await metodo(*argomenti)

    async def async_contratti_account(self) -> list[dict[str, Any]]:
        """List the account's contracts reusing the coordinator's session and token."""
        await self._async_assicura_token()
        return [contratto_da_api(p, c) for p, c in await self._chiama(self._api.async_contratti_account)]

    # --- Update --------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, DatiContratto]:
        precedenti = self.data or {}
        profili = list(dict.fromkeys(c["profilo"] for c in self.contratti))
        try:
            await self._async_assicura_token()
            # Bills belong to the profile; fetch profiles and contracts in parallel.
            risultati = await asyncio.gather(
                *(self._async_bollette(profilo) for profilo in profili),
                *(self._async_scarica_contratto(c) for c in self.contratti),
            )
        except (ApiError, UpdateFailed) as err:
            self.ultimo_errore = f"{type(err).__name__}: {err}"
            self.update_interval = INTERVALLO_DOPO_ERRORE
            if isinstance(err, UpdateFailed):
                raise
            raise UpdateFailed(f"Errore dal portale AcegasApsAmga: {err}") from err
        self.update_interval = INTERVALLO_NORMALE
        self.ultimo_errore = None

        bollette = dict(zip(profili, risultati[: len(profili)], strict=True))
        contratti_scaricati = risultati[len(profili) :]
        dati: dict[str, DatiContratto] = {}
        for contratto, (nuove_letture, nuova_finestra) in zip(
            self.contratti, contratti_scaricati, strict=True
        ):
            numero = contratto["contratto"]
            prec = precedenti.get(numero) or DatiContratto()
            bollette_profilo = bollette[contratto["profilo"]]
            dati[numero] = DatiContratto(
                letture=lt.unisci(prec.letture, nuove_letture),
                finestra=(
                    prec.finestra if nuova_finestra is _FINESTRA_MANCANTE else nuova_finestra
                ),
                bollette=(
                    bl.del_contratto(bollette_profilo, numero)
                    if bollette_profilo is not None
                    else prec.bollette
                ),
            )
            self._aggiorna_dispositivo(contratto, dati[numero])

        if "recorder" in self.hass.config.components:
            for contratto in self.contratti:
                numero = contratto["contratto"]
                try:
                    await self._async_aggiorna_statistiche(
                        contratto, dati[numero], precedenti.get(numero)
                    )
                except Exception:  # noqa: BLE001 - the sensors must update anyway
                    _LOGGER.exception(
                        "Contratto %s: scrittura delle statistiche non riuscita", numero
                    )
        await self._async_salva(dati)
        return dati

    async def _async_bollette(self, profilo: str) -> list[bl.Bolletta] | None:
        """Bills of a profile, or None if they cannot be read: then each
        contract keeps the ones it had."""
        try:
            raggruppamento = self._raggruppamenti.get(profilo)
            if raggruppamento is None:
                raggruppamento = await self._chiama(
                    self._api.async_raggruppamento_bollette, profilo
                )
                if raggruppamento is not None:
                    self._raggruppamenti[profilo] = raggruppamento
            grezze = await self._chiama(self._api.async_bollette, profilo, raggruppamento)
        except ApiError as err:
            _LOGGER.debug("Profilo %s: bollette non disponibili (%s)", profilo, err)
            return None
        return bl.estrai_bollette(grezze)

    async def _async_finestra(self, profilo: str, numero: str) -> dict[str, Any] | None:
        try:
            return finestra_da_api(
                await self._chiama(self._api.async_finestra_autolettura, profilo, numero)
            )
        except ApiError as err:
            _LOGGER.debug("Contratto %s: finestra di autolettura non disponibile (%s)", numero, err)
            return _FINESTRA_MANCANTE

    async def _async_scarica_contratto(
        self, contratto: dict[str, Any]
    ) -> tuple[list[lt.Lettura], dict[str, Any] | None]:
        profilo, numero = contratto["profilo"], contratto["contratto"]
        grezze, finestra = await asyncio.gather(
            self._chiama(self._api.async_letture, profilo, contratto["servizio"], numero),
            self._async_finestra(profilo, numero),
        )
        nuove = lt.estrai_letture(grezze)
        if grezze and not nuove:
            _LOGGER.warning(
                "Contratto %s: nessuna lettura interpretabile, formato cambiato? %r",
                numero,
                grezze[:3],
            )
        return nuove, finestra

    def _aggiorna_dispositivo(self, contratto: dict[str, Any], dati: DatiContratto) -> None:
        """Keep the device serial number in sync after a meter replacement."""
        ultima = dati.ultima_reale
        if not ultima or not ultima.contatore:
            return
        registro = dr.async_get(self.hass)
        identificatore = (DOMAIN, contratto["contratto"])
        dispositivo = next(
            (
                d
                for d in dr.async_entries_for_config_entry(registro, self.entry.entry_id)
                if identificatore in d.identifiers
            ),
            None,
        )
        if dispositivo is not None and dispositivo.serial_number != ultima.contatore:
            registro.async_update_device(dispositivo.id, serial_number=ultima.contatore)

    async def _async_aggiorna_statistiche(
        self,
        contratto: dict[str, Any],
        dati: DatiContratto,
        precedenti: DatiContratto | None,
    ) -> None:
        sid = self.statistic_id(contratto)
        righe = lt.serie_oraria(dati.letture, dt_util.utcnow())
        ultima_scritta = await async_ultima_ora(self.hass, sid)
        if not righe:
            _LOGGER.debug("%s: servono almeno due letture reali", sid)
            if ultima_scritta is not None:
                await async_cancella_serie(self.hass, sid)
                self._firme.pop(sid, None)
                self.serie_scritte.pop(sid, None)
            return
        nuova_firma = firma(dati.letture)
        # Nothing changed: skip the write.
        if ultima_scritta == righe[-1]["start"] and self._firme.get(sid) == nuova_firma:
            return
        # Append only new hours when every previously written anchor stayed unchanged.
        ancore_vecchie = precedenti.ancore if precedenti else []
        ancore_nuove = dati.ancore
        solo_coda = (
            ultima_scritta is not None
            and len(ancore_vecchie) >= 2
            and self._firme.get(sid) == firma(ancore_vecchie)
            and ancore_nuove[: len(ancore_vecchie)] == ancore_vecchie
            and righe[-1]["start"] > ultima_scritta
            and any(r["start"] == ultima_scritta for r in righe)
        )
        await async_scrivi_serie(
            self.hass,
            sid,
            self.nome_serie(contratto),
            righe,
            ultima_ora_scritta=ultima_scritta,
            riscrivi=not solo_coda,
        )
        self._firme[sid] = nuova_firma
        self.serie_scritte[sid] = righe[-1]["start"].isoformat()
