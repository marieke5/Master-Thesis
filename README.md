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

## Vergleich: Direktleitung oder reiner Netzbezug

Das Tool stellt zwei Varianten gegenüber (`vergleich.py`, Ausgabe „Vergleich“):
**A** = nur Netzbezug (Wärmepumpe + Backup + Wärmespeicher, Strom zu Szenariopreis + Netzentgelt + Abgaben,
keine Leitung; der Wärmespeicher gilt in beiden Varianten gleich) und **B** = Direktleitung + Netzbezug (normale Rechnung).
Ausgegeben werden LCOH beider Varianten je Szenario, der Vorteil der Direktleitung (A − B,
positiv = lohnt sich) und die **Break-even-Leitungskosten**: die maximale Investition in die
Direktleitung (`capex_anschluss_eur`), bei der beide gleich teuer sind. Die Variationsrechnung
enthält beides als Spalten. Regulatorik: `regulatorik.netzentgeltbefreiung_direktanschluss` (Standard `true`) legt fest, ob der
Direktstrom netzentgeltfrei ist. Bei `false` zahlt auch er das Netzentgelt; der Netzbezug
(Rückfall, z. B. bei Windstille) zahlt es immer. Leistungspreis: `leistungspreis_eur_pro_kw_a` (€/kW und Jahr) wird auf die Jahreshöchstlast des
Netzbezugs berechnet (A: höchste Stundenleistung der Wärmeerzeuger; B: höchster Rückfallstrom).
Annahmen: gleiche Fixkosten in A und B; `abgaben_eur_pro_mwh` und
`capex_netzanschluss_eur` (Standard 0) gelten für beide Varianten.

## Referenzjahr

`referenzjahr` (oberste Ebene der YAML) legt ein Wetter-/Marktjahr für alles fest: ERA5-Wind
(windpowerlib), ERA5-Temperatur für lpagg und die Auswahl aus mehrjährigen Wind-/Preis-CSV.
Eine WindPRO-CSV sollte genau ein Jahr enthalten; enthält ein Profil mehrere Jahre und ist kein
Referenzjahr gesetzt, bricht das Tool mit einer Fehlermeldung ab. Die Marktpreise holst du für
dasselbe Jahr (`marktpreise_abruf --jahr <Referenzjahr>`).

## Wärmelast mit lpagg (nur Lastverteilung)

Priorität 1 ist die hochgeladene Wärmelast-CSV (`waermelast_pfad`). Ohne CSV werden
`jahreswaermebedarf_mwh` und die Gebäudetypen/-anzahl (`lpagg.gebaeude`) manuell
angegeben. lpagg liefert dann **nur die Verteilung** (VDI 4655 / BDEW, Feiertage,
Gleichzeitigkeit); das Profil wird auf den Jahreswert skaliert. `q_heiz_a_kwh` je
Gebäudetyp ist optional (relative Größe); ohne Angabe wird gleichmäßig verteilt.

Wetter für die Lastverteilung: `lpagg.wetterquelle: era5` holt die Temperatur des
Wetterjahres aus dem Copernicus CDS (Standort und Jahr des Windparks, oder eigene
`breitengrad`/`laengengrad`/`wetterjahr`; gleicher Cache wie beim Wind). `try` nutzt
das mitgelieferte DWD-Testreferenzjahr.

## Preisgesteuerte Direktleitung

Mit dem optionalen Block `steuerung` in der YAML-Config (Beispiel:
`config/parameter_steuerung.yaml`) wird die Direktleitung nur bei negativen oder
sehr niedrigen Marktpreisen genutzt (`betrieb.py`):

- **Preis <= `preisschwelle_eur_pro_mwh`** (Standard 0): Direktleitung aktiv, Wärme
  deckt den Bedarf und lädt den Speicher.
- **Preis darüber:** der Speicher deckt den Bedarf. **Ausnahme Notbetrieb:** Ist der
  Speicher fast leer (`speicher_untergrenze_anteil`, Standard 10 %) und wird Wärme
  gebraucht, läuft die Direktleitung trotzdem und deckt den aktuellen Bedarf. „Fast leer“
  lässt sich alternativ als Stunden der Wärmespitzenlast angeben
  (`speicher_untergrenze_stunden`, hat Vorrang), unabhängig von der Speichergröße.
- Reihenfolge der Bedarfsdeckung: Direktstrom -> Speicher -> Netzbezug (Rückfallstrom
  mit Netzentgelt). Wärmepumpe vor Elektrodenkessel.
- Direktstrom wird zum **Marktpreis der Stunde** bewertet (Opportunitätskosten;
  negativer Preis = Erlös). Alternativ `direktstrom_bepreisung: fest`.
- Marktpreise: eigene CSV (`zeitstempel`, `preis_eur_mwh`, stündlich, z. B. SMARD),
  Jahr wird wie bei den Profilen auf das Jahr der Wärmelast gelegt.
  `data/marktpreise_beispiel_jahr.csv` ist ein **synthetischer Platzhalter**
  (nicht korreliert mit dem Wind), `marktpreise_beispiel.csv` hat 48 Stunden.

Annahmen: Speicherkapazität und `nennleistung_kw` von Wärmepumpe/Backup gelten in
dieser Betriebsweise als **thermisch**; Leistungsgrenzen werden angewendet (nicht
gedeckte Wärme erscheint als Deckungslücke). Ohne Block `steuerung` bleibt das
bisherige Verhalten (Direktstrom kostenlos) unverändert.

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

### Marktpreise (ENTSO-E)

