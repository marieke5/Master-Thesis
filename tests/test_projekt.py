from pathlib import Path

import pytest

from lcoh_tool.config import load_config
from lcoh_tool.projekt import ProjektErgebnis, berechne_projekt

PARAMETER_CONFIG = Path(__file__).parents[1] / "config" / "parameter.yaml"


def test_berechne_projekt_gibt_ergebnisobjekt_zurueck():
    ergebnis = berechne_projekt(PARAMETER_CONFIG)
    assert isinstance(ergebnis, ProjektErgebnis)
    assert ergebnis.lcoh.lcoh_eur_pro_mwh > 0
    assert 0 <= ergebnis.anteil_direktanschluss_prozent <= 100
    assert not ergebnis.bilanz.empty


def test_berechne_projekt_akzeptiert_fertiges_toolconfig():
    config = load_config(PARAMETER_CONFIG)
    ergebnis = berechne_projekt(config)
    assert ergebnis.config is config


def test_berechne_projekt_ohne_waermebedarf_wirft_fehler():
    config = load_config(PARAMETER_CONFIG)
    config.waermebedarf.waermelast_pfad = None
    config.waermebedarf.jahreswaermebedarf_mwh = None
    with pytest.raises(ValueError):
        berechne_projekt(config)
