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


def lade_erzeugung(config: ToolConfig) -> pd.Series:
    """Erzeugungsprofil je nach ``windpark.quelle`` (CSV oder windpowerlib)."""
    windpark = config.windpark
    if windpark.quelle == "windpowerlib":
        if windpark.windpowerlib is None:
            raise ValueError("windpark.quelle 'windpowerlib' braucht den Block 'windpowerlib'.")
        from lcoh_tool.windpark import erzeuge_windprofil

        return erzeuge_windprofil(windpark.windpowerlib)
    if windpark.erzeugungsprofil_pfad is None:
        raise ValueError("Kein erzeugungsprofil_pfad (CSV) in der Config gesetzt.")
    return load_erzeugungsprofil(windpark.erzeugungsprofil_pfad)


def lade_waermelast(config: ToolConfig) -> pd.Series:
    """Waermelast: CSV (Pfad/Upload) vor lpagg vor Jahreswert-Platzhalter."""
    bedarf = config.waermebedarf
    if bedarf.waermelast_pfad:
        return load_waermebedarf(bedarf.waermelast_pfad)
    if bedarf.lpagg is not None:
        from lcoh_tool.lastprofil_lpagg import erzeuge_waermelast_lpagg

        return erzeuge_waermelast_lpagg(bedarf.lpagg)
    if bedarf.jahreswaermebedarf_mwh:
        parameter = GebaeudeLastparameter(
            gesamtwaermebedarf_mwh=bedarf.jahreswaermebedarf_mwh,
            anzahl_gebaeude=bedarf.anzahl_gebaeude or 1,
        )
        return lastverteilung_platzhalter(parameter)
    raise ValueError(
        "Keine Waermelast-Quelle in der Config: waermelast_pfad, lpagg oder "
        "jahreswaermebedarf_mwh setzen."
    )


def berechne_projekt(
    config: ToolConfig | str | Path,
    erzeugungsprofil: pd.Series | None = None,
    waermelastprofil: pd.Series | None = None,
) -> ProjektErgebnis:
    """Fuehrt die komplette Berechnung aus.

    ``config`` ist entweder ein bereits gebautes ``ToolConfig`` (z. B. aus
    einer GUI) oder der Pfad zu einer YAML-Datei. Mit ``erzeugungsprofil`` /
    ``waermelastprofil`` lassen sich fertige Zeitreihen direkt vorgeben; dann
    werden die jeweiligen Quellen der Config uebergangen.
    """
    if not isinstance(config, ToolConfig):
        config = load_config(config)

    erzeugung = erzeugungsprofil if erzeugungsprofil is not None else lade_erzeugung(config)
    waermelast = waermelastprofil if waermelastprofil is not None else lade_waermelast(config)

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
