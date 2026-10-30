"""Konfiguration des Tools: Laden und Validieren der Eingabeparameter aus
einer YAML-Datei in strukturierte, typisierte Dataclasses.

Die Parameter orientieren sich am aktuellen Stand der Masterarbeit
(Erstgespraech Green Wind): Windpark-Input, Waermeerzeuger-Konfiguration,
wirtschaftliche und regulatorische Parameter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

import yaml

BackupTyp = Literal["elektrodenkessel"]  # gaskessel: fuer eine spaetere Version vorgesehen
Strompreisszenario = Literal["best_case", "realistisch", "worst_case"]


Wetterquelle = Literal["open_meteo", "era5", "csv"]


@dataclass
class WindpowerlibConfig:
    """Parameter fuer die Schnellabschaetzung des Erzeugungsprofils mit
    windpowerlib (siehe ``windpark.py``). Ersetzt kein Ertragsgutachten."""

    breitengrad: float
    laengengrad: float
    jahr: int = 2023  # Wetterjahr
    anlagentyp: str = "E-141/4200"  # Name aus der windpowerlib-Anlagendatenbank
    nabenhoehe_m: float = 129.0
    anzahl_anlagen: int = 1
    parkwirkungsgrad: float = 0.9  # pauschale Abschattungs-/Parkverluste (0..1)
    rauigkeitslaenge_m: float = 0.15
    # era5 (Copernicus CDS) erlaubt nach Lizenz auch kommerzielle Nutzung;
    # open_meteo ist in der kostenlosen Variante nur nicht-kommerziell nutzbar.
    wetterquelle: Wetterquelle = "era5"
    wetter_pfad: Optional[str] = None  # nur bei wetterquelle "csv"
    wind_messhoehe_m: float = 100.0  # Hoehe der Windgeschwindigkeit in der Wetter-CSV
    wetter_cache_ordner: Optional[str] = "data/wetter_cache"


@dataclass
class WindparkConfig:
    """Input des Windparks.

    ``quelle="csv"``: extern erstelltes Erzeugungsprofil (z. B. Ertragsgutachten),
    stundenscharf (8760 Werte), Pfad in ``erzeugungsprofil_pfad``.
    ``quelle="windpowerlib"``: Schnellabschaetzung aus Wetterdaten, siehe
    ``WindpowerlibConfig``.
    """

    erzeugungsprofil_pfad: Optional[Any] = None  # CSV-Pfad oder hochgeladene Datei
    quelle: Literal["csv", "windpowerlib"] = "csv"
    windpowerlib: Optional[WindpowerlibConfig] = None


@dataclass
class GebaeudetypConfig:
    """Ein Gebaeudetyp fuer lpagg (VDI 4655 / BDEW), ggf. mit mehreren Kopien."""

    house_type: str  # "EFH", "MFH" oder BDEW-Typ wie "GHD/G1", "GHA/G4"
    q_heiz_a_kwh: float  # jaehrlicher Heizenergieverbrauch je Gebaeude
    anzahl: int = 1  # Anzahl identischer Gebaeude ("copies" in lpagg)
    q_tww_a_kwh: Any = "calculate"  # Trinkwarmwasser je Gebaeude oder "calculate"
    w_a_kwh: Any = "calculate"  # Strombedarf je Gebaeude oder "calculate" (hier ohne Einfluss)
    q_kalt_a_kwh: Optional[float] = None  # Kaeltebedarf (nur Gewerbe, hier ohne Einfluss)
    n_pers: int = 0
    n_we: int = 0  # Wohneinheiten
    sigma: int = 0  # Zeitverschiebung der Kopien (Gleichzeitigkeit), in Zeitschritten


@dataclass
class LpaggConfig:
    """Waermelast aus Gebaeudetypen ueber lpagg (siehe ``lastprofil_lpagg.py``)."""

    gebaeude: dict[str, GebaeudetypConfig]
    try_region: int = 4  # DWD-Testreferenzjahr 2010, Region 1..15 (4 = Potsdam)
    jahr: int = 2027
    sommer_temperaturgrenze_c: float = 12.0
    wetter_pfad: Optional[str] = None  # eigene DWD-TRY-Datei statt der mitgelieferten
    feiertage_land: str = "DE"
    feiertage_bundesland: Optional[str] = "SH"


@dataclass
class WaermebedarfConfig:
    """Input der Waermelast.

    Drei Wege, siehe waermebedarf.py (Prioritaet in dieser Reihenfolge):
    1. ``waermelast_pfad``: eine bereits vorliegende stundenscharfe CSV-Zeitreihe
       (Pfad oder hochgeladene Datei).
    2. ``lpagg``: Gebaeudetypen und -anzahl, Profil ueber lpagg (VDI 4655/BDEW).
    3. ``jahreswaermebedarf_mwh``: Gesamtwaermebedarf mit einfachem Platzhalter-
       Muster (saisonal), ohne Gebaeudebezug.
    """

    waermelast_pfad: Optional[Any] = None  # CSV-Pfad oder hochgeladene Datei
    lpagg: Optional[LpaggConfig] = None
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
    wirkungsgrad: float  # z. B. 0.98 fuer Elektrodenkessel
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

    windpark_rohdaten = dict(rohdaten["windpark"])
    if windpark_rohdaten.get("windpowerlib") is not None:
        windpark_rohdaten["windpowerlib"] = WindpowerlibConfig(
            **windpark_rohdaten["windpowerlib"]
        )

    waermebedarf_rohdaten = dict(rohdaten.get("waermebedarf") or {})
    if waermebedarf_rohdaten.get("lpagg") is not None:
        lpagg_rohdaten = dict(waermebedarf_rohdaten["lpagg"])
        lpagg_rohdaten["gebaeude"] = {
            name: GebaeudetypConfig(**werte)
            for name, werte in lpagg_rohdaten["gebaeude"].items()
        }
        waermebedarf_rohdaten["lpagg"] = LpaggConfig(**lpagg_rohdaten)

    return ToolConfig(
        projektname=rohdaten["projektname"],
        windpark=WindparkConfig(**windpark_rohdaten),
        waermebedarf=WaermebedarfConfig(**waermebedarf_rohdaten),
        waermepumpe=WaermepumpeConfig(**rohdaten["waermepumpe"]),
        backup=BackupConfig(**rohdaten["backup"]),
        speicher=SpeicherConfig(**rohdaten["speicher"]),
        wirtschaft=WirtschaftConfig(
            strompreisszenarien=strompreisszenarien, **wirtschaft_rohdaten
        ),
        regulatorik=RegulatorikConfig(**rohdaten.get("regulatorik", {})),
        fossile_referenz=FossileReferenzConfig(**rohdaten.get("fossile_referenz", {})),
    )
