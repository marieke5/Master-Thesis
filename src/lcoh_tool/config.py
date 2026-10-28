"""Konfiguration des Tools: Laden und Validieren der Eingabeparameter aus
einer YAML-Datei in strukturierte, typisierte Dataclasses.

Die Parameter orientieren sich am aktuellen Stand der Masterarbeit
(Erstgespraech Green Wind): Windpark-Input, Waermeerzeuger-Konfiguration,
wirtschaftliche und regulatorische Parameter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import yaml

BackupTyp = Literal["elektrodenkessel", "gaskessel"]
Strompreisszenario = Literal["best_case", "realistisch", "worst_case"]


@dataclass
class WindparkConfig:
    """Input des Windparks als Blackbox-Energiequelle."""

    erzeugungsprofil_pfad: str  # CSV, stundenscharf, 8760 Werte


@dataclass
class WaermebedarfConfig:
    """Input der Waermelast.

    Zwei Wege, siehe waermebedarf.py:
    1. ``waermelast_pfad``: eine bereits vorliegende stundenscharfe CSV-Zeitreihe.
    2. ``jahreswaermebedarf_mwh`` (+ optional ``anzahl_gebaeude``): Gesamtwaermebedarf,
       der ueber eine im Tool hinterlegte Lastverteilung auf Stunden verteilt wird.
       Diese Lastverteilung ist aktuell ein Platzhalter und soll durch ein
       Referenzprofil aus der App nPro ersetzt werden, sobald der Export vorliegt.
    """

    waermelast_pfad: Optional[str] = None  # CSV, stundenscharf, falls vorhanden
    jahreswaermebedarf_mwh: Optional[float] = None  # Fallback: Jahreswert + Lastverteilung
    anzahl_gebaeude: Optional[int] = None  # fuer die (noch zu ergaenzende) nPro-Lastverteilung
    lastprofil_typ: Optional[str] = None  # z. B. "VDI4655" (fuer spaetere Erweiterung)


@dataclass
class WaermepumpeConfig:
    jazl: float  # Jahresarbeitszahl (COP im Jahresmittel)
    nennleistung_kw: float


@dataclass
class BackupConfig:
    typ: BackupTyp
    wirkungsgrad: float  # z. B. 0.98 fuer Elektrodenkessel, 0.9 fuer Gaskessel
    nennleistung_kw: float


@dataclass
class SpeicherConfig:
    kapazitaet_kwh: float
    verlust_pro_stunde: float = 0.0  # Anteil Speicherverlust je Stunde (0..1)


@dataclass
class Strompreisszenarien:
    """Drei Preispfade fuer den Rueckfall-Netzbezug, zur Auswahl/zum Vergleich.

    Die Netzentgelte selbst (``WirtschaftConfig.netzentgelt_eur_pro_mwh``) sind
    davon unabhaengig und kommen in allen drei Szenarien gleich oben drauf.
    """

    best_case_eur_pro_mwh: float
    realistisch_eur_pro_mwh: float
    worst_case_eur_pro_mwh: float

    def preis(self, szenario: Strompreisszenario) -> float:
        return {
            "best_case": self.best_case_eur_pro_mwh,
            "realistisch": self.realistisch_eur_pro_mwh,
            "worst_case": self.worst_case_eur_pro_mwh,
        }[szenario]


@dataclass
class WirtschaftConfig:
    wacc: float  # gewichtete Kapitalkosten, z. B. 0.05
    abschreibungsdauer_jahre: int
    strompreisszenarien: Strompreisszenarien
    netzentgelt_eur_pro_mwh: float
    strompreisszenario_aktiv: Strompreisszenario = "realistisch"
    gaspreis_eur_pro_mwh: Optional[float] = None
    capex_waermepumpe_eur: float = 0.0
    capex_backup_eur: float = 0.0
    capex_speicher_eur: float = 0.0
    capex_anschluss_eur: float = 0.0  # Direktleitung/Anschlusskosten
    opex_fix_eur_pro_jahr: float = 0.0


@dataclass
class RegulatorikConfig:
    netzentgeltbefreiung_direktanschluss: bool = True


@dataclass
class FossileReferenzConfig:
    """Optionaler Vergleichsoutput: LCOH der fossilen Referenzversorgung."""

    aktiv: bool = False
    wirkungsgrad_kessel: float = 0.9
    brennstoffpreis_eur_pro_mwh: float = 0.0
    capex_eur: float = 0.0


@dataclass
class ToolConfig:
    projektname: str
    windpark: WindparkConfig
    waermebedarf: WaermebedarfConfig
    waermepumpe: WaermepumpeConfig
    backup: BackupConfig
    speicher: SpeicherConfig
    wirtschaft: WirtschaftConfig
    regulatorik: RegulatorikConfig = field(default_factory=RegulatorikConfig)
    fossile_referenz: FossileReferenzConfig = field(default_factory=FossileReferenzConfig)


def load_config(pfad: str | Path) -> ToolConfig:
    """Laedt eine YAML-Konfigurationsdatei und baut daraus ein ToolConfig-Objekt.

    Wirft ``FileNotFoundError`` bzw. ``KeyError``, wenn die Datei fehlt oder
    Pflichtfelder nicht gesetzt sind.
    """
    pfad = Path(pfad)
    if not pfad.exists():
        raise FileNotFoundError(f"Konfigurationsdatei nicht gefunden: {pfad}")

    with pfad.open("r", encoding="utf-8") as f:
        rohdaten = yaml.safe_load(f)

    wirtschaft_rohdaten = dict(rohdaten["wirtschaft"])
    strompreisszenarien = Strompreisszenarien(
        **wirtschaft_rohdaten.pop("strompreisszenarien")
    )

    return ToolConfig(
        projektname=rohdaten["projektname"],
        windpark=WindparkConfig(**rohdaten["windpark"]),
        waermebedarf=WaermebedarfConfig(**rohdaten.get("waermebedarf", {})),
        waermepumpe=WaermepumpeConfig(**rohdaten["waermepumpe"]),
        backup=BackupConfig(**rohdaten["backup"]),
        speicher=SpeicherConfig(**rohdaten["speicher"]),
        wirtschaft=WirtschaftConfig(
            strompreisszenarien=strompreisszenarien, **wirtschaft_rohdaten
        ),
        regulatorik=RegulatorikConfig(**rohdaten.get("regulatorik", {})),
        fossile_referenz=FossileReferenzConfig(**rohdaten.get("fossile_referenz", {})),
    )
