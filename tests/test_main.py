from pathlib import Path

from lcoh_tool.main import run

BEISPIEL_CONFIG = Path(__file__).parents[1] / "config" / "beispiel_siebeneichen.yaml"


def test_run_end_to_end_ohne_fehler(capsys):
    """Rauchtest: das gesamte Beispielprojekt laeuft ohne Exception durch
    und gibt ein LCOH-Ergebnis aus."""
    run(str(BEISPIEL_CONFIG))
    ausgabe = capsys.readouterr().out
    assert "LCOH Direktanschluss" in ausgabe
