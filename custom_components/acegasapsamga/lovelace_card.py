"""The meter card, served by the integration itself.

The JS file in frontend/ is exposed as a static path and added to every
dashboard as an extra module: the card shows up in the card picker with no
resource to add by hand.

The file is cached for a month (cache_headers=True): the ?v= parameter is a
hash of its content, so a new card is downloaded as soon as the file changes.
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

_CHIAVE_REGISTRATA = f"{DOMAIN}_card_registrata"


def impronta_file(percorso: Path = PERCORSO_FILE) -> str:
    """First 12 hex digits of the file's SHA-256."""
    return hashlib.sha256(percorso.read_bytes()).hexdigest()[:12]


async def async_registra_card(hass: HomeAssistant) -> None:
    """Serve the card once per start. Without http or frontend (tests,
    headless installs) it does nothing: the card must never block the setup."""
    if hass.data.get(_CHIAVE_REGISTRATA):
        return
    if hass.http is None or "frontend" not in hass.config.components:
        _LOGGER.debug("http/frontend non attivi: card non registrata")
        return

    # Imported here: frontend and http are optional dependencies.
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    try:
        impronta = await hass.async_add_executor_job(impronta_file, PERCORSO_FILE)
    except OSError as err:
        _LOGGER.warning("Impossibile leggere il file della card (%s): %s", PERCORSO_FILE, err)
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(URL_STATICO, str(PERCORSO_FILE), cache_headers=True)]
    )
    add_extra_js_url(hass, f"{URL_STATICO}?v={impronta}")
    hass.data[_CHIAVE_REGISTRATA] = True
    _LOGGER.debug("Card registrata su %s", URL_STATICO)
