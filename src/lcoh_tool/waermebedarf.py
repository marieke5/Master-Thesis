"""Einlesen bzw. Bereitstellen der stundenscharfen Waermelast.

Drei Wege sind vorgesehen (siehe Config und ``projekt.py``):
1. Eine vorliegende stundenscharfe CSV-Zeitreihe wird direkt eingelesen.
2. Gebaeudetypen und -anzahl: Profil ueber lpagg (``lastprofil_lpagg.py``).
3. Fallback: aus dem Gesamtwaermebedarf wird ueber ein einfaches saisonales
   Muster eine stundenscharfe Lastkurve erzeugt.

Die aktuell hinterlegte Lastverteilung ist ein Platzhalter (einfaches
saisonales Muster) und TODO: durch ein echtes Referenzprofil aus der App
nPro ersetzen, sobald der Export vorliegt. Die Gebaeudeanzahl wird bereits
als Parameter durchgereicht, auch wenn die Platzhalter-Verteilung sie noch
nicht nutzt - sobald das nPro-Profil nach Gebaeudetyp/-groesse differenziert,
kann es hier eingebaut werden, ohne die Schnittstelle zu aendern.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

STUNDEN_PRO_JAHR = 8760


@dataclass
class GebaeudeLastparameter:
    """Eingabe fuer die Lastverteilung: Gesamtwaermebedarf + Gebaeudeanzahl."""

    gesamtwaermebedarf_mwh: float
    anzahl_gebaeude: int = 1


def load_waermebedarf(pfad: str | Path | Any) -> pd.Series:
    """Laedt eine stundenscharfe Waermelast-Zeitreihe aus CSV.

    Erwartet die Spalten ``zeitstempel`` und ``waermelast_kwh``. ``pfad`` ist
    ein Dateipfad oder ein geoeffnetes Dateiobjekt (z. B. GUI-Upload).
    """
    if isinstance(pfad, (str, Path)):
        pfad = Path(pfad)
        if not pfad.exists():
            raise FileNotFoundError(f"Waermelastprofil nicht gefunden: {pfad}")

    df = pd.read_csv(pfad)
    fehlende = {"zeitstempel", "waermelast_kwh"} - set(df.columns)
    if fehlende:
        raise ValueError(
            f"CSV {getattr(pfad, 'name', pfad)} fehlen erwartete Spalten: {sorted(fehlende)}"
        )

    df["zeitstempel"] = pd.to_datetime(df["zeitstempel"])
    df = df.set_index("zeitstempel").sort_index()

    return df["waermelast_kwh"].rename("waermelast_kwh")


def synthetische_waermelast(
    jahreswaermebedarf_mwh: float,
    jahr: int = 2027,
) -> pd.Series:
    """Erzeugt eine stark vereinfachte synthetische Jahreslastkurve.

    Platzhalter, solange kein reales Lastprofil vorliegt: verteilt den
    Jahreswaermebedarf ueber ein einfaches saisonales Muster (mehr Last im
    Winter, weniger im Sommer). Fuer die Masterarbeit spaeter durch ein
    Referenzlastprofil (z. B. VDI 4655/2067) zu ersetzen.
    """
    zeitstempel = pd.date_range(
        start=f"{jahr}-01-01", periods=STUNDEN_PRO_JAHR, freq="h"
    )
    tag_des_jahres = zeitstempel.day_of_year.to_numpy()

    # Einfaches saisonales Gewicht: Maximum im Winter (Tag 1/365), Minimum im
    # Sommer (Tag ~182), reine Platzhalter-Heuristik.
    saisonales_gewicht = 0.5 + 0.5 * np.cos(2 * np.pi * (tag_des_jahres - 1) / 365)
    gewicht_normiert = saisonales_gewicht / saisonales_gewicht.sum()

    jahreswaermebedarf_kwh = jahreswaermebedarf_mwh * 1000
    werte = gewicht_normiert * jahreswaermebedarf_kwh

    return pd.Series(werte, index=zeitstempel, name="waermelast_kwh")


def lastverteilung_platzhalter(
    parameter: GebaeudeLastparameter,
    jahr: int = 2027,
) -> pd.Series:
    """Platzhalter fuer die "Lastverteilung Norddeutschland".

    Nimmt Gesamtwaermebedarf + Gebaeudeanzahl entgegen (so wie im Tool-Ablauf
    vorgesehen) und verteilt den Gesamtwaermebedarf aktuell ueber dasselbe
    einfache saisonale Muster wie ``synthetische_waermelast`` - die
    Gebaeudeanzahl geht noch nicht in die Form der Kurve ein, nur in die
    Dokumentation der Schnittstelle.

    TODO: durch das Referenzprofil aus nPro ersetzen, sobald der Export
    vorliegt. Sobald dieses Profil nach Gebaeudetyp/-anzahl differenziert,
    kann ``parameter.anzahl_gebaeude`` hier tatsaechlich verwendet werden,
    ohne dass sich main.py oder die Config aendern muessen.
    """
    return synthetische_waermelast(parameter.gesamtwaermebedarf_mwh, jahr)
