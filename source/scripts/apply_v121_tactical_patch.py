from pathlib import Path

root = Path(__file__).resolve().parents[1]
extensions = root / "extensions.py"
e = extensions.read_text(encoding="utf-8")

import_anchor = "from evidence_coverage_routes import router as evidence_coverage_router\n"
old_import_line = "from tactical_media_routes import router as tactical_media_router, enrich_sequence_cards\n"
import_line = "from tactical_media_routes import router as tactical_media_router, enrich_sequence_cards, build_tactical_study_pack\n"
if old_import_line in e:
    e = e.replace(old_import_line, import_line, 1)
elif import_line not in e:
    if import_anchor not in e:
        raise SystemExit("tactical media import anchor not found")
    e = e.replace(import_anchor, import_anchor + import_line, 1)

old_cards = "    sequence_cards = _sequence_cards(match, report, artifacts)\n"
new_cards = "    sequence_cards = enrich_sequence_cards(match, report, artifacts)\n"
if old_cards in e:
    e = e.replace(old_cards, new_cards, 1)
elif new_cards not in e:
    raise SystemExit("sequence-card integration anchor not found")

router_anchor = "    app.include_router(evidence_coverage_router)\n"
router_line = "    app.include_router(tactical_media_router)\n"
if router_line not in e:
    if router_anchor not in e:
        raise SystemExit("router integration anchor not found")
    e = e.replace(router_anchor, router_anchor + router_line, 1)

# FastAPI normally copies every APIRouter route at include_router() time. Keep an
# explicit idempotent fallback because extensions.py also performs legacy manual
# registrations and older integration passes can otherwise leave the POST route
# out of the final application router.
fallback = '''    tactical_study_path = "/matches/{match_id}/intelligence/study-pack"\n    if not any(\n        getattr(route, "path", None) == tactical_study_path\n        and "POST" in (getattr(route, "methods", set()) or set())\n        for route in app.routes\n    ):\n        app.add_api_route(\n            tactical_study_path,\n            build_tactical_study_pack,\n            methods=["POST"],\n            name="build_tactical_study_pack",\n        )\n'''
if "tactical_study_path = \"/matches/{match_id}/intelligence/study-pack\"" not in e:
    anchor = router_line
    if anchor not in e:
        raise SystemExit("tactical fallback anchor not found")
    e = e.replace(anchor, anchor + fallback, 1)

# Fail the patch itself if its postconditions are absent. This prevents a green
# "patch applied" message when a later source refactor invalidates an anchor.
required = [
    import_line.strip(),
    new_cards.strip(),
    router_line.strip(),
    'tactical_study_path = "/matches/{match_id}/intelligence/study-pack"',
    "build_tactical_study_pack,",
]
missing = [item for item in required if item not in e]
if missing:
    raise SystemExit("tactical integration postcondition failed: " + ", ".join(missing))

extensions.write_text(e, encoding="utf-8")
print("Applied AquaMetric V12.5 tactical media integration with route fallback")
