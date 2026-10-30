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
    )
    with pytest.warns(UserWarning, match="nicht-kommerzielle"):
        w.lade_wetterdaten(cfg)


def test_standard_wetterquelle_ist_era5():
    from lcoh_tool.config import WindpowerlibConfig

    assert WindpowerlibConfig(breitengrad=53.6, laengengrad=10.6).wetterquelle == "era5"


def test_era5_dataset_wird_in_normiertes_format_uebersetzt():
    xr = pytest.importorskip("xarray")
    import numpy as np

    zeit = pd.date_range("2023-01-01", periods=3, freq="h")
    ds = xr.Dataset(
        {
            "u10": ("valid_time", np.array([3.0, 0.0, 6.0])),
            "v10": ("valid_time", np.array([4.0, 0.0, 8.0])),
            "u100": ("valid_time", np.array([6.0, 0.0, 12.0])),
            "v100": ("valid_time", np.array([8.0, 0.0, 16.0])),
            "t2m": ("valid_time", np.array([283.15, 273.15, 293.15])),
            "sp": ("valid_time", np.array([101300.0, 100000.0, 102000.0])),
        },
        coords={"valid_time": zeit, "latitude": 53.6, "longitude": 10.6},
    )
    from lcoh_tool.wetterdaten import _era5_dataset_zu_df

    df = _era5_dataset_zu_df(ds)
    assert df["wind_10m_ms"].tolist() == pytest.approx([5.0, 0.0, 10.0])
    assert df["wind_100m_ms"].tolist() == pytest.approx([10.0, 0.0, 20.0])
    assert df["temperatur_c"].tolist() == pytest.approx([10.0, 0.0, 20.0])
    assert df["druck_hpa"].iloc[0] == pytest.approx(1013.0)


def test_era5_dataset_ohne_bekannte_variablen_wirft_fehler():
    xr = pytest.importorskip("xarray")
    import numpy as np
    from lcoh_tool.wetterdaten import _era5_dataset_zu_df

    ds = xr.Dataset({"x": ("valid_time", np.zeros(2))}, coords={"valid_time": pd.date_range("2023-01-01", periods=2, freq="h")})
    with pytest.raises(KeyError):
        _era5_dataset_zu_df(ds)
