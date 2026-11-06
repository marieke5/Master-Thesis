"""Wetterdaten fuer die Windertragsabschaetzung (siehe ``windpark.py``).

Alle Quellen liefern dasselbe flache Format (stuendlich, UTC, Index
``zeitstempel``) mit den Spalten:

- ``wind_<h>m_ms``: Windgeschwindigkeit in m/s auf <h> Meter Hoehe
  (z. B. ``wind_10m_ms``, ``wind_100m_ms``)
- ``temperatur_c``: Lufttemperatur in 2 m Hoehe in Grad Celsius
- ``druck_hpa``: Luftdruck an der Oberflaeche in hPa
- ``rauigkeit_m`` (optional): Rauigkeitslaenge z0 in m, nur bei
  ``rauigkeitsquelle`` "era5" (ERA5 ``forecast_surface_roughness``)

Rauigkeit aus ERA5: Der Punkt-Zeitreihen-Datensatz
(``reanalysis-era5-single-levels-timeseries``) enthaelt keine Rauigkeit. Sie wird
deshalb separat aus ``reanalysis-era5-single-levels-monthly-means`` geholt
(12 Monatsmittel des Wetterjahres, naechster Gitterpunkt, ca. 0,25 Grad bzw.
~30 km Zellmittel) und jeder Stunde des Monats zugeordnet. Das Zellmittel bildet
keine lokalen Hindernisse (Wald, Knicks) direkt an der Anlage ab.

Quellen:
- ``open_meteo``: Historical-Weather-API von Open-Meteo (ERA5-basiert), ohne
  Account per HTTP. LIZENZ: Die kostenlose API ist laut Anbieter nur fuer
  nicht-kommerzielle Zwecke gedacht. Fuer Projekte mit kommerziellem Bezug
  (z. B. echte Green-Wind-Projekte) ``era5`` oder eine eigene Wetter-CSV
  nutzen bzw. einen kostenpflichtigen Open-Meteo-Zugang erwerben.
- ``era5``: (Standard) direkter Abruf aus dem Copernicus Climate Data Store (CDS) per
  ``cdsapi``. Braucht einen CDS-Account mit API-Key (``~/.cdsapirc``), akzeptierte
  Lizenz und das Paket ``cdsapi`` (Extra ``era5``). Anfrage und Antwortformat
  (ZIP mit CSV) wurden an einem echten Abruf geprueft.
- ``csv``: eigene Wetterdatei (siehe ``lade_wetter_csv``).

Heruntergeladene Daten werden optional als CSV zwischengespeichert, damit
Rechnungen reproduzierbar sind und nicht bei jedem Lauf neu geladen wird.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from lcoh_tool.config import WindpowerlibConfig

OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
RAUIGKEIT_SPALTE = "rauigkeit_m"


def lade_wetterdaten(cfg: WindpowerlibConfig) -> pd.DataFrame:
    """Liefert die Wetterdaten fuer ``cfg`` aus der gewaehlten Quelle."""
    if cfg.wetterquelle == "csv":
        if not cfg.wetter_pfad:
            raise ValueError("wetterquelle 'csv' braucht wetter_pfad in der Config.")
        wetter = lade_wetter_csv(cfg.wetter_pfad, cfg.wind_messhoehe_m)
        if rauigkeitsquelle(cfg) == "era5":
            wetter = _ergaenze_rauigkeit(wetter, cfg)
        return wetter

    cache_datei = _cache_datei(cfg)
    if cache_datei is not None and cache_datei.exists():
        wetter = _lese_normiert(cache_datei)
        # Aeltere Caches ohne Rauigkeit: einmal nachladen und Cache ergaenzen.
        if rauigkeitsquelle(cfg) == "era5" and RAUIGKEIT_SPALTE not in wetter.columns:
            wetter = _ergaenze_rauigkeit(wetter, cfg)
            wetter.to_csv(cache_datei, index_label="zeitstempel")
        return wetter

    wetter = _lade_wetter_von_quelle(cfg)
    if rauigkeitsquelle(cfg) == "era5":
        wetter = _ergaenze_rauigkeit(wetter, cfg)

    if cache_datei is not None:
        cache_datei.parent.mkdir(parents=True, exist_ok=True)
        wetter.to_csv(cache_datei, index_label="zeitstempel")
    return wetter


def rauigkeitsquelle(cfg: WindpowerlibConfig) -> str:
    """Loest ``rauigkeitsquelle: auto`` auf: ERA5-z0 nur bei ERA5-Wetter."""
    if cfg.rauigkeitsquelle == "auto":
        return "era5" if cfg.wetterquelle == "era5" else "konstant"
    return cfg.rauigkeitsquelle


def _ergaenze_rauigkeit(wetter: pd.DataFrame, cfg: WindpowerlibConfig) -> pd.DataFrame:
    """Haengt die ERA5-Rauigkeitslaenge (Monatsmittel) als Stundenspalte an."""
    monatswerte = lade_era5_rauigkeit(cfg.breitengrad, cfg.laengengrad, cfg.jahr)
    wetter = wetter.copy()
    wetter[RAUIGKEIT_SPALTE] = monatswerte_auf_stunden(
        monatswerte, wetter.index, rueckfallwert=cfg.rauigkeitslaenge_m
    )
    return wetter


def monatswerte_auf_stunden(
    monatswerte: pd.Series, index: pd.DatetimeIndex, rueckfallwert: float
) -> np.ndarray:
    """Ordnet jeder Stunde den z0-Wert ihres Monats zu.

    Fehlende oder nicht plausible Monatswerte (NaN, <= 0) werden durch
    ``rueckfallwert`` ersetzt, mit Warnung.
    """
    werte = pd.Series(monatswerte, dtype=float)
    ungueltig = werte.isna() | (werte <= 0)
    if ungueltig.any() or len(werte) < 12:
        warnings.warn(
            "ERA5-Rauigkeit unvollstaendig oder nicht plausibel; fehlende Monate "
            f"werden mit {rueckfallwert} m gefuellt.",
            UserWarning,
            stacklevel=2,
        )
    werte = werte.where(~ungueltig)
    z0 = pd.Series(pd.DatetimeIndex(index).month, index=index).map(werte)
    return z0.fillna(rueckfallwert).to_numpy(dtype=float)


def _lade_wetter_von_quelle(cfg: WindpowerlibConfig) -> pd.DataFrame:
    if cfg.wetterquelle == "open_meteo":
        warnings.warn(
            "Open-Meteo (kostenlose API) ist nur fuer nicht-kommerzielle Nutzung "
            "gedacht. Fuer kommerzielle Projekte wetterquelle 'era5' oder 'csv' "
            "verwenden.",
            UserWarning,
            stacklevel=2,
        )
        wetter = lade_open_meteo(cfg.breitengrad, cfg.laengengrad, cfg.jahr)
    elif cfg.wetterquelle == "era5":
        wetter = lade_era5(cfg.breitengrad, cfg.laengengrad, cfg.jahr)
    else:
        raise ValueError(f"Unbekannte Wetterquelle: {cfg.wetterquelle}")
    return wetter


def lade_wetter_csv(pfad: str | Path | Any, wind_messhoehe_m: float = 100.0) -> pd.DataFrame:
    """Liest eine eigene Wetter-CSV.

    Erwartete Spalten: ``zeitstempel``, ``windgeschwindigkeit_ms`` (auf
    ``wind_messhoehe_m``), ``temperatur_c`` und ``druck_hpa``.
    """
    df = pd.read_csv(pfad)
    benoetigt = {"zeitstempel", "windgeschwindigkeit_ms", "temperatur_c", "druck_hpa"}
    fehlende = benoetigt - set(df.columns)
    if fehlende:
        raise ValueError(f"Wetter-CSV fehlen Spalten: {sorted(fehlende)}")
    df["zeitstempel"] = pd.to_datetime(df["zeitstempel"])
    df = df.set_index("zeitstempel").sort_index()
    spalte = f"wind_{int(wind_messhoehe_m)}m_ms"
    return pd.DataFrame(
        {
            spalte: df["windgeschwindigkeit_ms"],
            "temperatur_c": df["temperatur_c"],
            "druck_hpa": df["druck_hpa"],
        }
    )


def lade_open_meteo(breitengrad: float, laengengrad: float, jahr: int) -> pd.DataFrame:
    """Holt ein Jahr stuendliche Wetterdaten von Open-Meteo (ERA5-basiert)."""
    parameter = {
        "latitude": breitengrad,
        "longitude": laengengrad,
        "start_date": f"{jahr}-01-01",
        "end_date": f"{jahr}-12-31",
        "hourly": "wind_speed_10m,wind_speed_100m,temperature_2m,surface_pressure",
        "wind_speed_unit": "ms",
        "timezone": "GMT",
    }
    url = f"{OPEN_METEO_URL}?{urllib.parse.urlencode(parameter)}"
    with urllib.request.urlopen(url, timeout=60) as antwort:  # noqa: S310
        daten = json.load(antwort)
    return _open_meteo_antwort_zu_df(daten)


def _open_meteo_antwort_zu_df(daten: dict) -> pd.DataFrame:
    if daten.get("error"):
        raise RuntimeError(f"Open-Meteo-Fehler: {daten.get('reason', daten)}")
    stuendlich = daten["hourly"]
    index = pd.to_datetime(stuendlich["time"])
    return pd.DataFrame(
        {
            "wind_10m_ms": stuendlich["wind_speed_10m"],
            "wind_100m_ms": stuendlich["wind_speed_100m"],
            "temperatur_c": stuendlich["temperature_2m"],
            "druck_hpa": stuendlich["surface_pressure"],
        },
        index=pd.DatetimeIndex(index, name="zeitstempel"),
    )


def lade_era5(breitengrad: float, laengengrad: float, jahr: int) -> pd.DataFrame:
    """Holt ein Jahr ERA5-Daten fuer einen Punkt aus dem CDS.

    Nutzt den Datensatz ``reanalysis-era5-single-levels-timeseries``
    (Punktabfrage, naechstgelegener Gitterpunkt). Der CDS liefert die Daten als
    ZIP mit einer CSV (Spalten ``valid_time, u100, v100, u10, v10, t2m, sp,
    latitude, longitude``); das Format wurde an einem echten Abruf geprueft.
    """
    try:
        import cdsapi
    except ImportError as fehler:  # pragma: no cover
        raise ImportError(
            "Fuer wetterquelle 'era5' wird cdsapi benoetigt: "
            'pip install -e ".[era5]"'
        ) from fehler

    import tempfile

    anfrage = {
        "variable": [
            "100m_u_component_of_wind",
            "100m_v_component_of_wind",
            "10m_u_component_of_wind",
            "10m_v_component_of_wind",
            "2m_temperature",
            "surface_pressure",
        ],
        "location": {"longitude": laengengrad, "latitude": breitengrad},
        "date": [f"{jahr}-01-01/{jahr}-12-31"],
        "data_format": "csv",
    }
    with tempfile.TemporaryDirectory() as ordner:
        ziel = Path(ordner) / "era5_antwort"
        cdsapi.Client().retrieve(
            "reanalysis-era5-single-levels-timeseries", anfrage
        ).download(str(ziel))
        return _era5_antwort_zu_df(ziel)


def _era5_antwort_zu_df(datei: Path) -> pd.DataFrame:
    """Liest die CDS-Antwort (ZIP mit CSV oder direkt eine CSV)."""
    import tempfile
    import zipfile

    if zipfile.is_zipfile(datei):
        with zipfile.ZipFile(datei) as archiv:
            csv_namen = [n for n in archiv.namelist() if n.lower().endswith(".csv")]
            if not csv_namen:
                raise ValueError(f"ERA5-ZIP enthaelt keine CSV: {archiv.namelist()}")
            with tempfile.TemporaryDirectory() as ordner:
                archiv.extract(csv_namen[0], ordner)
                return _era5_csv_zu_df(Path(ordner) / csv_namen[0])
    return _era5_csv_zu_df(datei)


def _era5_csv_zu_df(pfad: Path) -> pd.DataFrame:
    """Uebersetzt die ERA5-CSV ins normierte Wetterformat (UTC, m/s, Grad C, hPa)."""
    df = pd.read_csv(pfad, parse_dates=["valid_time"])
    fehlende = {"valid_time", "u100", "v100", "u10", "v10", "t2m", "sp"} - set(df.columns)
    if fehlende:
        raise ValueError(f"ERA5-CSV fehlen Spalten: {sorted(fehlende)}")
    return pd.DataFrame(
        {
            "wind_10m_ms": np.hypot(df["u10"], df["v10"]).to_numpy(),
            "wind_100m_ms": np.hypot(df["u100"], df["v100"]).to_numpy(),
            "temperatur_c": (df["t2m"] - 273.15).to_numpy(),
            "druck_hpa": (df["sp"] / 100.0).to_numpy(),
        },
        index=pd.DatetimeIndex(df["valid_time"], name="zeitstempel"),
    )


def lade_era5_rauigkeit(breitengrad: float, laengengrad: float, jahr: int) -> pd.Series:
    """Holt die ERA5-Rauigkeitslaenge (Monatsmittel des Jahres) am naechsten Gitterpunkt.

    Datensatz ``reanalysis-era5-single-levels-monthly-means``, Variable
    ``forecast_surface_roughness`` (fsr, in m). Rueckgabe: Series mit Index
    Monat 1..12. Braucht ``cdsapi`` und ``xarray`` (Extra ``era5``).
    """
    try:
        import cdsapi
    except ImportError as fehler:  # pragma: no cover
        raise ImportError(
            "Fuer die ERA5-Rauigkeit wird cdsapi benoetigt: "
            'pip install -e ".[era5]" (oder rauigkeitsquelle: konstant)'
        ) from fehler

    import tempfile

    anfrage = {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": ["forecast_surface_roughness"],
        "year": [str(jahr)],
        "month": [f"{m:02d}" for m in range(1, 13)],
        "time": ["00:00"],
        # kleines Gebiet um den Standort (N, W, S, E); der naechste Punkt wird gewaehlt
        "area": [
            breitengrad + 0.25,
            laengengrad - 0.25,
            breitengrad - 0.25,
            laengengrad + 0.25,
        ],
        "data_format": "netcdf",
        "download_format": "unarchived",
    }
    with tempfile.TemporaryDirectory() as ordner:
        ziel = Path(ordner) / "era5_rauigkeit"
        cdsapi.Client().retrieve(
            "reanalysis-era5-single-levels-monthly-means", anfrage
        ).download(str(ziel))
        return _era5_rauigkeit_zu_monatswerten(ziel, breitengrad, laengengrad)


def _era5_rauigkeit_zu_monatswerten(
    datei: Path, breitengrad: float, laengengrad: float
) -> pd.Series:
    """Liest die netCDF-Antwort (ggf. im ZIP) und liefert z0 je Monat (1..12)."""
    import tempfile
    import zipfile

    if zipfile.is_zipfile(datei):
        with zipfile.ZipFile(datei) as archiv:
            nc_namen = [n for n in archiv.namelist() if n.lower().endswith(".nc")]
            if not nc_namen:
                raise ValueError(f"ERA5-ZIP enthaelt keine netCDF-Datei: {archiv.namelist()}")
            with tempfile.TemporaryDirectory() as ordner:
                archiv.extract(nc_namen[0], ordner)
                return _era5_rauigkeit_zu_monatswerten(
                    Path(ordner) / nc_namen[0], breitengrad, laengengrad
                )

    try:
        import xarray as xr
    except ImportError as fehler:  # pragma: no cover
        raise ImportError(
            'Fuer die ERA5-Rauigkeit wird xarray benoetigt: pip install -e ".[era5]"'
        ) from fehler

    with xr.open_dataset(datei) as ds:
        if "fsr" not in ds:
            raise ValueError(f"ERA5-Antwort enthaelt keine Variable 'fsr': {list(ds.data_vars)}")
        punkt = ds["fsr"].sel(latitude=breitengrad, longitude=laengengrad, method="nearest")
        zeit = "valid_time" if "valid_time" in punkt.dims else "time"
        werte = punkt.to_series()
        if werte.index.nlevels > 1:  # z. B. zusaetzliche Dimension expver/number
            werte = werte.groupby(level=zeit).mean()
    monate = pd.DatetimeIndex(werte.index).month
    return pd.Series(werte.to_numpy(dtype=float), index=monate, name="rauigkeit_m").groupby(
        level=0
    ).mean()


def _cache_datei(cfg: WindpowerlibConfig) -> Path | None:
    if not cfg.wetter_cache_ordner:
        return None
    name = (
        f"{cfg.wetterquelle}_{cfg.breitengrad:.3f}_{cfg.laengengrad:.3f}_{cfg.jahr}.csv"
    )
    return Path(cfg.wetter_cache_ordner) / name


def _lese_normiert(pfad: Path) -> pd.DataFrame:
    df = pd.read_csv(pfad, index_col="zeitstempel", parse_dates=True)
    return df
