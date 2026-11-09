from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

from lcoh_tool.betrieb import berechne_bilanz_preisgesteuert
from lcoh_tool.config import load_config
from lcoh_tool.erzeugungsprofil import load_erzeugungsprofil
from lcoh_tool.marktpreise import load_marktpreise
from lcoh_tool.plots import kennzahlen_text, plot_jahr, plot_woche
from lcoh_tool.projekt import lade_waermelast

ROOT = Path(__file__).parents[1]


def _bilanz():
    cfg = load_config(ROOT / "config" / "parameter_steuerung.yaml")
    wind = load_erzeugungsprofil(ROOT / cfg.windpark.erzeugungsprofil_pfad)
    last = lade_waermelast(cfg)
    preis = load_marktpreise(ROOT / "data" / "marktpreise_beispiel.csv")
    return berechne_bilanz_preisgesteuert(wind, last, preis, cfg)


def test_strom_je_erzeuger_summiert_sich_zu_direkt_und_rueckfall():
    b = _bilanz()
    assert (b["strom_wp_direkt_kwh"] + b["strom_bk_direkt_kwh"]).sum() == pytest.approx(b["direktanschluss_kwh"].sum())
    assert (b["strom_wp_netz_kwh"] + b["strom_bk_netz_kwh"]).sum() == pytest.approx(b["rueckfall_kwh"].sum())
    assert kennzahlen_text(b)["wp_stunden"] >= 0


def test_plots_werden_geschrieben(tmp_path):
    b = _bilanz()
    assert plot_jahr(b, tmp_path / "jahr.png").stat().st_size > 1000
    assert plot_woche(b, tmp_path / "woche.png", 0.0).stat().st_size > 1000


def test_beladung_und_entladung_stimmen_mit_speicherstand(tmp_path):
    from lcoh_tool.plots import plot_speicher

    b = _bilanz()
    assert (b["waerme_in_speicher_kwh"] >= 0).all()
    # Bilanz: Endstand = Start + Beladung - Entladung - Verluste (Verluste >= 0)
    cfg = load_config(ROOT / "config" / "parameter_steuerung.yaml")
    start = cfg.steuerung.speicher_start_anteil * cfg.speicher.kapazitaet_kwh
    ende = b["speicherstand_kwh"].iloc[-1]
    assert ende <= start + b["waerme_in_speicher_kwh"].sum() - b["waerme_aus_speicher_kwh"].sum() + 1e-6
    assert plot_speicher(b, tmp_path / "speicher.png").stat().st_size > 1000
