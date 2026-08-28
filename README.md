# AquaMetric Water-Polo Intelligence — V12.1

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/azertyuiop95200/aquametric-Waterpolo)

AquaMetric is a FastAPI web application for water-polo analysis, scouting, player and coach intelligence, tactical preparation, competition planning, match simulation, and evidence-assisted video review.

## V12.1 highlights

- Responsive desktop/mobile interface with iPhone regression coverage, outside-tap menu closing and horizontally scrollable workspaces.
- Interface language support for English, French, Italian, Spanish and Russian with persisted preference.
- My Team workspace, calendars, competitions, matches, players, scouting and national-team intelligence.
- Unified Player Intelligence linking identity, transfers, match evidence, ratings, stats, shot preferences, video and provenance.
- Coach Intelligence profiles and team-dossier coach/transfer integrations.
- Transfer Watch grouped by year and transfer window, with arrivals/departures surfaced in team dossiers.
- France Intelligence, advanced metrics and evidence-based shot maps with minimum-sample safeguards.
- Tactical Chess / knowledge synthesis as a neutral tactical learning and reference module.
- Match Simulation with level hierarchy, historical-results weighting, home/away context, roster continuity and transfer/signing context.
- Deep Match Intelligence with role-aware player evaluations, tactical phases, evidence clips and confidence labels.
- Video Vision Lab with OpenCV pre-scan, scoreboard ROI/OCR, whistle candidates, autonomous candidate interpretation and evidence-linked reporting.
- Production security middleware, hidden public API documentation, origin checks, auth rate limiting and secure deployment settings.
- Multi-user isolation for private clubs, teams, match-derived player evaluations and latest-run autonomous reports.
- CI validation aligned across Python, Docker smoke and mobile/browser regression before integrated source is published.

## Video-analysis status

The current release can perform visual pre-scans, scoreboard OCR, audio whistle-candidate detection, quarter evidence and score-change/goal candidates on uploaded local video. These outputs remain evidence candidates until verified.

Reliable player identity, cap-number recognition, ball tracking, possession, passes, shot attribution, foul/exclusion classification and full tactical-shape recognition still require dedicated model layers. AquaMetric does not present those missing capabilities as verified AI results.

The legacy `/analysis/start` placeholder remains intentionally non-fabricating; the active workflow for owned video is **Vision Lab → automatic interpretation → verified events/report**.

## Data and privacy model

- User-created clubs, teams, matches, uploads, generated evidence and match-derived evaluations are private to their owner.
- Shared scouting, official-data, transfer, coach and intelligence catalogues are application-wide reference data.
- Unified public/reference player profiles may combine shared scouting evidence with the signed-in user's own private match evaluations only.
- Historical/provisional rosters must not be silently presented as current confirmed rosters.
- Synthetic/demo data must remain clearly labelled. Missing information remains unavailable or provisional rather than being fabricated.

## Validation and delivery

GitHub Actions validates the integrated source before publication:

- full Python test suite;
- V12 route/security smoke checks;
- production Docker build and runtime smoke test;
- iPhone/mobile browser regression;
- live Render release-marker verification.

The integration patch is idempotent. Validation workflows apply the same integrated source, while the finalization workflow is the single publisher and only commits generated integration changes after green tests.

## Web deployment

The repository is prepared for a free Render demo. `render.yaml` configures ephemeral `/tmp` storage for the demo database, uploads and evidence. A release marker under `source/static/release.json` is used by the live verification workflow to confirm that the current build has reached Render.

The free instance is intended for preview/testing: local data can disappear after restart/redeploy, and heavy long-video analysis should not be treated as production-scale hosting.
