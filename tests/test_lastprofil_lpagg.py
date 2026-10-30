import pytest

from lcoh_tool.config import GebaeudetypConfig, LpaggConfig
from lcoh_tool.lastprofil_lpagg import baue_lpagg_cfg, erzeuge_waermelast_lpagg


def test_gewerbe_mit_calculate_wirft_fehler():
    cfg = LpaggConfig(gebaeude={"Buero": GebaeudetypConfig(house_type="GHD/G1", q_heiz_a_kwh=50000)})
    with pytest.raises(ValueError, match="Gewerbetypen"):
        baue_lpagg_cfg(cfg, "wetter.dat")


def test_baue_lpagg_cfg_uebersetzt_gebaeude():
    cfg = LpaggConfig(
        gebaeude={"EFH": GebaeudetypConfig(house_type="EFH", q_heiz_a_kwh=6000, anzahl=25, n_pers=3, n_we=1)},
        try_region=4,
        jahr=2027,
    )
    lpagg_cfg = baue_lpagg_cfg(cfg, "wetter.dat")
    haus = lpagg_cfg["houses"]["EFH"]
    assert haus["Q_Heiz_a"] == 6000
    assert haus["copies"] == 25
    assert lpagg_cfg["settings"]["start"] == [2027, 1, 1, 0, 0, 0]


def test_erzeuge_waermelast_lpagg_liefert_jahresprofil():
    pytest.importorskip("lpagg")
    cfg = LpaggConfig(
        gebaeude={"EFH": GebaeudetypConfig(house_type="EFH", q_heiz_a_kwh=6000, anzahl=3, n_pers=3, n_we=1)},
        jahr=2027,
    )
    profil = erzeuge_waermelast_lpagg(cfg)
    assert len(profil) == 8760
    assert str(profil.index[0]) == "2027-01-01 00:00:00"
    assert (profil >= 0).all()
    # Heizwaerme (3 x 6000 kWh) plus Trinkwarmwasser -> mindestens Heizenergie
    assert profil.sum() >= 3 * 6000 * 0.95
