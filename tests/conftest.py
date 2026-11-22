"""Shared fixtures: real portal answers (anonymized) and a fake HTTP session."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.acegasapsamga.const import CONF_CONTRATTI, CONF_ID_UTENTE, DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"

FIXTURES = Path(__file__).parent / "fixtures"

CONTRATTO = {
    "profilo": "PROFILO0001",
    "contratto": "1000000001",
    "servizio": "WATER",
    "pod": "0500000000000001",
    "contatore": "MATRICOLA0001",
    "modello": "Cont.acqDN20volumL190MIDNB-IoT",
    "indirizzo": "VIA DI ESEMPIO 1, TRIESTE TS, 34100 Italia",
    "stato": "ACTIVE",
    "attivazione": "2025-11-27",
    "uso": "1101-Domestico",
    "mercato": "Regolamentato",
    "raggruppamento": "200000000001",
    "installazione": "2025-11-27",
    "calibro": "A1302",
    "unita": "mc",
    "tipo_contatore": "MONO",
    "autolettura_disponibile": True,
}


def carica(nome: str) -> Any:
    return json.loads((FIXTURES / nome).read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(request):
    # The recorder must start before 'hass', so it is requested first.
    if "recorder_mock" in request.fixturenames:
        request.getfixturevalue("recorder_mock")
    request.getfixturevalue("enable_custom_integrations")


@pytest.fixture
def entry(hass) -> MockConfigEntry:
    voce = MockConfigEntry(
        domain=DOMAIN,
        title="utente@example.com",
        unique_id="utente-1",
        data={
            CONF_EMAIL: "utente@example.com",
            CONF_PASSWORD: "segreta",
            CONF_ID_UTENTE: "utente-1",
            CONF_CONTRATTI: [dict(CONTRATTO)],
        },
    )
    voce.add_to_hass(hass)
    return voce


class RispostaFinta:
    def __init__(self, status: int = 200, corpo: Any = None, headers: dict | None = None):
        self.status = status
        self._corpo = corpo
        self.headers = headers or {}

    async def text(self) -> str:
        if isinstance(self._corpo, (bytes, bytearray)):
            return self._corpo.decode("utf-8", errors="replace")
        return self._corpo if isinstance(self._corpo, str) else json.dumps(self._corpo)

    async def read(self) -> bytes:
        if isinstance(self._corpo, (bytes, bytearray)):
            return bytes(self._corpo)
        return (await self.text()).encode("utf-8")

    async def json(self, content_type=None) -> Any:
        return json.loads(await self.text())

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class CookieJarFinto:
    def __init__(self):
        self.pulito: list[str] = []
        self.svuotato = 0

    def clear_domain(self, dominio: str) -> None:
        self.pulito.append(dominio)

    def clear(self) -> None:
        self.svuotato += 1


class SessioneFinta:
    """Answers by (method, URL prefix); records every request."""

    def __init__(self):
        self.rotte: list[tuple[str, str, Any]] = []
        self.richieste: list[dict[str, Any]] = []
        self.cookie_jar = CookieJarFinto()

    def aggiungi(self, metodo: str, prefisso: str, risposta) -> None:
        """'risposta' is a RispostaFinta, a list of them (one per call) or an exception."""
        self.rotte.append((metodo, prefisso, risposta))

    def _rispondi(self, metodo: str, url: str, **kwargs):
        self.richieste.append({"metodo": metodo, "url": url, **kwargs})
        for m, prefisso, risposta in self.rotte:
            if m == metodo and url.startswith(prefisso):
                if isinstance(risposta, list):
                    risposta = risposta.pop(0) if len(risposta) > 1 else risposta[0]
                if isinstance(risposta, Exception):
                    raise risposta
                return risposta
        raise AssertionError(f"richiesta non prevista: {metodo} {url}")

    def get(self, url, **kwargs):
        return self._rispondi("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._rispondi("POST", url, **kwargs)

    async def close(self):
        pass


@pytest.fixture
def sessione() -> SessioneFinta:
    return SessioneFinta()
