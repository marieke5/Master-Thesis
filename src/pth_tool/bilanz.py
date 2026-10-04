"""Stundenscharfe Bilanz: Winderzeugung vs. Strombedarf der Waermeerzeugung.

Kernidee (siehe Exposee): Fuer jede Stunde wird geprueft, ob die
Windleistung den Strombedarf der Waermepumpe (bzw. des Backups) deckt.
- Deckt die Windleistung den Bedarf -> Direktanschluss-Strom, netzentgeltfrei.
- Reicht sie nicht -> Rueckfall auf Netzbezug (mit Netzentgelt).

Der Waermespeicher wird hier als einfacher Puffer beruecksichtigt: Ueberschuss
an Windenergie (nach Deckung des aktuellen Bedarfs) kann - bis zur
Speicherkapazitaet - fuer spaetere Stunden vorgehalten werden. Backup wird
aktiviert, sobald die Waermepumpe (inkl. Speicherentnahme) den Bedarf nicht
mehr decken kann; die konkrete Aufteilung Waermepumpe/Backup ist ein
Platzhalter fuer die methodische Vertiefung.
"""

from __future__ import annotations

import pandas as pd

from lcoh_tool.config import ToolConfig


def berechne_bilanz(
    erzeugung_kwh: pd.Series,
    waermelast_kwh: pd.Series,
    config: ToolConfig,
) -> pd.DataFrame:
    """Berechnet die stundenscharfe Energiebilanz fuer ein Jahr.

    Gibt ein DataFrame mit einer Zeile je Stunde und den Spalten zurueck:
    - ``waermelast_kwh``: Waermebedarf
    - ``strombedarf_wp_kwh``: Strombedarf der Waermepumpe zur Deckung der Last
    - ``erzeugung_kwh``: verfuegbare Windenergie
    - ``speicherstand_kwh``: Fuellstand des Waermespeichers am Stundenende
    - ``direktanschluss_kwh``: aus Windstrom gedeckter Strombedarf
    - ``rueckfall_kwh``: aus Netzbezug gedeckter Strombedarf
    - ``deckungsluecke_kwh``: verbleibende, ungedeckte Waermelast (Backup-Bedarf)
    """
    index = waermelast_kwh.index
    erzeugung = erzeugung_kwh.reindex(index).fillna(0.0)

    jazl = config.waermepumpe.jazl
    speicher_kapazitaet = config.speicher.kapazitaet_kwh
    speicherverlust = config.speicher.verlust_pro_stunde

    strombedarf_wp = waermelast_kwh / jazl

    direktanschluss = pd.Series(0.0, index=index)
    rueckfall = pd.Series(0.0, index=index)
    speicherstand = pd.Series(0.0, index=index)

    aktueller_speicherstand = 0.0
    for zeitpunkt in index:
        verfuegbare_windenergie = erzeugung.loc[zeitpunkt]
        bedarf = strombedarf_wp.loc[zeitpunkt]

        # Speicherverlust seit letzter Stunde
        aktueller_speicherstand *= 1 - speicherverlust

        if verfuegbare_windenergie >= bedarf:
            # Windenergie deckt den Bedarf direkt; Ueberschuss geht (bis zur
            # Kapazitaetsgrenze) in den Speicher.
            direktanschluss.loc[zeitpunkt] = bedarf
            ueberschuss = verfuegbare_windenergie - bedarf
            aktueller_speicherstand = min(
                speicher_kapazitaet, aktueller_speicherstand + ueberschuss
            )
        else:
            # Windenergie reicht nicht: erst Speicher nutzen, dann Rueckfall.
            luecke = bedarf - verfuegbare_windenergie
            direktanschluss.loc[zeitpunkt] = verfuegbare_windenergie
            entnahme = min(luecke, aktueller_speicherstand)
            aktueller_speicherstand -= entnahme
            direktanschluss.loc[zeitpunkt] += entnahme
            luecke -= entnahme
            rueckfall.loc[zeitpunkt] = luecke

        speicherstand.loc[zeitpunkt] = aktueller_speicherstand

    ergebnis = pd.DataFrame(
        {
            "waermelast_kwh": waermelast_kwh,
            "strombedarf_wp_kwh": strombedarf_wp,
            "erzeugung_kwh": erzeugung,
            "speicherstand_kwh": speicherstand,
            "direktanschluss_kwh": direktanschluss,
            "rueckfall_kwh": rueckfall,
        }
    )
    # Deckungsluecke: bislang wird davon ausgegangen, dass WP+Speicher+Rueckfall-
    # Strom den Strombedarf immer vollstaendig decken (kein Leistungslimit).
    # Ein Leistungslimit (Nennleistung WP/Backup) ist ein TODO fuer die
    # methodische Vertiefung.
    ergebnis["deckungsluecke_kwh"] = 0.0

    return ergebnis
