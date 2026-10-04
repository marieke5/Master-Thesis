"""Wirtschaftlichkeitsberechnung: Annuitaet, Betriebskosten und LCOH.

LCOH (Levelized Cost of Heat) = (Annuitaet der Investition + jaehrliche
Betriebskosten) / jaehrlich erzeugte Waermemenge.

Die Berechnung ist bewusst modular gehalten (eigene Funktionen fuer
Annuitaetsfaktor, Investitions- und Betriebskosten, LCOH), damit einzelne
Bausteine spaeter unabhaengig verfeinert werden koennen (z. B. detailliertere
CAPEX-Aufschluesselung, Preissteigerungsraten).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from lcoh_tool.config import ToolConfig


def annuitaetsfaktor(wacc: float, laufzeit_jahre: int) -> float:
    """Kapitalwiedergewinnungsfaktor fuer gegebenen Zinssatz und Laufzeit."""
    if wacc == 0:
        return 1 / laufzeit_jahre
    return (wacc * (1 + wacc) ** laufzeit_jahre) / ((1 + wacc) ** laufzeit_jahre - 1)


@dataclass
class LCOHErgebnis:
    lcoh_eur_pro_mwh: float
    jahreskosten_kapital_eur: float
    jahreskosten_betrieb_eur: float
    jaehrliche_waermemenge_mwh: float
    lcoh_fossile_referenz_eur_pro_mwh: float | None = None


def berechne_lcoh(bilanz: pd.DataFrame, config: ToolConfig) -> LCOHErgebnis:
    """Berechnet die LCOH der Direktanschluss-Versorgung aus der Jahresbilanz.

    ``bilanz`` ist das Ergebnis von ``bilanz.berechne_bilanz`` und enthaelt
    u. a. die Spalten ``waermelast_kwh``, ``direktanschluss_kwh`` und
    ``rueckfall_kwh``.
    """
    wirtschaft = config.wirtschaft

    capex_gesamt = (
        wirtschaft.capex_waermepumpe_eur
        + wirtschaft.capex_backup_eur
        + wirtschaft.capex_speicher_eur
        + wirtschaft.capex_anschluss_eur
    )
    af = annuitaetsfaktor(wirtschaft.wacc, wirtschaft.abschreibungsdauer_jahre)
    jahreskosten_kapital = capex_gesamt * af

    rueckfall_kwh = bilanz["rueckfall_kwh"].sum()
    kosten_rueckfallstrom = rueckfall_kwh / 1000 * (
        wirtschaft.strompreis_rueckfall_eur_pro_mwh
        + wirtschaft.netzentgelt_eur_pro_mwh
    )
    jahreskosten_betrieb = wirtschaft.opex_fix_eur_pro_jahr + kosten_rueckfallstrom

    jaehrliche_waermemenge_mwh = bilanz["waermelast_kwh"].sum() / 1000

    lcoh = (jahreskosten_kapital + jahreskosten_betrieb) / jaehrliche_waermemenge_mwh

    lcoh_referenz = None
    if config.fossile_referenz.aktiv:
        lcoh_referenz = _berechne_lcoh_fossile_referenz(
            jaehrliche_waermemenge_mwh, config
        )

    return LCOHErgebnis(
        lcoh_eur_pro_mwh=lcoh,
        jahreskosten_kapital_eur=jahreskosten_kapital,
        jahreskosten_betrieb_eur=jahreskosten_betrieb,
        jaehrliche_waermemenge_mwh=jaehrliche_waermemenge_mwh,
        lcoh_fossile_referenz_eur_pro_mwh=lcoh_referenz,
    )


def _berechne_lcoh_fossile_referenz(
    jaehrliche_waermemenge_mwh: float, config: ToolConfig
) -> float:
    """Vereinfachte LCOH-Berechnung fuer die fossile Referenzversorgung
    (aktueller Gas-/Oelkessel-Betrieb) als optionaler Vergleichsoutput."""
    referenz = config.fossile_referenz
    wirtschaft = config.wirtschaft

    af = annuitaetsfaktor(wirtschaft.wacc, wirtschaft.abschreibungsdauer_jahre)
    jahreskosten_kapital = referenz.capex_eur * af

    brennstoffbedarf_mwh = jaehrliche_waermemenge_mwh / referenz.wirkungsgrad_kessel
    jahreskosten_brennstoff = (
        brennstoffbedarf_mwh * referenz.brennstoffpreis_eur_pro_mwh
    )

    return (jahreskosten_kapital + jahreskosten_brennstoff) / jaehrliche_waermemenge_mwh
