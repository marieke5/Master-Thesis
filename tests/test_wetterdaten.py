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
