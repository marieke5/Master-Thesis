"""Preisgesteuerte Betriebsweise der Direktleitung (stundenscharf).

Regel (siehe ``config.SteuerungConfig``):

* **Direktleitung aktiv**, wenn der Marktpreis der Stunde <= Preisschwelle liegt
  (negativ oder sehr niedrig). Dann wird Waerme erzeugt, der Bedarf gedeckt und
  der Waermespeicher bis zur Kapazitaet geladen.
* **Notbetrieb**, wenn der Preis ueber der Schwelle liegt, der Speicher aber
  fast leer ist (Fuellstand <= Untergrenze) und Waerme gebraucht wird. Dann wird
  nur der aktuelle Bedarf aus Windstrom gedeckt (keine Speicherladung).
* Sonst deckt der Speicher den Bedarf.

Reihenfolge der Bedarfsdeckung je Stunde: Direktstrom -> Speicher -> Netzbezug
(Rueckfallstrom, mit Netzentgelt). Waermepumpe wird vor dem Elektrodenkessel
eingesetzt; ``nennleistung_kw`` von Waermepumpe und Backup gilt als thermische
Leistung, die Speicherkapazitaet als thermische Kapazitaet. Direktstrom wird zum
Marktpreis der Stunde bewertet (Opportunitaetskosten; negativ = Erloes).

Annahmen/Vereinfachungen: Speicher startet mit ``speicher_start_anteil``; der
Endfuellstand wird nicht bilanziert; Wind, der nicht verbraucht wird, bleibt
ausserhalb der Betrachtung.
"""

from __future__ import annotations

import pandas as pd

from lcoh_tool.config import ToolConfig


def berechne_bilanz_preisgesteuert(
    erzeugung_kwh: pd.Series,
    waermelast_kwh: pd.Series,
    marktpreis_eur_mwh: pd.Series,
    config: ToolConfig,
) -> pd.DataFrame:
    """Stundenbilanz mit preisgesteuerter Direktleitung (Spalten wie ``bilanz.berechne_bilanz``
    plus ``marktpreis_eur_mwh``, ``direktleitung_aktiv``, ``notbetrieb``, ...)."""
    st = config.steuerung
    if st is None:
        raise ValueError("Keine Steuerung (Block 'steuerung') in der Config gesetzt.")
    if st.direktstrom_bepreisung == "fest" and st.direktstrompreis_eur_pro_mwh is None:
        raise ValueError("direktstrom_bepreisung 'fest' braucht direktstrompreis_eur_pro_mwh.")

    index = waermelast_kwh.index
    preis = marktpreis_eur_mwh.reindex(index)
    fehlend = int(preis.isna().sum())
    if fehlend:
        raise ValueError(
            f"Marktpreise fehlen fuer {fehlend} von {len(index)} Stunden der Waermelast "
            "(Zeitbasis und Jahr der Preisreihe pruefen)."
        )
    wind = erzeugung_kwh.reindex(index).fillna(0.0).to_numpy()
    last = waermelast_kwh.to_numpy()
    preis_np = preis.to_numpy()

    jazl = config.waermepumpe.jazl
    p_wp = config.waermepumpe.nennleistung_kw
    eta = config.backup.wirkungsgrad
    p_bk = config.backup.nennleistung_kw
    kap = config.speicher.kapazitaet_kwh
    verlust = config.speicher.verlust_pro_stunde
    if st.speicher_untergrenze_stunden is not None:
        untergrenze = min(st.speicher_untergrenze_stunden * float(last.max()), kap)
    else:
        untergrenze = st.speicher_untergrenze_anteil * kap
    schwelle = st.preisschwelle_eur_pro_mwh

    n = len(index)
    aktiv = [False] * n
    notbetrieb = [False] * n
    direkt = [0.0] * n
    rueckfall = [0.0] * n
    stand = [0.0] * n
    waerme_direkt = [0.0] * n
    aus_speicher = [0.0] * n
    luecke = [0.0] * n

    s = st.speicher_start_anteil * kap
    for i in range(n):
        s *= 1 - verlust
        q, w, p = last[i], wind[i], preis_np[i]

        niedrig = p <= schwelle
        noet = (not niedrig) and q > 0 and s <= untergrenze
        aktiv[i] = niedrig or noet
        notbetrieb[i] = noet

        hw = hb = 0.0
        if aktiv[i]:
            ziel = q + max(kap - s, 0.0) if niedrig else q
            hw = min(p_wp, ziel, w * jazl)
            hb = min(p_bk, ziel - hw, (w - hw / jazl) * eta)
            direkt[i] = hw / jazl + hb / eta
        erzeugt = hw + hb
        waerme_direkt[i] = erzeugt

        gedeckt = min(erzeugt, q)
        s = min(kap, s + (erzeugt - gedeckt))
        rest = q - gedeckt

        entnahme = min(rest, s)
        s -= entnahme
        rest -= entnahme
        aus_speicher[i] = entnahme

        if rest > 1e-9:
            hw2 = min(p_wp - hw, rest)
            hb2 = min(p_bk - hb, rest - hw2)
            rueckfall[i] = hw2 / jazl + hb2 / eta
            rest -= hw2 + hb2
        luecke[i] = max(rest, 0.0)
        stand[i] = s

    direkt_s = pd.Series(direkt, index=index)
    if st.direktstrom_bepreisung == "fest":
        strompreis = pd.Series(st.direktstrompreis_eur_pro_mwh, index=index, dtype=float)
    else:
        strompreis = preis.astype(float)

    return pd.DataFrame(
        {
            "waermelast_kwh": waermelast_kwh,
            "strombedarf_wp_kwh": waermelast_kwh / jazl,
            "erzeugung_kwh": wind,
            "marktpreis_eur_mwh": preis,
            "direktleitung_aktiv": aktiv,
            "notbetrieb": notbetrieb,
            "speicherstand_kwh": stand,
            "direktanschluss_kwh": direkt_s,
            "rueckfall_kwh": rueckfall,
            "waerme_direkt_kwh": waerme_direkt,
            "waerme_aus_speicher_kwh": aus_speicher,
            "deckungsluecke_kwh": luecke,
            "direktstrom_preis_eur_mwh": strompreis,
            "direktstrom_kosten_eur": direkt_s / 1000 * strompreis,
        },
        index=index,
    )
