"""Wetterdaten fuer die Windertragsabschaetzung (siehe ``windpark.py``).

Alle Quellen liefern dasselbe flache Format (stuendlich, UTC, Index
``zeitstempel``) mit den Spalten:

- ``wind_<h>m_ms``: Windgeschwindigkeit in m/s auf <h> Meter Hoehe
  (z. B. ``wind_10m_ms``, ``wind_100m_ms``)
- ``temperatur_c``: Lufttemperatur in 2 m Hoehe in Grad Celsius
- ``druck_hpa``: Luftdruck an der Oberflaeche in hPa

Quellen:
- ``open_meteo``: Historical-Weather-API von Open-Meteo (ERA5-basiert), ohne
  Account per HTTP. LIZENZ: Die kostenlose API ist laut Anbieter nur fuer
  nicht-kommerzielle Zwecke gedacht. Fuer Projekte mit kommerziellem Bezug
  (z. B. echte Green-Wind-Projekte) ``era5`` oder eine eigene Wetter-CSV
  nutzen bzw. einen kostenpflichtigen Open-Meteo-Zugang erwerben.
- ``era5``: (Standard) direkter Abruf aus dem Copernicus Climate Data Store (CDS) per
  ``cdsapi``. Braucht einen CDS-Account mit API-Key (``~/.cdsapirc``) sowie die
  Pakete ``cdsapi``, ``xarray`` und ``netCDF4`` (Extra ``era5``). Die Anfrage
  entspricht dem vom CDS erzeugten Code; das Einlesen der Antwortdatei ist
  bislang nur mit einer nachgebauten Datei getestet.
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


def lade_wetterdaten(cfg: WindpowerlibConfig) -> pd.DataFrame:
    """Liefert die Wetterdaten fuer ``cfg`` aus der gewaehlten Quelle."""
    if cfg.wetterquelle == "csv":
        if not cfg.wetter_pfad:
            raise ValueError("wetterquelle 'csv' braucht wetter_pfad in der Config.")
        return lade_wetter_csv(cfg.wetter_pfad, cfg.wind_messhoehe_m)

    cache_datei = _cache_datei(cfg)
    if cache_datei is not None and cache_datei.exists():
        return _lese_normiert(cache_datei)

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

    if cache_datei is not None:
        cache_datei.parent.mkdir(parents=True, exist_ok=True)
        wetter.to_csv(cache_datei, index_label="zeitstempel")
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

    Nutzt den Datensatz ``reanalysis-era5-single-levels-timeseries`` (Punktabfrage,
    Anfrageformat wie vom CDS-Formular unter "Show API request" erzeugt).
    HINWEIS: Das Einlesen der zurueckgegebenen NetCDF-Datei ist bislang nur mit
    einer nachgebauten Datei getestet, nicht mit einer echten CDS-Antwort.
    """
    try:
        import cdsapi
        import xarray as xr
    except ImportError as fehler:  # pragma: no cover
        raise ImportError(
            "Fuer wetterquelle 'era5' werden cdsapi, xarray und netCDF4 benoetigt: "
            'pip install -e ".[era5]"'
        ) from fehler

    import tempfile
    import zipfile

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
        "data_format": "netcdf",
    }
    with tempfile.TemporaryDirectory() as ordner:
        ziel = Path(ordner) / "era5.nc"
        cdsapi.Client().retrieve(
            "reanalysis-era5-single-levels-timeseries", anfrage
        ).download(str(ziel))
        if zipfile.is_zipfile(ziel):  # manche Antworten kommen gezippt
            with zipfile.ZipFile(ziel) as archiv:
                name = next(n for n in archiv.namelist() if n.endswith(".nc"))
                archiv.extract(name, ordner)
                ziel = Path(ordner) / name
        with xr.open_dataset(ziel) as ds:
            return _era5_dataset_zu_df(ds)


def _era5_dataset_zu_df(ds: Any) -> pd.DataFrame:
    """Uebersetzt ein ERA5-Punkt-Dataset (xarray) ins normierte Wetterformat."""

    def variable(*kandidaten: str) -> np.ndarray:
        for name in kandidaten:
            if name in ds:
                werte = np.asarray(ds[name].squeeze(drop=True).values, dtype=float)
                if werte.ndim != 1:
                    raise ValueError(f"ERA5-Variable {name} ist nicht eindimensional.")
                return werte
        raise KeyError(f"ERA5-Datei enthaelt keine der Variablen {kandidaten}: {list(ds.data_vars)}")

    zeit = next((z for z in ("valid_time", "time") if z in ds.coords), None)
    if zeit is None:
        raise KeyError(f"ERA5-Datei hat keine Zeitachse: {list(ds.coords)}")
    index = pd.DatetimeIndex(ds[zeit].values, name="zeitstempel")

    return pd.DataFrame(
        {
            "wind_10m_ms": np.hypot(variable("u10", "10u"), variable("v10", "10v")),
            "wind_100m_ms": np.hypot(variable("u100", "100u"), variable("v100", "100v")),
            "temperatur_c": variable("t2m", "2t") - 273.15,
            "druck_hpa": variable("sp") / 100.0,
        },
        index=index,
    )


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
