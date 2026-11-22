"""Client of the Servizi Online API.

Every call sends the B2C access token as a Bearer token and the two headers
of the web app; no cookie is needed. Dates in the answers are epoch
milliseconds of a calendar day (see letture.giorno_da_ms).

No Home Assistant imports. Real answers, anonymized, are in tests/fixtures.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import API_BASE_URL, API_PLATFORM_ID, API_REFERER, DIMENSIONE_PAGINA, MAX_PAGINE
from .letture import giorno_da_ms

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=30)


class ApiError(Exception):
    def __init__(self, messaggio: str, *, status: int | None = None, rete: bool = False):
        super().__init__(messaggio)
        self.status = status
        self.rete = rete


class TokenScaduto(ApiError):
    """The API refused the access token."""


class AutoletturaInferiore(ApiError):
    """HTTP 692: submitted reading is lower than the previous one."""


class AutoletturaFuoriFinestra(ApiError):
    """HTTP 695: submitted reading is outside the allowed self-reading window."""


class ApiClient:
    def __init__(self, session: aiohttp.ClientSession, access_token: str = "") -> None:
        self._session = session
        self.access_token = access_token

    def _headers(self, *, accept: str = "application/json") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "X-Bwb-PlatformId": API_PLATFORM_ID,
            "X-Bwb-Referer": API_REFERER,
            "Accept": accept,
        }

    async def _request(
        self,
        metodo: str,
        percorso: str,
        *,
        parametri: list[tuple[str, str]] | None = None,
        corpo_json: Any = None,
        binario: bool = False,
    ) -> Any:
        headers = self._headers(accept="*/*" if binario else "application/json")
        kwargs: dict[str, Any] = {"headers": headers, "timeout": TIMEOUT}
        if parametri is not None:
            kwargs["params"] = parametri
        if corpo_json is not None:
            kwargs["json"] = corpo_json
        chiamata = self._session.post if metodo == "POST" else self._session.get
        try:
            async with chiamata(f"{API_BASE_URL}/{percorso}", **kwargs) as risposta:
                stato = risposta.status
                if stato in (200, 201, 204):
                    if binario:
                        return await risposta.read()
                    if stato == 204:
                        return None
                    testo_ok = await risposta.text()
                    if not testo_ok.strip():
                        return None
                    return await risposta.json(content_type=None)
                testo = (await risposta.text())[:300]
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ApiError(str(err) or type(err).__name__, rete=True) from err
        except ValueError as err:
            raise ApiError(f"{percorso}: risposta non JSON") from err

        # A missing or invalid token gets 403 "role not allowed".
        if stato in (401, 403) or "TOKEN_EXPIRED" in testo:
            raise TokenScaduto(f"{percorso}: HTTP {stato}", status=stato)
        if stato == 692:
            raise AutoletturaInferiore(f"{percorso}: HTTP 692 {testo}", status=stato)
        if stato == 695:
            raise AutoletturaFuoriFinestra(f"{percorso}: HTTP 695 {testo}", status=stato)
        raise ApiError(f"{percorso}: HTTP {stato} {testo}", status=stato)

    async def _get(self, percorso: str, parametri: list[tuple[str, str]] | None = None) -> Any:
        return await self._request("GET", percorso, parametri=parametri)

    async def _post(self, percorso: str, corpo_json: Any) -> Any:
        return await self._request("POST", percorso, corpo_json=corpo_json)

    async def _lista_paginata(
        self,
        percorso: str,
        parametri: list[tuple[str, str]] | None = None,
        *,
        chiave: str = "list",
    ) -> list[dict]:
        elementi: list[dict] = []
        for pagina in range(MAX_PAGINE):
            corpo = await self._get(
                percorso,
                [
                    *(parametri or []),
                    ("pageNumber", str(pagina)),
                    ("pageSize", str(DIMENSIONE_PAGINA)),
                ],
            )
            if not isinstance(corpo, dict):
                raise ApiError(f"{percorso}: risposta inattesa")
            pagina_elementi = [e for e in corpo.get(chiave) or [] if isinstance(e, dict)]
            elementi.extend(pagina_elementi)
            if not pagina_elementi or not corpo.get("hasNext"):
                return elementi
        _LOGGER.warning("%s: interrotto dopo %d pagine", percorso, MAX_PAGINE)
        return elementi

    async def _lista(
        self,
        percorso: str,
        parametri: list[tuple[str, str]] | None = None,
        *,
        chiave: str = "list",
    ) -> list[dict]:
        corpo = await self._get(percorso, parametri)
        if isinstance(corpo, list):
            return [e for e in corpo if isinstance(e, dict)]
        if not isinstance(corpo, dict):
            raise ApiError(f"{percorso}: risposta inattesa")
        return [e for e in corpo.get(chiave) or [] if isinstance(e, dict)]

    # --- Account & profiles ---------------------------------------------------

    async def async_utente(self) -> dict[str, Any]:
        """Non-PII account status: password expiration and terms acceptance."""
        corpo = await self._get("user")
        if not isinstance(corpo, dict):
            raise ApiError("user: risposta inattesa")
        cambio = giorno_da_ms(corpo.get("pwdChangedTime"))
        scadenza = giorno_da_ms(corpo.get("pwdExpireTime"))
        return {
            "cambio_password": cambio.isoformat() if cambio else None,
            "scadenza_password": scadenza.isoformat() if scadenza else None,
            "rinnovo_password": bool(corpo.get("renewPassword")),
            "nuove_condizioni_accettate": (
                bool(corpo["newConditionsAcceptance"])
                if corpo.get("newConditionsAcceptance") is not None
                else None
            ),
            "energy_manager": bool(corpo.get("energyManager")),
            "hera_ambiente": bool(corpo.get("heraAmbiente")),
        }

    async def async_profili(self) -> list[dict]:
        return await self._lista("profile/list")

    async def async_profilo(self, profilo: str) -> dict[str, Any]:
        """Non-PII profile capabilities: bill grouping and daily reads flag."""
        corpo = await self._get(f"profile/{profilo}")
        if not isinstance(corpo, dict):
            return {}
        raggruppamento = corpo.get("billGroupType")
        return {
            "raggruppamento": str(raggruppamento) if raggruppamento else None,
            "letture_giornaliere": bool(corpo.get("enabledDailyReads")),
            "gestore_acqua": bool(corpo.get("waterManager")),
            "gestore_ambiente": bool(corpo.get("environmentManager")),
            "energy_wallet": bool(corpo.get("energyWallet")),
            "zcode": str(corpo["zcode"]) if corpo.get("zcode") else None,
            "numerosita_contratti": corpo.get("contractNumerosity"),
        }

    async def async_raggruppamento_bollette(self, profilo: str) -> str | None:
        """How the profile's bills are grouped (billGroupType)."""
        info = await self.async_profilo(profilo)
        return info.get("raggruppamento")

    async def async_contratti(self, profilo: str) -> list[dict]:
        return await self._lista(
            f"profile/{profilo}/contract/list",
            [
                ("domiciliation", "true"),
                ("meters", "true"),
                ("status", "ACTIVE"),
                ("status", "DEACTIVE"),
            ],
        )

    async def async_contratti_account(self) -> list[tuple[str, dict]]:
        """(profile id, contract) for every profile of the account: one
        account can hold a household and a business profile."""
        id_profili = [str(p["id"]) for p in await self.async_profili() if p.get("id")]
        if not id_profili:
            return []
        elenchi = await asyncio.gather(*(self.async_contratti(p) for p in id_profili))
        return [
            (id_profilo, c)
            for id_profilo, elenco in zip(id_profili, elenchi, strict=True)
            for c in elenco
            if c.get("id")
        ]

    # --- Readings & consumption -----------------------------------------------

    async def async_letture(self, profilo: str, servizio: str, contratto: str) -> list[dict]:
        """The whole read archive of a contract, newest first."""
        return await self._lista_paginata(
            f"v2/profile/{profilo}/read/archive/{servizio}",
            [("contractId", contratto), ("selfReading", "false")],
        )

    async def async_autoletture(self, profilo: str, servizio: str, contratto: str) -> list[dict]:
        """Self-readings archive of a contract (includes acceptance status)."""
        return await self._lista_paginata(
            f"v2/profile/{profilo}/read/archive/{servizio}",
            [("contractId", contratto), ("selfReading", "true")],
        )

    async def async_consumi(self, profilo: str, contratto: str) -> list[dict]:
        """Consumption per billing period, newest first."""
        return await self._lista_paginata(f"profile/{profilo}/contract/{contratto}/usage")

    async def async_consumi_giornalieri(
        self,
        profilo: str,
        contratto: str,
        pdr: str,
        dal_ms: int,
        al_ms: int,
    ) -> list[dict]:
        """Daily consumption for profiles with enabledDailyReads=true."""
        return await self._lista(
            f"v2/profile/{profilo}/contract/{contratto}/usage",
            [
                ("pdr", pdr),
                ("fromDate", str(dal_ms)),
                ("toDate", str(al_ms)),
                ("pageNumber", "0"),
                ("pageSize", "31"),
            ],
        )

    async def async_finestra_autolettura(self, profilo: str, contratto: str) -> dict | None:
        corpo = await self._get(f"profile/{profilo}/read/timeframe/{contratto}")
        return corpo if isinstance(corpo, dict) else None

    async def async_calendario_autoletture(self, profilo: str, contratto: str) -> list[dict]:
        """Upcoming self-reading windows for a contract."""
        return await self._lista_paginata(f"profile/{profilo}/read/calendar/{contratto}")

    async def async_ultima_lettura_contatore(
        self,
        profilo: str,
        contratto: str,
        contatore: str,
        *,
        pod: bool = False,
    ) -> dict | None:
        """Latest meter measurement structure required to submit a self-reading."""
        corpo = await self._get(
            f"v2/profile/{profilo}/contract/{contratto}/meter/{contatore}/read/last",
            [("pod", "true" if pod else "false")],
        )
        return corpo if isinstance(corpo, dict) else None

    async def async_invia_autolettura(self, profilo: str, payload: dict[str, Any]) -> Any:
        """Submit a self-reading (POST /api/v2/profile/{p}/read)."""
        return await self._post(f"v2/profile/{profilo}/read", payload)

    # --- Bills & payments -----------------------------------------------------

    async def async_bollette(self, profilo: str, raggruppamento: str | None) -> list[dict]:
        """Bills of a profile, with the same grouping as the portal's page."""
        parametri = [("groupBy", raggruppamento)] if raggruppamento else None
        return await self._lista_paginata(f"profile/{profilo}/bill/list", parametri)

    async def async_pagamenti_bollette(self, profilo: str) -> list[dict]:
        """Actual payment and refund records linked to bill IDs."""
        return await self._lista_paginata(f"profile/{profilo}/bill/invoice/list")

    async def async_bolletta_pdf(
        self, profilo: str, numero: str, *, dettaglio: bool = False
    ) -> bytes:
        """Download a bill PDF (summary or detailed v2)."""
        prefisso = "v2/" if dettaglio else ""
        dati = await self._request(
            "GET",
            f"{prefisso}profile/{profilo}/bill/export/pdf/{numero}",
            binario=True,
        )
        if not isinstance(dati, (bytes, bytearray)) or not dati:
            raise ApiError(f"PDF non disponibile per la bolletta {numero}")
        return bytes(dati)

    # --- Notifications & VAS --------------------------------------------------

    async def async_notifiche(self, profilo: str, *, dimensione: int = 20) -> dict[str, Any]:
        """Portal notifications: unread count, total and recent entries."""
        corpo = await self._get(
            f"profile/{profilo}/notification/list",
            [("pageNumber", "0"), ("pageSize", str(dimensione))],
        )
        if not isinstance(corpo, dict):
            raise ApiError(f"profile/{profilo}/notification/list: risposta inattesa")
        elementi = []
        for voce in corpo.get("list") or []:
            if not isinstance(voce, dict):
                continue
            giorno = giorno_da_ms(voce.get("date"))
            elementi.append(
                {
                    "id": str(voce.get("id") or ""),
                    "letta": bool(voce.get("isRead")),
                    "tipo": str(voce.get("type") or "UNKNOWN"),
                    "titolo": voce.get("title"),
                    "sottotitolo": voce.get("subTitle"),
                    "descrizione": voce.get("description"),
                    "data": giorno.isoformat() if giorno else None,
                }
            )
        return {
            "totale": int(corpo.get("total") or len(elementi)),
            "non_lette": int(corpo.get("toRead") or 0),
            "lista": elementi,
        }

    async def async_configurazione_notifiche(self, profilo: str) -> list[dict[str, Any]]:
        """Configured portal alert categories (excluding phone/email PII)."""
        corpo = await self._get(f"profile/{profilo}/notification/configuration/list")
        if not isinstance(corpo, dict):
            return []
        risultato: list[dict[str, Any]] = []
        for conf in corpo.get("configurations") or []:
            if not isinstance(conf, dict):
                continue
            risultato.append(
                {
                    "id": conf.get("id"),
                    "nome": conf.get("name"),
                    "tipo": conf.get("type"),
                    "categoria": conf.get("notifyType"),
                    "attivo": bool(conf.get("enabled")),
                }
            )
        return risultato

    async def async_vas(self, profilo: str) -> list[dict[str, Any]]:
        """Value-added services (e.g. Diario dei Consumi / ORS)."""
        grezze = await self._lista(f"profile/{profilo}/vas/list")
        risultato: list[dict[str, Any]] = []
        for voce in grezze:
            servizi = []
            for vas in voce.get("vasList") or []:
                if not isinstance(vas, dict):
                    continue
                servizi.append(
                    {
                        "id": vas.get("id"),
                        "stato": vas.get("status"),
                        "riferimento": vas.get("referer"),
                        "offerta": vas.get("offerCode"),
                        "canone": vas.get("fee"),
                    }
                )
            risultato.append(
                {
                    "servizio": voce.get("service"),
                    "contratto": str(voce["contractId"]) if voce.get("contractId") else None,
                    "bolletta_email": bool(voce.get("deliveryTypeEmail")),
                    "servizi": servizi,
                }
            )
        return risultato

    # --- Waste / TARI (ENVIRONMENT / TCP) -------------------------------------

    async def async_dotazioni_rifiuti(self, profilo: str, contratto: str) -> list[dict]:
        """Bins, cards and keys assigned to an ENVIRONMENT (TARI) contract."""
        return await self._lista(f"profile/{profilo}/TCP/equipment/{contratto}")

    async def async_svuotamenti_rifiuti(
        self,
        profilo: str,
        contratto: str,
        *,
        tipo: str = "RSU",
        anno: str = "CURRENT",
    ) -> dict[str, Any]:
        """Waste disposals for a waste fraction and year (CURRENT or PREVIOUS)."""
        svuotamenti: list[dict] = []
        volume_totale: Any = None
        for pagina in range(MAX_PAGINE):
            corpo = await self._get(
                f"profile/{profilo}/TCP/wastedisposal/{contratto}",
                [
                    ("type", tipo),
                    ("year", anno),
                    ("pageNumber", str(pagina)),
                    ("pageSize", str(DIMENSIONE_PAGINA)),
                ],
            )
            if not isinstance(corpo, dict):
                raise ApiError(f"profile/{profilo}/TCP/wastedisposal/{contratto}: risposta inattesa")
            if pagina == 0 and corpo.get("totalVolume") is not None:
                volume_totale = corpo.get("totalVolume")
            pagina_elementi = [e for e in corpo.get("wasteDisposals") or [] if isinstance(e, dict)]
            svuotamenti.extend(pagina_elementi)
            if not pagina_elementi or not corpo.get("hasNext"):
                break
        return {"wasteDisposals": svuotamenti, "totalVolume": volume_totale}

    async def async_vantaggi_rifiuti(self, profilo: str, contratto: str) -> list[dict]:
        """Available TARI discounts and advantages for an ENVIRONMENT contract."""
        return await self._lista(f"v1/profile/{profilo}/TCP/advantage/{contratto}")


