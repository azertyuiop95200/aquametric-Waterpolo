from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ultimate_result_loads_complete_measured_analytics_surface():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "analysis-metrics-surface.js").read_text(encoding="utf-8")
    assert "/static/analysis-metrics-surface.js?v=12.2.0" in base
    assert "/api/matches/${m[1]}/performance" in js
    assert "DONNÉES MESURÉES & ANALYSÉES · COMPLET" in js
    assert "Toutes les données mesurées" in js


def test_surface_exposes_full_team_and_player_measurement_families():
    js = (ROOT / "static" / "analysis-metrics-surface.js").read_text(encoding="utf-8")
    required = [
        "Précision tir", "Efficacité but", "Passes tentées", "Passes clés", "Actions créées",
        "Exclusions provoquées", "Exclusions concédées", "Interceptions", "Récupérations", "Blocs",
        "Arrêts", "Duels gagnés", "Duels perdus", "Pertes / 100 passes",
        "Sprint 5 m", "Sprint 10 m", "Vitesse nage max", "Vitesse de tir", "Temps de release",
        "Pertes de possession — cause, zone, phase, pression, décision",
        "Tirs — localisation, type, main, distance, vitesse, release",
        "Passes — type, zone, pression, décision",
        "Possessions, décisions et résistance à la pression",
        "Splits par période et par phase tactique",
        "Joueuse par joueuse — toutes les mesures",
    ]
    for needle in required:
        assert needle in js


def test_surface_never_substitutes_unmeasured_physical_values_and_retires_old_atlas_links():
    js = (ROOT / "static" / "analysis-metrics-surface.js").read_text(encoding="utf-8")
    assert "aucune mesure calibrée" in js
    assert "Une donnée non mesurée reste « — »" in js
    assert "a[href=\"/static/elite-video-atlas.html\"]" in js
    assert "/analysis-library#filmroom" in js
