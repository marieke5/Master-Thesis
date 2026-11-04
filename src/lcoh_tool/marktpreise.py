"""Einlesen der stuendlichen Marktpreise (Day-Ahead) fuer die Steuerung der
Direktleitung (siehe ``betrieb.py``).

Erwartet eine CSV mit den Spalten ``zeitstempel`` und ``preis_eur_mwh``, stuendlich,
z. B. aus einem Download von SMARD (Bundesnetzagentur) oder der EPEX/ENTSO-E.
Negative Preise sind ausdruecklich vorgesehen. Wind- und Preisjahr sollten
dasselbe Jahr sein, weil beide stark zusammenhaengen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def load_marktpreise(pfad: str | Path | Any) -> pd.Series:
    """Laedt die Marktpreis-Zeitreihe (EUR/MWh) aus einer CSV (Pfad oder Dateiobjekt)."""
    if isinstance(pfad, (str, Path)):
        pfad = Path(pfad)
        if not pfad.exists():
            raise FileNotFoundError(f"Marktpreisdatei nicht gefunden: {pfad}")

    df = pd.read_csv(pfad)
    fehlende = {"zeitstempel", "preis_eur_mwh"} - set(df.columns)
    if fehlende:
        raise ValueError(
            f"Marktpreis-CSV {getattr(pfad, 'name', pfad)} fehlen Spalten: {sorted(fehlende)}"
        )
    df["zeitstempel"] = pd.to_datetime(df["zeitstempel"])
    df = df.set_index("zeitstempel").sort_index()
    return df["preis_eur_mwh"].rename("marktpreis_eur_mwh")
