# AquaMetric Water-Polo Intelligence — V11.2

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/azertyuiop95200/aquametric-Waterpolo)

AquaMetric is a FastAPI web application for water-polo analysis, scouting, player intelligence, tactical preparation, competition planning, match simulation, and evidence-assisted video review.

## V11.2 highlights

- Responsive web interface designed for desktop and phone.
- My Team workspace, calendars, matches, players, scouting and national-team intelligence.
- Player Intelligence linking identity, transfers, match evidence, stats, video and sources.
- France Intelligence, advanced metrics and shot-map views.
- Tactical Chess as a neutral tactical learning/reference module.
- Match Simulation with level hierarchy, historical-results weighting, home/away context, roster continuity and transfer/signing context.
- Video Vision Lab with OpenCV pre-scan, scoreboard ROI/OCR, whistle candidates and evidence-linked reporting.
- Confidence/provenance labels distinguishing official, confirmed, AI-estimated and provisional information.

## Video-analysis status

The current release can perform visual pre-scans, scoreboard OCR, audio whistle candidate detection, quarter evidence and score-change goal candidates on uploaded/local video. Reliable player identity, cap-number recognition, ball tracking, possession, passes and shot attribution remain future model layers and are not presented as verified facts.

## Web deployment

This repository is prepared for a free Render demo. The source bundle is reconstructed automatically during the Docker build. `render.yaml` configures ephemeral `/tmp` storage for the demo database, uploads and evidence.

Tap the **Deploy to Render** button at the top of this page, sign in to Render, review the Blueprint, and approve deployment. Render will provide a public `onrender.com` address after the build completes.

The free instance is intended for preview/testing: local data can disappear after restart/redeploy and heavy long-video AI processing should not be treated as production hosting.

## Data integrity

AquaMetric is evidence-first. Historical/provisional rosters must not be silently presented as current confirmed rosters. Synthetic/demo data must remain clearly labelled. Missing information remains unavailable or provisional rather than being fabricated.
