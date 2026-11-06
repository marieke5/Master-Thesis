import pandas as pd
import pytest

from lcoh_tool.wetterdaten import _open_meteo_antwort_zu_df, lade_wetter_csv


def test_open_meteo_antwort_wird_in_normiertes_format_uebersetzt():
    antwort = {
        "hourly": {
            "time": ["2023-01-01T00:00", "2023-01-01T01:00"],
            "wind_speed_10m": [4.0, 5.0],
            "wind_speed_100m": [7.0, 8.0],
            "temperature_2m": [3.5, 3.0],
            "surface_pressure": [1010.0, 1011.0],
        }
    }
    df = _open_meteo_antwort_zu_df(antwort)
    assert list(df.columns) == ["wind_10m_ms", "wind_100m_ms", "temperatur_c", "druck_hpa"]
    assert df.index[0] == pd.Timestamp("2023-01-01 00:00")
    assert df["wind_100m_ms"].iloc[1] == pytest.approx(8.0)


def test_open_meteo_fehlerantwort_wirft_fehler():
    with pytest.raises(RuntimeError, match="Limit"):
        _open_meteo_antwort_zu_df({"error": True, "reason": "Limit exceeded"})


def test_lade_wetter_csv_benennt_windspalte_nach_messhoehe(tmp_path):
    pfad = tmp_path / "wetter.csv"
    pfad.write_text(
        "zeitstempel,windgeschwindigkeit_ms,temperatur_c,druck_hpa\n"
        "2023-01-01 00:00:00,6.0,5.0,1000\n"
        "2023-01-01 01:00:00,7.0,5.5,1001\n"
    )
    df = lade_wetter_csv(pfad, wind_messhoehe_m=120)
    assert "wind_120m_ms" in df.columns
    assert df["temperatur_c"].iloc[1] == pytest.approx(5.5)


def test_lade_wetter_csv_fehlende_spalten(tmp_path):
    pfad = tmp_path / "wetter.csv"
    pfad.write_text("zeitstempel,windgeschwindigkeit_ms\n2023-01-01 00:00:00,6.0\n")
    with pytest.raises(ValueError, match="fehlen Spalten"):
        lade_wetter_csv(pfad)


def test_open_meteo_gibt_lizenzwarnung(monkeypatch):
    import lcoh_tool.wetterdaten as w
    from lcoh_tool.config import WindpowerlibConfig

    monkeypatch.setattr(
        w, "lade_open_meteo", lambda *args: pd.DataFrame({"wind_100m_ms": [5.0]})
    )
    cfg = WindpowerlibConfig(
        breitengrad=53.6, laengengrad=10.6, wetterquelle="open_meteo", wetter_cache_ordner=None
    )  # rauigkeitsquelle auto -> konstant, also kein CDS-Abruf
    with pytest.warns(UserWarning, match="nicht-kommerzielle"):
        w.lade_wetterdaten(cfg)


def test_standard_wetterquelle_ist_era5():
    from lcoh_tool.config import WindpowerlibConfig

    assert WindpowerlibConfig(breitengrad=53.6, laengengrad=10.6).wetterquelle == "era5"


ERA5_BEISPIEL_CSV = (
    "valid_time,u100,v100,u10,v10,t2m,sp,latitude,longitude\n"
    "2023-01-01 00:00:00,11.190704,8.6180725,6.7195435,5.484909,288.70737,100161.13,53.5,10.5\n"
    "2023-01-01 01:00:00,10.829803,8.948929,6.4891205,5.629593,288.91345,100170.22,53.5,10.5\n"
)


def test_era5_csv_wird_in_normiertes_format_uebersetzt(tmp_path):
    from lcoh_tool.wetterdaten import _era5_csv_zu_df

    pfad = tmp_path / "era5.csv"
    pfad.write_text(ERA5_BEISPIEL_CSV)
    df = _era5_csv_zu_df(pfad)
    assert list(df.columns) == ["wind_10m_ms", "wind_100m_ms", "temperatur_c", "druck_hpa"]
    assert df.index[0] == pd.Timestamp("2023-01-01 00:00")
    assert df["wind_100m_ms"].iloc[0] == pytest.approx((11.190704**2 + 8.6180725**2) ** 0.5)
    assert df["temperatur_c"].iloc[0] == pytest.approx(288.70737 - 273.15)
    assert df["druck_hpa"].iloc[0] == pytest.approx(1001.6113)


def test_era5_antwort_als_zip_wird_entpackt(tmp_path):
    import zipfile

    from lcoh_tool.wetterdaten import _era5_antwort_zu_df

    pfad = tmp_path / "antwort"
    with zipfile.ZipFile(pfad, "w") as archiv:
        archiv.writestr("reanalysis-era5-single-levels-timeseries-abc.csv", ERA5_BEISPIEL_CSV)
    df = _era5_antwort_zu_df(pfad)
    assert len(df) == 2


def test_era5_csv_mit_fehlenden_spalten_wirft_fehler(tmp_path):
    from lcoh_tool.wetterdaten import _era5_csv_zu_df

    pfad = tmp_path / "era5.csv"
    pfad.write_text("valid_time,u100\n2023-01-01 00:00:00,1.0\n")
    with pytest.raises(ValueError, match="fehlen Spalten"):
        _era5_csv_zu_df(pfad)


