from pathlib import Path

import pandas as pd
import pytest

from lcoh_tool.betrieb import berechne_bilanz_preisgesteuert
from lcoh_tool.config import SteuerungConfig, load_config
from lcoh_tool.marktpreise import load_marktpreise
from lcoh_tool.projekt import berechne_projekt

ROOT = Path(__file__).parents[1]
STEUERUNG_CONFIG = ROOT / "config" / "parameter_steuerung.yaml"


def _config(**steuerung):
    config = load_config(STEUERUNG_CONFIG)
    config.waermepumpe.jazl = 4.0
    config.waermepumpe.nennleistung_kw = 1000
    config.backup.wirkungsgrad = 1.0
    config.backup.nennleistung_kw = 1000
    config.speicher.kapazitaet_kwh = 1000
    config.speicher.verlust_pro_stunde = 0.0
    werte = dict(
        preisschwelle_eur_pro_mwh=0.0,
        speicher_untergrenze_anteil=0.1,
        speicher_start_anteil=0.5,
    )
    werte.update(steuerung)
    config.steuerung = SteuerungConfig(**werte)
    return config


def _reihen(wind, last, preis):
    idx = pd.date_range("2027-01-01", periods=len(last), freq="h")
    return (
        pd.Series(wind, index=idx, dtype=float),
        pd.Series(last, index=idx, dtype=float),
        pd.Series(preis, index=idx, dtype=float),
    )


def test_hoher_preis_speicher_deckt_bedarf_direktleitung_aus():
    wind, last, preis = _reihen([5000], [100], [80])
    b = berechne_bilanz_preisgesteuert(wind, last, preis, _config())
    assert not b["direktleitung_aktiv"].iloc[0]
    assert b["direktanschluss_kwh"].iloc[0] == 0
    assert b["waerme_aus_speicher_kwh"].iloc[0] == pytest.approx(100)
    assert b["speicherstand_kwh"].iloc[0] == pytest.approx(400)  # 500 - 100
    assert b["rueckfall_kwh"].iloc[0] == 0


def test_negativer_preis_deckt_bedarf_und_laedt_speicher():
    wind, last, preis = _reihen([5000], [100], [-20])
    b = berechne_bilanz_preisgesteuert(wind, last, preis, _config())
    assert b["direktleitung_aktiv"].iloc[0]
    assert not b["notbetrieb"].iloc[0]
    # WP-Leistung 1000 kW_th begrenzt: 1000 Waerme, 100 Bedarf, 900 in den Speicher
    # (Speicher von 500 auf Kapazitaet 1000 -> nur 500 passen)
    assert b["speicherstand_kwh"].iloc[0] == pytest.approx(1000)
    assert b["waerme_direkt_kwh"].iloc[0] == pytest.approx(600)
    assert b["direktanschluss_kwh"].iloc[0] == pytest.approx(150)  # 600 / JAZ 4
    # Direktstrom bei negativem Preis = Erloes
    assert b["direktstrom_kosten_eur"].iloc[0] == pytest.approx(0.15 * -20)


def test_notbetrieb_bei_fast_leerem_speicher_trotz_hohem_preis():
    cfg = _config(speicher_start_anteil=0.05)
    wind, last, preis = _reihen([5000], [100], [150])
    b = berechne_bilanz_preisgesteuert(wind, last, preis, cfg)
    assert b["notbetrieb"].iloc[0]
    assert b["direktleitung_aktiv"].iloc[0]
    # nur der aktuelle Bedarf, keine Speicherladung
    assert b["waerme_direkt_kwh"].iloc[0] == pytest.approx(100)
    assert b["speicherstand_kwh"].iloc[0] == pytest.approx(50)
    assert b["direktstrom_kosten_eur"].iloc[0] == pytest.approx(25 / 1000 * 150)


def test_kein_notbetrieb_ohne_waermebedarf():
    cfg = _config(speicher_start_anteil=0.0)
    wind, last, preis = _reihen([5000], [0], [150])
    b = berechne_bilanz_preisgesteuert(wind, last, preis, cfg)
    assert not b["direktleitung_aktiv"].iloc[0]


def test_windmangel_im_notbetrieb_faellt_auf_netzbezug_zurueck():
    cfg = _config(speicher_start_anteil=0.0)
    wind, last, preis = _reihen([0], [100], [150])
    b = berechne_bilanz_preisgesteuert(wind, last, preis, cfg)
    assert b["direktanschluss_kwh"].iloc[0] == 0
    assert b["rueckfall_kwh"].iloc[0] == pytest.approx(25)  # 100 kWh_th / JAZ 4
    assert b["deckungsluecke_kwh"].iloc[0] == 0


def test_leistungsgrenzen_erzeugen_deckungsluecke():
    cfg = _config(speicher_start_anteil=0.0)
    cfg.waermepumpe.nennleistung_kw = 10
    cfg.backup.nennleistung_kw = 10
    wind, last, preis = _reihen([0], [100], [150])
    b = berechne_bilanz_preisgesteuert(wind, last, preis, cfg)
    assert b["deckungsluecke_kwh"].iloc[0] == pytest.approx(80)


