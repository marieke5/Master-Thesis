import io

import pytest

from lcoh_tool.erzeugungsprofil import load_erzeugungsprofil

KOPF = (
    "Projekt | 3 x WEA\tScaler:\tx\n"
    "09.11.2026 14:01:40;Total;;For reference WTG: x;;;\n"
    "Time stamp;Power;Time;" + ";".join(f"c{i}" for i in range(3, 21)) + ";Power;c22\n"
    "Date-time;[kW];[h]\n"
)


def _zeile(zeit, gesamt, einzel):
    mitte = ";".join("" for _ in range(3, 21))
    return f"{zeit};{gesamt};1,0000;{mitte};{einzel};9,1\n"


def _datei(tmp_path):
    inhalt = KOPF + _zeile("01.01.2023 01:00", "3000,5", "1000,2") + _zeile("01.01.2023 02:00", "600,0", "200,0") \
        + _zeile("01.01.2024 00:00", "30,0", "10,0")
    p = tmp_path / "windpro.txt"
    p.write_text(inhalt, encoding="latin-1")
    return p


def test_windpro_gesamt_und_stundenbeginn(tmp_path):
    s = load_erzeugungsprofil(_datei(tmp_path))
    assert s.iloc[0] == pytest.approx(3000.5)  # Dezimalkomma gelesen
    assert str(s.index[0]) == "2023-01-01 00:00:00"  # Stundenende 01:00 -> Beginn 00:00
    assert str(s.index[-1]) == "2023-12-31 23:00:00"  # 01.01.2024 00:00 gehoert noch zu 2023


def test_windpro_je_wea(tmp_path):
    s = load_erzeugungsprofil(_datei(tmp_path), windpro_block="je_wea")
    assert list(s) == [pytest.approx(1000.2), pytest.approx(200.0), pytest.approx(10.0)]


def test_windpro_aus_dateiobjekt(tmp_path):
    p = _datei(tmp_path)
    s = load_erzeugungsprofil(io.BytesIO(p.read_bytes()))
    assert len(s) == 3


def test_normale_csv_bleibt_unveraendert(tmp_path):
    p = tmp_path / "e.csv"
    p.write_text("zeitstempel,energie_kwh\n2023-01-01 00:00,5\n")
    assert load_erzeugungsprofil(p).iloc[0] == 5
