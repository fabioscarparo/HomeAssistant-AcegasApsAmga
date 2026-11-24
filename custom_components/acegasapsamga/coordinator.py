"""Coordinator: downloads account and contract data and writes statistics.

For each metered contract it downloads the read archive, self-reading archive,
self-reading window and calendar, optional daily reads (when enabledDailyReads
is true), and profile bills enriched with actual payment dates. For waste
(ENVIRONMENT / TARI) contracts it downloads equipment, disposals and discounts.
At account level it tracks password expiration, terms acceptance, portal
notifications, and value-added services (VAS).

Everything is kept in the integration's store, so entities come up immediately
after a restart and stay available while the portal is unreachable.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import cached_property
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import bollette as bl
from . import letture as lt
from . import rifiuti as rf
from .api import (
    ApiClient,
    ApiError,
    AutoletturaFuoriFinestra,
    AutoletturaInferiore,
    TokenScaduto,
    contratto_da_api,
)
from .auth import (
    AuthClient,
    AuthError,
    CredenzialiNonValide,
    ErroreRete,
    PassaggioInatteso,
    Token,
    nuovo_cookie_jar,
)
from .const import (
    CONF_CONTRATTI,
    DOMAIN,
    GIORNI_AVVISO_PASSWORD,
    INTERVALLO_AGGIORNAMENTO_ORE,
    MAX_NOTIFICHE_ATTRIBUTO,
    PORTALE_ORIGIN,
    SERVIZI_CONSUMO,
    SERVIZIO_ACQUA,
    SERVIZIO_AMBIENTE,
    SERVIZIO_GAS,
    SERVIZIO_LUCE,
    SERVIZIO_TLR,
    TIPI_RIFIUTO,
)
from .statistics import async_cancella_serie, async_scrivi_serie, async_ultima_ora, statistic_id
from .testi import testo

_LOGGER = logging.getLogger(__name__)

VERSIONE_STORE = 1
INTERVALLO_NORMALE = timedelta(hours=INTERVALLO_AGGIORNAMENTO_ORE)
INTERVALLO_DOPO_ERRORE = timedelta(minutes=30)
_MANCANTE: Any = object()


@dataclass
class DatiAccount:
    cambio_password: str | None = None
    scadenza_password: str | None = None
    rinnovo_password: bool = False
    nuove_condizioni_accettate: bool | None = None
    notifiche_totali: int = 0
    notifiche_non_lette: int = 0
    notifiche: list[dict[str, Any]] = field(default_factory=list)
    avvisi_configurati: list[dict[str, Any]] = field(default_factory=list)
    profili: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def avvisi_idrici_attivi(self) -> bool | None:
        trovati = [
            a
            for a in self.avvisi_configurati
            if str(a.get("tipo") or "").upper() in ("WATER_SERVICE", "WTR_FLT")
            or str(a.get("categoria") or "").upper() in ("WATER_SERVICE", "WTR_FLT")
        ]
        if not trovati:
            return None
        return any(bool(a.get("attivo")) for a in trovati)

    def come_dict(self) -> dict[str, Any]:
        return {
            "cambio_password": self.cambio_password,
            "scadenza_password": self.scadenza_password,
            "rinnovo_password": self.rinnovo_password,
            "nuove_condizioni_accettate": self.nuove_condizioni_accettate,
            "notifiche_totali": self.notifiche_totali,
            "notifiche_non_lette": self.notifiche_non_lette,
            "notifiche": list(self.notifiche[:MAX_NOTIFICHE_ATTRIBUTO]),
            "avvisi_configurati": list(self.avvisi_configurati),
            "profili": dict(self.profili),
        }

    @classmethod
    def da_dict(cls, dati: dict[str, Any] | None) -> DatiAccount:
        if not isinstance(dati, dict):
            return cls()
        return cls(
            cambio_password=dati.get("cambio_password"),
            scadenza_password=dati.get("scadenza_password"),
            rinnovo_password=bool(dati.get("rinnovo_password")),
            nuove_condizioni_accettate=dati.get("nuove_condizioni_accettate"),
            notifiche_totali=int(dati.get("notifiche_totali") or 0),
            notifiche_non_lette=int(dati.get("notifiche_non_lette") or 0),
            notifiche=[n for n in dati.get("notifiche") or [] if isinstance(n, dict)],
            avvisi_configurati=[
                a for a in dati.get("avvisi_configurati") or [] if isinstance(a, dict)
            ],
            profili={
                str(k): v for k, v in (dati.get("profili") or {}).items() if isinstance(v, dict)
            },
        )


@dataclass
class DatiContratto:
    letture: list[lt.Lettura] = field(default_factory=list)
    finestra: dict[str, Any] | None = None
    bollette: list[bl.Bolletta] = field(default_factory=list)
    calendario_autoletture: list[dict[str, Any]] = field(default_factory=list)
    autoletture: list[lt.Lettura] = field(default_factory=list)
    vas: list[dict[str, Any]] = field(default_factory=list)
    consumi_giornalieri: list[dict[str, Any]] = field(default_factory=list)
    rifiuti: rf.DatiRifiuti | None = None

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
        risultato: dict[str, Any] = {
            "letture": [lettura.come_dict() for lettura in self.letture],
            "finestra": self.finestra,
            "bollette": [bolletta.come_dict() for bolletta in self.bollette],
        }
        if self.calendario_autoletture:
            risultato["calendario_autoletture"] = list(self.calendario_autoletture)
        if self.autoletture:
            risultato["autoletture"] = [a.come_dict() for a in self.autoletture]
        if self.vas:
            risultato["vas"] = list(self.vas)
        if self.consumi_giornalieri:
            risultato["consumi_giornalieri"] = list(self.consumi_giornalieri)
        if self.rifiuti is not None:
            risultato["rifiuti"] = self.rifiuti.come_dict()
        return risultato

    @classmethod
    def da_dict(cls, dati: dict[str, Any]) -> DatiContratto:
        letture = []
        for grezza in dati.get("letture") or []:
            try:
                letture.append(lt.Lettura.da_dict(grezza))
            except (KeyError, TypeError, ValueError):
                _LOGGER.debug("Lettura salvata non valida, ignorata: %r", grezza)
        autoletture = []
        for grezza in dati.get("autoletture") or []:
            try:
                autoletture.append(lt.Lettura.da_dict(grezza))
            except (KeyError, TypeError, ValueError):
                _LOGGER.debug("Autolettura salvata non valida, ignorata: %r", grezza)
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
            calendario_autoletture=[
                c for c in dati.get("calendario_autoletture") or [] if isinstance(c, dict)
            ],
            autoletture=lt.ordina(autoletture),
            vas=[v for v in dati.get("vas") or [] if isinstance(v, dict)],
            consumi_giornalieri=[
                g for g in dati.get("consumi_giornalieri") or [] if isinstance(g, dict)
            ],
            rifiuti=rf.DatiRifiuti.da_dict(dati.get("rifiuti")),
        )


def _giorno_iso(valore: Any) -> str | None:
    giorno = lt.giorno_da_ms(valore)
    return giorno.isoformat() if giorno else None


def finestra_da_api(grezza: dict[str, Any] | None) -> dict[str, Any] | None:
    """Self-reading window: first and last day, open flag and remaining days."""
    if not grezza:
        return None
    inizio, fine = _giorno_iso(grezza.get("startDate")), _giorno_iso(grezza.get("endDate"))
    if inizio is None:
        return None
    risultato: dict[str, Any] = {
        "inizio": inizio,
        "fine": fine,
        "aperta": bool(grezza.get("insideTimeFrame")),
    }
    giorni_raw = grezza.get("remainingDays")
    if isinstance(giorni_raw, (int, float)) and not isinstance(giorni_raw, bool):
        risultato["giorni_mancanti"] = max(int(giorni_raw), 0)
    return risultato


def calendario_da_api(grezze: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract self-reading calendar windows, sorted chronologically."""
    finestre: dict[tuple[str, str | None], dict[str, Any]] = {}
    for voce in grezze:
        if not isinstance(voce, dict):
            continue
        inizio = _giorno_iso(voce.get("startDate"))
        fine = _giorno_iso(voce.get("endDate"))
        if inizio is None:
            continue
        finestre[(inizio, fine)] = {
            "periodo": voce.get("period"),
            "inizio": inizio,
            "fine": fine or inizio,
        }
    return [finestre[k] for k in sorted(finestre)]


