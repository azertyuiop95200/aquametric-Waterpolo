"""Coach-first report presentation: confirmed sample only, not sport recognition."""
from pathlib import Path
from types import SimpleNamespace
import re
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[1]
ENV = Environment(loader=FileSystemLoader(str(ROOT / "templates")),
                  autoescape=select_autoescape(["html"]))

def render_report(team=None, opponent=None, players=None):
    stats = dict(labels={"goals": "Buts", "events": "Actions confirmées"},
                 note="Échantillon confirmé uniquement.",
                 excluded_unverified_events=2,
                 team={"basic": team or {"events": 0, "goals": None}},
                 opponent={"basic": opponent or {"events": 0, "goals": None}},
                 players=players or [])
    match = SimpleNamespace(team=SimpleNamespace(name="Blanc"), opponent="Bleu")
    return ENV.get_template("analysis_all_measurements.html").render(
        match=match, snapshot={"statistics": stats, "reference": None, "tactical": None})

def test_empty_report_has_accessible_sections_and_missing_values():
    result = render_report()
    ids = re.findall(r'id="(coach-[^"]+)"', result)
    links = re.findall(r'href="#(coach-[^"]+)"', result)
    assert len(ids) == len(set(ids)) == 11
    assert set(ids) == set(links)
    assert "Non mesuré" in result
    assert "Aucune joueuse identifiée" in result
    assert "Temps de jeu : registre de rotations" in result

def test_sample_zero_not_unknown_and_no_composite_player_evaluation():
    result = render_report(
        {"events": 3, "goals": 0}, {"events": 0, "goals": None},
        [{"player_id": 1, "name": "Joueuse test", "perspective": "for", "cap_number": 7,
          "report": {"basic": {"goals": 0}, "evaluation": {"overall": "PRIVATE_SCORE_MARKER"}}}])
    assert "0<small class=\"coach-report-muted\"> · échantillon</small>" in result
    assert "Non mesuré" in result
    assert "Joueuse test" in result and "bonnet 7" in result
    assert "PRIVATE_SCORE_MARKER" not in result

def test_unknown_module_does_not_render_empty_data_as_performance():
    result = render_report()
    assert "Cartographie : trajectoires identifiées" in result
    assert "Aucune joueuse identifiée" in result
