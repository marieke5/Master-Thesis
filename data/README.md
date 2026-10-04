# Beispieldaten

`erzeugungsprofil_beispiel.csv` und `waermelast_beispiel.csv` enthalten
**48 Stunden** zufällig generierter Platzhalterdaten (nur zu Demo- und
Testzwecken, kein reales Projekt).

Für die echte Analyse werden vollständige Jahresprofile (8.760 Stunden)
benötigt:

- **Erzeugungsprofil:** stundenscharfes Windpark-Ertragsprofil, extern
  erstellt (z. B. Ertragsgutachten, SCADA-Daten eines bestehenden Standorts).
- **Wärmelast:** stundenscharfes Lastprofil des Nahwärmenetzes (z. B. aus
  Messdaten des Netzbetreibers oder einem Referenzlastprofil).

Format (identisch für beide Dateien, nur die zweite Spalte unterscheidet
sich):

| Spalte | Beschreibung |
|---|---|
| `zeitstempel` | Datum/Uhrzeit, stündliche Auflösung |
| `energie_kwh` / `waermelast_kwh` | Energiemenge der jeweiligen Stunde in kWh |
