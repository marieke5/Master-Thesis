"""Einlesen bzw. Bereitstellen der stundenscharfen Waermelast.

Zwei Wege sind vorgesehen (siehe Config):
1. Eine vorliegende stundenscharfe CSV-Zeitreihe wird direkt eingelesen.
2. Fallback: aus einem Jahreswaermebedarf wird - als Platzhalter fuer ein
   spaeteres Referenzlastprofil (z. B. VDI 4655/2067) - eine vereinfachte
   synthetische Lastkurve erzeugt.

Die synthetische Erzeugung ist bewusst simpel gehalten und als TODO fuer die
methodische Vertiefung markiert.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

STUNDEN_PRO_JAHR = 8760


def load_waermebedarf(pfad: str | Path) -> pd.Series:
    """Laedt eine stundenscharfe Waermelast-Zeitreihe aus CSV.

    Erwartet die Spalten ``zeitstempel`` und ``waermelast_kwh``.
    """
    pfad = Path(pfad)
    if not pfad.exists():
        raise FileNotFoundError(f"Waermelastprofil nicht gefunden: {pfad}")

    df = pd.read_csv(pfad)
    fehlende = {"zeitstempel", "waermelast_kwh"} - set(df.columns)
    if fehlende:
        raise ValueError(f"CSV {pfad} fehlen erwartete Spalten: {sorted(fehlende)}")

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
    tag_des_jahres = zeitstempel.dayofyear.to_numpy()

    # Einfaches saisonales Gewicht: Maximum im Winter (Tag 1/365), Minimum im
    # Sommer (Tag ~182), reine Platzhalter-Heuristik.
    saisonales_gewicht = 0.5 + 0.5 * np.cos(2 * np.pi * (tag_des_jahres - 1) / 365)
    gewicht_normiert = saisonales_gewicht / saisonales_gewicht.sum()

    jahreswaermebedarf_kwh = jahreswaermebedarf_mwh * 1000
    werte = gewicht_normiert * jahreswaermebedarf_kwh

    return pd.Series(werte, index=zeitstempel, name="waermelast_kwh")
