"""Variationsrechnung: Speichergroesse x Preisschwelle der preisgesteuerten Direktleitung.

Profile (Wind, Waermelast, Marktpreise) werden einmal geladen und fuer alle Varianten
wiederverwendet. Die Speicher-Investition wird linear mit der Kapazitaet skaliert
(``capex_speicher_eur / kapazitaet_kwh`` der Basis-Config je kWh, oder explizit
``capex_eur_pro_kwh``).

Aufruf:
    python -m lcoh_tool.variation --config config/parameter_jahreslauf.yaml \
        --speicher 5000 20000 50000 100000 --schwellen 0 20 40 --ausgabe variation.csv
"""

from __future__ import annotations

import argparse
import copy
import itertools
from typing import Sequence

import pandas as pd

from lcoh_tool.config import ToolConfig, load_config

from lcoh_tool.projekt import (
    berechne_projekt,
    lade_erzeugung,
    lade_marktpreisreihe,
    lade_waermelast,
    wende_referenzjahr_an,
)


def variiere(
    config: ToolConfig,
    speicher_kwh: Sequence[float],
    schwellen_eur_mwh: Sequence[float],
    capex_eur_pro_kwh: float | None = None,
    erzeugung: pd.Series | None = None,
    waermelast: pd.Series | None = None,
    marktpreis: pd.Series | None = None,
    direktstrompreise_eur_mwh: Sequence[float] | None = None,
) -> pd.DataFrame:
    """Rechnet alle Kombinationen und gibt eine Tabelle (eine Zeile je Variante) zurueck.

    Mit ``direktstrompreise_eur_mwh`` wird der Windstrom zusaetzlich zu einem festen Preis
    (EUR/MWh) statt zum Marktpreis bewertet und der Preis mitvariiert.
    """
    if config.steuerung is None:
        raise ValueError("Variation braucht den Block 'steuerung' in der Config.")
    config = wende_referenzjahr_an(config)
    if capex_eur_pro_kwh is None:
        basis = config.speicher.kapazitaet_kwh
        capex_eur_pro_kwh = config.wirtschaft.capex_speicher_eur / basis if basis else 0.0

    erzeugung = erzeugung if erzeugung is not None else lade_erzeugung(config)
    waermelast = waermelast if waermelast is not None else lade_waermelast(config)
    if marktpreis is None and config.ppa is None:  # mit PPA keine Marktpreisreihe noetig
        marktpreis = lade_marktpreisreihe(config)

    zeilen = []
    preise = list(direktstrompreise_eur_mwh) if direktstrompreise_eur_mwh else [None]
    for kapazitaet, schwelle, festpreis in itertools.product(speicher_kwh, schwellen_eur_mwh, preise):
        cfg = copy.deepcopy(config)
        if festpreis is not None and cfg.ppa is not None:
            cfg.ppa.preis_eur_pro_mwh = float(festpreis)  # mit PPA variiert der PPA-Preis
        elif festpreis is not None:
            cfg.steuerung.direktstrom_bepreisung = "fest"
            cfg.steuerung.direktstrompreis_eur_pro_mwh = float(festpreis)
        cfg.speicher.kapazitaet_kwh = float(kapazitaet)
        cfg.wirtschaft.capex_speicher_eur = capex_eur_pro_kwh * kapazitaet
        cfg.steuerung.preisschwelle_eur_pro_mwh = float(schwelle)
        e = berechne_projekt(cfg, erzeugung, waermelast, marktpreis)
        k = e.kennzahlen
        zeilen.append(
            {
                "speicher_kwh": kapazitaet,
                "schwelle_eur_mwh": schwelle,
                **({"direktstrompreis_eur_mwh": festpreis} if festpreis is not None else {}),
                "lcoh_eur_mwh": e.lcoh.lcoh_eur_pro_mwh,
                "vorteil_vs_netzbezug_eur_mwh": e.vergleich.vorteil_direktleitung_eur_pro_mwh[
                    e.vergleich.szenario_aktiv
                ],
                "breakeven_leitung_eur": e.vergleich.breakeven_leitungskosten_eur[
                    e.vergleich.szenario_aktiv
                ],
                **(
                    {
                        "vorteil_vs_ppa_netz_eur_mwh": e.vergleich.vorteil_vs_ppa_netz_eur_pro_mwh[
                            e.vergleich.szenario_aktiv
                        ],
                        "breakeven_vs_ppa_netz_eur": e.vergleich.breakeven_vs_ppa_netz_eur[
                            e.vergleich.szenario_aktiv
                        ],
                    }
                    if e.vergleich.vorteil_vs_ppa_netz_eur_pro_mwh is not None
                    else {}
                ),
                "direktstrom_eur_mwh": k.direktstrom_durchschnittspreis_eur_mwh,
                "direktstrom_kosten_eur": k.direktstrom_kosten_eur,
                "rueckfall_mwh": k.rueckfall_mwh,
                "notbetrieb_h": k.notbetrieb_stunden,
                "direktleitung_h": k.direktleitung_stunden,
                "ungedeckt_mwh": k.deckungsluecke_mwh,
            }
        )
    return pd.DataFrame(zeilen)


