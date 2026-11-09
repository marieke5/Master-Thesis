"""Vergleich: Direktleitung (+ Netzbezug) gegen reinen Netzbezug.

Variante A (Referenz, ``berechne_netzbezug_referenz``): Der Waermeerzeuger bezieht den
gesamten Strom aus dem Netz. Es gibt keine Direktleitung und keine preisgesteuerte
Betriebsweise. Der Waermespeicher gehoert zur Waermeversorgung und ist in beiden
Varianten gleich (gleiche Investition, kein Einfluss auf den Strombezug in A).
Investition = Waermepumpe + Backup + Speicher + Netzanschluss; Betriebskosten = Fixkosten + Strom * (Szenariopreis + Netzentgelt +
Abgaben) plus Leistungspreis auf die Jahreshoechstlast des Strombezugs. Die Waermepumpe wird vor dem Elektrodenkessel eingesetzt; die Leistungsgrenzen
gelten wie im Direktleitungs-Fall.

Variante B ist das Ergebnis der normalen Rechnung (``wirtschaftlichkeit.berechne_lcoh``).

``berechne_vergleich`` stellt beide je Strompreisszenario gegenueber und bestimmt die
**Break-even-Leitungskosten**: die Investition in die Direktleitung (``capex_anschluss_eur``),
bei der B und A gleich teuer sind. Die LCOH ist linear in dieser Investition, daher gilt
exakt: x = capex_anschluss + (LCOH_A - LCOH_B) * Waermemenge / Annuitaetsfaktor.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from lcoh_tool.config import ToolConfig
from lcoh_tool.wirtschaftlichkeit import LCOHErgebnis, annuitaetsfaktor

SZENARIEN = ("best_case", "realistisch", "worst_case")


@dataclass
class NetzbezugReferenz:
    lcoh_je_strompreisszenario_eur_pro_mwh: dict[str, float]
    strombedarf_mwh: float
    jahreskosten_kapital_eur: float
    ungedeckt_mwh: float  # Waerme, die WP + Backup (Leistungsgrenzen) nicht liefern
    netzbezug_spitze_kw: float = 0.0  # Jahreshoechstlast des Strombezugs in Variante A
    leistungspreis_kosten_eur: float = 0.0


@dataclass
class Vergleich:
    """Direktleitung (B) gegen reinen Netzbezug (A), je Strompreisszenario."""

    lcoh_direktleitung_eur_pro_mwh: dict[str, float]
    lcoh_netzbezug_eur_pro_mwh: dict[str, float]
    vorteil_direktleitung_eur_pro_mwh: dict[str, float]  # A - B; positiv = Direktleitung guenstiger
    breakeven_leitungskosten_eur: dict[str, float]  # max. tragbare Investition Direktleitung
    leitungskosten_aktuell_eur: float
    szenario_aktiv: str
    direktleitung_lohnt_sich: bool  # fuer das aktive Szenario (mit PPA: gegen PPA ueber das Netz)
    referenz: NetzbezugReferenz
    # Nur mit PPA (config.ppa): Fall 2 = PPA ueber das Netz (gleicher Betrieb wie B, aber mit
    # Netzentgelt, Abgaben, Sleeving und Leistungspreis auf den PPA-Strom, ohne Leitung).
    lcoh_ppa_netz_eur_pro_mwh: dict[str, float] | None = None
    vorteil_vs_ppa_netz_eur_pro_mwh: dict[str, float] | None = None  # Fall 2 - Fall 3
    breakeven_vs_ppa_netz_eur: dict[str, float] | None = None
    ppa_netz_spitze_kw: float = 0.0


def berechne_netzbezug_referenz(waermelast_kwh: pd.Series, config: ToolConfig) -> NetzbezugReferenz:
    """LCOH der Variante A (reiner Netzbezug) fuer alle drei Strompreisszenarien."""
    w = config.wirtschaft
    p_wp = config.waermepumpe.nennleistung_kw
    p_bk = config.backup.nennleistung_kw

    last = waermelast_kwh.clip(lower=0)
    waerme_wp = last.clip(upper=p_wp)
    waerme_bk = (last - waerme_wp).clip(upper=p_bk)
    ungedeckt_kwh = float((last - waerme_wp - waerme_bk).sum())
    strom_h = waerme_wp / config.waermepumpe.jazl + waerme_bk / config.backup.wirkungsgrad
    strom_kwh = float(strom_h.sum())
    spitze_kw = float(strom_h.max()) if len(strom_h) else 0.0
    leistungskosten = spitze_kw * w.leistungspreis_eur_pro_kw_a
    strom_mwh = strom_kwh / 1000

    waermemenge_mwh = float(last.sum() / 1000)
    capex = (
        w.capex_waermepumpe_eur
        + w.capex_backup_eur
        + w.capex_speicher_eur
        + w.capex_netzanschluss_eur
    )
    kapital = capex * annuitaetsfaktor(w.wacc, w.abschreibungsdauer_jahre)

    lcoh = {}
    for szenario in SZENARIEN:
        preis = w.strompreisszenarien.preis(szenario) + w.netzentgelt_eur_pro_mwh + w.abgaben_eur_pro_mwh
        lcoh[szenario] = (kapital + w.opex_fix_eur_pro_jahr + leistungskosten + strom_mwh * preis) / waermemenge_mwh
    return NetzbezugReferenz(
        lcoh_je_strompreisszenario_eur_pro_mwh=lcoh,
        strombedarf_mwh=strom_mwh,
        jahreskosten_kapital_eur=kapital,
        ungedeckt_mwh=ungedeckt_kwh / 1000,
        netzbezug_spitze_kw=spitze_kw,
        leistungspreis_kosten_eur=leistungskosten,
    )


def berechne_ppa_ueber_netz(bilanz: pd.DataFrame, config: ToolConfig) -> tuple[dict[str, float], float]:
    """Fall 2: PPA ueber das Netz. Gleicher Betrieb (Bilanz) wie mit Direktleitung, aber der
    PPA-Strom zahlt zusaetzlich Netzentgelt, Abgaben und Sleeving, der Leistungspreis gilt auf
    die Spitze des gesamten Strombezugs, und es gibt keine Leitungskosten.
    Gibt die LCOH je Szenario und die Netzspitze (kW) zurueck."""
    w, ppa = config.wirtschaft, config.ppa
    q_mwh = float(bilanz["waermelast_kwh"].sum() / 1000)
    capex = w.capex_waermepumpe_eur + w.capex_backup_eur + w.capex_speicher_eur + w.capex_netzanschluss_eur
    kapital = capex * annuitaetsfaktor(w.wacc, w.abschreibungsdauer_jahre)
    direkt_mwh = float(bilanz["direktanschluss_kwh"].sum() / 1000)
    rueck_mwh = float(bilanz["rueckfall_kwh"].sum() / 1000)
    spitze = float((bilanz["direktanschluss_kwh"] + bilanz["rueckfall_kwh"]).max()) if len(bilanz) else 0.0
    ppa_preis = ppa.preis_eur_pro_mwh + w.netzentgelt_eur_pro_mwh + w.abgaben_eur_pro_mwh + ppa.sleeving_eur_pro_mwh
    lcoh = {}
    for s in SZENARIEN:
        rueck_preis = w.strompreisszenarien.preis(s) + w.netzentgelt_eur_pro_mwh + w.abgaben_eur_pro_mwh
        kosten = (
            w.opex_fix_eur_pro_jahr + direkt_mwh * ppa_preis + rueck_mwh * rueck_preis
            + spitze * w.leistungspreis_eur_pro_kw_a
        )
        lcoh[s] = (kapital + kosten) / q_mwh
    return lcoh, spitze


def berechne_vergleich(
    lcoh_b: LCOHErgebnis, referenz: NetzbezugReferenz, config: ToolConfig,
    bilanz: pd.DataFrame | None = None,
) -> Vergleich:
    """Stellt Direktleitung (B) und Netzbezug (A) gegenueber und bestimmt den Break-even."""
    w = config.wirtschaft
    af = annuitaetsfaktor(w.wacc, w.abschreibungsdauer_jahre)
    q = lcoh_b.jaehrliche_waermemenge_mwh

    b = dict(lcoh_b.lcoh_je_strompreisszenario_eur_pro_mwh)
    a = dict(referenz.lcoh_je_strompreisszenario_eur_pro_mwh)
    vorteil = {s: a[s] - b[s] for s in SZENARIEN}
    breakeven = {s: w.capex_anschluss_eur + vorteil[s] * q / af for s in SZENARIEN}
    aktiv = w.strompreisszenario_aktiv
    ppa_netz = vorteil_ppa = breakeven_ppa = None
    spitze_ppa = 0.0
    lohnt = bool(vorteil[aktiv] > 0)
    if config.ppa is not None and bilanz is not None:
        ppa_netz, spitze_ppa = berechne_ppa_ueber_netz(bilanz, config)
        vorteil_ppa = {s: ppa_netz[s] - b[s] for s in SZENARIEN}
        breakeven_ppa = {s: w.capex_anschluss_eur + vorteil_ppa[s] * q / af for s in SZENARIEN}
        lohnt = bool(vorteil_ppa[aktiv] > 0)
    return Vergleich(
        lcoh_direktleitung_eur_pro_mwh=b,
        lcoh_netzbezug_eur_pro_mwh=a,
        vorteil_direktleitung_eur_pro_mwh=vorteil,
        breakeven_leitungskosten_eur=breakeven,
        leitungskosten_aktuell_eur=w.capex_anschluss_eur,
        szenario_aktiv=aktiv,
        direktleitung_lohnt_sich=lohnt,
        referenz=referenz,
        lcoh_ppa_netz_eur_pro_mwh=ppa_netz,
        vorteil_vs_ppa_netz_eur_pro_mwh=vorteil_ppa,
        breakeven_vs_ppa_netz_eur=breakeven_ppa,
        ppa_netz_spitze_kw=spitze_ppa,
    )
