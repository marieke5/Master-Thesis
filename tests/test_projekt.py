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


def test_gleiche_jahr_an_legt_profil_auf_zieljahr():
    import pandas as pd

    from lcoh_tool.projekt import gleiche_jahr_an

    erzeugung = pd.Series(
        range(8784), index=pd.date_range("2024-01-01", periods=8784, freq="h")
    )  # Schaltjahr
    waermelast = pd.Series(
        1.0, index=pd.date_range("2027-01-01", periods=8760, freq="h")
    )
    angeglichen = gleiche_jahr_an(erzeugung, waermelast)
    assert angeglichen.index.year.unique().tolist() == [2027]
    assert len(angeglichen) == 8760
    assert angeglichen.index.is_unique
    assert angeglichen.index.isin(waermelast.index).all()


def test_gleiche_jahr_an_laesst_gleiches_jahr_unveraendert():
    import pandas as pd

    from lcoh_tool.projekt import gleiche_jahr_an

    idx = pd.date_range("2027-01-01", periods=24, freq="h")
    profil = pd.Series(1.0, index=idx)
    assert gleiche_jahr_an(profil, profil).equals(profil)


def test_kennzahlen_und_hinweise_bei_ueberdimensioniertem_wind():
    config = load_config(PARAMETER_CONFIG)
    ergebnis = berechne_projekt(config)
    k = ergebnis.kennzahlen
    assert k.erzeugung_mwh > 0
    assert k.waermebedarf_mwh > 0
    assert k.erzeugung_zu_strombedarf > 0
    assert k.rueckfall_stunden >= 0


def test_kennzahlen_hinweis_ohne_rueckfall():
    import pandas as pd

    from lcoh_tool.projekt import berechne_kennzahlen

    idx = pd.date_range("2027-01-01", periods=4, freq="h")
    bilanz = pd.DataFrame(
        {
            "erzeugung_kwh": [1000.0] * 4,
            "strombedarf_wp_kwh": [10.0] * 4,
            "waermelast_kwh": [32.0] * 4,
            "rueckfall_kwh": [0.0] * 4,
        },
        index=idx,
    )
    k = berechne_kennzahlen(bilanz, load_config(PARAMETER_CONFIG))
    assert k.rueckfall_stunden == 0
    assert k.erzeugung_zu_strombedarf == pytest.approx(100.0)
    assert any("Kein Rueckfallstrom" in h for h in k.hinweise)
    assert any("sehr gross" in h for h in k.hinweise)


def _mehrjahres_profil():
    import pandas as pd

    idx = pd.date_range("2022-01-01", "2024-01-01", freq="h", inclusive="left")
    return pd.Series(range(len(idx)), index=idx, dtype=float)


def test_waehle_jahr_waehlt_referenzjahr_aus_mehrjahresprofil():
    from lcoh_tool.projekt import waehle_jahr

    profil = _mehrjahres_profil()
    ausgewaehlt = waehle_jahr(profil, 2023, "Wind")
    assert ausgewaehlt.index.year.unique().tolist() == [2023]
    assert len(ausgewaehlt) == 8760


def test_waehle_jahr_mehrjahresprofil_ohne_referenzjahr_wirft_fehler():
    from lcoh_tool.projekt import waehle_jahr

    with pytest.raises(ValueError, match="referenzjahr"):
        waehle_jahr(_mehrjahres_profil(), None, "Wind")


def test_waehle_jahr_unbekanntes_referenzjahr_wirft_fehler():
    from lcoh_tool.projekt import waehle_jahr

    with pytest.raises(ValueError, match="nicht"):
        waehle_jahr(_mehrjahres_profil(), 2019, "Wind")


def test_waehle_jahr_einjahresprofil_bleibt_unveraendert():
    from lcoh_tool.projekt import waehle_jahr

    profil = _mehrjahres_profil().loc["2022"]
    assert waehle_jahr(profil, 2030, "Wind") is profil


def test_referenzjahr_wird_auf_windpowerlib_und_lpagg_uebertragen():
    from lcoh_tool.config import (
        GebaeudetypConfig,
        LpaggConfig,
        WindpowerlibConfig,
    )
    from lcoh_tool.projekt import wende_referenzjahr_an

    config = load_config(PARAMETER_CONFIG)
    config.windpark.windpowerlib = WindpowerlibConfig(breitengrad=53.5, laengengrad=10.6, jahr=2019)
    config.waermebedarf.lpagg = LpaggConfig(
        gebaeude={"EFH": GebaeudetypConfig(house_type="EFH", anzahl=1)}, wetterquelle="era5"
    )
    assert wende_referenzjahr_an(config) is config  # ohne Referenzjahr unveraendert
    config.referenzjahr = 2023
    neu = wende_referenzjahr_an(config)
    assert neu.windpark.windpowerlib.jahr == 2023
    assert neu.waermebedarf.lpagg.wetterjahr == 2023
    assert config.windpark.windpowerlib.jahr == 2019  # Original unveraendert


def test_berechne_projekt_mit_mehrjahres_windprofil_und_referenzjahr():
    import pandas as pd

    config = load_config(PARAMETER_CONFIG)
    config.referenzjahr = 2023
    waermelast = pd.Series(10.0, index=pd.date_range("2027-01-01", periods=8760, freq="h"))
    ergebnis = berechne_projekt(config, erzeugungsprofil=_mehrjahres_profil(), waermelastprofil=waermelast)
    assert ergebnis.kennzahlen.erzeugung_mwh > 0
    config.referenzjahr = None
    with pytest.raises(ValueError, match="referenzjahr"):
        berechne_projekt(config, erzeugungsprofil=_mehrjahres_profil(), waermelastprofil=waermelast)
