"""Gesamtablauf der Berechnung als wiederverwendbare Funktion.

``berechne_projekt`` fuehrt alle Schritte (Config laden, Profile einlesen,
Bilanz, LCOH) aus und gibt die Ergebnisse als Objekt zurueck - ohne etwas
auszugeben. So koennen die CLI (``main.py``) und eine spaetere GUI dieselbe
Rechnung nutzen und jeweils auf ihre Art darstellen.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from lcoh_tool.bilanz import berechne_bilanz
from lcoh_tool.config import ToolConfig, load_config
from lcoh_tool.erzeugungsprofil import load_erzeugungsprofil
from lcoh_tool.waermebedarf import (
    GebaeudeLastparameter,
    lastverteilung_platzhalter,
    load_waermebedarf,
)
from lcoh_tool.wirtschaftlichkeit import LCOHErgebnis, berechne_lcoh


@dataclass
class ProjektErgebnis:
    config: ToolConfig
    erzeugung_kwh: pd.Series
    waermelast_kwh: pd.Series
    bilanz: pd.DataFrame
    lcoh: LCOHErgebnis
    anteil_direktanschluss_prozent: float


def berechne_projekt(config: ToolConfig | str | Path) -> ProjektErgebnis:
    """Fuehrt die komplette Berechnung aus.

    ``config`` ist entweder ein bereits gebautes ``ToolConfig`` (z. B. aus
    einer GUI) oder der Pfad zu einer YAML-Datei.
    """
    if not isinstance(config, ToolConfig):
        config = load_config(config)

    erzeugung = load_erzeugungsprofil(config.windpark.erzeugungsprofil_pfad)

    if config.waermebedarf.waermelast_pfad:
        waermelast = load_waermebedarf(config.waermebedarf.waermelast_pfad)
    elif config.waermebedarf.jahreswaermebedarf_mwh:
        parameter = GebaeudeLastparameter(
            gesamtwaermebedarf_mwh=config.waermebedarf.jahreswaermebedarf_mwh,
            anzahl_gebaeude=config.waermebedarf.anzahl_gebaeude or 1,
        )
        waermelast = lastverteilung_platzhalter(parameter)
    else:
        raise ValueError(
            "Weder waermelast_pfad noch jahreswaermebedarf_mwh in der Config gesetzt."
        )

    bilanz = berechne_bilanz(erzeugung, waermelast, config)
    lcoh = berechne_lcoh(bilanz, config)

    direkt = bilanz["direktanschluss_kwh"].sum()
    gesamt = direkt + bilanz["rueckfall_kwh"].sum()
    anteil = direkt / gesamt * 100 if gesamt > 0 else 0.0

    return ProjektErgebnis(
        config=config,
        erzeugung_kwh=erzeugung,
        waermelast_kwh=waermelast,
        bilanz=bilanz,
        lcoh=lcoh,
        anteil_direktanschluss_prozent=anteil,
    )
