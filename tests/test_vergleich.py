from pathlib import Path

import pandas as pd
import pytest

from lcoh_tool.config import load_config
from lcoh_tool.projekt import berechne_projekt
from lcoh_tool.vergleich import berechne_netzbezug_referenz
from lcoh_tool.wirtschaftlichkeit import annuitaetsfaktor

ROOT = Path(__file__).parents[1]
STEUERUNG = ROOT / "config" / "parameter_steuerung.yaml"


def _config():
    config = load_config(STEUERUNG)
    w = config.wirtschaft
    w.wacc, w.abschreibungsdauer_jahre = 0.0, 10
    w.capex_waermepumpe_eur, w.capex_backup_eur, w.capex_netzanschluss_eur = 1000, 500, 0
    w.capex_speicher_eur = 0
    w.leistungspreis_eur_pro_kw_a = 0.0
    w.opex_fix_eur_pro_jahr = 100
    w.netzentgelt_eur_pro_mwh, w.abgaben_eur_pro_mwh = 40.0, 10.0
    w.strompreisszenarien.realistisch_eur_pro_mwh = 90.0
    config.waermepumpe.jazl, config.waermepumpe.nennleistung_kw = 4.0, 1000
    config.backup.wirkungsgrad, config.backup.nennleistung_kw = 1.0, 1000
    return config


def test_netzbezug_referenz_rechnet_strom_und_kosten_nach():
    last = pd.Series(100.0, index=pd.date_range("2027-01-01", periods=10, freq="h"))  # 1000 kWh
    ref = berechne_netzbezug_referenz(last, _config())
    assert ref.strombedarf_mwh == pytest.approx(0.25)  # 1000 kWh / JAZ 4
    # Kapital 1500 / 10 = 150; Strom 0,25 MWh * (90 + 40 + 10) = 35; Fix 100 -> 285 / 1 MWh
    assert ref.lcoh_je_strompreisszenario_eur_pro_mwh["realistisch"] == pytest.approx(285.0)
    assert ref.ungedeckt_mwh == 0


def test_backup_uebernimmt_ueber_waermepumpenleistung():
    config = _config()
    config.waermepumpe.nennleistung_kw = 60
    last = pd.Series(100.0, index=pd.date_range("2027-01-01", periods=1, freq="h"))
    ref = berechne_netzbezug_referenz(last, config)
    assert ref.strombedarf_mwh == pytest.approx((60 / 4 + 40 / 1.0) / 1000)


def test_breakeven_macht_beide_varianten_gleich_teuer():
    config = load_config(STEUERUNG)
    ergebnis = berechne_projekt(config)
    v = ergebnis.vergleich
    aktiv = v.szenario_aktiv
    config.wirtschaft.capex_anschluss_eur = v.breakeven_leitungskosten_eur[aktiv]
    neu = berechne_projekt(config)
    assert neu.vergleich.vorteil_direktleitung_eur_pro_mwh[aktiv] == pytest.approx(0.0, abs=1e-6)


def test_vorteil_und_urteil_sind_konsistent():
    v = berechne_projekt(STEUERUNG).vergleich
    assert v.direktleitung_lohnt_sich == (v.vorteil_direktleitung_eur_pro_mwh[v.szenario_aktiv] > 0)
    assert set(v.breakeven_leitungskosten_eur) == {"best_case", "realistisch", "worst_case"}


def test_abgaben_und_netzanschluss_wirken_auf_direktleitungsfall():
    config = load_config(STEUERUNG)
    basis = berechne_projekt(config).lcoh.lcoh_eur_pro_mwh
    config.wirtschaft.capex_netzanschluss_eur = 100_000
    mit_anschluss = berechne_projekt(config).lcoh.lcoh_eur_pro_mwh
    assert mit_anschluss > basis
    af = annuitaetsfaktor(config.wirtschaft.wacc, config.wirtschaft.abschreibungsdauer_jahre)
    menge = berechne_projekt(config).lcoh.jaehrliche_waermemenge_mwh
    assert mit_anschluss - basis == pytest.approx(100_000 * af / menge)


def test_speicher_investition_zaehlt_in_beiden_varianten_gleich():
    config = _config()
    last = pd.Series(100.0, index=pd.date_range("2027-01-01", periods=10, freq="h"))
    ohne = berechne_netzbezug_referenz(last, config).lcoh_je_strompreisszenario_eur_pro_mwh["realistisch"]
    config.wirtschaft.capex_speicher_eur = 500
    mit = berechne_netzbezug_referenz(last, config).lcoh_je_strompreisszenario_eur_pro_mwh["realistisch"]
    assert mit - ohne == pytest.approx(500 / 10)  # 500 EUR / 10 Jahre / 1 MWh


def test_speicherkosten_aendern_den_vorteil_der_direktleitung_nicht():
    config = load_config(STEUERUNG)
    config.wirtschaft.capex_speicher_eur = 0
    a = berechne_projekt(config).vergleich.vorteil_direktleitung_eur_pro_mwh["realistisch"]
    config.wirtschaft.capex_speicher_eur = 300_000
    b = berechne_projekt(config).vergleich.vorteil_direktleitung_eur_pro_mwh["realistisch"]
    assert a == pytest.approx(b)


def test_leistungspreis_auf_jahreshoechstlast_in_variante_a():
    config = _config()
    config.wirtschaft.leistungspreis_eur_pro_kw_a = 20.0
    last = pd.Series([100.0, 400.0, 100.0], index=pd.date_range("2027-01-01", periods=3, freq="h"))
    ref = berechne_netzbezug_referenz(last, config)
    assert ref.netzbezug_spitze_kw == pytest.approx(100.0)  # 400 kWh_th / JAZ 4
    assert ref.leistungspreis_kosten_eur == pytest.approx(2000.0)


def test_leistungspreis_variante_b_nutzt_hoechsten_rueckfall():
    config = load_config(STEUERUNG)
    ohne = berechne_projekt(config)
    config.wirtschaft.leistungspreis_eur_pro_kw_a = 50.0
    mit = berechne_projekt(config)
    spitze = mit.lcoh.netzbezug_spitze_kw
    assert spitze == pytest.approx(mit.bilanz["rueckfall_kwh"].max())
    assert mit.lcoh.leistungspreis_kosten_eur == pytest.approx(spitze * 50.0)
    menge = mit.lcoh.jaehrliche_waermemenge_mwh
    assert mit.lcoh.lcoh_eur_pro_mwh - ohne.lcoh.lcoh_eur_pro_mwh == pytest.approx(spitze * 50.0 / menge)
