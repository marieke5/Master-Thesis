"""Plots zum Betrieb: Windstrom, Waermepumpe, Elektrodenkessel und Netzbezug.

Erzeugt aus einem Projektlauf (preisgesteuerte Betriebsweise) drei Bilder:

* ``betrieb_jahr.png``  - Monatssummen: Windstromerzeugung und Strombedarf der Waermeerzeuger
  nach Quelle (Direktleitung/Netz) sowie Waermeerzeugung nach Erzeuger.
* ``betrieb_woche.png`` - eine Woche stuendlich: Windleistung, Strombezug je Erzeuger und
  Quelle, Speicherstand und Marktpreis (mit Preisschwelle).

Aufruf:
    python -m lcoh_tool.plots --config config/parameter_jahreslauf.yaml --ausgabe plots
    python -m lcoh_tool.plots --config ... --woche 2023-01-09     # Startdatum der Woche

Ohne ``--woche`` wird die Woche mit der hoechsten Waermelast gezeigt. Benoetigt matplotlib.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

# Farbe folgt dem Akteur (feste Reihenfolge der Referenzpalette), Netz neutral grau.
FARBEN = {
    "wind": "#2a78d6",
    "wp": "#eb6834",
    "ek": "#1baf7a",
    "netz": "#8b8a85",
    "speicher": "#6250d6",
    "beladung": "#6250d6",
    "entladung": "#e87ba4",
    "preis": "#52514e",
}
TEXT, TEXT2, GITTER, FLAECHE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONATE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.facecolor": FLAECHE, "axes.facecolor": FLAECHE, "savefig.facecolor": FLAECHE,
            "text.color": TEXT, "axes.labelcolor": TEXT2, "xtick.color": TEXT2, "ytick.color": TEXT2,
            "axes.edgecolor": GITTER, "axes.grid": True, "grid.color": GITTER, "grid.linewidth": 0.8,
            "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False,
            "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
            "font.size": 10, "legend.frameon": False,
        }
    )
    return plt


def pruefe_bilanz(bilanz: pd.DataFrame) -> None:
    if "strom_wp_direkt_kwh" not in bilanz.columns:
        raise ValueError("Die Plots brauchen die preisgesteuerte Betriebsweise (Block 'steuerung').")


def monatsdaten(bilanz: pd.DataFrame) -> pd.DataFrame:
    """Monatssummen in MWh (Strom und Waerme)."""
    b = bilanz
    m = pd.DataFrame(
        {
            "wind": b["erzeugung_kwh"],
            "wp_direkt": b["strom_wp_direkt_kwh"],
            "ek_direkt": b["strom_bk_direkt_kwh"],
            "netz": b["strom_wp_netz_kwh"] + b["strom_bk_netz_kwh"],
            "waerme_speicher": b["waerme_aus_speicher_kwh"],
            "waermelast": b["waermelast_kwh"],
        }
    ).resample("MS").sum() / 1000
    return m


def kennzahlen_text(bilanz: pd.DataFrame) -> dict[str, float]:
    """Jahressummen und Betriebsstunden fuer Beschriftung/Ausgabe."""
    b = bilanz
    return {
        "wind_mwh": b["erzeugung_kwh"].sum() / 1000,
        "wp_direkt_mwh": b["strom_wp_direkt_kwh"].sum() / 1000,
        "ek_direkt_mwh": b["strom_bk_direkt_kwh"].sum() / 1000,
        "netz_mwh": (b["strom_wp_netz_kwh"] + b["strom_bk_netz_kwh"]).sum() / 1000,
        "wp_stunden": int(((b["strom_wp_direkt_kwh"] + b["strom_wp_netz_kwh"]) > 0).sum()),
        "ek_stunden": int(((b["strom_bk_direkt_kwh"] + b["strom_bk_netz_kwh"]) > 0).sum()),
    }


def plot_jahr(bilanz: pd.DataFrame, pfad: Path) -> Path:
    plt = _plt()
    pruefe_bilanz(bilanz)
    m = monatsdaten(bilanz)
    k = kennzahlen_text(bilanz)
    x = range(len(m))
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 7.5), sharex=True, constrained_layout=True)

    a1.bar(x, m["wind"], color=FARBEN["wind"], width=0.7)
    a1.set_title(f"Windstromerzeugung je Monat (Jahr: {k['wind_mwh']:,.0f} MWh)".replace(",", "."))
    a1.set_ylabel("MWh Strom")

    unten = pd.Series(0.0, index=m.index)
    for spalte, farbe, name in [
        ("wp_direkt", FARBEN["wp"], f"Wärmepumpe, Direktleitung ({k['wp_direkt_mwh']:.0f} MWh, {k['wp_stunden']} h)"),
        ("ek_direkt", FARBEN["ek"], f"Elektrodenkessel, Direktleitung ({k['ek_direkt_mwh']:.0f} MWh, {k['ek_stunden']} h)"),
        ("netz", FARBEN["netz"], f"Netzbezug, Rückfall ({k['netz_mwh']:.0f} MWh)"),
    ]:
        a2.bar(x, m[spalte], bottom=unten, color=farbe, width=0.7, label=name, edgecolor=FLAECHE, linewidth=1.5)
        unten = unten + m[spalte]
    a2.set_title("Strombedarf der Wärmeerzeuger je Monat, nach Quelle")
    a2.set_ylabel("MWh Strom")
    a2.legend(loc="upper center", ncol=1, fontsize=9)
    a2.set_xticks(list(x), [MONATE[d.month - 1] for d in m.index])
    a2.set_ylim(0, max(unten.max() * 1.45, 1))
    fig.savefig(pfad, dpi=200)
    plt.close(fig)
    return pfad


def waehle_woche(bilanz: pd.DataFrame, start: str | None) -> pd.DataFrame:
    if start is not None:
        beginn = pd.Timestamp(start)
    else:  # Woche mit der hoechsten Waermelast
        wochen = bilanz["waermelast_kwh"].resample("W-MON", closed="left", label="left").sum()
        beginn = wochen.idxmax()
    woche = bilanz.loc[beginn: beginn + pd.Timedelta(days=7) - pd.Timedelta(hours=1)]
    if woche.empty:
        raise ValueError(f"Keine Daten fuer die Woche ab {beginn.date()}.")
    return woche


def plot_woche(bilanz: pd.DataFrame, pfad: Path, schwelle_eur_mwh: float | None = None,
               start: str | None = None) -> Path:
    plt = _plt()
    import matplotlib.dates as mdates
    from matplotlib.ticker import FuncFormatter

    pruefe_bilanz(bilanz)
    w = waehle_woche(bilanz, start)
    fig, axes = plt.subplots(4, 1, figsize=(10, 10), sharex=True, constrained_layout=True,
                             gridspec_kw={"height_ratios": [1, 1.3, 1, 1]})
    a1, a2, a3, a4 = axes
    a1.plot(w.index, w["erzeugung_kwh"], color=FARBEN["wind"], linewidth=2)
    a1.set_title("Windleistung")
    a1.set_ylabel("kW")

    wp = w["strom_wp_direkt_kwh"]
    ek = w["strom_bk_direkt_kwh"]
    netz = w["strom_wp_netz_kwh"] + w["strom_bk_netz_kwh"]
    a2.stackplot(w.index, wp, ek, netz, colors=[FARBEN["wp"], FARBEN["ek"], FARBEN["netz"]],
                 labels=["Wärmepumpe, Direktleitung", "Elektrodenkessel, Direktleitung", "Netzbezug (Rückfall)"],
                 linewidth=0)
    a2.set_title("Strombezug der Wärmeerzeuger")
    a2.set_ylabel("kW")
    a2.legend(loc="upper left", ncol=1, fontsize=9)

    a3.plot(w.index, w["speicherstand_kwh"], color=FARBEN["speicher"], linewidth=2)
    a3.set_title("Speicherstand (thermisch)")
    a3.set_ylabel("kWh")
    a3.set_ylim(bottom=0)

    a4.plot(w.index, w["marktpreis_eur_mwh"], color=FARBEN["preis"], linewidth=1.6)
    if schwelle_eur_mwh is not None:
        a4.axhline(schwelle_eur_mwh, color=FARBEN["wp"], linewidth=1.2, linestyle="--")
        a4.annotate(f"Preisschwelle {schwelle_eur_mwh:g} €/MWh", xy=(w.index[0], schwelle_eur_mwh),
                    xytext=(4, 4), textcoords="offset points", fontsize=9, color=TEXT2)
    a4.set_title("Marktpreis Day-Ahead" if schwelle_eur_mwh is not None else "PPA-Preis (fest)")
    a4.set_ylabel("€/MWh")
    a4.xaxis.set_major_locator(mdates.DayLocator())
    a4.xaxis.set_major_formatter(
        FuncFormatter(lambda v, _: f"{WOCHENTAGE[mdates.num2date(v).weekday()]} {mdates.num2date(v):%d.%m.}")
    )
    fig.savefig(pfad, dpi=200)
    plt.close(fig)
    return pfad


def plot_speicher(bilanz: pd.DataFrame, pfad: Path, start: str | None = None) -> Path:
    """Be- und Entladen des Waermespeichers: Jahr (Tagesstand, Monatssummen) und eine Woche."""
    plt = _plt()
    import matplotlib.dates as mdates
    from matplotlib.ticker import FuncFormatter

    pruefe_bilanz(bilanz)
    b = bilanz
    fig, (a1, a2, a3, a4) = plt.subplots(4, 1, figsize=(10, 11.5), constrained_layout=True,
                                         gridspec_kw={"height_ratios": [1, 1, 1, 1]})
    # 1) Fuellstand ueber das Jahr: Tagesmittel mit Spanne Min-Max
    tag = b["speicherstand_kwh"].resample("D")
    a1.fill_between(tag.min().index, tag.min(), tag.max(), color=FARBEN["speicher"], alpha=0.25, linewidth=0)
    a1.plot(tag.mean().index, tag.mean(), color=FARBEN["speicher"], linewidth=1.6)
    a1.set_title("Speicherstand über das Jahr (Linie: Tagesmittel, Fläche: Tagesminimum bis -maximum)")
    a1.set_ylabel("kWh Wärme")
    a1.set_ylim(bottom=0)
    a1.xaxis.set_major_locator(mdates.MonthLocator())
    a1.xaxis.set_major_formatter(FuncFormatter(lambda v, _: MONATE[mdates.num2date(v).month - 1]))

    # 2) Monatssummen Be- und Entladung
    lade = b["waerme_in_speicher_kwh"].resample("MS").sum() / 1000
    entl = b["waerme_aus_speicher_kwh"].resample("MS").sum() / 1000
    x = range(len(lade))
    a2.bar(x, lade, color=FARBEN["beladung"], width=0.7, label=f"Beladung ({lade.sum():.0f} MWh)")
    a2.bar(x, -entl, color=FARBEN["entladung"], width=0.7, label=f"Entladung ({entl.sum():.0f} MWh)")
    a2.axhline(0, color=TEXT2, linewidth=0.8)
    a2.set_title("Be- und Entladung je Monat")
    a2.set_ylabel("MWh Wärme")
    a2.set_xticks(list(x), [MONATE[d.month - 1] for d in lade.index])
    a2.legend(loc="upper left", fontsize=9)
    a2.set_ylim(top=max(lade.max(), entl.max(), 1) * 1.35)

    # 3) + 4) eine Woche stuendlich
    w = waehle_woche(b, start)
    a3.bar(w.index, w["waerme_in_speicher_kwh"], width=1 / 24, color=FARBEN["beladung"], label="Beladung")
    a3.bar(w.index, -w["waerme_aus_speicher_kwh"], width=1 / 24, color=FARBEN["entladung"], label="Entladung")
    a3.axhline(0, color=TEXT2, linewidth=0.8)
    a3.set_title("Be- und Entladen, stündlich (gleiche Woche wie im Betriebsplot)")
    a3.set_ylabel("kW Wärme")
    a3.legend(loc="upper left", fontsize=9)
    a4.plot(w.index, w["speicherstand_kwh"], color=FARBEN["speicher"], linewidth=2)
    a4.set_title("Speicherstand in dieser Woche")
    a4.set_ylabel("kWh Wärme")
    a4.set_ylim(bottom=0)
    for ax in (a3, a4):
        ax.xaxis.set_major_locator(mdates.DayLocator())
        ax.xaxis.set_major_formatter(
            FuncFormatter(lambda v, _: f"{WOCHENTAGE[mdates.num2date(v).weekday()]} {mdates.num2date(v):%d.%m.}")
        )
    fig.savefig(pfad, dpi=200)
    plt.close(fig)
    return pfad


def main() -> None:
    parser = argparse.ArgumentParser(description="Betriebs-Plots (Wind, Waermepumpe, Kessel, Netz)")
    parser.add_argument("--config", required=True)
    parser.add_argument("--ausgabe", default="plots", help="Zielordner fuer die PNG-Dateien")
    parser.add_argument("--woche", default=None, help="Startdatum der Woche, z. B. 2023-01-09")
    args = parser.parse_args()

    from lcoh_tool.projekt import berechne_projekt

    ergebnis = berechne_projekt(args.config)
    ordner = Path(args.ausgabe)
    ordner.mkdir(parents=True, exist_ok=True)
    cfg = ergebnis.config
    schwelle = cfg.steuerung.preisschwelle_eur_pro_mwh if cfg.steuerung and cfg.ppa is None else None
    print(plot_jahr(ergebnis.bilanz, ordner / "betrieb_jahr.png"))
    print(plot_woche(ergebnis.bilanz, ordner / "betrieb_woche.png", schwelle, args.woche))
    print(plot_speicher(ergebnis.bilanz, ordner / "betrieb_speicher.png", args.woche))


if __name__ == "__main__":
    main()
