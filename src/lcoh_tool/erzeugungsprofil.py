"""Einlesen des stundenscharfen Windpark-Erzeugungsprofils.

Das Erzeugungsprofil wird nicht vom Tool berechnet, sondern liegt extern
vor (z. B. Ertragsgutachten, SCADA-Daten) und wird als CSV mit den Spalten
``zeitstempel`` und ``energie_kwh`` eingelesen (8.760 Zeilen fuer ein
volles Jahr).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def load_erzeugungsprofil(pfad: str | Path | Any, windpro_block: str = "gesamt") -> pd.Series:
    """Laedt das Erzeugungsprofil als stundenscharfe Zeitreihe (kWh).

    Erwartet eine CSV mit den Spalten ``zeitstempel`` (parsebar als
    Datum/Uhrzeit) und ``energie_kwh``. ``pfad`` ist ein Dateipfad oder ein
    bereits geoeffnetes Dateiobjekt (z. B. der Upload einer Streamlit-App).
    Gibt eine ``pd.Series`` zurueck, indiziert auf den Zeitstempel.

    Eine WindPRO-Zeitreihe (Export "Time Variation", Textdatei mit ``;``) wird automatisch
    erkannt und direkt gelesen, siehe ``lade_windpro``. ``windpro_block`` waehlt dort
    "gesamt" (alle WEA) oder "je_wea" (eine WEA).
    """
    if isinstance(pfad, (str, Path)):
        pfad = Path(pfad)
        if not pfad.exists():
            raise FileNotFoundError(f"Erzeugungsprofil nicht gefunden: {pfad}")

    if _ist_windpro(pfad):
        return lade_windpro(pfad, windpro_block)

    df = pd.read_csv(pfad)
    _pruefe_spalten(df, {"zeitstempel", "energie_kwh"}, pfad)

    df["zeitstempel"] = pd.to_datetime(df["zeitstempel"])
    df = df.set_index("zeitstempel").sort_index()

    return df["energie_kwh"].rename("erzeugung_kwh")


_WINDPRO_SPALTE = {"gesamt": 1, "je_wea": 21}  # Spalte "Power" des jeweiligen Blocks


def _kopfzeilen(pfad: Any, n: int = 6) -> list[str]:
    if isinstance(pfad, Path):
        with open(pfad, encoding="latin-1") as f:
            return [f.readline() for _ in range(n)]
    position = pfad.tell()
    inhalt = pfad.read(20000)
    pfad.seek(position)
    text = inhalt.decode("latin-1") if isinstance(inhalt, bytes) else inhalt
    return (text.splitlines() + [""] * n)[:n]


def _ist_windpro(pfad: Any) -> bool:
    return any(z.startswith("Time stamp;Power") for z in _kopfzeilen(pfad))


def lade_windpro(pfad: str | Path | Any, block: str = "gesamt") -> pd.Series:
    """Liest eine WindPRO-Zeitreihe (Power in kW je Stunde) als Erzeugung in kWh.

    Format: Kopfzeilen mit Projekt/Wetterquelle, Spaltennamen (``Time stamp;Power;...``) und
    Einheiten, danach ``TT.MM.JJJJ hh:mm;Wert;...`` mit Dezimalkomma. Der erste Block (Spalte 2) ist die Summe
    aller WEA, der zweite Block (Spalte 22) eine einzelne WEA. WindPRO beschriftet jede Stunde
    mit ihrem **Ende** (01:00 = Stunde 00-01 Uhr); der Zeitstempel wird deshalb um eine Stunde
    auf den Stundenbeginn zurueckgesetzt, damit ein Kalenderjahr genau seine Stunden enthaelt.
    """
    if block not in _WINDPRO_SPALTE:
        raise ValueError(f"windpro_block muss 'gesamt' oder 'je_wea' sein, nicht {block!r}.")
    if isinstance(pfad, (str, Path)):
        pfad = Path(pfad)
    spalte = _WINDPRO_SPALTE[block]
    kopf = next(z for z in _kopfzeilen(pfad) if z.startswith("Time stamp;Power")).split(";")
    if len(kopf) <= spalte or kopf[spalte] != "Power":
        raise ValueError(f"WindPRO-Datei: Spalte {spalte + 1} ist keine 'Power'-Spalte ({block}).")
    df = pd.read_csv(
        pfad, sep=";", skiprows=0, header=None, on_bad_lines="skip", usecols=[0, spalte],
        names=[f"c{i}" for i in range(spalte + 1)],
        dtype=str, encoding="latin-1",
    )
    df.columns = ["t", "kw"]
    df["t"] = pd.to_datetime(df["t"], format="%d.%m.%Y %H:%M", errors="coerce")
    df["kw"] = pd.to_numeric(df["kw"].str.replace(",", ".", regex=False), errors="coerce")
    df = df.dropna()
    if df.empty:
        raise ValueError("WindPRO-Datei enthaelt keine lesbaren Zeilen.")
    serie = df.set_index("t")["kw"].sort_index()
    serie.index = serie.index - pd.Timedelta(hours=1)
    serie.index.name = "zeitstempel"
    return serie.rename("erzeugung_kwh")  # kW ueber 1 h = kWh


def _pruefe_spalten(df: pd.DataFrame, erwartete_spalten: set[str], pfad: Any) -> None:
    fehlende = erwartete_spalten - set(df.columns)
    if fehlende:
        raise ValueError(
            f"CSV {getattr(pfad, 'name', pfad)} fehlen erwartete Spalten: {sorted(fehlende)}"
        )
