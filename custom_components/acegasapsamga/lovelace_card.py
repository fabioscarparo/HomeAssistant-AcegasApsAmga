"""Lovelace cards served directly by the integration.

The JS modules in frontend/ are exposed as static paths and added to every
dashboard as extra modules: every card shows up in the card picker with no
resource to add by hand.

Files are cached for a month (cache_headers=True): the ?v= parameter is a
hash of each file's content, so browsers download updates immediately.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

NOME_FILE = "acegasapsamga-contatore-card.js"
URL_STATICO = f"/{DOMAIN}_static/{NOME_FILE}"
PERCORSO_FILE = Path(__file__).parent / "frontend" / NOME_FILE

CARDS: tuple[str, ...] = (
    NOME_FILE,
    "acegasapsamga-luce-card.js",
    "acegasapsamga-rifiuti-card.js",
    "acegasapsamga-bollette-card.js",
)

_CHIAVE_REGISTRATA = f"{DOMAIN}_card_registrata"


def impronta_file(percorso: Path = PERCORSO_FILE) -> str:
    """First 12 hex digits of the file's SHA-256."""
    return hashlib.sha256(percorso.read_bytes()).hexdigest()[:12]


def percorsi_card() -> list[tuple[str, Path]]:
    """Return (static_url, file_path) for every card served by the integration."""
    cartella = PERCORSO_FILE.parent
    risultato: list[tuple[str, Path]] = [(URL_STATICO, PERCORSO_FILE)]
    for nome in CARDS[1:]:
        risultato.append((f"/{DOMAIN}_static/{nome}", cartella / nome))
    return risultato


async def async_registra_card(hass: HomeAssistant) -> None:
    """Serve all cards once per start. Without http or frontend (tests,
    headless installs) it does nothing: cards must never block setup."""
    if hass.data.get(_CHIAVE_REGISTRATA):
        return
    if hass.http is None or "frontend" not in hass.config.components:
        _LOGGER.debug("http/frontend non attivi: card non registrate")
        return

    # Imported here: frontend and http are optional dependencies.
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    percorsi_statici = []
    urls_con_versione: list[str] = []
    for url, percorso in percorsi_card():
        try:
            impronta = await hass.async_add_executor_job(impronta_file, percorso)
        except OSError as err:
            _LOGGER.warning("Impossibile leggere il file della card (%s): %s", percorso, err)
            continue
        percorsi_statici.append(StaticPathConfig(url, str(percorso), cache_headers=True))
        urls_con_versione.append(f"{url}?v={impronta}")

    if not percorsi_statici:
        return

    await hass.http.async_register_static_paths(percorsi_statici)
    for url_versionato in urls_con_versione:
        add_extra_js_url(hass, url_versionato)
    hass.data[_CHIAVE_REGISTRATA] = True
    _LOGGER.debug("Card registrate: %s", ", ".join(urls_con_versione))
