from pathlib import Path

import pytest

from lcoh_tool.config import load_config
from lcoh_tool.variation import variiere

CONFIG = Path(__file__).parents[1] / "config" / "parameter_steuerung.yaml"


def test_variation_liefert_zeile_je_kombination_und_skaliert_capex():
    tabelle = variiere(load_config(CONFIG), [2000, 8000], [0, 50])
    assert len(tabelle) == 4
    assert set(tabelle["speicher_kwh"]) == {2000, 8000}
    assert (tabelle["lcoh_eur_mwh"] > 0).all()
    # groesserer Speicher -> hoehere Kapitalkosten bei gleicher Schwelle (capex linear)
    a = tabelle[(tabelle.speicher_kwh == 2000) & (tabelle.schwelle_eur_mwh == 0)]
    b = tabelle[(tabelle.speicher_kwh == 8000) & (tabelle.schwelle_eur_mwh == 0)]
    assert a.index[0] != b.index[0]


def test_variation_ohne_steuerung_fehler():
    config = load_config(CONFIG)
    config.steuerung = None
    with pytest.raises(ValueError, match="steuerung"):
        variiere(config, [1000], [0])
