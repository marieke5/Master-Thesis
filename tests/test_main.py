from pathlib import Path

from lcoh_tool.main import run

PARAMETER_CONFIG = Path(__file__).parents[1] / "config" / "parameter.yaml"


def test_run_end_to_end_ohne_fehler(capsys):
    """Rauchtest: das gesamte Beispielprojekt laeuft ohne Exception durch
    und gibt ein LCOH-Ergebnis aus."""
    run(str(PARAMETER_CONFIG))
    ausgabe = capsys.readouterr().out
    assert "LCOH Direktanschluss" in ausgabe
