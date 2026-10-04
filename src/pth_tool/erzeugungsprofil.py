"""Einlesen des stundenscharfen Windpark-Erzeugungsprofils.

Das Erzeugungsprofil wird nicht vom Tool berechnet, sondern liegt extern
vor (z. B. Ertragsgutachten, SCADA-Daten) und wird als CSV mit den Spalten
``zeitstempel`` und ``energie_kwh`` eingelesen (8.760 Zeilen fuer ein
volles Jahr).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_erzeugungsprofil(pfad: str | Path) -> pd.Series:
    """Laedt das Erzeugungsprofil als stundenscharfe Zeitreihe (kWh).

    Erwartet eine CSV mit den Spalten ``zeitstempel`` (parsebar als
    Datum/Uhrzeit) und ``energie_kwh``. Gibt eine ``pd.Series`` zurueck,
    indiziert auf den Zeitstempel.
    """
    pfad = Path(pfad)
    if not pfad.exists():
        raise FileNotFoundError(f"Erzeugungsprofil nicht gefunden: {pfad}")

    df = pd.read_csv(pfad)
    _pruefe_spalten(df, {"zeitstempel", "energie_kwh"}, pfad)

    df["zeitstempel"] = pd.to_datetime(df["zeitstempel"])
    df = df.set_index("zeitstempel").sort_index()

    return df["energie_kwh"].rename("erzeugung_kwh")


def _pruefe_spalten(df: pd.DataFrame, erwartete_spalten: set[str], pfad: Path) -> None:
    fehlende = erwartete_spalten - set(df.columns)
    if fehlende:
        raise ValueError(
            f"CSV {pfad} fehlen erwartete Spalten: {sorted(fehlende)}"
        )
