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


def test_berechne_projekt_nutzt_vorgegebene_profile():
    config = load_config(PARAMETER_CONFIG)
    # Config-Quellen sind absichtlich unbrauchbar: die vorgegebenen Profile muessen gewinnen.
    config.windpark.erzeugungsprofil_pfad = "gibt_es_nicht.csv"
    config.waermebedarf.waermelast_pfad = "gibt_es_nicht.csv"
    from lcoh_tool.erzeugungsprofil import load_erzeugungsprofil
    from lcoh_tool.waermebedarf import load_waermebedarf

    basis = load_config(PARAMETER_CONFIG)
    erzeugung = load_erzeugungsprofil(basis.windpark.erzeugungsprofil_pfad)
    waermelast = load_waermebedarf(basis.waermebedarf.waermelast_pfad)
    ergebnis = berechne_projekt(config, erzeugungsprofil=erzeugung, waermelastprofil=waermelast)
    assert ergebnis.lcoh.lcoh_eur_pro_mwh > 0


def test_csv_upload_als_dateiobjekt_wird_akzeptiert():
    from lcoh_tool.erzeugungsprofil import load_erzeugungsprofil

    config = load_config(PARAMETER_CONFIG)
    with open(config.windpark.erzeugungsprofil_pfad, "rb") as datei:
        profil = load_erzeugungsprofil(datei)
    assert len(profil) > 0


def test_windpowerlib_ohne_block_wirft_fehler():
    config = load_config(PARAMETER_CONFIG)
    config.windpark.quelle = "windpowerlib"
    config.windpark.windpowerlib = None
    with pytest.raises(ValueError, match="windpowerlib"):
        berechne_projekt(config)
