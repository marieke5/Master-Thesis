import numpy as np
import pandas as pd
import pytest

from lcoh_tool.verfuegbarkeit import wende_verfuegbarkeit_an


def _reihe(n=8760):
    return pd.Series(100.0, index=pd.date_range("2023-01-01", periods=n, freq="h"))


def test_ohne_ausfall_unveraendert():
    r = _reihe()
    assert wende_verfuegbarkeit_an(r, 1.0).equals(r)


def test_anteil_der_ausfallstunden_und_bloecke():
    r = wende_verfuegbarkeit_an(_reihe(), 0.95, dauer_h=48, seed=1)
    aus = (r == 0)
    assert aus.sum() == round(0.05 * 8760)
    # Ausfaelle bestehen aus zusammenhaengenden Bloecken (nicht Einzelstunden)
    wechsel = (aus != aus.shift()).sum()
    assert wechsel <= 2 * (aus.sum() // 48 + 2)


def test_reproduzierbar_und_seed_abhaengig():
    a = wende_verfuegbarkeit_an(_reihe(), 0.9, seed=3)
    b = wende_verfuegbarkeit_an(_reihe(), 0.9, seed=3)
    c = wende_verfuegbarkeit_an(_reihe(), 0.9, seed=4)
    assert a.equals(b) and not a.equals(c)


def test_ungueltige_verfuegbarkeit():
    with pytest.raises(ValueError):
        wende_verfuegbarkeit_an(_reihe(), 0.0)
