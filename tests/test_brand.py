"""Integration icon: Home Assistant 2026.3+ reads brand/icon.png (256 px) and
brand/icon@2x.png (512 px) from the integration's folder."""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

BRAND = Path(__file__).parent.parent / "custom_components" / "acegasapsamga" / "brand"


@pytest.mark.parametrize(("nome", "lato"), [("icon.png", 256), ("icon@2x.png", 512)])
def test_icona(nome, lato):
    dati = (BRAND / nome).read_bytes()[:26]
    assert dati[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", dati[16:24]) == (lato, lato)
    # RGBA, for the transparent rounded corners.
    assert dati[25] == 6
