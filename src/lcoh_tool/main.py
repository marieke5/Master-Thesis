"""CLI-Einstiegspunkt: laedt eine Konfiguration, fuehrt die Berechnung aus
(siehe ``projekt.berechne_projekt``) und gibt das Ergebnis aus.

Aufruf:
    python -m lcoh_tool.main --config config/parameter.yaml
"""

from __future__ import annotations

import argparse

from lcoh_tool.projekt import ProjektErgebnis, berechne_projekt


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


def zeige_ergebnis(ergebnis: ProjektErgebnis) -> None:
    """Gibt ein ``ProjektErgebnis`` auf der Konsole aus."""
    config = ergebnis.config
    lcoh = ergebnis.lcoh
    aktiv = config.wirtschaft.strompreisszenario_aktiv

    print(f"Projekt: {config.projektname}")
    print(f"Jaehrliche Waermemenge: {lcoh.jaehrliche_waermemenge_mwh:.1f} MWh")
    print(f"Kapitalkosten p.a.: {lcoh.jahreskosten_kapital_eur:,.0f} EUR")
    print(f"Betriebskosten p.a. ({aktiv}): {lcoh.jahreskosten_betrieb_eur:,.0f} EUR")
    print(f"LCOH Direktanschluss ({aktiv}): {lcoh.lcoh_eur_pro_mwh:.1f} EUR/MWh")
    print("LCOH je Strompreisszenario:")
    for szenario, wert in lcoh.lcoh_je_strompreisszenario_eur_pro_mwh.items():
        print(f"  - {szenario}: {wert:.1f} EUR/MWh")
    if lcoh.lcoh_fossile_referenz_eur_pro_mwh is not None:
        print(f"LCOH fossile Referenz: {lcoh.lcoh_fossile_referenz_eur_pro_mwh:.1f} EUR/MWh")
    print(
        f"Anteil Direktanschluss am Strombedarf: "
        f"{ergebnis.anteil_direktanschluss_prozent:.1f} %"
    )

    k = ergebnis.kennzahlen
    print("Kennzahlen zur Plausibilitaet:")
    print(f"  Windstrom: {k.erzeugung_mwh:,.0f} MWh/a, Spitze {k.erzeugung_spitze_kw:,.0f} kW, "
          f"{k.erzeugung_volllaststunden:,.0f} Volllaststunden")
    print(f"  Waermebedarf: {k.waermebedarf_mwh:,.0f} MWh/a, Spitzenlast {k.waermelast_spitze_kw:,.0f} kW")
    print(f"  Strombedarf Waermepumpe: {k.strombedarf_wp_mwh:,.0f} MWh/a, "
          f"Spitze {k.strombedarf_wp_spitze_kw:,.0f} kW")
    print(f"  Rueckfallstrom: {k.rueckfall_mwh:,.1f} MWh/a in {k.rueckfall_stunden} Stunden")
    if ergebnis.config.steuerung is not None:
        st = ergebnis.config.steuerung
        print(f"Preisgesteuerte Direktleitung (Schwelle {st.preisschwelle_eur_pro_mwh:g} EUR/MWh):")
        print(f"  Direktleitung aktiv: {k.direktleitung_stunden} h, davon Notbetrieb "
              f"{k.notbetrieb_stunden} h; Stunden mit negativem Preis im Jahr: "
              f"{k.stunden_preis_negativ} h")
        print(f"  Direktstrom: {k.direktstrom_mwh:,.0f} MWh, Kosten {k.direktstrom_kosten_eur:,.0f} EUR "
              f"(Durchschnitt {k.direktstrom_durchschnittspreis_eur_mwh:.1f} EUR/MWh)")
        if k.deckungsluecke_mwh > 0:
            print(f"  Ungedeckte Waerme: {k.deckungsluecke_mwh:,.1f} MWh")
    for hinweis in k.hinweise:
        print(f"  Hinweis: {hinweis}")


def run(config_pfad: str) -> ProjektErgebnis:
    ergebnis = berechne_projekt(config_pfad)
    zeige_ergebnis(ergebnis)
    return ergebnis


def main() -> None:
    args = parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
