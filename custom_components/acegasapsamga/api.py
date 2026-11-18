"""Client of the Servizi Online API.

Every call sends the B2C access token as a Bearer token and the two headers
of the web app; no cookie is needed. Dates in the answers are epoch
milliseconds of a calendar day (see letture.giorno_da_ms).

No Home Assistant imports. Real answers, anonymized, are in tests/fixtures.
"""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import API_BASE_URL, API_PLATFORM_ID, API_REFERER, DIMENSIONE_PAGINA, MAX_PAGINE

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=30)


class ApiError(Exception):
    def __init__(self, messaggio: str, *, status: int | None = None, rete: bool = False):
        super().__init__(messaggio)
        self.status = status
        self.rete = rete


class TokenScaduto(ApiError):
    """The API refused the access token."""


class ApiClient:
    def __init__(self, session: aiohttp.ClientSession, access_token: str = "") -> None:
        self._session = session
        self.access_token = access_token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "X-Bwb-PlatformId": API_PLATFORM_ID,
            "X-Bwb-Referer": API_REFERER,
            "Accept": "application/json",
        }

    async def _get(self, percorso: str, parametri: list[tuple[str, str]] | None = None) -> Any:
        try:
            async with self._session.get(
                f"{API_BASE_URL}/{percorso}",
                params=parametri,
                headers=self._headers(),
                timeout=TIMEOUT,
            ) as risposta:
                stato = risposta.status
                if stato == 200:
                    return await risposta.json(content_type=None)
                testo = (await risposta.text())[:300]
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ApiError(str(err) or type(err).__name__, rete=True) from err
        except ValueError as err:
            raise ApiError(f"{percorso}: risposta non JSON") from err

        # A missing or invalid token gets 403 "role not allowed".
        if stato in (401, 403) or "TOKEN_EXPIRED" in testo:
            raise TokenScaduto(f"{percorso}: HTTP {stato}", status=stato)
        raise ApiError(f"{percorso}: HTTP {stato} {testo}", status=stato)

    async def _lista_paginata(
        self, percorso: str, parametri: list[tuple[str, str]] | None = None
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
            elementi.extend(e for e in corpo.get("list") or [] if isinstance(e, dict))
            if not corpo.get("hasNext"):
                return elementi
        _LOGGER.warning("%s: interrotto dopo %d pagine", percorso, MAX_PAGINE)
        return elementi

    async def _lista(self, percorso: str, parametri: list[tuple[str, str]] | None = None) -> list[dict]:
        corpo = await self._get(percorso, parametri)
        return [e for e in (corpo or {}).get("list") or [] if isinstance(e, dict)]

    async def async_profili(self) -> list[dict]:
        return await self._lista("profile/list")

    async def async_contratti(self, profilo: str) -> list[dict]:
        return await self._lista(
            f"profile/{profilo}/contract/list",
            [
                ("domiciliation", "false"),
                ("meters", "true"),
                ("status", "ACTIVE"),
                ("status", "DEACTIVE"),
            ],
        )

    async def async_contratti_account(self) -> list[tuple[str, dict]]:
        """(profile id, contract) for every profile of the account: one
        account can hold a household and a business profile."""
        contratti: list[tuple[str, dict]] = []
        for profilo in await self.async_profili():
            if profilo.get("id"):
                id_profilo = str(profilo["id"])
                contratti.extend((id_profilo, c) for c in await self.async_contratti(id_profilo))
        return contratti

    async def async_letture(self, profilo: str, servizio: str, contratto: str) -> list[dict]:
        """The whole read archive of a contract, newest first."""
        return await self._lista_paginata(
            f"v2/profile/{profilo}/read/archive/{servizio}",
            [("contractId", contratto), ("selfReading", "false")],
        )

    async def async_consumi(self, profilo: str, contratto: str) -> list[dict]:
        """Consumption per billing period, newest first."""
        return await self._lista_paginata(f"profile/{profilo}/contract/{contratto}/usage")

    async def async_finestra_autolettura(self, profilo: str, contratto: str) -> dict | None:
        corpo = await self._get(f"profile/{profilo}/read/timeframe/{contratto}")
        return corpo if isinstance(corpo, dict) else None

    async def async_raggruppamento_bollette(self, profilo: str) -> str | None:
        """How the profile's bills are grouped (billGroupType). The rest of
        the profile is personal data and is not returned."""
        corpo = await self._get(f"profile/{profilo}")
        valore = corpo.get("billGroupType") if isinstance(corpo, dict) else None
        return str(valore) if valore else None

    async def async_bollette(self, profilo: str, raggruppamento: str | None) -> list[dict]:
        """Bills of a profile, with the same grouping as the portal's page."""
        parametri = [("groupBy", raggruppamento)] if raggruppamento else None
        return await self._lista_paginata(f"profile/{profilo}/bill/list", parametri)


def contratto_da_api(profilo: str, contratto: dict) -> dict:
    """What the config entry keeps of a contract: the ids for the API calls
    and what names the device."""
    contatori = [m for m in contratto.get("meters") or [] if isinstance(m, dict)]
    contatore = next(
        (m for m in contatori if m.get("status") == "ACTIVE"),
        contatori[0] if contatori else {},
    )
    return {
        "profilo": profilo,
        "contratto": str(contratto.get("id")),
        "servizio": contratto.get("serviceType"),
        "pod": contratto.get("pod") or contatore.get("pod"),
        "contatore": contatore.get("id"),
        "modello": contatore.get("phase"),
        "indirizzo": contratto.get("supplyAddress"),
        "stato": contratto.get("status"),
    }
