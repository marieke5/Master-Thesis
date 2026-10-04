import pandas as pd

from lcoh_tool.bilanz import berechne_bilanz
from lcoh_tool.config import (
    BackupConfig,
    SpeicherConfig,
    ToolConfig,
    WaermebedarfConfig,
    WaermepumpeConfig,
    WindparkConfig,
    WirtschaftConfig,
)


def _minimal_config(jazl=3.0, speicher_kwh=0.0) -> ToolConfig:
    return ToolConfig(
        projektname="Test",
        windpark=WindparkConfig(erzeugungsprofil_pfad="irrelevant.csv"),
        waermebedarf=WaermebedarfConfig(),
        waermepumpe=WaermepumpeConfig(jazl=jazl, nennleistung_kw=100),
        backup=BackupConfig(typ="elektrodenkessel", wirkungsgrad=0.98, nennleistung_kw=100),
        speicher=SpeicherConfig(kapazitaet_kwh=speicher_kwh),
        wirtschaft=WirtschaftConfig(
            wacc=0.05,
            abschreibungsdauer_jahre=20,
            strompreis_rueckfall_eur_pro_mwh=90,
            netzentgelt_eur_pro_mwh=40,
        ),
    )


def test_bilanz_volle_deckung_durch_wind():
    index = pd.date_range("2027-01-01", periods=3, freq="h")
    erzeugung = pd.Series([100, 100, 100], index=index)
    waermelast = pd.Series([300, 300, 300], index=index)  # -> Strombedarf 100 kWh/h bei JAZ=3

    bilanz = berechne_bilanz(erzeugung, waermelast, _minimal_config(jazl=3.0))

    assert (bilanz["rueckfall_kwh"] == 0).all()
    assert bilanz["direktanschluss_kwh"].sum() == 300


def test_bilanz_rueckfall_bei_windflaute():
    index = pd.date_range("2027-01-01", periods=2, freq="h")
    erzeugung = pd.Series([0, 0], index=index)
    waermelast = pd.Series([300, 300], index=index)  # Strombedarf 100 kWh/h

    bilanz = berechne_bilanz(erzeugung, waermelast, _minimal_config(jazl=3.0))

    assert bilanz["direktanschluss_kwh"].sum() == 0
    assert bilanz["rueckfall_kwh"].sum() == 200


def test_bilanz_speicher_gleicht_ueberschuss_und_defizit_aus():
    index = pd.date_range("2027-01-01", periods=2, freq="h")
    # Stunde 1: Ueberschuss an Windenergie -> geht in den Speicher.
    # Stunde 2: keine Erzeugung -> Speicher deckt den Bedarf.
    erzeugung = pd.Series([200, 0], index=index)
    waermelast = pd.Series([300, 300], index=index)  # Strombedarf 100 kWh/h je Stunde

    bilanz = berechne_bilanz(erzeugung, waermelast, _minimal_config(jazl=3.0, speicher_kwh=100))

    assert bilanz["rueckfall_kwh"].sum() == 0
    assert bilanz.loc[index[1], "direktanschluss_kwh"] == 100