def firma(letture: list[lt.Lettura]) -> str:
    """Fingerprint of the real readings, to rewrite the series only when they change."""
    grezzo = json.dumps([lettura.come_dict() for lettura in lt.ancore(letture)], sort_keys=True)
    return hashlib.sha256(grezzo.encode()).hexdigest()[:16]


def _costruisci_payload_autolettura(
    contratto: dict[str, Any],
    struttura_ultima: dict[str, Any] | None,
    *,
    valore: float | None,
    f1: float | None,
    f2: float | None,
    f3: float | None,
) -> dict[str, Any]:
    """Build the POST /api/v2/profile/{p}/read payload for any metered service."""
    servizio = contratto["servizio"]
    numero = contratto["contratto"]
    contatore = contratto.get("contatore") or ""
    fasce_input: dict[str, float] = {}
    if f1 is not None:
        fasce_input["F1"] = float(f1)
    if f2 is not None:
        fasce_input["F2"] = float(f2)
    if f3 is not None:
        fasce_input["F3"] = float(f3)

    misure_api = [
        m
        for m in (struttura_ultima or {}).get("measurements") or []
        if isinstance(m, dict) and not m.get("correttore")
    ]

    misure_payload: list[dict[str, Any]] = []
    if misure_api:
        for misura in misure_api:
            bande_api = [b for b in misura.get("bands") or [] if isinstance(b, dict)]
            bande_payload: list[dict[str, Any]] = []
            tipi_bande = {str(b.get("type") or "").upper() for b in bande_api}
            multi_fascia = servizio == SERVIZIO_LUCE and len(tipi_bande & {"F1", "F2", "F3"}) >= 2
            for banda in bande_api:
                tipo_b = str(banda.get("type") or "F0").upper()
                id_b = str(banda.get("id") or "001")
                if multi_fascia:
                    if tipo_b not in fasce_input:
                        continue
                    v = fasce_input[tipo_b]
                else:
                    if valore is None:
                        continue
                    v = float(valore)
                bande_payload.append({"id": id_b, "type": tipo_b, "value": v})
            if not bande_payload:
                continue
            voce_misura: dict[str, Any] = {
                "id": str(misura.get("id") or misura.get("type") or servizio),
                "type": str(misura.get("type") or servizio),
                "bands": bande_payload,
            }
            if servizio == SERVIZIO_GAS:
                voce_misura["meterId"] = misura.get("meterId") or contatore
                voce_misura["correttore"] = False
                if voce_misura["meterId"]:
                    contatore = str(voce_misura["meterId"])
            misure_payload.append(voce_misura)
            break

    if not misure_payload:
        if servizio == SERVIZIO_LUCE and fasce_input:
            bande_fallback = [
                {"id": f"00{i}", "type": k, "value": fasce_input[k]}
                for i, k in enumerate(("F1", "F2", "F3"), start=1)
                if k in fasce_input
            ]
        elif valore is not None:
            bande_fallback = [{"id": "001", "type": "F0", "value": float(valore)}]
        else:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="autolettura_valore_mancante",
            )
        voce_fb: dict[str, Any] = {
            "id": servizio,
            "type": servizio,
            "bands": bande_fallback,
        }
        if servizio == SERVIZIO_GAS:
            voce_fb["meterId"] = contatore
            voce_fb["correttore"] = False
        misure_payload = [voce_fb]

    return {
        "contractId": numero,
        "meterId": contatore,
        "serviceType": servizio,
        "measurements": misure_payload,
    }