# --- Rauigkeit aus ERA5 -------------------------------------------------------


def _cfg_rauigkeit(**kwargs):
    from lcoh_tool.config import WindpowerlibConfig

    return WindpowerlibConfig(breitengrad=53.6, laengengrad=10.6, jahr=2023, **kwargs)


def test_rauigkeitsquelle_auto_folgt_der_wetterquelle():
    from lcoh_tool.wetterdaten import rauigkeitsquelle

    assert rauigkeitsquelle(_cfg_rauigkeit()) == "era5"
    assert rauigkeitsquelle(_cfg_rauigkeit(wetterquelle="open_meteo")) == "konstant"
    assert rauigkeitsquelle(_cfg_rauigkeit(rauigkeitsquelle="konstant")) == "konstant"
    assert rauigkeitsquelle(_cfg_rauigkeit(wetterquelle="csv", rauigkeitsquelle="era5")) == "era5"


def test_monatswerte_werden_den_stunden_zugeordnet():
    from lcoh_tool.wetterdaten import monatswerte_auf_stunden

    monate = pd.Series({m: 0.1 * m for m in range(1, 13)})
    index = pd.DatetimeIndex(["2023-01-15 03:00", "2023-02-01 00:00", "2023-12-31 23:00"])
    z0 = monatswerte_auf_stunden(monate, index, rueckfallwert=0.15)
    assert z0 == pytest.approx([0.1, 0.2, 1.2])


def test_ungueltige_monatswerte_werden_mit_rueckfallwert_gefuellt():
    import numpy as np

    from lcoh_tool.wetterdaten import monatswerte_auf_stunden

    monate = pd.Series({m: 0.3 for m in range(1, 13)})
    monate[2] = np.nan
    monate[3] = 0.0
    index = pd.DatetimeIndex(["2023-01-01", "2023-02-01", "2023-03-01"])
    with pytest.warns(UserWarning, match="Rauigkeit"):
        z0 = monatswerte_auf_stunden(monate, index, rueckfallwert=0.15)
    assert z0 == pytest.approx([0.3, 0.15, 0.15])


def test_era5_rauigkeit_netcdf_naechster_gitterpunkt(tmp_path):
    xr = pytest.importorskip("xarray")
    import numpy as np

    zeiten = pd.date_range("2023-01-01", periods=12, freq="MS")
    lat = [53.75, 53.5]
    lon = [10.5, 10.75]
    werte = np.zeros((12, 2, 2))
    werte[:, 1, 0] = np.linspace(0.4, 0.6, 12)  # Punkt 53.5 / 10.5 ist am naechsten
    werte[:, 0, 1] = 9.9
    ds = xr.Dataset(
        {"fsr": (("valid_time", "latitude", "longitude"), werte)},
        coords={"valid_time": zeiten, "latitude": lat, "longitude": lon},
    )
    pfad = tmp_path / "fsr.nc"
    ds.to_netcdf(pfad)

    from lcoh_tool.wetterdaten import _era5_rauigkeit_zu_monatswerten

    monate = _era5_rauigkeit_zu_monatswerten(pfad, 53.55, 10.55)
    assert list(monate.index) == list(range(1, 13))
    assert monate[1] == pytest.approx(0.4)
    assert monate[12] == pytest.approx(0.6)


def test_lade_wetterdaten_ergaenzt_rauigkeit_und_cache(monkeypatch, tmp_path):
    import lcoh_tool.wetterdaten as w

    index = pd.date_range("2023-01-01", periods=3, freq="h", name="zeitstempel")
    wetter = pd.DataFrame(
        {"wind_100m_ms": [5.0, 6.0, 7.0], "temperatur_c": 1.0, "druck_hpa": 1000.0},
        index=index,
    )
    aufrufe = []
    monkeypatch.setattr(w, "lade_era5", lambda *a: wetter)

    def fake_rauigkeit(*a):
        aufrufe.append(a)
        return pd.Series({m: 0.42 for m in range(1, 13)})

    monkeypatch.setattr(w, "lade_era5_rauigkeit", fake_rauigkeit)
    cfg = _cfg_rauigkeit(wetter_cache_ordner=str(tmp_path))

    df = w.lade_wetterdaten(cfg)
    assert df["rauigkeit_m"].tolist() == pytest.approx([0.42] * 3)
    # zweiter Lauf kommt aus dem Cache, ohne neuen Abruf
    df2 = w.lade_wetterdaten(cfg)
    assert "rauigkeit_m" in df2.columns
    assert len(aufrufe) == 1


def test_alter_cache_ohne_rauigkeit_wird_ergaenzt(monkeypatch, tmp_path):
    import lcoh_tool.wetterdaten as w

    cfg = _cfg_rauigkeit(wetter_cache_ordner=str(tmp_path))
    cache = w._cache_datei(cfg)
    cache.write_text(
        "zeitstempel,wind_100m_ms,temperatur_c,druck_hpa\n2023-01-01 00:00:00,5.0,1.0,1000\n"
    )
    monkeypatch.setattr(w, "lade_era5_rauigkeit", lambda *a: pd.Series({m: 0.3 for m in range(1, 13)}))
    df = w.lade_wetterdaten(cfg)
    assert df["rauigkeit_m"].iloc[0] == pytest.approx(0.3)
    assert "rauigkeit_m" in pd.read_csv(cache).columns
