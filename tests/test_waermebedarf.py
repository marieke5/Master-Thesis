from pathlib import Path

from lcoh_tool.waermebedarf import load_waermebedarf, synthetische_waermelast

BEISPIEL_CSV = Path(__file__).parents[1] / "data" / "waermelast_beispiel.csv"


def test_load_waermebedarf_laenge_und_typ():
    lastprofil = load_waermebedarf(BEISPIEL_CSV)
    assert len(lastprofil) == 48
    assert lastprofil.name == "waermelast_kwh"


def test_synthetische_waermelast_summe_stimmt():
    lastprofil = synthetische_waermelast(jahreswaermebedarf_mwh=3500)
    assert len(lastprofil) == 8760
    # Summe entspricht (bis auf Rundung) dem vorgegebenen Jahreswaermebedarf
    assert lastprofil.sum() == pytest_approx_mwh(3500)


def pytest_approx_mwh(mwh: float):
    import pytest

    return pytest.approx(mwh * 1000, rel=1e-6)