def contratto_da_api(profilo: str, contratto: dict) -> dict[str, Any]:
    """What the config entry keeps of a contract: API ids, device metadata,
    and non-PII billing/meter flags. Never stores IBAN or email addresses."""
    contatori = [m for m in contratto.get("meters") or [] if isinstance(m, dict)]
    contatore = next(
        (m for m in contatori if m.get("status") == "ACTIVE"),
        contatori[0] if contatori else {},
    )
    risultato: dict[str, Any] = {
        "profilo": profilo,
        "contratto": str(contratto.get("id")),
        "servizio": contratto.get("serviceType"),
        "pod": contratto.get("pod") or contatore.get("pod"),
        "contatore": contatore.get("id"),
        "modello": contatore.get("phase"),
        "indirizzo": contratto.get("supplyAddress"),
        "stato": contratto.get("status"),
    }

    attivazione = giorno_da_ms(contratto.get("activationDate"))
    installazione = giorno_da_ms(contatore.get("installationDate"))
    extra: dict[str, Any] = {
        "attivazione": attivazione.isoformat() if attivazione else None,
        "uso": contratto.get("usage"),
        "mercato": contratto.get("sfdcMarket") or contratto.get("market"),
        "raggruppamento": contratto.get("groupingCode"),
        "installazione": installazione.isoformat() if installazione else None,
        "calibro": contatore.get("caliber"),
        "distributore": contatore.get("dealer"),
        "unita": contatore.get("unit"),
        "tipo_contatore": contatore.get("type"),
        "potenza": contatore.get("power"),
    }
    if contatore.get("selfReadingAvailable") is not None:
        extra["autolettura_disponibile"] = bool(contatore["selfReadingAvailable"])
    if contatore.get("isTgl") is not None:
        extra["teleletto"] = bool(contatore["isTgl"])

    cb = contratto.get("contractBill")
    if isinstance(cb, dict):
        if cb.get("domiciled") is not None:
            extra["domiciliato"] = bool(cb["domiciled"])
        if cb.get("domiciliationType"):
            extra["tipo_domiciliazione"] = str(cb["domiciliationType"])
        tipi_recapito = [str(t) for t in cb.get("deliveryTypes") or [] if t]
        if tipi_recapito:
            extra["modalita_recapito"] = tipi_recapito
            extra["bolletta_web"] = any(t.upper() in ("EMAIL", "PAPEREMAIL", "PEC") for t in tipi_recapito)

    for chiave, valore in extra.items():
        if valore is not None and valore != "":
            risultato[chiave] = valore
    return risultato
