# Master-Thesis: Techno-ökonomisches Tool "Direktanschluss"

Python-Tool zur techno-ökonomischen Analyse eines netzentgeltfreien
**Direktanschlusses** eines Windparks an Wärmeerzeuger (Wärmepumpe,
Elektrodenkessel als Backup) mit Wärmespeicher. Zentrale
Zielgröße ist die **LCOH** (Levelized Cost of Heat, Wärmegestehungskosten).

Teil der Masterarbeit von Marieke Stein (Sustainable Energy Engineering,
Europa-Universität Flensburg) in Kooperation mit Green Wind Energy GmbH.
Anwendungsfall: Windpark- und Nahwärmeprojekt in Siebeneichen (Amt Büchen).

## Konzept / Scope

- **Input Windpark** (stundenscharfes Erzeugungsprofil, 8.760 Werte/Jahr), zwei Wege:
  - **Projektbezogene CSV** (Standard, z. B. aus dem Ertragsgutachten) – die
    Erzeugung wird dann **nicht** im Tool modelliert. Auch als Datei-Upload
    (z. B. aus einer GUI) möglich.
  - **Schnellabschätzung mit windpowerlib** (optional): Standort, Anlagentyp,
    Nabenhöhe und Anlagenzahl genügen; Wetterdaten kommen aus ERA5 (Standard:
    direkt über den Copernicus CDS, auch kommerziell nutzbar), über Open-Meteo
    (nur für Demos/nicht-kommerzielle Nutzung, Lizenz der kostenlosen API) oder
    aus einer eigenen Wetter-CSV. Grobe Näherung (ca. 30 km Auflösung, pauschale Parkverluste),
    ersetzt kein Ertragsgutachten.
- **Input Wärmebedarf** (stundenscharf), drei Wege in dieser Priorität:
  1. **Projektbezogene CSV** (auch als Upload).
  2. **Gebäudetypen und -anzahl über lpagg:** Aus EFH/MFH/Gewerbe, jährlichem
     Heizenergie- und Warmwasserbedarf und Gebäudeanzahl erzeugt lpagg ein
     Stundenprofil (VDI 4655 für Wohngebäude, BDEW für Gewerbe) auf Basis des
     DWD-Testreferenzjahres 2010 (Region frei wählbar, Standard Region 4 =
     Potsdam) inkl. Feiertagen, Sommerzeit und Gleichzeitigkeit. Enthalten
     sind Raumheizung und Trinkwarmwasser; Kälte und Netzverluste nicht.
  3. **Nur Jahreswärmebedarf:** einfaches saisonales Platzhalter-Muster.
- **Bilanz:** Für jede Stunde wird geprüft, ob die Windleistung den
  Strombedarf der Wärmeerzeugung deckt (→ Direktanschluss, netzentgeltfrei)
  oder ob auf Netzbezug zurückgefallen werden muss (→ Rückfallstrom, mit
  Netzentgelt).
- **Wärmeerzeugung:** Wärmepumpe als Hauptquelle, Elektrodenkessel als
  Backup; das Tool ist so aufgebaut, dass weitere Quellen (z. B. ein
  Gaskessel als Backup-Alternative, Industrieabwärme) später ergänzt
  werden können.
- **Output:** LCOH der Direktanschluss-Versorgung.
- **Explizit außerhalb des Scopes:** Umbau/Erweiterung des Nahwärmenetzes
  selbst sowie die Modellierung der Windenergieerzeugung.

## Projektstruktur

```
master-thesis/
├── config/                    Beispiel-Konfigurationen (YAML)
├── data/                      Beispiel-Inputdaten (CSV)
├── src/lcoh_tool/              Python-Paket mit den Tool-Modulen
│   ├── config.py              Konfiguration laden/validieren
│   ├── erzeugungsprofil.py    Windpark-Erzeugungsprofil aus CSV einlesen
│   ├── windpark.py            Erzeugungsprofil per windpowerlib (optional)
│   ├── wetterdaten.py         Wetterdaten: Open-Meteo, ERA5 (CDS), eigene CSV
│   ├── waermebedarf.py        Wärmelastprofil aus CSV / Jahreswert
│   ├── lastprofil_lpagg.py    Wärmelastprofil aus Gebäudetypen per lpagg (optional)
│   ├── bilanz.py              Stundenscharfe Bilanz Erzeugung vs. Bedarf
│   ├── wirtschaftlichkeit.py  Investitions-/Betriebskosten, LCOH-Berechnung
│   ├── projekt.py             Gesamtablauf, gibt ein Ergebnisobjekt zurück
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

Optionale Bausteine (nur bei Bedarf):

```bash
pip install -e ".[wind]"           # windpowerlib: Erzeugungsprofil-Schnellabschätzung
pip install -e ".[lpagg]"          # lpagg: Wärmelast aus Gebäudetypen
pip install -e ".[era5]"           # ERA5-Direktabruf (benötigt CDS-Account/API-Key)
pip install -e ".[alle]"           # alles inklusive pytest
```

lpagg liegt nicht auf PyPI und wird aus dem GitHub-Archiv installiert. Die
Konfiguration der einzelnen Quellen ist in `config/parameter.yaml` als
auskommentierte Beispiele beschrieben.

## Ausführen

```bash
python -m lcoh_tool.main --config config/parameter.yaml
```

## Tests

```bash
pytest
```

## Status

Erstes Gerüst (Platzhalter-Logik in `bilanz.py` und `wirtschaftlichkeit.py`,
lauffähig mit Beispieldaten). Die eigentliche Modellierung wird im Laufe der
Bearbeitung ergänzt.
