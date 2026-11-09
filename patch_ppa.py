"""Spielt den PPA-Block in die lokale config.py und die Jahreslauf-YAML ein (idempotent).

Aufruf im Repo-Ordner:  python patch_ppa.py
Aendert nur, was fehlt; die uebrigen Aenderungen in config.py und YAML bleiben erhalten.
"""

from pathlib import Path

PPA_CLASS = '''@dataclass
class PpaConfig:
    """Stromversorgung per PPA (fester Preis, Abrechnung pay-as-consumed).

    Verglichen werden drei Faelle mit demselben Betrieb und demselben PPA-Preis:
    (1) reiner Netzbezug ohne PPA, (2) PPA ueber das Netz, (3) PPA mit Direktleitung.
    Mit PPA nutzt die Waermeseite Windstrom, wann immer er verfuegbar ist; die
    Preisschwelle der ``steuerung`` und die Marktpreisreihe werden nicht gebraucht.
    ``wirtschaft.abgaben_eur_pro_mwh`` (alle Umlagen/Steuern auf Netzstrom) fallen im Fall 2
    auf den PPA-Strom an, im Fall 3 nur ``abgaben_direktleitung_eur_pro_mwh`` (z. B. Stromsteuer).
    """

    preis_eur_pro_mwh: float
    sleeving_eur_pro_mwh: float = 0.0  # Lieferantenaufschlag/Bilanzierung, nur PPA ueber das Netz
    abgaben_direktleitung_eur_pro_mwh: float = 0.0  # Abgaben, die auch auf Direktstrom anfallen
    # Vergleichswert der WEA (Stromgestehungskosten oder Marktwert): Liegt der PPA-Preis
    # darunter, gibt das Tool einen Hinweis (Deal fuer den Windpark unattraktiv).
    vergleichswert_eur_pro_mwh: Optional[float] = None


'''

YAML_BLOCK = '''
# PPA-Betrieb (optional): Stromversorgung per PPA mit festem Preis, Abrechnung pay-as-consumed.
# Das Tool vergleicht (1) Netzbezug ohne PPA, (2) PPA ueber das Netz, (3) PPA mit Direktleitung.
# Ohne diesen Block gilt die preisgesteuerte Betriebsweise aus 'steuerung' (ENTSO-E-Preise).
# Mit PPA entfallen Preisschwelle und Marktpreisreihe (kein Token noetig).
ppa:
  preis_eur_pro_mwh: 60                    # PLATZHALTER: PPA-Preis, in allen PPA-Faellen gleich
  sleeving_eur_pro_mwh: 0                  # PLATZHALTER: Lieferantenaufschlag, nur PPA ueber das Netz
  abgaben_direktleitung_eur_pro_mwh: 0     # Abgaben auch auf Direktstrom, z. B. Stromsteuer (WEA > 2 MW; aktuellen Satz pruefen)
  # vergleichswert_eur_pro_mwh: 70         # optional: Stromgestehungskosten/Marktwert der WEA -> Hinweis bei zu niedrigem PPA-Preis
'''


def lies(pfad: Path) -> tuple[str, str]:
    roh = pfad.read_bytes().decode("utf-8")
    return roh.replace("\r\n", "\n"), ("\r\n" if "\r\n" in roh else "\n")


def schreibe(pfad: Path, text: str, zeilenende: str) -> None:
    pfad.write_bytes(text.replace("\n", zeilenende).encode("utf-8"))


def patche_config(pfad: Path) -> None:
    text, ende = lies(pfad)
    if "class PpaConfig" in text:
        print(f"{pfad}: PpaConfig schon vorhanden")
        return
    anker = "@dataclass\nclass ToolConfig:"
    if anker not in text:
        raise SystemExit("config.py: Anker 'class ToolConfig' nicht gefunden")
    text = text.replace(anker, PPA_CLASS + anker, 1)
    feld = "    referenzjahr: Optional[int] = None\n"
    if feld not in text:
        raise SystemExit("config.py: Feld 'referenzjahr' in ToolConfig nicht gefunden")
    text = text.replace(feld, feld + "    ppa: Optional[PpaConfig] = None\n", 1)
    lader = '        referenzjahr=rohdaten.get("referenzjahr"),\n'
    if lader not in text:
        raise SystemExit("config.py: Zeile 'referenzjahr=rohdaten.get' in load_config nicht gefunden")
    text = text.replace(lader, lader + '        ppa=PpaConfig(**rohdaten["ppa"]) if rohdaten.get("ppa") else None,\n', 1)
    schreibe(pfad, text, ende)
    print(f"{pfad}: PpaConfig eingefuegt")


def patche_yaml(pfad: Path) -> None:
    text, ende = lies(pfad)
    if "\nppa:" in text or text.startswith("ppa:"):
        print(f"{pfad}: Block 'ppa' schon vorhanden")
        return
    schreibe(pfad, text.rstrip("\n") + "\n" + YAML_BLOCK, ende)
    print(f"{pfad}: Block 'ppa' angehaengt")


if __name__ == "__main__":
    patche_config(Path("src/lcoh_tool/config.py"))
    yaml_pfad = Path("config/parameter_jahreslauf.yaml")
    if yaml_pfad.exists():
        patche_yaml(yaml_pfad)
