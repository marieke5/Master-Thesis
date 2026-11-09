"""Ergaenzt config.py und die Jahreslauf-YAML um Ladeleistungsgrenze und WEA-Verfuegbarkeit.

Aufruf im Repo-Ordner:  python patch_verfuegbarkeit.py   (idempotent, aendert nur, was fehlt)
"""

from pathlib import Path

SPEICHER_FELDER = '''    # Maximale thermische Ladeleistung (kW Waerme) in den Speicher, zusaetzlich zur Deckung der
    # aktuellen Last. None = nur durch Waermepumpe + Kessel begrenzt.
    max_ladeleistung_kw: Optional[float] = None
'''
WINDPARK_FELDER = '''    # Verfuegbarkeit der WEA (Anteil der Stunden, 0..1). Ausfaelle werden in Bloecken von
    # ``ausfall_dauer_h`` Stunden zufaellig (reproduzierbar ueber ``ausfall_seed``) auf Null gesetzt.
    # Nur setzen, wenn der Ertrag (z. B. WindPRO-Reihe) keine Verfuegbarkeit enthaelt.
    verfuegbarkeit: float = 1.0
    ausfall_dauer_h: int = 48
    ausfall_seed: int = 42
'''


def lies(pfad):
    roh = pfad.read_bytes().decode("utf-8")
    return roh.replace("\r\n", "\n"), ("\r\n" if "\r\n" in roh else "\n")


def schreibe(pfad, text, ende):
    pfad.write_bytes(text.replace("\n", ende).encode("utf-8"))


def fuege_nach(text, anker, neu, name):
    if anker not in text:
        raise SystemExit(f"{name}: Anker nicht gefunden: {anker.strip()[:60]}")
    return text.replace(anker, anker + neu, 1)


def patche_config(pfad):
    text, ende = lies(pfad)
    geaendert = False
    if "max_ladeleistung_kw" not in text:
        text = fuege_nach(text, "    verlust_pro_stunde: float = 0.0  # Anteil Speicherverlust je Stunde (0..1)\n",
                          SPEICHER_FELDER, "config.py")
        geaendert = True
    if "verfuegbarkeit" not in text:
        text = fuege_nach(text, '    windpro_block: Literal["gesamt", "je_wea"] = "gesamt"\n', WINDPARK_FELDER, "config.py")
        geaendert = True
    if geaendert:
        schreibe(pfad, text, ende)
        print(f"{pfad}: Felder eingefuegt")
    else:
        print(f"{pfad}: schon vorhanden")


def patche_yaml(pfad):
    text, ende = lies(pfad)
    zeilen, neu, geaendert = text.split("\n"), [], False
    for z in zeilen:
        neu.append(z)
        if z.rstrip() == "windpark:" and "verfuegbarkeit:" not in text:
            neu += ["  verfuegbarkeit: 0.97        # PLATZHALTER: Anteil der Stunden, in denen die WEA laeuft",
                    "  ausfall_dauer_h: 48         # Ausfaelle in Bloecken dieser Laenge (zufaellig, reproduzierbar)"]
            geaendert = True
        if z.rstrip() == "speicher:" and "max_ladeleistung_kw:" not in text:
            neu.append("  max_ladeleistung_kw: 800    # thermische Ladeleistung; ohne Angabe nur durch die Erzeuger begrenzt")
            geaendert = True
    if geaendert:
        schreibe(pfad, "\n".join(neu), ende)
        print(f"{pfad}: Parameter eingefuegt")
    else:
        print(f"{pfad}: schon vorhanden")


if __name__ == "__main__":
    patche_config(Path("src/lcoh_tool/config.py"))
    y = Path("config/parameter_jahreslauf.yaml")
    if y.exists():
        patche_yaml(y)
