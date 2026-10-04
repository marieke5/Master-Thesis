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


def test_load_config_datei_fehlt():
    with pytest.raises(FileNotFoundError):
        load_config("config/existiert_nicht.yaml")
