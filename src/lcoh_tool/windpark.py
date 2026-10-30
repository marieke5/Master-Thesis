"""Schnellabschaetzung des Windpark-Erzeugungsprofils mit windpowerlib.

ACHTUNG: Das ist eine grobe Abschaetzung aus Reanalyse-Wetterdaten (ca. 30 km
Aufloesung, keine Standortmessung, pauschale Parkverluste). Sie ersetzt kein
Ertragsgutachten und sollte in der Arbeit als Vereinfachung gekennzeichnet
werden. Fuer belastbare Ergebnisse das extern erstellte Profil als CSV nutzen
(``windpark.quelle: csv``).

windpowerlib ist eine optionale Abhaengigkeit: ``pip install -e ".[wind]"``.
"""

from __future__ import annotations

import re

import pandas as pd

from lcoh_tool.config import WindpowerlibConfig
from lcoh_tool.wetterdaten import lade_wetterdaten


def erzeuge_windprofil(cfg: WindpowerlibConfig) -> pd.Series:
    """Berechnet das stuendliche Erzeugungsprofil des Windparks in kWh."""
    return berechne_windprofil(lade_wetterdaten(cfg), cfg)


def berechne_windprofil(wetter: pd.DataFrame, cfg: WindpowerlibConfig) -> pd.Series:
    """Wie ``erzeuge_windprofil``, aber mit bereits geladenen Wetterdaten."""
    try:
        from windpowerlib import ModelChain, WindTurbine
    except ImportError as fehler:
        raise ImportError(
            "Fuer windpark.quelle 'windpowerlib' wird windpowerlib benoetigt: "
            'pip install -e ".[wind]"'
        ) from fehler

    spalten = {}
    for name in wetter.columns:
        treffer = re.fullmatch(r"wind_(\d+)m_ms", name)
        if treffer:
            spalten[("wind_speed", int(treffer.group(1)))] = wetter[name]
    if not spalten:
        raise ValueError("Wetterdaten enthalten keine Spalte 'wind_<h>m_ms'.")
    spalten[("temperature", 2)] = wetter["temperatur_c"] + 273.15  # Kelvin
    spalten[("pressure", 0)] = wetter["druck_hpa"] * 100.0  # Pascal
    spalten[("roughness_length", 0)] = cfg.rauigkeitslaenge_m

    wetter_wpl = pd.DataFrame(spalten, index=wetter.index)
    wetter_wpl.columns = pd.MultiIndex.from_tuples(
        wetter_wpl.columns, names=["variable_name", "height"]
    )

    anlage = WindTurbine(turbine_type=cfg.anlagentyp, hub_height=cfg.nabenhoehe_m)
    leistung_w = ModelChain(anlage).run_model(wetter_wpl).power_output

    # Leistung je Stunde in W -> Energie je Stunde in kWh, hochgerechnet auf den Park.
    energie_kwh = leistung_w / 1000.0 * cfg.anzahl_anlagen * cfg.parkwirkungsgrad
    energie_kwh.index.name = "zeitstempel"
    return energie_kwh.rename("erzeugung_kwh")