Die Day-Ahead-Preise des `referenzjahr` werden immer automatisch von ENTSO-E geholt (Token in
`$env:ENTSOE_API_KEY`, `pip install -e ".[entsoe]"`) und als `data/marktpreise_<jahr>.csv`
gespeichert. Ist die Datei da, braucht der Lauf weder Token noch Internet.

### Mehrjahresvergleich

`python -m lcoh_tool.mehrjahre --config config/parameter_jahreslauf.yaml --von 2016 --bis 2025 --ausgabe data/mehrjahre.csv`
rechnet jedes Referenzjahr einzeln (Wind, Temperatur, ENTSO-E-Preise des Jahres) und zeigt
LCOH, Vorteil der Direktleitung und Break-even je Jahr sowie Mittel/Min/Max. Neue Jahre
laden ERA5 und ENTSO-E nach (einige Minuten je Jahr), danach kommt alles aus dem Cache.
Fuer DE_LU gibt es Preise erst ab 1.10.2018; davor holt das Tool automatisch die
Vorgaengerzone DE_AT_LU (2018 beide kombiniert). Jahre mit Fehler werden uebersprungen.

### WindPRO-Zeitreihe als Erzeugungsprofil

Die WindPRO-Textdatei ("Time Variation", Semikolon, Dezimalkomma) wird direkt gelesen, ohne
Umformatieren: `windpark.quelle: csv`, `erzeugungsprofil_pfad: data/<Datei>.txt` und
`windpro_block: gesamt` (alle WEA) oder `je_wea` (eine WEA). Die Datei darf mehrere Jahre
enthalten; das `referenzjahr` waehlt das Jahr. WindPRO beschriftet Stunden mit dem Ende
(01:00 = 00-01 Uhr); das Tool setzt auf den Stundenbeginn zurueck. Fuer die ERA5-Temperatur
der Waermelast (lpagg) dann `breitengrad`/`laengengrad` im Block `lpagg` setzen, weil es keinen
`windpowerlib`-Block mehr gibt.

### Direktstrompreis variieren

`python -m lcoh_tool.variation --config ... --speicher 20000 --schwellen 40 --capex-pro-kwh 3 --direktstrompreise 20 40 60 80`
bewertet den Windstrom zu festen Preisen (statt Marktpreis) und nennt den Direktstrompreis,
bis zu dem sich die Direktleitung bei den angesetzten Leitungskosten gegenueber reinem
Netzbezug lohnt.

### Plots zum Betrieb

`python -m lcoh_tool.plots --config config/parameter_jahreslauf.yaml --ausgabe plots`
schreibt `betrieb_jahr.png` (Monatssummen: Windstrom, Strombedarf von Waermepumpe und
Elektrodenkessel aus Direktleitung bzw. Netz) und `betrieb_woche.png` (eine Woche stuendlich:
Windleistung, Strombezug je Erzeuger und Quelle, Speicherstand, Marktpreis mit Preisschwelle)
und `betrieb_speicher.png` (Fuellstand, Be- und Entladen des Waermespeichers: Jahr, Monate, Woche).
`--woche 2023-01-09` waehlt die Woche, sonst die mit der hoechsten Waermelast. Braucht matplotlib
(`pip install matplotlib`, kommt mit lpagg ohnehin mit).

### PPA-Betrieb: drei Faelle vergleichen

Mit dem Block `ppa` in der Config (fester PPA-Preis, pay-as-consumed) vergleicht das Tool
(1) Netzbezug ohne PPA, (2) PPA ueber das Netz, (3) PPA mit Direktleitung. Betrieb und
PPA-Preis sind in (2) und (3) gleich: Windstrom wird genutzt, wann immer er verfuegbar ist
(Preisschwelle und Marktpreisreihe entfallen, kein ENTSO-E-Token noetig). Unterschied:
(2) zahlt auf den PPA-Strom Netzentgelt, `wirtschaft.abgaben_eur_pro_mwh`, Sleeving
(`ppa.sleeving_eur_pro_mwh`) und Leistungspreis, hat aber keine Leitungskosten; (3) zahlt nur
`ppa.abgaben_direktleitung_eur_pro_mwh` (z. B. Stromsteuer) und die Leitung
(`capex_anschluss_eur`). Der Break-even der Leitungskosten bezieht sich auf Fall 2.
`ppa.vergleichswert_eur_pro_mwh` (Stromgestehungskosten/Marktwert der WEA) loest einen Hinweis
aus, wenn der PPA-Preis darunter liegt. Die Variation des PPA-Preises:
`python -m lcoh_tool.variation ... --direktstrompreise 40 50 60 70`.
Vereinfachung: Beladung des Speichers laeuft mit voller Leistung; in Fall 2 zaehlt sie zur
Netzspitze (Leistungspreis) und kann diesen Fall verteuern.

### Ladeleistung des Speichers und Verfuegbarkeit der WEA

* `speicher.max_ladeleistung_kw` (thermisch) begrenzt die Beladung zusaetzlich zur Lastdeckung.
  Im PPA-Betrieb laedt ausschliesslich die Waermepumpe den Speicher; der Elektrodenkessel deckt nur
  die aktuelle Last. Das verhindert unrealistische Netzspitzen (Leistungspreis) im Fall "PPA ueber das Netz".
* `windpark.verfuegbarkeit` (0..1), `ausfall_dauer_h`, `ausfall_seed`: Ausfaelle der WEA als
  Bloecke zufaellig, aber reproduzierbar auf Null setzen. Nur ansetzen, wenn der Ertrag (z. B. WindPRO)
  keine Verfuegbarkeit enthaelt. Erst durch Ausfaelle entsteht Netzbezug mit Direktleitung; ein Speicher
  ueberbrueckt kurze Ausfaelle.
