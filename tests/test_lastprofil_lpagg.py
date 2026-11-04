import pytest

from lcoh_tool.config import GebaeudetypConfig, LpaggConfig
from lcoh_tool.lastprofil_lpagg import baue_lpagg_cfg, erzeuge_waermelast_lpagg


def test_gewerbe_mit_calculate_wirft_fehler():
    cfg = LpaggConfig(gebaeude={"Buero": GebaeudetypConfig(house_type="GHD/G1", q_heiz_a_kwh=50000)})
    with pytest.raises(ValueError, match="Gewerbetypen"):
        baue_lpagg_cfg(cfg, "wetter.dat")


def test_baue_lpagg_cfg_uebersetzt_gebaeude():
    cfg = LpaggConfig(
        gebaeude={"EFH": GebaeudetypConfig(house_type="EFH", q_heiz_a_kwh=6000, anzahl=25, n_pers=3, n_we=1)},
        try_region=4,
        jahr=2027,
    )
    lpagg_cfg = baue_lpagg_cfg(cfg, "wetter.dat")
    haus = lpagg_cfg["houses"]["EFH"]
    assert haus["Q_Heiz_a"] == 6000
    assert haus["copies"] == 25
    assert lpagg_cfg["settings"]["start"] == [2027, 1, 1, 0, 0, 0]


def test_erzeuge_waermelast_lpagg_liefert_jahresprofil():
    pytest.importorskip("lpagg")
    cfg = LpaggConfig(
        gebaeude={"EFH": GebaeudetypConfig(house_type="EFH", q_heiz_a_kwh=6000, anzahl=3, n_pers=3, n_we=1)},
        jahr=2027,
    )
    profil = erzeuge_waermelast_lpagg(cfg)
    assert len(profil) == 8760
    assert str(profil.index[0]) == "2027-01-01 00:00:00"
    assert (profil >= 0).all()
    # Heizwaerme (3 x 6000 kWh) plus Trinkwarmwasser -> mindestens Heizenergie
    assert profil.sum() >= 3 * 6000 * 0.95


def test_q_heiz_fehlt_wird_gleichmaessig_aus_jahreswert_abgeleitet():
    cfg = LpaggConfig(
        gebaeude={
            "EFH": GebaeudetypConfig(house_type="EFH", anzahl=30, n_pers=3, n_we=1),
            "MFH": GebaeudetypConfig(house_type="MFH", anzahl=10, n_pers=20, n_we=8),
        }
    )
    lpagg_cfg = baue_lpagg_cfg(cfg, "wetter.dat", jahreswaermebedarf_kwh=400_000)
    assert lpagg_cfg["houses"]["EFH"]["Q_Heiz_a"] == pytest.approx(10_000)
    assert lpagg_cfg["houses"]["MFH"]["Q_Heiz_a"] == pytest.approx(10_000)


def test_q_heiz_fehlt_ohne_jahreswert_wirft_fehler():
    cfg = LpaggConfig(gebaeude={"EFH": GebaeudetypConfig(house_type="EFH", anzahl=3)})
    with pytest.raises(ValueError, match="q_heiz_a_kwh fehlt"):
        baue_lpagg_cfg(cfg, "wetter.dat")


def _wetter(jahr=2023, schaltjahr=False):
    import numpy as np
    import pandas as pd

    idx = pd.date_range(f"{jahr}-01-01", f"{jahr + 1}-01-01", freq="h", inclusive="left")
    t = 8 - 12 * np.cos(2 * np.pi * (idx.day_of_year - 20) / 365) + 3 * np.sin(2 * np.pi * idx.hour / 24)
    return pd.DataFrame(
        {"wind_10m_ms": 5.0, "temperatur_c": t, "druck_hpa": 1010.0},
        index=pd.DatetimeIndex(idx, name="zeitstempel"),
    )


def test_era5_wird_als_igs_datei_geschrieben(tmp_path):
    from lcoh_tool.lastprofil_lpagg import schreibe_era5_als_igs

    pfad = tmp_path / "w.dat"
    schreibe_era5_als_igs(_wetter(2024), str(pfad))  # Schaltjahr -> 29.2. entfaellt
    zeilen = pfad.read_text().strip().splitlines()
    assert len(zeilen) == 8760
    assert zeilen[0].split()[0] == "1" and zeilen[-1].split()[0] == "8760"
    assert len(zeilen[0].split()) == 9


def test_lpagg_mit_era5_und_skalierung_auf_jahreswert(monkeypatch):
    pytest.importorskip("lpagg")
    import lcoh_tool.wetterdaten as wd

    monkeypatch.setattr(wd, "lade_wetterdaten", lambda cfg: _wetter(cfg.jahr))
    cfg = LpaggConfig(
        gebaeude={"EFH": GebaeudetypConfig(house_type="EFH", anzahl=3, n_pers=3, n_we=1)},
        wetterquelle="era5",
        jahr=2027,
    )
    profil = erzeuge_waermelast_lpagg(cfg, jahreswaermebedarf_mwh=50, wetter_standort=(53.5, 10.6, 2023))
    assert len(profil) == 8760
    assert profil.sum() == pytest.approx(50_000)
    assert profil.index[0].year == 2027


def test_era5_ohne_standort_wirft_fehler():
    pytest.importorskip("lpagg")
    cfg = LpaggConfig(
        gebaeude={"EFH": GebaeudetypConfig(house_type="EFH", q_heiz_a_kwh=6000, anzahl=1, n_pers=3, n_we=1)},
        wetterquelle="era5",
    )
    with pytest.raises(ValueError, match="breitengrad"):
        erzeuge_waermelast_lpagg(cfg)