def test_fehlende_marktpreise_werfen_fehler():
    wind, last, preis = _reihen([1, 1], [1, 1], [1, 1])
    with pytest.raises(ValueError, match="Marktpreise fehlen"):
        berechne_bilanz_preisgesteuert(wind, last, preis.iloc[:1], _config())


def test_feste_bepreisung_braucht_preis():
    wind, last, preis = _reihen([1], [1], [1])
    with pytest.raises(ValueError, match="direktstrompreis"):
        berechne_bilanz_preisgesteuert(
            wind, last, preis, _config(direktstrom_bepreisung="fest")
        )


def test_feste_bepreisung_ignoriert_marktpreis_fuer_kosten():
    wind, last, preis = _reihen([5000], [100], [-20])
    cfg = _config(direktstrom_bepreisung="fest", direktstrompreis_eur_pro_mwh=50.0)
    b = berechne_bilanz_preisgesteuert(wind, last, preis, cfg)
    assert b["direktleitung_aktiv"].iloc[0]  # Steuerung weiter nach Marktpreis
    assert b["direktstrom_kosten_eur"].iloc[0] == pytest.approx(0.15 * 50)


def test_energieerhalt_waerme():
    wind, last, preis = _reihen([800, 0, 3000, 0], [200, 300, 100, 400], [-5, 90, 10, 200])
    b = berechne_bilanz_preisgesteuert(wind, last, preis, _config(preisschwelle_eur_pro_mwh=0))
    gedeckt = (
        b["waerme_direkt_kwh"]
        - (b["speicherstand_kwh"].diff().fillna(b["speicherstand_kwh"].iloc[0] - 500)
           + b["waerme_aus_speicher_kwh"])
    )
    # Waerme aus Erzeugung = Bedarf-Deckung direkt + Speicherladung
    assert (gedeckt >= -1e-6).all()


def test_marktpreise_csv_laden():
    preise = load_marktpreise(ROOT / "data" / "marktpreise_beispiel.csv")
    assert len(preise) == 48
    assert (preise < 0).any()


def test_marktpreise_csv_spalten_pruefen(tmp_path):
    datei = tmp_path / "preise.csv"
    datei.write_text("zeit,preis\n2027-01-01 00:00,1\n")
    with pytest.raises(ValueError, match="fehlen Spalten"):
        load_marktpreise(datei)


def test_berechne_projekt_mit_steuerung_und_kennzahlen():
    ergebnis = berechne_projekt(STEUERUNG_CONFIG)
    k = ergebnis.kennzahlen
    assert k.direktleitung_stunden > 0
    assert k.stunden_preis_negativ > 0
    assert ergebnis.lcoh.direktstrom_kosten_eur == pytest.approx(k.direktstrom_kosten_eur)
    assert ergebnis.lcoh.lcoh_eur_pro_mwh > 0


def test_ohne_steuerung_bleibt_direktstrom_kostenlos():
    ergebnis = berechne_projekt(ROOT / "config" / "parameter.yaml")
    assert ergebnis.lcoh.direktstrom_kosten_eur == 0.0
    assert ergebnis.kennzahlen.direktleitung_stunden == 0


def test_untergrenze_in_stunden_der_spitzenlast():
    # Spitzenlast 100 kW, 2 h -> Untergrenze 200 kWh; Start 150 kWh liegt darunter -> Notbetrieb
    cfg = _config(speicher_untergrenze_stunden=2.0, speicher_start_anteil=0.15)
    wind, last, preis = _reihen([5000], [100], [150])
    b = berechne_bilanz_preisgesteuert(wind, last, preis, cfg)
    assert b["notbetrieb"].iloc[0]
    # Anteil 10 % haette bei 1000 kWh nur 100 kWh Untergrenze -> kein Notbetrieb
    cfg2 = _config(speicher_start_anteil=0.15)
    assert not berechne_bilanz_preisgesteuert(wind, last, preis, cfg2)["notbetrieb"].iloc[0]


def test_ohne_netzentgeltbefreiung_zahlt_direktstrom_netzentgelt():
    wind, last, preis = _reihen([5000], [100], [-20])
    cfg = _config()
    cfg.wirtschaft.netzentgelt_eur_pro_mwh = 40.0
    cfg.regulatorik.netzentgeltbefreiung_direktanschluss = True
    frei = berechne_bilanz_preisgesteuert(wind, last, preis, cfg)["direktstrom_kosten_eur"].iloc[0]
    cfg.regulatorik.netzentgeltbefreiung_direktanschluss = False
    mit = berechne_bilanz_preisgesteuert(wind, last, preis, cfg)["direktstrom_kosten_eur"].iloc[0]
    assert mit - frei == pytest.approx(0.15 * 40.0)  # 150 kWh Direktstrom * 40 EUR/MWh


def test_ohne_steuerung_und_ohne_befreiung_kostet_direktstrom_netzentgelt():
    config = load_config(ROOT / "config" / "parameter.yaml")
    frei = berechne_projekt(config).lcoh
    assert frei.direktstrom_kosten_eur == 0.0
    config.regulatorik.netzentgeltbefreiung_direktanschluss = False
    mit = berechne_projekt(config).lcoh
    assert mit.direktstrom_kosten_eur > 0
    assert mit.lcoh_eur_pro_mwh > frei.lcoh_eur_pro_mwh
