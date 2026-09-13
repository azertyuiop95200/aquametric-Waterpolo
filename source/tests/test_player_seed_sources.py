from services.player_intelligence import PROFILE_SEEDS


def _seed(name):
    return next(row for row in PROFILE_SEEDS if row["name"] == name)


def test_priority_transfers_use_direct_official_sources():
    assert _seed("Emily Ausmus")["club"] == "USC Trojans"
    assert "usctrojans.com" in _seed("Emily Ausmus")["source"]
    assert _seed("Elena Ruiz")["status"] == "club_official_transfer"
    assert "cnab.cat" in _seed("Elena Ruiz")["source"]
    assert _seed("Iva Rozic")["status"] == "club_official_transfer"
    assert "sisroma.it" in _seed("Iva Rozic")["source"]
    assert _seed("Isabel Piralkova")["club"] == "CN Sabadell"
    assert "rfen.es" in _seed("Isabel Piralkova")["source"]


def test_france_2026_roster_has_current_club_identity_evidence():
    names = {
        row["name"] for row in PROFILE_SEEDS
        if row["status"] == "federation_current_roster"
        and row["national"] == "France — Women Senior"
    }
    assert {"Lara Andres", "Lana Di Fraja", "Elhyne Kilic-Pegourie", "Eszter Lefebvre"} <= names
    for name in names:
        row = _seed(name)
        assert row["club"]
        assert row["national"] == "France — Women Senior"
        assert "ffnatation.fr" in row["source"]
        assert row["confidence"] >= .99
