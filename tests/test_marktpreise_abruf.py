import pandas as pd
import pytest

from lcoh_tool.marktpreise_abruf import lade_entsoe_preise, normiere_preise


def _roh(freq, start="2022-12-31 23:00", ende="2024-01-01 00:00", tz="UTC"):
    idx = pd.date_range(start, ende, freq=freq, tz=tz, inclusive="left")
    return pd.Series(50.0, index=idx)


def test_viertelstunden_werden_zu_stunden_gemittelt():
    roh = _roh("15min", "2023-01-01 00:00", "2024-01-01 00:00")
    roh.iloc[0:4] = [10, 20, 30, 40]
    s = normiere_preise(roh, 2023)
    assert len(s) == 8760
    assert s.iloc[0] == pytest.approx(25.0)
    assert s.index.tz is None and s.index.name == "zeitstempel"


def test_zeitzone_wird_nach_utc_umgerechnet():
    roh = _roh("h", "2022-12-31 23:00", "2023-12-31 23:00", tz="Europe/Berlin")
    s = normiere_preise(roh, 2023)
    assert s.index[0] == pd.Timestamp("2023-01-01 00:00")
    assert len(s) == 8760


def test_kleine_luecke_wird_gefuellt_grosse_wirft_fehler():
    roh = _roh("h", "2023-01-01 00:00", "2024-01-01 00:00")
    assert len(normiere_preise(roh.drop(roh.index[10:12]), 2023)) == 8760
    with pytest.raises(ValueError, match="ohne Preis"):
        normiere_preise(roh.drop(roh.index[10:20]), 2023)


def test_ohne_token_fehler(monkeypatch):
    monkeypatch.delenv("ENTSOE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ENTSOE_API_KEY"):
        lade_entsoe_preise(2023)
