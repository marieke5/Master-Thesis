# Master-Thesis: Techno-ökonomisches Tool "Direktanschluss"

Python-Tool zur techno-ökonomischen Analyse eines netzentgeltfreien
**Direktanschlusses** eines Windparks an Wärmeerzeuger (Wärmepumpe,
Elektrodenkessel/Gaskessel als Backup) mit Wärmespeicher. Zentrale
Zielgröße ist die **LCOH** (Levelized Cost of Heat, Wärmegestehungskosten),
optional im Vergleich zur fossilen Referenzversorgung.

Teil der Masterarbeit von Marieke Stein (Sustainable Energy Engineering,
Europa-Universität Flensburg) in Kooperation mit Green Wind Energy GmbH.
Anwendungsfall: Windpark- und Nahwärmeprojekt in Siebeneichen (Amt Büchen).

## Konzept / Scope

- **Input Windpark:** stundenscharfes Erzeugungsprofil (CSV, 8.760 Werte/Jahr),
  extern erstellt (Ertragsgutachten o. Ä.) — die Erzeugung selbst wird
  **nicht** im Tool modelliert.
- **Input Wärmebedarf:** stundenscharfe Wärmelast (CSV oder synthetisch
  über ein Referenzlastprofil).
- **Bilanz:** Für jede Stunde wird geprüft, ob die Windleistung den
  Strombedarf der Wärmeerzeugung deckt (→ Direktanschluss, netzentgeltfrei)
  oder ob auf Netzbezug zurückgefallen werden muss (→ Rückfallstrom, mit
  Netzentgelt).
- **Wärmeerzeugung:** Wärmepumpe als Hauptquelle, Elektrodenkessel oder
  Gaskessel als zu Beginn wählbares Backup; das Tool ist so aufgebaut, dass
  weitere Quellen (z. B. Industrieabwärme) später ergänzt werden können.
- **Output:** LCOH der Direktanschluss-Versorgung; optional LCOH der
  fossilen Referenzversorgung (aktueller Gas-/Ölkessel) zum Vergleich.
- **Explizit außerhalb des Scopes:** Umbau/Erweiterung des Nahwärmenetzes
  selbst sowie die Modellierung der Windenergieerzeugung.

## Projektstruktur

```
master-thesis/
├── config/                    Beispiel-Konfigurationen (YAML)
├── data/                      Beispiel-Inputdaten (CSV)
├── src/lcoh_tool/             Python-Paket mit den Tool-Modulen
│   ├── config.py              Konfiguration laden/validieren
│   ├── erzeugungsprofil.py    Windpark-Erzeugungsprofil einlesen
│   ├── waermebedarf.py        Wärmelastprofil einlesen/generieren
│   ├── bilanz.py              Stundenscharfe Bilanz Erzeugung vs. Bedarf
│   ├── wirtschaftlichkeit.py  Investitions-/Betriebskosten, LCOH-Berechnung
│   └── main.py                CLI-Einstiegspunkt
├── tests/                     Unit-Tests (pytest)
└── notebooks/                 Explorative Auswertungen (nicht Teil des Tools)
```

Jedes Modul deckt einen Baustein aus dem Exposee ab (Erzeugungsprofil,
Wärmebedarf, techno-ökonomische Analyse inkl. Anschlusskosten und
Versorgungssicherheit) und kann unabhängig weiterentwickelt und getestet
werden.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .                   # Paket im "editable"-Modus installieren
```

## Ausführen

```bash
python -m lcoh_tool.main --config config/beispiel_siebeneichen.yaml
```

## Tests

```bash
pytest
```

## Status

Erstes Gerüst (Platzhalter-Logik in `bilanz.py` und `wirtschaftlichkeit.py`,
lauffähig mit Beispieldaten). Die eigentliche Modellierung wird im Laufe der
Bearbeitung ergänzt.
