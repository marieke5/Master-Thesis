from pathlib import Path

import pytest

from lcoh_tool.config import PpaConfig, load_config
from lcoh_tool.projekt import berechne_projekt

CONFIG = Path(__file__).parents[1] / "config" / "parameter_steuerung.yaml"


def _cfg(**ppa):
    cfg = load_config(CONFIG)
    cfg.wirtschaft.leistungspreis_eur_pro_kw_a = 0.0
    cfg.wirtschaft.netzentgelt_eur_pro_mwh = 40.0
    cfg.wirtschaft.abgaben_eur_pro_mwh = 0.0
    cfg.ppa = PpaConfig(**{"preis_eur_pro_mwh": 50.0, **ppa})
    return cfg


def test_mit_ppa_ist_direktleitung_immer_aktiv_und_preis_fest():
    e = berechne_projekt(_cfg(abgaben_direktleitung_eur_pro_mwh=5.0))
    b = e.bilanz
    assert b["direktleitung_aktiv"].all()
    assert (b["direktstrom_preis_eur_mwh"] == 55.0).all()  # PPA + Abgaben auf Direktstrom


def test_fall2_minus_fall3_ist_netzentgelt_auf_direktstrom_minus_leitung():
    cfg = _cfg()
    cfg.wirtschaft.capex_anschluss_eur = 0.0  # keine Leitungskosten
    e = berechne_projekt(cfg)
    v = e.vergleich
    s = v.szenario_aktiv
    direkt_mwh = e.bilanz["direktanschluss_kwh"].sum() / 1000
    q = e.lcoh.jaehrliche_waermemenge_mwh
    assert v.vorteil_vs_ppa_netz_eur_pro_mwh[s] == pytest.approx(40.0 * direkt_mwh / q)
    assert v.direktleitung_lohnt_sich


def test_breakeven_gegen_ppa_netz_ist_konsistent():
    cfg = _cfg(sleeving_eur_pro_mwh=2.0)
    e = berechne_projekt(cfg)
    s = e.vergleich.szenario_aktiv
    be = e.vergleich.breakeven_vs_ppa_netz_eur[s]
    cfg.wirtschaft.capex_anschluss_eur = be
    e2 = berechne_projekt(cfg)
    assert e2.vergleich.vorteil_vs_ppa_netz_eur_pro_mwh[s] == pytest.approx(0.0, abs=1e-6)


def test_hinweis_bei_zu_niedrigem_ppa_preis():
    e = berechne_projekt(_cfg(preis_eur_pro_mwh=40.0, vergleichswert_eur_pro_mwh=70.0))
    assert any("PPA" in h and "unattraktiv" in h for h in e.kennzahlen.hinweise)
    e = berechne_projekt(_cfg(preis_eur_pro_mwh=80.0, vergleichswert_eur_pro_mwh=70.0))
    assert not any("unattraktiv" in h for h in e.kennzahlen.hinweise)


def test_ohne_ppa_bleibt_alles_wie_vorher():
    cfg = load_config(CONFIG)
    assert cfg.ppa is None
    assert berechne_projekt(cfg).vergleich.lcoh_ppa_netz_eur_pro_mwh is None


def test_ladeleistungsgrenze_begrenzt_beladung_und_netzspitze():
    cfg = _cfg()
    cfg.speicher.kapazitaet_kwh = 20000
    frei = berechne_projekt(cfg)
    cfg.speicher.max_ladeleistung_kw = 300.0
    begrenzt = berechne_projekt(cfg)
    last_max = begrenzt.bilanz["waermelast_kwh"].max()
    assert begrenzt.bilanz["waerme_in_speicher_kwh"].max() <= 300.0 + 1e-6
    assert frei.bilanz["waerme_in_speicher_kwh"].max() > 300.0
    assert begrenzt.vergleich.ppa_netz_spitze_kw <= frei.vergleich.ppa_netz_spitze_kw


def test_verfuegbarkeit_erzeugt_rueckfall():
    cfg = _cfg()
    cfg.windpark.verfuegbarkeit = 0.5
    cfg.windpark.ausfall_dauer_h = 6
    e = berechne_projekt(cfg)
    assert (e.erzeugung_kwh == 0).sum() >= round(0.5 * len(e.erzeugung_kwh))
