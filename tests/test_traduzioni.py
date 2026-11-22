"""Italian and English translations have the same keys, and cover the code."""
from __future__ import annotations

import json
import re
from pathlib import Path

from custom_components.acegasapsamga import lovelace_card

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
    sensor_code = (PACCHETTO / "sensor.py").read_text()
    sensori = set(re.findall(r'chiave = "(\w+)"', sensor_code))
    assert sensori == set(italiano["entity"]["sensor"])

    codice = "\n".join(p.read_text() for p in PACCHETTO.glob("*.py"))
    # translation_key is used for exceptions and repair issues.
    chiavi_trad = set(re.findall(r'translation_key="(\w+)"', codice))
    assert chiavi_trad <= (set(italiano["exceptions"]) | set(italiano["issues"]))

    config_flow = (PACCHETTO / "config_flow.py").read_text()
    blocco_errori = config_flow[
        config_flow.index("def errore_accesso") : config_flow.index("def etichetta")
    ]
    errori = set(re.findall(r'return "(\w+)"', blocco_errori)) | {"nessuna_scelta"}
    assert errori <= set(italiano["config"]["error"])

    icone = json.loads((PACCHETTO / "icons.json").read_text())
    # Meter reading and period consumption keep device class icons (water/gas/energy).
    assert set(icone["entity"]["sensor"]) == sensori - {"lettura", "consumo_periodo"}
    assert set(icone["entity"]["calendar"]) == set(italiano["entity"]["calendar"])
    assert set(icone["services"]) == set(italiano["services"])


def test_versione_tutte_le_card_uguale_al_manifest():
    manifest = json.loads((PACCHETTO / "manifest.json").read_text())
    for _, percorso in lovelace_card.percorsi_card():
        card = percorso.read_text(encoding="utf-8")
        versione = re.search(r'const VERSION = "([^"]+)"', card).group(1)
        assert versione == manifest["version"], percorso.name
