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


@dataclass
class WindparkConfig:
    """Input des Windparks als Blackbox-Energiequelle."""

    erzeugungsprofil_pfad: str  # CSV, stundenscharf, 8760 Werte


@dataclass
class WaermebedarfConfig:
    """Input der Waermelast."""

    waermelast_pfad: Optional[str] = None  # CSV, stundenscharf, falls vorhanden
    jahreswaermebedarf_mwh: Optional[float] = None  # Fallback: Jahreswert + Profiltyp
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
class WirtschaftConfig:
    wacc: float  # gewichtete Kapitalkosten, z. B. 0.05
    abschreibungsdauer_jahre: int
    strompreis_rueckfall_eur_pro_mwh: float
    netzentgelt_eur_pro_mwh: float
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

    return ToolConfig(
        projektname=rohdaten["projektname"],
        windpark=WindparkConfig(**rohdaten["windpark"]),
        waermebedarf=WaermebedarfConfig(**rohdaten.get("waermebedarf", {})),
        waermepumpe=WaermepumpeConfig(**rohdaten["waermepumpe"]),
        backup=BackupConfig(**rohdaten["backup"]),
        speicher=SpeicherConfig(**rohdaten["speicher"]),
        wirtschaft=WirtschaftConfig(**rohdaten["wirtschaft"]),
        regulatorik=RegulatorikConfig(**rohdaten.get("regulatorik", {})),
        fossile_referenz=FossileReferenzConfig(**rohdaten.get("fossile_referenz", {})),
    )
