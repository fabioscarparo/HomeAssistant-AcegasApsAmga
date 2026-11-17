"""Italian and English translations have the same keys, and cover the code."""
from __future__ import annotations

import json
import re
from pathlib import Path

PACCHETTO = Path(__file__).parent.parent / "custom_components" / "acegasapsamga"


def _chiavi(valore, prefisso=""):
    if isinstance(valore, dict):
        for chiave, figlio in valore.items():
            yield from _chiavi(figlio, f"{prefisso}{chiave}.")
    else:
        yield prefisso.rstrip(".")


def _traduzioni(lingua: str) -> dict:
    return json.loads((PACCHETTO / "translations" / f"{lingua}.json").read_text())


def test_stesse_chiavi():
    assert set(_chiavi(_traduzioni("it"))) == set(_chiavi(_traduzioni("en")))


def test_stessi_segnaposto():
    italiano, inglese = _traduzioni("it"), _traduzioni("en")
    for chiave in _chiavi(italiano):
        it_testo, en_testo = italiano, inglese
        for parte in chiave.split("."):
            it_testo, en_testo = it_testo[parte], en_testo[parte]
        assert set(re.findall(r"\{(\w+)\}", it_testo)) == set(re.findall(r"\{(\w+)\}", en_testo)), chiave


def test_chiavi_usate_nel_codice():
    italiano = _traduzioni("it")
    codice = "\n".join(p.read_text() for p in PACCHETTO.glob("*.py"))
    sensori = set(re.findall(r'chiave = "(\w+)"', codice))
    assert sensori == set(italiano["entity"]["sensor"])
    eccezioni = set(re.findall(r'translation_key="(\w+)"', codice))
    assert eccezioni <= set(italiano["exceptions"])
    errori = set(re.findall(r'return "(\w+)"', codice)) | {"nessuna_scelta"}
    assert errori <= set(italiano["config"]["error"])
    icone = json.loads((PACCHETTO / "icons.json").read_text())
    # Volume sensors keep the device class icon (water or gas).
    assert set(icone["entity"]["sensor"]) == sensori - {"lettura", "consumo_periodo"}
