import numpy as np
import pandas as pd
import pytest

pytest.importorskip("windpowerlib")

from lcoh_tool.config import WindpowerlibConfig
from lcoh_tool.windpark import berechne_windprofil


def _wetter(stunden=48, wind=8.0):
    index = pd.date_range("2023-01-01", periods=stunden, freq="h", name="zeitstempel")
    return pd.DataFrame(
        {
            "wind_100m_ms": np.full(stunden, wind),
            "temperatur_c": 10.0,
            "druck_hpa": 1013.0,
        },
        index=index,
    )


def _cfg(**kwargs):
    return WindpowerlibConfig(breitengrad=53.6, laengengrad=10.6, **kwargs)


def test_windprofil_hat_gleiche_laenge_und_ist_nicht_negativ():
    profil = berechne_windprofil(_wetter(), _cfg())
    assert len(profil) == 48
    assert (profil >= 0).all()
    assert profil.max() > 0


def test_windprofil_skaliert_mit_anlagenzahl_und_parkwirkungsgrad():
    einzeln = berechne_windprofil(_wetter(), _cfg(anzahl_anlagen=1, parkwirkungsgrad=1.0))
    park = berechne_windprofil(_wetter(), _cfg(anzahl_anlagen=3, parkwirkungsgrad=0.9))
    assert park.iloc[0] == pytest.approx(einzeln.iloc[0] * 3 * 0.9)


def test_windprofil_ohne_wind_ist_null():
    profil = berechne_windprofil(_wetter(wind=0.0), _cfg())
    assert profil.sum() == pytest.approx(0.0)
