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


def baue_lpagg_cfg(cfg: LpaggConfig, wetter_pfad: str) -> dict:
    """Uebersetzt die Tool-Config in das cfg-Dictionary von lpagg."""
    haeuser = {}
    for name, g in cfg.gebaeude.items():
        if g.house_type not in WOHNGEBAEUDE and "calculate" in (g.q_tww_a_kwh, g.w_a_kwh):
            raise ValueError(
                f"Gebaeude '{name}' ({g.house_type}): Bei Gewerbetypen muessen "
                "q_tww_a_kwh und w_a_kwh als Zahlen angegeben werden (nicht 'calculate')."
            )
        eintrag = {
            "Q_Heiz_a": g.q_heiz_a_kwh,
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
        "weather_data_type": "DWD",
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


def erzeuge_waermelast_lpagg(cfg: LpaggConfig) -> pd.Series:
    """Berechnet die stuendliche Heizwaermelast (kWh) fuer die Gebaeude in ``cfg``."""
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

    wetter_pfad = cfg.wetter_pfad or os.path.join(
        os.path.dirname(lpagg.__file__),
        "resources_weather",
        f"TRY2010_{cfg.try_region:02d}_Jahr.dat",
    )
    lpagg_cfg = perform_configuration(
        cfg=baue_lpagg_cfg(cfg, os.path.abspath(wetter_pfad)), ignore_errors=False
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
    return last.rename("waermelast_kwh")
