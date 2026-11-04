"""Abruf der Day-Ahead-Marktpreise von der ENTSO-E Transparency Platform.

Schreibt eine CSV im Format von ``marktpreise.load_marktpreise``
(``zeitstempel``, ``preis_eur_mwh``), stuendlich, **in UTC** (wie die ERA5-Wetterdaten,
damit Wind und Preis dieselbe Zeitbasis haben). Seit Oktober 2025 liefert der
Day-Ahead-Markt 15-Minuten-Preise; sie werden auf Stundenmittel verdichtet.

Der API-Token wird NICHT in Dateien gespeichert, sondern aus der Umgebungsvariable
``ENTSOE_API_KEY`` gelesen. Installation: ``pip install -e ".[entsoe]"``.

Aufruf:
    $env:ENTSOE_API_KEY = "<token>"     # PowerShell, nur fuer diese Sitzung
    python -m lcoh_tool.marktpreise_abruf --jahr 2023 --ausgabe data/marktpreise_2023.csv
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd


def lade_entsoe_preise(jahr: int, zone: str = "DE_LU", api_key: str | None = None) -> pd.Series:
    """Holt die Day-Ahead-Preise (EUR/MWh) eines Kalenderjahres (UTC) als Stundenreihe."""
    api_key = api_key or os.environ.get("ENTSOE_API_KEY")
    if not api_key:
        raise ValueError("Kein API-Token: Umgebungsvariable ENTSOE_API_KEY setzen.")
    try:
        from entsoe import EntsoePandasClient
    except ImportError as fehler:  # pragma: no cover
        raise ImportError('Fuer den Preisabruf wird entsoe-py benoetigt: pip install -e ".[entsoe]"') from fehler

    client = EntsoePandasClient(api_key=api_key)
    roh = client.query_day_ahead_prices(
        zone,
        start=pd.Timestamp(f"{jahr}-01-01", tz="UTC"),
        end=pd.Timestamp(f"{jahr + 1}-01-01", tz="UTC"),
    )
    return normiere_preise(roh, jahr)


def normiere_preise(roh: pd.Series, jahr: int) -> pd.Series:
    """Stundenmittel in UTC (ohne Zeitzone), vollstaendig fuer das Jahr; kleine Luecken
    (bis 2 Stunden) werden vorwaertsgefuellt, groessere Luecken fuehren zu einem Fehler."""
    utc = roh.copy()
    utc.index = pd.DatetimeIndex(utc.index).tz_convert("UTC").tz_localize(None)
    stunden = utc.resample("h").mean()
    voll = pd.date_range(f"{jahr}-01-01", f"{jahr + 1}-01-01", freq="h", inclusive="left")
    stunden = stunden.reindex(voll)
    fehlend_vor = int(stunden.isna().sum())
    stunden = stunden.ffill(limit=2)
    rest = int(stunden.isna().sum())
    if rest:
        raise ValueError(f"{rest} Stunden ohne Preis in {jahr} (ENTSO-E-Daten unvollstaendig).")
    if fehlend_vor:
        print(f"Hinweis: {fehlend_vor} fehlende Stunden vorwaertsgefuellt.")
    stunden.index.name = "zeitstempel"
    return stunden.rename("preis_eur_mwh")


def main() -> None:
    parser = argparse.ArgumentParser(description="Day-Ahead-Preise von ENTSO-E als CSV speichern")
    parser.add_argument("--jahr", type=int, required=True)
    parser.add_argument("--zone", default="DE_LU")
    parser.add_argument("--ausgabe", required=True, help="Ziel-CSV, z. B. data/marktpreise_2023.csv")
    args = parser.parse_args()
    preise = lade_entsoe_preise(args.jahr, args.zone)
    ziel = Path(args.ausgabe)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    preise.to_csv(ziel)
    print(f"{len(preise)} Stunden gespeichert: {ziel} "
          f"(Mittel {preise.mean():.1f} EUR/MWh, negativ in {(preise < 0).sum()} h)")


if __name__ == "__main__":
    main()
