"""Waermelastprofil aus Gebaeudetypen und -anzahl mit lpagg.

lpagg (https://github.com/jnettels/lpagg, MIT) erzeugt aus Gebaeudetypen
(VDI 4655 fuer Wohngebaeude, BDEW fuer Gewerbe), Jahresverbraeuchen und einem
DWD-Testreferenzjahr ein stuendliches Lastprofil und beruecksichtigt dabei
Feiertage, Sommerzeit und die Gleichzeitigkeit mehrerer Gebaeude.

Hier wird nur die Heizwaerme verwendet: Raumheizung (E_th_RH) plus
Trinkwarmwasser (E_th_TWE) von Wohn- und Gewerbegebaeuden. Kaelte und
Netzverluste sind nicht enthalten (das Waermenetz selbst liegt ausserhalb des
Scopes des Tools).

lpagg ist optional und nicht auf PyPI: ``pip install -e ".[lpagg]"``.
Die Rechnung dauert je nach Gebaeudezahl einige Sekunden bis Minuten.
"""

from __future__ import annotations

import os
import sys
import types

import numpy as np
import pandas as pd

from lcoh_tool.config import LpaggConfig


def _stub_tkinter_falls_noetig() -> None:
    """lpagg importiert tkinter fuer einen Dateidialog, den wir nicht nutzen.
    Fehlt tkinter (z. B. auf Linux-Servern), wird ein leerer Platzhalter gesetzt."""
    try:
        import tkinter  # noqa: F401
    except ModuleNotFoundError:
        tk = types.ModuleType("tkinter")
        tk.Tk = object
        dialog = types.ModuleType("tkinter.filedialog")
        tk.filedialog = dialog
        sys.modules["tkinter"] = tk
        sys.modules["tkinter.filedialog"] = dialog


WOHNGEBAEUDE = ("EFH", "MFH")


def baue_lpagg_cfg(
    cfg: LpaggConfig,
    wetter_pfad: str,
    jahreswaermebedarf_kwh: float | None = None,
    wetter_typ: str = "DWD",
) -> dict:
    """Uebersetzt die Tool-Config in das cfg-Dictionary von lpagg.

    Fehlt bei einem Gebaeudetyp ``q_heiz_a_kwh``, wird der Gesamtwaermebedarf
    gleichmaessig auf alle Gebaeude verteilt (Naeherung; die Skalierung auf den
    Jahreswert folgt am Ende in ``erzeuge_waermelast_lpagg``).
    """
    anzahl_gesamt = sum(g.anzahl for g in cfg.gebaeude.values())
    haeuser = {}
    for name, g in cfg.gebaeude.items():
        q_heiz = g.q_heiz_a_kwh
        if q_heiz is None:
            if not jahreswaermebedarf_kwh:
                raise ValueError(
                    f"Gebaeude '{name}': q_heiz_a_kwh fehlt und kein jahreswaermebedarf_mwh "
                    "angegeben, aus dem er sich ableiten liesse."
                )
            q_heiz = jahreswaermebedarf_kwh / anzahl_gesamt
        if g.house_type not in WOHNGEBAEUDE and "calculate" in (g.q_tww_a_kwh, g.w_a_kwh):
            raise ValueError(
                f"Gebaeude '{name}' ({g.house_type}): Bei Gewerbetypen muessen "
                "q_tww_a_kwh und w_a_kwh als Zahlen angegeben werden (nicht 'calculate')."
            )
        eintrag = {
            "Q_Heiz_a": q_heiz,
            "Q_TWW_a": g.q_tww_a_kwh,
            "W_a": g.w_a_kwh,
            "TRY": cfg.try_region,
            "house_type": g.house_type,
            "N_Pers": g.n_pers,
            "N_WE": g.n_we,
            "copies": g.anzahl,
            "sigma": g.sigma,
        }
        if g.q_kalt_a_kwh is not None:
            eintrag["Q_Kalt_a"] = g.q_kalt_a_kwh
        haeuser[name] = eintrag

    einstellungen = {
        "weather_file": wetter_pfad,
        "weather_data_type": wetter_typ,
        "print_file": "lpagg_load.dat",
        "rename_columns": {
            "Q_Heiz_TT": "E_th_RH",
            "Q_Kalt_TT": "E_th_KL",
            "Q_TWW_TT": "E_th_TWE",
            "Q_loss": "E_th_loss",
            "W_TT": "E_el",
        },
        "intervall": "1 hours",
        "start": [cfg.jahr, 1, 1, 0, 0, 0],
        "end": [cfg.jahr + 1, 1, 1, 0, 0, 0],
        "remove_leapyear": False,
        "apply_DST": True,
        "summer_temperature_limit": cfg.sommer_temperaturgrenze_c,
        "zero_summer_heat_demand": True,
        "holidays": {"country": cfg.feiertage_land},
        "log_level": "warning",
        "show_plot": False,
        "save_plot_filetypes": [],
    }
    if cfg.feiertage_bundesland:
        einstellungen["holidays"]["province"] = cfg.feiertage_bundesland
    return {"settings": einstellungen, "houses": haeuser}


