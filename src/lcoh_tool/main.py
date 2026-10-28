"""CLI-Einstiegspunkt: laedt eine Konfiguration, fuehrt die Bilanz- und
LCOH-Berechnung aus und gibt das Ergebnis aus.

Aufruf:
    python -m lcoh_tool.main --config config/parameter.yaml
"""

from __future__ import annotations

import argparse

from lcoh_tool.bilanz import berechne_bilanz
from lcoh_tool.config import load_config
from lcoh_tool.erzeugungsprofil import load_erzeugungsprofil
from lcoh_tool.waermebedarf import (
    GebaeudeLastparameter,
    lastverteilung_platzhalter,
    load_waermebedarf,
)
from lcoh_tool.wirtschaftlichkeit import berechne_lcoh


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Techno-oekonomische LCOH-Analyse eines Windpark-Direktanschlusses"
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Pfad zur YAML-Konfigurationsdatei (siehe config/parameter.yaml)",
    )
    return parser.parse_args()


def run(config_pfad: str) -> None:
    config = load_config(config_pfad)

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
    ergebnis = berechne_lcoh(bilanz, config)

    print(f"Projekt: {config.projektname}")
    print(f"Jaehrliche Waermemenge: {ergebnis.jaehrliche_waermemenge_mwh:.1f} MWh")
    print(f"Kapitalkosten p.a.: {ergebnis.jahreskosten_kapital_eur:,.0f} EUR")
    print(f"Betriebskosten p.a. ({config.wirtschaft.strompreisszenario_aktiv}): "
          f"{ergebnis.jahreskosten_betrieb_eur:,.0f} EUR")
    print(f"LCOH Direktanschluss ({config.wirtschaft.strompreisszenario_aktiv}): "
          f"{ergebnis.lcoh_eur_pro_mwh:.1f} EUR/MWh")
    print("LCOH je Strompreisszenario:")
    for szenario, lcoh in ergebnis.lcoh_je_strompreisszenario_eur_pro_mwh.items():
        print(f"  - {szenario}: {lcoh:.1f} EUR/MWh")
    if ergebnis.lcoh_fossile_referenz_eur_pro_mwh is not None:
        print(
            f"LCOH fossile Referenz: {ergebnis.lcoh_fossile_referenz_eur_pro_mwh:.1f} EUR/MWh"
        )

    anteil_direktanschluss = (
        bilanz["direktanschluss_kwh"].sum()
        / (bilanz["direktanschluss_kwh"].sum() + bilanz["rueckfall_kwh"].sum())
        * 100
    )
    print(f"Anteil Direktanschluss am Strombedarf: {anteil_direktanschluss:.1f} %")


def main() -> None:
    args = parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