def _scrivi_file(percorso: Path, contenuto: bytes) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_bytes(contenuto)


class AcegasCoordinator(DataUpdateCoordinator[dict[str, DatiContratto]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            # The entry id, not the title: the title is the account email, and logs get shared.
            name=f"{DOMAIN} ({entry.entry_id})",
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
        # Profile capabilities (billGroupType, enabledDailyReads): cached per profile.
        self._profili_info: dict[str, dict[str, Any]] = {}
        self.dati_account: DatiAccount = DatiAccount()
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

    def trova_contratto(self, numero: str) -> dict[str, Any] | None:
        return next((c for c in self.contratti if c["contratto"] == numero), None)

    # --- Store ---------------------------------------------------------------

    async def async_carica_cache(self) -> bool:
        """Load the data of the last update. True if there was any."""
        salvati = await self._store.async_load() or {}
        per_contratto = salvati.get("contratti") or {}
        sid_attivi = {
            self.statistic_id(c)
            for c in self.contratti
            if c.get("servizio") in SERVIZI_CONSUMO
        }
        self._firme = {
            sid: valore
            for sid, valore in (salvati.get("firme") or {}).items()
            if sid in sid_attivi
        }
        self.dati_account = DatiAccount.da_dict(salvati.get("account"))
        self._profili_info = dict(self.dati_account.profili)
        dati = {
            c["contratto"]: DatiContratto.da_dict(per_contratto[c["contratto"]])
            for c in self.contratti
            if c["contratto"] in per_contratto
        }
        if dati:
            self.data = dati
        return bool(dati)

    async def _async_salva(self, dati: dict[str, DatiContratto]) -> None:
        sid_attivi = {
            self.statistic_id(c)
            for c in self.contratti
            if c.get("servizio") in SERVIZI_CONSUMO
        }
        self._firme = {sid: v for sid, v in self._firme.items() if sid in sid_attivi}
        await self._store.async_save(
            {
                "contratti": {numero: valori.come_dict() for numero, valori in dati.items()},
                "firme": self._firme,
                "account": self.dati_account.come_dict(),
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

    async def _chiama(self, metodo, *argomenti, **kwargs):
        """Call the API; if the token is refused, refresh/log in once and retry."""
        token_usato = self._api.access_token
        try:
            return await metodo(*argomenti, **kwargs)
        except TokenScaduto:
            await self._async_assicura_token(forza=True, token_rifiutato=token_usato)
            return await metodo(*argomenti, **kwargs)

    async def async_contratti_account(self) -> list[dict[str, Any]]:
        """List the account's contracts reusing the coordinator's session and token."""
        await self._async_assicura_token()
        return [
            contratto_da_api(p, c)
            for p, c in await self._chiama(self._api.async_contratti_account)
        ]

    # --- Update --------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, DatiContratto]:
        precedenti = self.data or {}
        profili = list(dict.fromkeys(c["profilo"] for c in self.contratti))
        try:
            await self._async_assicura_token()
            # Ensure profile capabilities are loaded first so daily-reads flags are known.
            await asyncio.gather(*(self._async_info_profilo(p) for p in profili))
            utente_res, profili_res, contratti_res = await asyncio.gather(
                self._async_utente(),
                asyncio.gather(*(self._async_dati_profilo(p) for p in profili)),
                asyncio.gather(*(self._async_scarica_contratto(c) for c in self.contratti)),
            )
        except (ApiError, UpdateFailed) as err:
            self.ultimo_errore = f"{type(err).__name__}: {err}"
            self.update_interval = INTERVALLO_DOPO_ERRORE
            if isinstance(err, UpdateFailed):
                raise
            raise UpdateFailed(f"Errore dal portale AcegasApsAmga: {err}") from err
        self.update_interval = INTERVALLO_NORMALE
        self.ultimo_errore = None

        per_profilo = dict(zip(profili, profili_res, strict=True))
        self._aggiorna_account(utente_res, per_profilo)
        self._aggiorna_repair_issues()

        dati: dict[str, DatiContratto] = {}
        for contratto, scaricato in zip(self.contratti, contratti_res, strict=True):
            numero = contratto["contratto"]
            profilo = contratto["profilo"]
            prec = precedenti.get(numero) or DatiContratto()
            dati_prof = per_profilo[profilo]
            bollette_profilo = dati_prof["bollette"]
            vas_profilo = dati_prof["vas"]
            vas_contratto = (
                [
                    s
                    for voce in vas_profilo
                    if voce.get("contratto") in (None, numero)
                    for s in voce.get("servizi") or []
                ]
                if vas_profilo is not _MANCANTE
                else prec.vas
            )

            dati[numero] = DatiContratto(
                letture=lt.unisci(prec.letture, scaricato["letture"]),
                finestra=(
                    prec.finestra
                    if scaricato["finestra"] is _MANCANTE
                    else scaricato["finestra"]
                ),
                bollette=(
                    bl.del_contratto(bollette_profilo, numero)
                    if bollette_profilo is not None
                    else prec.bollette
                ),
                calendario_autoletture=(
                    prec.calendario_autoletture
                    if scaricato["calendario"] is _MANCANTE
                    else scaricato["calendario"]
                ),
                autoletture=(
                    prec.autoletture
                    if scaricato["autoletture"] is _MANCANTE
                    else scaricato["autoletture"]
                ),
                vas=vas_contratto,
                consumi_giornalieri=(
                    prec.consumi_giornalieri
                    if scaricato["giornalieri"] is _MANCANTE
                    else scaricato["giornalieri"]
                ),
                rifiuti=(
                    prec.rifiuti
                    if scaricato["rifiuti"] is _MANCANTE
                    else scaricato["rifiuti"]
                ),
            )
            self._aggiorna_dispositivo(contratto, dati[numero])

        if "recorder" in self.hass.config.components:
            for contratto in self.contratti:
                if contratto.get("servizio") not in SERVIZI_CONSUMO:
                    continue
                numero = contratto["contratto"]
                try:
                    await self._async_aggiorna_statistiche(
                        contratto, dati[numero], precedenti.get(numero)
                    )
                except Exception:  # noqa: BLE001 - sensors must update anyway
                    _LOGGER.exception(
                        "Contratto %s: scrittura delle statistiche non riuscita", numero
                    )
        await self._async_salva(dati)
        return dati

    async def _async_info_profilo(self, profilo: str) -> dict[str, Any]:
        if profilo in self._profili_info:
            return self._profili_info[profilo]
        try:
            if hasattr(self._api, "async_profilo"):
                info = await self._chiama(self._api.async_profilo, profilo)
            else:
                rag = await self._chiama(self._api.async_raggruppamento_bollette, profilo)
                info = {"raggruppamento": rag} if rag else {}
        except ApiError as err:
            _LOGGER.debug("Profilo %s: info profilo non disponibili (%s)", profilo, err)
            return {}
        if info:
            self._profili_info[profilo] = info
        return info

    async def _async_utente(self) -> dict[str, Any] | None:
        if not hasattr(self._api, "async_utente"):
            return None
        try:
            return await self._chiama(self._api.async_utente)
        except ApiError as err:
            _LOGGER.debug("Stato account non disponibile (%s)", err)
            return None

    async def _async_dati_profilo(self, profilo: str) -> dict[str, Any]:
        info = self._profili_info.get(profilo) or {}
        raggruppamento = info.get("raggruppamento")

        async def _bollette_e_pagamenti() -> list[bl.Bolletta] | None:
            try:
                grezze = await self._chiama(self._api.async_bollette, profilo, raggruppamento)
            except ApiError as err:
                _LOGGER.debug("Profilo %s: bollette non disponibili (%s)", profilo, err)
                return None
            bollette = bl.estrai_bollette(grezze)
            if hasattr(self._api, "async_pagamenti_bollette"):
                try:
                    pagamenti = await self._chiama(self._api.async_pagamenti_bollette, profilo)
                    bollette = bl.applica_pagamenti(bollette, pagamenti)
                except ApiError as err:
                    _LOGGER.debug("Profilo %s: pagamenti non disponibili (%s)", profilo, err)
            return bollette

        async def _notifiche() -> Any:
            if not hasattr(self._api, "async_notifiche"):
                return _MANCANTE
            try:
                return await self._chiama(self._api.async_notifiche, profilo)
            except ApiError as err:
                _LOGGER.debug("Profilo %s: notifiche non disponibili (%s)", profilo, err)
                return _MANCANTE

        async def _conf_notifiche() -> Any:
            if not hasattr(self._api, "async_configurazione_notifiche"):
                return _MANCANTE
            try:
                return await self._chiama(self._api.async_configurazione_notifiche, profilo)
            except ApiError as err:
                _LOGGER.debug(
                    "Profilo %s: configurazione notifiche non disponibile (%s)", profilo, err
                )
                return _MANCANTE

        async def _vas() -> Any:
            if not hasattr(self._api, "async_vas"):
                return _MANCANTE
            try:
                return await self._chiama(self._api.async_vas, profilo)
            except ApiError as err:
                _LOGGER.debug("Profilo %s: VAS non disponibili (%s)", profilo, err)
                return _MANCANTE

        bollette, notifiche, conf_notifiche, vas = await asyncio.gather(
            _bollette_e_pagamenti(), _notifiche(), _conf_notifiche(), _vas()
        )
        return {
            "bollette": bollette,
            "notifiche": notifiche,
            "conf_notifiche": conf_notifiche,
            "vas": vas,
        }

    def _aggiorna_account(
        self, utente: dict[str, Any] | None, per_profilo: dict[str, dict[str, Any]]
    ) -> None:
        prec = self.dati_account
        notifiche_valide = [
            v["notifiche"] for v in per_profilo.values() if v["notifiche"] is not _MANCANTE
        ]
        if notifiche_valide:
            totale = sum(n["totale"] for n in notifiche_valide)
            non_lette = sum(n["non_lette"] for n in notifiche_valide)
            lista = sorted(
                [item for n in notifiche_valide for item in n["lista"]],
                key=lambda x: str(x.get("data") or ""),
                reverse=True,
            )[:MAX_NOTIFICHE_ATTRIBUTO]
        else:
            totale = prec.notifiche_totali
            non_lette = prec.notifiche_non_lette
            lista = prec.notifiche

        conf_valide = [
            v["conf_notifiche"]
            for v in per_profilo.values()
            if v["conf_notifiche"] is not _MANCANTE
        ]
        avvisi = (
            [item for c in conf_valide for item in c] if conf_valide else prec.avvisi_configurati
        )

        self.dati_account = DatiAccount(
            cambio_password=(
                utente["cambio_password"] if utente is not None else prec.cambio_password
            ),
            scadenza_password=(
                utente["scadenza_password"] if utente is not None else prec.scadenza_password
            ),
            rinnovo_password=(
                utente["rinnovo_password"] if utente is not None else prec.rinnovo_password
            ),
            nuove_condizioni_accettate=(
                utente["nuove_condizioni_accettate"]
                if utente is not None
                else prec.nuove_condizioni_accettate
            ),
            notifiche_totali=totale,
            notifiche_non_lette=non_lette,
            notifiche=lista,
            avvisi_configurati=avvisi,
            profili=dict(self._profili_info),
        )

    def _aggiorna_repair_issues(self) -> None:
        """Create or clear HA Repair Issues for password expiry and new terms."""
        acc = self.dati_account
        id_pwd = f"password_scadenza_{self.entry.entry_id}"
        id_cond = f"nuove_condizioni_{self.entry.entry_id}"

        avvisa_pwd = acc.rinnovo_password
        giorni_str = "0"
        if acc.scadenza_password:
            oggi = dt_util.now(lt.FUSO).date()
            rimanenti = (date.fromisoformat(acc.scadenza_password) - oggi).days
            giorni_str = str(max(rimanenti, 0))
            if rimanenti <= GIORNI_AVVISO_PASSWORD:
                avvisa_pwd = True

        if avvisa_pwd:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                id_pwd,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                learn_more_url=PORTALE_ORIGIN,
                translation_key="password_in_scadenza",
                translation_placeholders={
                    "email": str(self.entry.data.get(CONF_EMAIL) or self.entry.title),
                    "giorni": giorni_str,
                    "scadenza": acc.scadenza_password or "-",
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, id_pwd)

        if acc.nuove_condizioni_accettate is False:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                id_cond,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                learn_more_url=PORTALE_ORIGIN,
                translation_key="nuove_condizioni",
                translation_placeholders={
                    "email": str(self.entry.data.get(CONF_EMAIL) or self.entry.title),
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, id_cond)

    async def _async_finestra(self, profilo: str, numero: str) -> Any:
        try:
            return finestra_da_api(
                await self._chiama(self._api.async_finestra_autolettura, profilo, numero)
            )
        except ApiError as err:
            _LOGGER.debug(
                "Contratto %s: finestra di autolettura non disponibile (%s)", numero, err
            )
            return _MANCANTE

    async def _async_calendario(self, profilo: str, numero: str) -> Any:
        if not hasattr(self._api, "async_calendario_autoletture"):
            return _MANCANTE
        try:
            return calendario_da_api(
                await self._chiama(self._api.async_calendario_autoletture, profilo, numero)
            )
        except ApiError as err:
            _LOGGER.debug(
                "Contratto %s: calendario autoletture non disponibile (%s)", numero, err
            )
            return _MANCANTE

    async def _async_autoletture(self, profilo: str, servizio: str, numero: str) -> Any:
        if not hasattr(self._api, "async_autoletture"):
            return _MANCANTE
        try:
            grezze = await self._chiama(self._api.async_autoletture, profilo, servizio, numero)
            return lt.estrai_letture(grezze)
        except ApiError as err:
            _LOGGER.debug("Contratto %s: archivio autoletture non disponibile (%s)", numero, err)
            return _MANCANTE

    async def _async_consumi_giornalieri(self, contratto: dict[str, Any]) -> Any:
        profilo = contratto["profilo"]
        info = self._profili_info.get(profilo) or {}
        if not info.get("letture_giornaliere") or not hasattr(
            self._api, "async_consumi_giornalieri"
        ):
            return _MANCANTE
        pod = contratto.get("pod")
        if not pod:
            return _MANCANTE
        adesso = dt_util.utcnow()
        al_ms = int(adesso.timestamp() * 1000)
        dal_ms = int((adesso - timedelta(days=31)).timestamp() * 1000)
        try:
            grezze = await self._chiama(
                self._api.async_consumi_giornalieri,
                profilo,
                contratto["contratto"],
                str(pod),
                dal_ms,
                al_ms,
            )
            return lt.estrai_consumi_giornalieri(grezze)
        except ApiError as err:
            _LOGGER.debug(
                "Contratto %s: consumi giornalieri non disponibili (%s)",
                contratto["contratto"],
                err,
            )
            return _MANCANTE

    async def _async_scarica_rifiuti(self, profilo: str, numero: str) -> Any:
        if not hasattr(self._api, "async_dotazioni_rifiuti"):
            return _MANCANTE

        async def _dotazioni():
            try:
                return rf.estrai_dotazioni(
                    await self._chiama(self._api.async_dotazioni_rifiuti, profilo, numero)
                )
            except ApiError as err:
                _LOGGER.debug("Contratto %s: dotazioni rifiuti non disponibili (%s)", numero, err)
                return None

        async def _vantaggi():
            if not hasattr(self._api, "async_vantaggi_rifiuti"):
                return []
            try:
                return rf.estrai_vantaggi(
                    await self._chiama(self._api.async_vantaggi_rifiuti, profilo, numero)
                )
            except ApiError as err:
                _LOGGER.debug("Contratto %s: vantaggi TARI non disponibili (%s)", numero, err)
                return []

        async def _svuotamenti_tipo(tipo: str, anno: str):
            try:
                return await self._chiama(
                    self._api.async_svuotamenti_rifiuti, profilo, numero, tipo=tipo, anno=anno
                )
            except ApiError as err:
                _LOGGER.debug(
                    "Contratto %s: svuotamenti %s/%s non disponibili (%s)",
                    numero,
                    tipo,
                    anno,
                    err,
                )
                return None

        dotazioni_task = _dotazioni()
        vantaggi_task = _vantaggi()
        correnti_tasks = [_svuotamenti_tipo(t, "CURRENT") for t in TIPI_RIFIUTO]
        prec_rsu_task = _svuotamenti_tipo("RSU", "PREVIOUS")

        risultati = await asyncio.gather(
            dotazioni_task, vantaggi_task, prec_rsu_task, *correnti_tasks
        )
        dotazioni = risultati[0]
        vantaggi = risultati[1]
        prec_rsu_raw = risultati[2]
        correnti_raw = risultati[3:]

        if dotazioni is None and prec_rsu_raw is None and all(r is None for r in correnti_raw):
            return _MANCANTE

        svuotamenti_correnti: list[rf.Svuotamento] = []
        volume_corrente: float | None = None
        for tipo, risposta in zip(TIPI_RIFIUTO, correnti_raw, strict=True):
            if risposta is None:
                continue
            elementi, vol = rf.estrai_svuotamenti(risposta, tipo_predefinito=tipo)
            svuotamenti_correnti.extend(elementi)
            if tipo == "RSU" and vol is not None:
                volume_corrente = vol
        svuotamenti_correnti.sort(key=lambda s: s.giorno, reverse=True)

        svuotamenti_prec, volume_prec = rf.estrai_svuotamenti(
            prec_rsu_raw, tipo_predefinito="RSU"
        )
        return rf.DatiRifiuti(
            dotazioni=dotazioni or [],
            svuotamenti_anno_corrente=svuotamenti_correnti,
            svuotamenti_anno_precedente=svuotamenti_prec,
            volume_anno_corrente=volume_corrente,
            volume_anno_precedente=volume_prec,
            vantaggi=vantaggi,
        )

    async def _async_scarica_contratto(self, contratto: dict[str, Any]) -> dict[str, Any]:
        profilo, numero = contratto["profilo"], contratto["contratto"]
        servizio = contratto["servizio"]
        if servizio == SERVIZIO_AMBIENTE:
            rifiuti = await self._async_scarica_rifiuti(profilo, numero)
            return {
                "letture": [],
                "finestra": None,
                "calendario": [],
                "autoletture": [],
                "giornalieri": [],
                "rifiuti": rifiuti,
            }

        grezze, finestra, calendario, autoletture, giornalieri = await asyncio.gather(
            self._chiama(self._api.async_letture, profilo, servizio, numero),
            self._async_finestra(profilo, numero),
            self._async_calendario(profilo, numero),
            self._async_autoletture(profilo, servizio, numero),
            self._async_consumi_giornalieri(contratto),
        )
        nuove = lt.estrai_letture(grezze)
        if grezze and not nuove:
            _LOGGER.warning(
                "Contratto %s: nessuna lettura interpretabile, formato cambiato? %r",
                numero,
                grezze[:3],
            )
        return {
            "letture": nuove,
            "finestra": finestra,
            "calendario": calendario,
            "autoletture": autoletture,
            "giornalieri": giornalieri,
            "rifiuti": None,
        }

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
            servizio=contratto["servizio"],
            unita_contatore=contratto.get("unita"),
        )
        self._firme[sid] = nuova_firma
        self.serie_scritte[sid] = righe[-1]["start"].isoformat()

    # --- Actions (self-reading & PDF download) -------------------------------

    async def async_invia_autolettura(
        self,
        numero_contratto: str,
        *,
        valore: float | None = None,
        f1: float | None = None,
        f2: float | None = None,
        f3: float | None = None,
    ) -> dict[str, Any]:
        """Submit a self-reading for a metered contract."""
        contratto = self.trova_contratto(numero_contratto)
        if contratto is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="contratto_non_trovato",
                translation_placeholders={"contratto": numero_contratto},
            )
        servizio = contratto["servizio"]
        if servizio not in SERVIZI_CONSUMO:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="servizio_senza_autolettura",
                translation_placeholders={"servizio": servizio},
            )
        await self._async_assicura_token()
        profilo = contratto["profilo"]
        struttura: dict[str, Any] | None = None
        usa_pod = servizio in (SERVIZIO_ACQUA, SERVIZIO_TLR)
        id_ricerca = (
            contratto.get("pod") if usa_pod else contratto.get("contatore")
        ) or contratto.get("contatore") or contratto.get("pod")
        if id_ricerca and hasattr(self._api, "async_ultima_lettura_contatore"):
            try:
                struttura = await self._chiama(
                    self._api.async_ultima_lettura_contatore,
                    profilo,
                    numero_contratto,
                    str(id_ricerca),
                    pod=usa_pod,
                )
            except ApiError as err:
                _LOGGER.debug(
                    "Contratto %s: struttura ultima lettura non disponibile (%s)",
                    numero_contratto,
                    err,
                )
        payload = _costruisci_payload_autolettura(
            contratto, struttura, valore=valore, f1=f1, f2=f2, f3=f3
        )
        try:
            await self._chiama(self._api.async_invia_autolettura, profilo, payload)
        except AutoletturaInferiore as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="autolettura_inferiore",
            ) from err
        except AutoletturaFuoriFinestra as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="autolettura_fuori_finestra",
            ) from err
        except ApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="errore_portale",
                translation_placeholders={"messaggio": str(err)},
            ) from err

        await self.async_request_refresh()
        return {
            "contratto": numero_contratto,
            "servizio": servizio,
            "inviata": True,
            "misure": payload["measurements"],
        }

    def _destinazione_pdf(
        self, numero: str, dettaglio: bool, percorso: str | None
    ) -> Path | None:
        """Where to save a bill PDF, or None if the path is not allowed.

        By default media/acegasapsamga/, inside Home Assistant's allowlisted
        media folder (out of www, which is served at /local/ without sign-in).
        A path of the user's own starts from the media folder when relative,
        and must be a .pdf in a folder Home Assistant allows (media,
        allowlist_external_dirs), never www.
        """
        media_dirs = self.hass.config.media_dirs or {}
        cartella_media = Path(
            media_dirs.get("local")
            or next(iter(media_dirs.values()), None)
            or self.hass.config.path("media")
        )
        if percorso:
            candidato = Path(percorso)
            destinazione = candidato if candidato.is_absolute() else cartella_media / candidato
        else:
            sicuro = re.sub(r"[^A-Za-z0-9_-]", "_", numero)
            suffisso = "_dettaglio" if dettaglio else ""
            destinazione = cartella_media / DOMAIN / f"bolletta_{sicuro}{suffisso}.pdf"
        try:
            destinazione = destinazione.resolve()
            www = Path(self.hass.config.path("www")).resolve()
        except (OSError, RuntimeError):
            return None
        if destinazione.suffix.lower() != ".pdf" or destinazione.is_relative_to(www):
            return None
        ammesso = self.hass.config.is_allowed_path(str(destinazione))
        if not ammesso:
            for dir_ammessa in self.hass.config.allowlist_external_dirs:
                try:
                    if destinazione.is_relative_to(Path(dir_ammessa).resolve()):
                        ammesso = True
                        break
                except (OSError, RuntimeError):
                    continue
        return destinazione if ammesso else None

    async def async_scarica_bolletta(
        self,
        numero_contratto: str,
        *,
        numero_bolletta: str | None = None,
        dettaglio: bool = False,
        percorso: str | None = None,
    ) -> dict[str, Any]:
        """Download a bill PDF into the media folder, or another folder Home
        Assistant lets integrations write to, never www."""
        contratto = self.trova_contratto(numero_contratto)
        if contratto is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="contratto_non_trovato",
                translation_placeholders={"contratto": numero_contratto},
            )
        dati = (self.data or {}).get(numero_contratto)
        numero = (numero_bolletta or "").strip()
        if not numero:
            if not dati or not dati.bollette:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="nessuna_bolletta",
                )
            numero = dati.bollette[0].numero

        # Resolving paths touches the disk: done in the executor.
        destinazione = await self.hass.async_add_executor_job(
            self._destinazione_pdf, numero, dettaglio, percorso
        )
        if destinazione is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="percorso_non_valido",
                translation_placeholders={"percorso": str(percorso or numero)},
            )

        await self._async_assicura_token()
        try:
            contenuto = await self._chiama(
                self._api.async_bolletta_pdf,
                contratto["profilo"],
                numero,
                dettaglio=dettaglio,
            )
        except ApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="errore_portale",
                translation_placeholders={"messaggio": str(err)},
            ) from err

        await self.hass.async_add_executor_job(_scrivi_file, destinazione, contenuto)
        return {
            "contratto": numero_contratto,
            "numero": numero,
            "percorso": str(destinazione),
            "dimensione": len(contenuto),
        }