def schreibe_era5_als_igs(wetter: pd.DataFrame, pfad: str) -> None:
    """Schreibt die ERA5-Temperatur als lpagg-Wetterdatei (Format "IGS", 8760 Stunden).

    Nur die Lufttemperatur (und Wind/Druck) sind belegt; lpagg nutzt fuer die
    Lastverteilung die Temperatur. ERA5 liegt in UTC und wird um eine Stunde auf
    Mitteleuropaeische Zeit verschoben. Ein 29. Februar entfaellt.
    """
    w = wetter.sort_index()
    w = w[~((w.index.month == 2) & (w.index.day == 29))]
    if len(w) != 8760:
        raise ValueError(f"ERA5-Wetter ergibt {len(w)} statt 8760 Stunden (volles Jahr noetig).")
    daten = pd.DataFrame(
        {
            "HOUR": range(1, 8761),
            "IBEAM_H": 0.0,
            "IDIFF_H": 0.0,
            "TAMB": np.roll(w["temperatur_c"].to_numpy(), 1),
            "WSPEED": np.roll(w["wind_10m_ms"].to_numpy(), 1) if "wind_10m_ms" in w else 0.0,
            "RHUM": 70.0,
            "WDIR": 0.0,
            "CCOVER": 0.0,
            "PAMB": np.roll(w["druck_hpa"].to_numpy(), 1) if "druck_hpa" in w else 1013.0,
        }
    )
    daten.to_csv(pfad, sep=" ", header=False, index=False, float_format="%.2f")


def erzeuge_waermelast_lpagg(
    cfg: LpaggConfig,
    jahreswaermebedarf_mwh: float | None = None,
    wetter_standort: tuple[float, float, int] | None = None,
) -> pd.Series:
    """Berechnet die stuendliche Heizwaermelast (kWh) fuer die Gebaeude in ``cfg``.

    lpagg liefert die Lastverteilung. Ist ``jahreswaermebedarf_mwh`` gesetzt, wird das
    Profil auf diese Jahressumme skaliert. ``wetter_standort`` = (Breite, Laenge, Jahr)
    ist der Standard fuer ``wetterquelle: era5``, wenn die Config keinen eigenen nennt.
    """
    import tempfile

    _stub_tkinter_falls_noetig()
    try:
        import matplotlib

        matplotlib.use("Agg")  # keine Fenster/Plots aus lpagg
        import lpagg
        from lpagg.agg import aggregator_run, perform_configuration
    except ImportError as fehler:
        raise ImportError(
            "Fuer die lpagg-Waermelast wird lpagg benoetigt: "
            'pip install -e ".[lpagg]"'
        ) from fehler

    gesamt_kwh = jahreswaermebedarf_mwh * 1000 if jahreswaermebedarf_mwh else None

    with tempfile.TemporaryDirectory() as ordner:
        if cfg.wetterquelle == "era5":
            from lcoh_tool.config import WindpowerlibConfig
            from lcoh_tool.wetterdaten import lade_wetterdaten

            breite = cfg.breitengrad if cfg.breitengrad is not None else (wetter_standort or (None,))[0]
            laenge = cfg.laengengrad if cfg.laengengrad is not None else (wetter_standort or (0, None))[1]
            jahr = cfg.wetterjahr or (wetter_standort or (0, 0, None))[2]
            if breite is None or laenge is None or jahr is None:
                raise ValueError(
                    "lpagg wetterquelle 'era5' braucht breitengrad, laengengrad und wetterjahr "
                    "(oder einen Windpark-Block windpowerlib, dessen Werte dann gelten)."
                )
            wetter = lade_wetterdaten(
                WindpowerlibConfig(
                    breitengrad=breite,
                    laengengrad=laenge,
                    jahr=jahr,
                    wetterquelle="era5",
                    wetter_cache_ordner=cfg.wetter_cache_ordner,
                )
            )
            wetter_pfad = os.path.join(ordner, "era5_igs.dat")
            schreibe_era5_als_igs(wetter, wetter_pfad)
            wetter_typ = "IGS"
        else:
            wetter_pfad = os.path.abspath(
                cfg.wetter_pfad
                or os.path.join(
                    os.path.dirname(lpagg.__file__),
                    "resources_weather",
                    f"TRY2010_{cfg.try_region:02d}_Jahr.dat",
                )
            )
            wetter_typ = "DWD"

        lpagg_cfg = perform_configuration(
            cfg=baue_lpagg_cfg(cfg, wetter_pfad, gesamt_kwh, wetter_typ), ignore_errors=False
        )
        ergebnis = aggregator_run(lpagg_cfg)["weather_data"]

    spalten = [
        s
        for s in ergebnis.columns
        if str(s).startswith(("E_th_RH_", "E_th_TWE_"))
    ]
    if not spalten:
        raise RuntimeError("lpagg lieferte keine Waermespalten (E_th_RH_*/E_th_TWE_*).")
    last = ergebnis[spalten].sum(axis=1)

    # lpagg beschriftet Stunden mit dem Stundenende (01:00 ... 00:00 Folgetag);
    # das Tool nutzt Stundenanfang (00:00 ... 23:00), wie die Erzeugungsprofile.
    last.index = last.index - pd.Timedelta(hours=1)
    last.index.name = "zeitstempel"

    if gesamt_kwh:
        if last.sum() <= 0:
            raise RuntimeError("lpagg-Profil hat keinen Waermebedarf; Skalierung nicht moeglich.")
        last = last * (gesamt_kwh / last.sum())
    return last.rename("waermelast_kwh")
