# AquaMetric — free web demo on Render

This package is prepared for a **free Render Web Service**. It is a preview environment, not production.

## What works
- Responsive web UI on phone/tablet/computer.
- One-click temporary demo workspace at `/demo-login`.
- Granville training/calendar/scouting, player intelligence, France intelligence, analysis library, tactics and simulations.
- Normal account creation also works while the instance is alive.
- Small temporary uploads can be tested (configured to 50 MB in `render.yaml`).

## Free-host limitations
- The service may sleep when inactive and can take roughly a minute to wake.
- Local SQLite data and uploads are **ephemeral** and can disappear after restart/redeploy.
- Do not use this configuration for private or important team video.
- Heavy long-video AI processing should stay off the free web instance.

## Deploy in about 5 minutes
1. Create a free GitHub account/repository if needed.
2. Upload **the contents of this folder** to the repository root (including `render.yaml` and `Dockerfile`).
3. Create/sign in to Render.
4. Choose **New → Blueprint** and connect the GitHub repository.
5. Render detects `render.yaml`. Confirm the `free` service.
6. Wait for the first build/deploy.
7. Open the generated `*.onrender.com` address on your phone.
8. Tap **Open free web demo**.

No paid database is attached in this demo package. When AquaMetric is ready for real users, migrate storage to persistent Postgres/object storage before uploading real match videos.
