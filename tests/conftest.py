from pathlib import Path

import pytest

from lcoh_tool.marktpreise import load_marktpreise

BEISPIEL = Path(__file__).parents[1] / "data" / "marktpreise_beispiel.csv"


@pytest.fixture(autouse=True)
def marktpreise_ohne_entsoe(monkeypatch):
    """Tests rufen ENTSO-E nie auf, sondern lesen die 48-Stunden-Beispieldatei."""
    import lcoh_tool.projekt as projekt
    import lcoh_tool.variation as variation

    lade = lambda config: load_marktpreise(BEISPIEL)
    monkeypatch.setattr(projekt, "lade_marktpreisreihe", lade)
    monkeypatch.setattr(variation, "lade_marktpreisreihe", lade)
