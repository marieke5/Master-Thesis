from pathlib import Path

import pytest

from lcoh_tool.config import load_config

BEISPIEL_CONFIG = Path(__file__).parents[1] / "config" / "beispiel_siebeneichen.yaml"


def test_load_config_liest_projektname():
    config = load_config(BEISPIEL_CONFIG)
    assert config.projektname == "Siebeneichen - Direktanschluss Windpark an Nahwaermenetz"


def test_load_config_setzt_verschachtelte_werte():
    config = load_config(BEISPIEL_CONFIG)
    assert config.waermepumpe.jazl == pytest.approx(3.2)
    assert config.backup.typ == "elektrodenkessel"
    assert config.wirtschaft.wacc == pytest.approx(0.05)
    assert config.fossile_referenz.aktiv is True


def test_load_config_liest_strompreisszenarien():
    config = load_config(BEISPIEL_CONFIG)
    szenarien = config.wirtschaft.strompreisszenarien
    assert szenarien.best_case_eur_pro_mwh == pytest.approx(70)
    assert szenarien.realistisch_eur_pro_mwh == pytest.approx(90)
    assert szenarien.worst_case_eur_pro_mwh == pytest.approx(130)
    assert config.wirtschaft.strompreisszenario_aktiv == "realistisch"
    assert szenarien.preis("worst_case") == pytest.approx(130)


def test_load_config_datei_fehlt():
    with pytest.raises(FileNotFoundError):
        load_config("config/existiert_nicht.yaml")
