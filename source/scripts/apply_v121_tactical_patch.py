from pathlib import Path

root = Path(__file__).resolve().parents[1]
extensions = root / "extensions.py"
e = extensions.read_text(encoding="utf-8")

import_anchor = "from evidence_coverage_routes import router as evidence_coverage_router\n"
import_line = "from tactical_media_routes import router as tactical_media_router, enrich_sequence_cards\n"
if import_line not in e:
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

extensions.write_text(e, encoding="utf-8")
print("Applied AquaMetric V12.1 tactical media integration")
