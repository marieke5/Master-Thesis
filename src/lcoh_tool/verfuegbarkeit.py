"""Verfuegbarkeit der WEA: Ausfallbloecke (Wartung, Stoerung, Abschaltung) im Erzeugungsprofil.

Ein Ertragsgutachten oder eine WindPRO-Reihe liefert meist den Ertrag ohne Ausfaelle. Fuer die
Frage, wie oft die Waermeseite auf Netzbezug zurueckfallen muss, werden deshalb
``(1 - verfuegbarkeit)`` der Stunden in Bloecken von ``dauer_h`` Stunden zufaellig, aber
reproduzierbar (``seed``) auf Null gesetzt.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def wende_verfuegbarkeit_an(
    erzeugung: pd.Series, verfuegbarkeit: float = 1.0, dauer_h: int = 48, seed: int = 42
) -> pd.Series:
    if not 0 < verfuegbarkeit <= 1:
        raise ValueError("verfuegbarkeit muss zwischen 0 (ausschliesslich) und 1 liegen.")
    n = len(erzeugung)
    n_aus = int(round((1 - verfuegbarkeit) * n))
    if n_aus == 0 or n == 0:
        return erzeugung
    dauer = max(int(dauer_h), 1)
    rng = np.random.default_rng(seed)
    maske = np.zeros(n, dtype=bool)
    for start in rng.permutation(np.arange(0, n, dauer)):
        fehlt = n_aus - int(maske.sum())
        if fehlt <= 0:
            break
        maske[start : start + min(dauer, fehlt)] = True
    return erzeugung.where(~maske, 0.0)
