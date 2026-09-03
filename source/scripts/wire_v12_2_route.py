from pathlib import Path

p = Path(__file__).resolve().parents[1] / "extensions.py"
text = p.read_text(encoding="utf-8")

import_line = "from performance_routes import match_performance_api\n"
anchor_import = "from tactical_media_routes import router as tactical_media_router, enrich_sequence_cards, build_tactical_study_pack\n"
if import_line not in text:
    if anchor_import not in text:
        raise SystemExit("Could not find tactical media import anchor")
    text = text.replace(anchor_import, anchor_import + import_line, 1)

route_marker = 'performance_path = "/api/matches/{match_id}/performance"'
if route_marker not in text:
    anchor = "    app.include_router(tactical_media_router)\n"
    if anchor not in text:
        raise SystemExit("Could not find tactical media router registration anchor")
    block = '''    app.include_router(tactical_media_router)\n    # Defensive explicit registration: nested APIRouter additions made after an\n    # include_router() call are not copied into the already-built FastAPI app.\n    performance_path = "/api/matches/{match_id}/performance"\n    if not any(\n        getattr(route, "path", None) == performance_path\n        and "GET" in (getattr(route, "methods", set()) or set())\n        for route in app.routes\n    ):\n        app.add_api_route(\n            performance_path,\n            match_performance_api,\n            methods=["GET"],\n            name="match_performance_api",\n        )\n'''
    text = text.replace(anchor, block, 1)

p.write_text(text, encoding="utf-8")
print("V12.2 performance route registered explicitly")
