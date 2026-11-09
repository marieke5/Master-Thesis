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


def test_direktstrompreis_variation_und_breakeven():
    from lcoh_tool.variation import breakeven_direktstrompreis

    tabelle = variiere(load_config(CONFIG), [2000], [0], direktstrompreise_eur_mwh=[0, 50, 100])
    assert list(tabelle["direktstrompreis_eur_mwh"]) == [0, 50, 100]
    # teurerer Direktstrom -> hoehere LCOH der Direktleitung
    assert tabelle["lcoh_eur_mwh"].is_monotonic_increasing
    assert tabelle["vorteil_vs_netzbezug_eur_mwh"].is_monotonic_decreasing


def test_breakeven_interpolation():
    import pandas as pd

    from lcoh_tool.variation import breakeven_direktstrompreis

    g = pd.DataFrame({"direktstrompreis_eur_mwh": [0, 100], "vorteil_vs_netzbezug_eur_mwh": [10.0, -10.0]})
    assert breakeven_direktstrompreis(g) == pytest.approx(50.0)
    g["vorteil_vs_netzbezug_eur_mwh"] = [-5.0, -10.0]
    assert breakeven_direktstrompreis(g) is None
