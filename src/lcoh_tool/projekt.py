"""Gesamtablauf der Berechnung als wiederverwendbare Funktion.

``berechne_projekt`` fuehrt alle Schritte (Config laden, Profile einlesen,
Bilanz, LCOH) aus und gibt die Ergebnisse als Objekt zurueck - ohne etwas
auszugeben. So koennen die CLI (``main.py``) und eine spaetere GUI dieselbe
Rechnung nutzen und jeweils auf ihre Art darstellen.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from lcoh_tool.betrieb import berechne_bilanz_preisgesteuert
from lcoh_tool.bilanz import berechne_bilanz
from lcoh_tool.verfuegbarkeit import wende_verfuegbarkeit_an
from lcoh_tool.config import ToolConfig, load_config
from lcoh_tool.erzeugungsprofil import load_erzeugungsprofil
from lcoh_tool.waermebedarf import (
    GebaeudeLastparameter,
    lastverteilung_platzhalter,
    load_waermebedarf,
)
from lcoh_tool.vergleich import Vergleich, berechne_netzbezug_referenz, berechne_vergleich
from lcoh_tool.wirtschaftlichkeit import LCOHErgebnis, berechne_lcoh


@dataclass
class Kennzahlen:
    """Kennzahlen zur Plausibilitaetspruefung eines Laufs (Stundenwerte = kW)."""

    erzeugung_mwh: float
    erzeugung_spitze_kw: float
    erzeugung_volllaststunden: float  # bezogen auf die Spitzenleistung im Profil
    waermebedarf_mwh: float
    waermelast_spitze_kw: float
    strombedarf_wp_mwh: float
    strombedarf_wp_spitze_kw: float
    rueckfall_mwh: float
    rueckfall_stunden: int
    erzeugung_zu_strombedarf: float  # Faktor Erzeugung / Strombedarf WP
    hinweise: list[str]
    # Nur bei preisgesteuertem Betrieb (Block 'steuerung') belegt:
    direktleitung_stunden: int = 0
    notbetrieb_stunden: int = 0
    stunden_preis_negativ: int = 0
    direktstrom_mwh: float = 0.0
    direktstrom_kosten_eur: float = 0.0
    direktstrom_durchschnittspreis_eur_mwh: float = 0.0  # mengengewichtet
    deckungsluecke_mwh: float = 0.0


@dataclass
class ProjektErgebnis:
    config: ToolConfig
    erzeugung_kwh: pd.Series
    waermelast_kwh: pd.Series
    bilanz: pd.DataFrame
    lcoh: LCOHErgebnis
    anteil_direktanschluss_prozent: float
    kennzahlen: Kennzahlen
    vergleich: Vergleich


def berechne_kennzahlen(bilanz: pd.DataFrame, config: ToolConfig) -> Kennzahlen:
    """Kennzahlen und Hinweise, mit denen sich ein Lauf auf Plausibilitaet pruefen laesst."""
    erzeugung = bilanz["erzeugung_kwh"]
    strombedarf = bilanz["strombedarf_wp_kwh"]
    waermelast = bilanz["waermelast_kwh"]
    rueckfall = bilanz["rueckfall_kwh"]

    erzeugung_mwh = erzeugung.sum() / 1000
    spitze = float(erzeugung.max())
    strombedarf_mwh = strombedarf.sum() / 1000
    rueckfall_stunden = int((rueckfall > 1e-9).sum())
    faktor = erzeugung_mwh / strombedarf_mwh if strombedarf_mwh > 0 else float("inf")

    hinweise: list[str] = []
    if faktor > 20:
        hinweise.append(
            f"Die Windenergie ueberschreitet den Strombedarf der Waermepumpe um das "
            f"{faktor:.0f}-fache - der Windpark ist fuer dieses Waermenetz sehr gross. "
            "Sinnvoll waere ein zugeordneter Leistungsanteil des Parks."
        )
    gesteuert = config.steuerung is not None and "direktleitung_aktiv" in bilanz
    if rueckfall_stunden == 0 and not gesteuert:
        hinweise.append(
            "Kein Rueckfallstrom: Die LCOH haengt damit nicht von den Strompreisszenarien ab "
            "(Direktstrom kostet im Modell derzeit nichts)."
        )
    installiert_kw = config.waermepumpe.nennleistung_kw + config.backup.nennleistung_kw
    if not gesteuert and waermelast.max() > installiert_kw:
        hinweise.append(
            f"Die Waermespitzenlast ({waermelast.max():.0f} kW) liegt ueber den installierten "
            f"Leistungen von Waermepumpe + Backup ({installiert_kw:.0f} kW); Leistungsgrenzen "
            "werden in der Bilanz noch nicht angewendet."
        )

    extra: dict = {}
    if gesteuert:
        direkt_mwh = float(bilanz["direktanschluss_kwh"].sum() / 1000)
        kosten = float(bilanz["direktstrom_kosten_eur"].sum())
        luecke_mwh = float(bilanz["deckungsluecke_kwh"].sum() / 1000)
        extra = dict(
            direktleitung_stunden=int(bilanz["direktleitung_aktiv"].sum()),
            notbetrieb_stunden=int(bilanz["notbetrieb"].sum()),
            stunden_preis_negativ=int((bilanz["marktpreis_eur_mwh"] < 0).sum()),
            direktstrom_mwh=direkt_mwh,
            direktstrom_kosten_eur=kosten,
            direktstrom_durchschnittspreis_eur_mwh=kosten / direkt_mwh if direkt_mwh > 0 else 0.0,
            deckungsluecke_mwh=luecke_mwh,
        )
        if luecke_mwh > 0:
            hinweise.append(
                f"{luecke_mwh:,.0f} MWh Waerme bleiben ungedeckt: Leistung von Waermepumpe + "
                "Backup bzw. Speicher reichen zeitweise nicht aus."
            )
        ppa = config.ppa
        if ppa is not None and ppa.vergleichswert_eur_pro_mwh is not None \
                and ppa.preis_eur_pro_mwh < ppa.vergleichswert_eur_pro_mwh:
            hinweise.append(
                f"Der PPA-Preis ({ppa.preis_eur_pro_mwh:g} EUR/MWh) liegt unter dem Vergleichswert der WEA "
                f"({ppa.vergleichswert_eur_pro_mwh:g} EUR/MWh): Fuer den Windpark waere der PPA unattraktiv."
            )
        if bilanz["direktleitung_aktiv"].sum() == 0:
            hinweise.append(
                "Die Direktleitung wurde nie genutzt: Preisschwelle oder Preisreihe pruefen."
            )

    return Kennzahlen(
        erzeugung_mwh=float(erzeugung_mwh),
        erzeugung_spitze_kw=spitze,
        erzeugung_volllaststunden=float(erzeugung.sum() / spitze) if spitze > 0 else 0.0,
        waermebedarf_mwh=float(waermelast.sum() / 1000),
        waermelast_spitze_kw=float(waermelast.max()),
        strombedarf_wp_mwh=float(strombedarf_mwh),
        strombedarf_wp_spitze_kw=float(strombedarf.max()),
        rueckfall_mwh=float(rueckfall.sum() / 1000),
        rueckfall_stunden=rueckfall_stunden,
        erzeugung_zu_strombedarf=float(faktor),
        hinweise=hinweise,
        **extra,
    )


def gleiche_jahr_an(profil: pd.Series, ziel: pd.Series) -> pd.Series:
    """Verschiebt ein Ein-Jahres-Profil auf das Kalenderjahr von ``ziel``.

    Die Bilanz gleicht Profile ueber ihre Zeitstempel ab. Haben Erzeugung (z. B.
    Wetterjahr 2023) und Waermelast (z. B. Jahr 2027) verschiedene Jahre, gaebe
    es keine Ueberschneidung. Daher wird das Profil auf das Jahr der Waermelast
    gelegt (gleicher Tag und gleiche Stunde). Ein 29. Februar entfaellt dabei,
    wenn das Zieljahr kein Schaltjahr ist.
    """
    jahre_profil = profil.index.year.unique()
    jahre_ziel = ziel.index.year.unique()
    if len(jahre_profil) != 1 or len(jahre_ziel) != 1 or jahre_profil[0] == jahre_ziel[0]:
        return profil
    verschoben = profil.copy()
    verschoben.index = profil.index + pd.DateOffset(years=int(jahre_ziel[0] - jahre_profil[0]))
    return verschoben[~verschoben.index.duplicated(keep="first")]


def waehle_jahr(profil: pd.Series, jahr: int | None, name: str) -> pd.Series:
    """Stellt sicher, dass ein Profil genau ein Jahr enthaelt.

    Enthaelt es mehrere Jahre, wird ``jahr`` (Referenzjahr) ausgewaehlt; ohne Referenzjahr
    gibt es einen Fehler, damit nicht still mit einem falschen Zeitraum gerechnet wird.
    Ein Profil mit nur einem Jahr bleibt unveraendert (egal, welches Jahr es ist).
    """
    jahre = sorted(profil.index.year.unique())
    if len(jahre) <= 1:
        return profil
    if jahr is None:
        raise ValueError(
            f"{name} enthaelt mehrere Jahre {jahre}: bitte ein 'referenzjahr' in der Config setzen."
        )
    if jahr not in jahre:
        raise ValueError(f"{name} enthaelt das Referenzjahr {jahr} nicht (vorhanden: {jahre}).")
    return profil[profil.index.year == jahr]


def wende_referenzjahr_an(config: ToolConfig) -> ToolConfig:
    """Uebertraegt das Referenzjahr auf Windpark-Wetter (windpowerlib) und lpagg-Wetterjahr.

    Gibt eine Kopie zurueck; ohne Referenzjahr bleibt die Config unveraendert.
    """
    if config.referenzjahr is None:
        return config
    import copy

    cfg = copy.deepcopy(config)
    if cfg.windpark.windpowerlib is not None:
        cfg.windpark.windpowerlib.jahr = cfg.referenzjahr
    if cfg.waermebedarf.lpagg is not None and cfg.waermebedarf.lpagg.wetterjahr is None:
        cfg.waermebedarf.lpagg.wetterjahr = cfg.referenzjahr
    return cfg


def lade_erzeugung(config: ToolConfig) -> pd.Series:
    """Erzeugungsprofil je nach ``windpark.quelle`` (CSV oder windpowerlib)."""
    windpark = config.windpark
    if windpark.quelle == "windpowerlib":
        if windpark.windpowerlib is None:
            raise ValueError("windpark.quelle 'windpowerlib' braucht den Block 'windpowerlib'.")
        from lcoh_tool.windpark import erzeuge_windprofil

        return erzeuge_windprofil(windpark.windpowerlib)
    if windpark.erzeugungsprofil_pfad is None:
        raise ValueError("Kein erzeugungsprofil_pfad (CSV) in der Config gesetzt.")
    return load_erzeugungsprofil(windpark.erzeugungsprofil_pfad, windpark.windpro_block)


def lade_waermelast(config: ToolConfig) -> pd.Series:
    """Waermelast: CSV (Pfad/Upload) vor lpagg vor Jahreswert-Platzhalter."""
    bedarf = config.waermebedarf
    if bedarf.waermelast_pfad:
        return load_waermebedarf(bedarf.waermelast_pfad)
    if bedarf.lpagg is not None:
        from lcoh_tool.lastprofil_lpagg import erzeuge_waermelast_lpagg

        standort = None
        wp = config.windpark.windpowerlib
        if wp is not None:
            standort = (wp.breitengrad, wp.laengengrad, wp.jahr)
        return erzeuge_waermelast_lpagg(
            bedarf.lpagg,
            jahreswaermebedarf_mwh=bedarf.jahreswaermebedarf_mwh,
            wetter_standort=standort,
        )
    if bedarf.jahreswaermebedarf_mwh:
        parameter = GebaeudeLastparameter(
            gesamtwaermebedarf_mwh=bedarf.jahreswaermebedarf_mwh,
            anzahl_gebaeude=bedarf.anzahl_gebaeude or 1,
        )
        return lastverteilung_platzhalter(parameter)
    raise ValueError(
        "Keine Waermelast-Quelle in der Config: waermelast_pfad, lpagg oder "
        "jahreswaermebedarf_mwh setzen."
    )


def lade_marktpreisreihe(config: ToolConfig) -> pd.Series:
    """Day-Ahead-Preise des ``referenzjahr`` von ENTSO-E (mit Cache, siehe marktpreise_abruf)."""
    st = config.steuerung
    if config.referenzjahr is None:
        raise ValueError("Die Marktpreise kommen von ENTSO-E und brauchen ein referenzjahr.")
    from lcoh_tool.marktpreise_abruf import lade_preise_mit_cache

    return lade_preise_mit_cache(config.referenzjahr, st.marktpreis_zone, st.marktpreis_cache_ordner)


def berechne_projekt(
    config: ToolConfig | str | Path,
    erzeugungsprofil: pd.Series | None = None,
    waermelastprofil: pd.Series | None = None,
    marktpreisprofil: pd.Series | None = None,
) -> ProjektErgebnis:
    """Fuehrt die komplette Berechnung aus.

    ``config`` ist entweder ein bereits gebautes ``ToolConfig`` (z. B. aus
    einer GUI) oder der Pfad zu einer YAML-Datei. Mit ``erzeugungsprofil`` /
    ``waermelastprofil`` lassen sich fertige Zeitreihen direkt vorgeben; dann
    werden die jeweiligen Quellen der Config uebergangen. Ist in der Config ein
    Block ``steuerung`` gesetzt, laeuft die preisgesteuerte Betriebsweise
    (``betrieb.py``) mit den Marktpreisen aus ``marktpreisprofil`` bzw. der CSV.
    """
    if not isinstance(config, ToolConfig):
        config = load_config(config)
    config = wende_referenzjahr_an(config)

    erzeugung = erzeugungsprofil if erzeugungsprofil is not None else lade_erzeugung(config)
    waermelast = waermelastprofil if waermelastprofil is not None else lade_waermelast(config)
    erzeugung = waehle_jahr(erzeugung, config.referenzjahr, "Erzeugungsprofil")
    waermelast = waehle_jahr(waermelast, None, "Waermelastprofil")
    erzeugung = gleiche_jahr_an(erzeugung, waermelast)
    wp = config.windpark
    erzeugung = wende_verfuegbarkeit_an(erzeugung, wp.verfuegbarkeit, wp.ausfall_dauer_h, wp.ausfall_seed)

    if config.steuerung is not None:
        if config.ppa is not None:  # fester PPA-Preis: keine Marktpreisreihe noetig
            marktpreis = pd.Series(config.ppa.preis_eur_pro_mwh, index=waermelast.index, dtype=float)
        else:
            marktpreis = (
                marktpreisprofil
                if marktpreisprofil is not None
                else lade_marktpreisreihe(config)
            )
            marktpreis = waehle_jahr(marktpreis, config.referenzjahr, "Marktpreisreihe")
            marktpreis = gleiche_jahr_an(marktpreis, waermelast)
        bilanz = berechne_bilanz_preisgesteuert(erzeugung, waermelast, marktpreis, config)
    else:
        bilanz = berechne_bilanz(erzeugung, waermelast, config)
    lcoh = berechne_lcoh(bilanz, config)
    vergleich = berechne_vergleich(lcoh, berechne_netzbezug_referenz(waermelast, config), config, bilanz)

    direkt = bilanz["direktanschluss_kwh"].sum()
    gesamt = direkt + bilanz["rueckfall_kwh"].sum()
    anteil = direkt / gesamt * 100 if gesamt > 0 else 0.0

    return ProjektErgebnis(
        config=config,
        erzeugung_kwh=erzeugung,
        waermelast_kwh=waermelast,
        bilanz=bilanz,
        lcoh=lcoh,
        anteil_direktanschluss_prozent=anteil,
        kennzahlen=berechne_kennzahlen(bilanz, config),
        vergleich=vergleich,
    )