def breakeven_direktstrompreis(gruppe: pd.DataFrame) -> float | None:
    """Direktstrompreis, bei dem der Vorteil der Direktleitung 0 wird (lineare Interpolation).

    Gibt None zurueck, wenn der Vorteil im untersuchten Preisbereich nie das Vorzeichen wechselt
    (dann ist die Direktleitung durchgehend besser oder durchgehend schlechter).
    """
    g = gruppe.sort_values("direktstrompreis_eur_mwh")
    x = g["direktstrompreis_eur_mwh"].to_numpy(dtype=float)
    y = g["vorteil_vs_netzbezug_eur_mwh"].to_numpy(dtype=float)
    for i in range(len(x) - 1):
        if y[i] == 0:
            return float(x[i])
        if y[i] * y[i + 1] < 0:
            return float(x[i] + (0 - y[i]) * (x[i + 1] - x[i]) / (y[i + 1] - y[i]))
    return float(x[-1]) if y[-1] == 0 else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Speicher x Preisschwelle variieren")
    parser.add_argument("--config", required=True)
    parser.add_argument("--speicher", type=float, nargs="+", required=True, help="Kapazitaeten in kWh (thermisch)")
    parser.add_argument("--schwellen", type=float, nargs="+", required=True, help="Preisschwellen in EUR/MWh")
    parser.add_argument("--capex-pro-kwh", type=float, default=None)
    parser.add_argument("--direktstrompreise", type=float, nargs="+", default=None,
                        help="feste Direktstrompreise in EUR/MWh (statt Marktpreis)")
    parser.add_argument("--ausgabe", default=None, help="optional: Ergebnis-CSV")
    args = parser.parse_args()

    tabelle = variiere(load_config(args.config), args.speicher, args.schwellen, args.capex_pro_kwh,
                       direktstrompreise_eur_mwh=args.direktstrompreise)
    print(tabelle.round(1).to_string(index=False))
    beste = tabelle.loc[tabelle["lcoh_eur_mwh"].idxmin()]
    print(f"\nNiedrigste LCOH: {beste['lcoh_eur_mwh']:.1f} EUR/MWh bei Speicher "
          f"{beste['speicher_kwh']:,.0f} kWh und Schwelle {beste['schwelle_eur_mwh']:g} EUR/MWh")
    if "direktstrompreis_eur_mwh" in tabelle.columns:
        for (sp, sw), g in tabelle.groupby(["speicher_kwh", "schwelle_eur_mwh"]):
            p = breakeven_direktstrompreis(g)
            text = f"{p:.1f} EUR/MWh" if p is not None else "im untersuchten Bereich nicht erreicht"
            print(f"Direktleitung (angesetzte Leitungskosten) lohnt sich bis Direktstrompreis: {text} "
                  f"(Speicher {sp:,.0f} kWh, Schwelle {sw:g})")
    if args.ausgabe:
        tabelle.to_csv(args.ausgabe, index=False)


if __name__ == "__main__":
    main()
