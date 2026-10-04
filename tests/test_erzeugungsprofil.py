from pathlib import Path

import pytest

from lcoh_tool.erzeugungsprofil import load_erzeugungsprofil

BEISPIEL_CSV = Path(__file__).parents[1] / "data" / "erzeugungsprofil_beispiel.csv"


def test_load_erzeugungsprofil_laenge_und_typ():
    profil = load_erzeugungsprofil(BEISPIEL_CSV)
    assert len(profil) == 48
    assert profil.name == "erzeugung_kwh"
    assert (profil >= 0).all()


def test_load_erzeugungsprofil_datei_fehlt():
    with pytest.raises(FileNotFoundError):
        load_erzeugungsprofil("data/existiert_nicht.csv")


def test_load_erzeugungsprofil_fehlende_spalte(tmp_path):
    kaputte_csv = tmp_path / "kaputt.csv"
    kaputte_csv.write_text("zeitstempel,falsche_spalte\n2027-01-01 00:00:00,1\n")
    with pytest.raises(ValueError):
        load_erzeugungsprofil(kaputte_csv)
