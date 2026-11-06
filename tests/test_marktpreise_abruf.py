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


def test_cache_wird_gelesen_ohne_abruf(tmp_path, monkeypatch):
    import lcoh_tool.marktpreise_abruf as m

    idx = pd.date_range("2023-01-01", periods=3, freq="h", name="zeitstempel")
    pd.Series([1.0, 2.0, 3.0], index=idx, name="preis_eur_mwh").to_csv(tmp_path / "marktpreise_2023.csv")
    monkeypatch.setattr(m, "lade_entsoe_preise", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Abruf")))
    assert list(m.lade_preise_mit_cache(2023, "DE_LU", tmp_path)) == [1.0, 2.0, 3.0]


def test_abruf_wird_gecacht(tmp_path, monkeypatch):
    import lcoh_tool.marktpreise_abruf as m

    idx = pd.date_range("2024-01-01", periods=3, freq="h", name="zeitstempel")
    roh = pd.Series([5.0, 6.0, 7.0], index=idx, name="preis_eur_mwh")
    aufrufe = []
    monkeypatch.setattr(m, "lade_entsoe_preise", lambda j, z: aufrufe.append((j, z)) or roh)
    m.lade_preise_mit_cache(2024, "DE_LU", tmp_path)
    m.lade_preise_mit_cache(2024, "DE_LU", tmp_path)
    assert aufrufe == [(2024, "DE_LU")] and (tmp_path / "marktpreise_2024.csv").exists()
