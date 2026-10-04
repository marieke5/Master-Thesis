import pandas as pd
import pytest

from lcoh_tool.config import (
    BackupConfig,
    FossileReferenzConfig,
    SpeicherConfig,
    ToolConfig,
    WaermebedarfConfig,
    WaermepumpeConfig,
    WindparkConfig,
    WirtschaftConfig,
)
from lcoh_tool.wirtschaftlichkeit import annuitaetsfaktor, berechne_lcoh


def test_annuitaetsfaktor_ohne_zins_ist_gleichverteilung():
    assert annuitaetsfaktor(wacc=0.0, laufzeit_jahre=20) == pytest.approx(1 / 20)


def test_annuitaetsfaktor_mit_zins_plausibler_bereich():
    af = annuitaetsfaktor(wacc=0.05, laufzeit_jahre=20)
    assert 0.05 < af < 0.10  # grobe Plausibilitaetsgrenze


def test_berechne_lcoh_ohne_rueckfallstrom():
    bilanz = pd.DataFrame(
        {
            "waermelast_kwh": [1000.0, 1000.0],
            "direktanschluss_kwh": [400.0, 400.0],
            "rueckfall_kwh": [0.0, 0.0],
        }
    )
    config = ToolConfig(
        projektname="Test",
        windpark=WindparkConfig(erzeugungsprofil_pfad="irrelevant.csv"),
        waermebedarf=WaermebedarfConfig(),
        waermepumpe=WaermepumpeConfig(jazl=3.0, nennleistung_kw=100),
        backup=BackupConfig(typ="elektrodenkessel", wirkungsgrad=0.98, nennleistung_kw=100),
        speicher=SpeicherConfig(kapazitaet_kwh=0),
        wirtschaft=WirtschaftConfig(
            wacc=0.0,
            abschreibungsdauer_jahre=10,
            strompreis_rueckfall_eur_pro_mwh=90,
            netzentgelt_eur_pro_mwh=40,
            capex_waermepumpe_eur=10000,
            opex_fix_eur_pro_jahr=100,
        ),
    )

    ergebnis = berechne_lcoh(bilanz, config)

    # Kapitalkosten p.a.: 10000/10 = 1000; Betriebskosten: 100 (kein Rueckfallstrom)
    # Waermemenge: 2000 kWh = 2 MWh -> LCOH = 1100 / 2 = 550 EUR/MWh
    assert ergebnis.lcoh_eur_pro_mwh == pytest.approx(550.0)
    assert ergebnis.lcoh_fossile_referenz_eur_pro_mwh is None


def test_berechne_lcoh_mit_fossiler_referenz():
    bilanz = pd.DataFrame(
        {
            "waermelast_kwh": [1000.0],
            "direktanschluss_kwh": [400.0],
            "rueckfall_kwh": [0.0],
        }
    )
    config = ToolConfig(
        projektname="Test",
        windpark=WindparkConfig(erzeugungsprofil_pfad="irrelevant.csv"),
        waermebedarf=WaermebedarfConfig(),
        waermepumpe=WaermepumpeConfig(jazl=3.0, nennleistung_kw=100),
        backup=BackupConfig(typ="elektrodenkessel", wirkungsgrad=0.98, nennleistung_kw=100),
        speicher=SpeicherConfig(kapazitaet_kwh=0),
        wirtschaft=WirtschaftConfig(
            wacc=0.0,
            abschreibungsdauer_jahre=10,
            strompreis_rueckfall_eur_pro_mwh=90,
            netzentgelt_eur_pro_mwh=40,
        ),
        fossile_referenz=FossileReferenzConfig(
            aktiv=True,
            wirkungsgrad_kessel=1.0,
            brennstoffpreis_eur_pro_mwh=50,
            capex_eur=0,
        ),
    )

    ergebnis = berechne_lcoh(bilanz, config)

    # Waermemenge 1 MWh, Brennstoffbedarf 1 MWh, Kosten 50 EUR -> LCOH 50 EUR/MWh
    assert ergebnis.lcoh_fossile_referenz_eur_pro_mwh == pytest.approx(50.0)
