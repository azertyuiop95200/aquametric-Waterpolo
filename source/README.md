# AquaMetric Water-Polo Intelligence — V11.2

AquaMetric is a FastAPI web application for water-polo analysis, scouting, player intelligence, tactical preparation, competition planning, match simulation, and evidence-assisted video review.

## V11.2 highlights

- Responsive web interface designed for desktop and phone.
- My Team workspace, calendars, matches, players, scouting and national-team intelligence.
- Player Intelligence linking identity, transfers, match evidence, stats, video and sources.
- France Intelligence, advanced metrics and shot-map views.
- Tactical Chess as a neutral tactical learning/reference module.
- Match Simulation with level hierarchy, historical-results weighting, home/away context, roster continuity and transfer/signing context.
- Video Vision Lab with OpenCV pre-scan, scoreboard ROI/OCR, whistle candidates and evidence-linked reporting.
- Confidence/provenance labels to distinguish official, confirmed, AI-estimated and provisional information.

## Video-analysis status

The current release can perform visual pre-scans, scoreboard OCR, audio whistle candidate detection, quarter evidence and score-change goal candidates on uploaded/local video. Reliable player identity, cap-number recognition, ball tracking, possession, passes and shot attribution remain future model layers and are not presented as verified facts.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

Windows users can also use `START_WINDOWS.bat`. For same-Wi-Fi phone access, use `START_PHONE_LAN.bat`.

## Free Render demo

This repository includes `render.yaml` and a `Dockerfile` for a lightweight Render deployment. The free-demo configuration stores SQLite data, uploads and evidence under `/tmp`, so it must be treated as ephemeral demo storage rather than permanent production storage.

The service exposes `/health` for deployment health checks.

## Data integrity

AquaMetric is evidence-first. Historical/provisional rosters must not be silently presented as current confirmed rosters. Synthetic/demo data must remain clearly labelled. Missing information should remain unavailable or provisional rather than being fabricated.

## Tests

V11.2 extends the automated suite through the simulation, historical-results and roster-continuity layers.
