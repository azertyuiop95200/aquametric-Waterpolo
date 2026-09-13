# Empty analysis report recovery

## Fixed failure paths

- Native Python deployments no longer require a system Tesseract executable:
  an offline, CPU ONNX OCR backend is installed with its model files.
- V16 requests 240 scoreboard samples, rather than four. The verification
  pass has a 180-second work budget; it is still partial if that budget expires.
- Reused frames retain their actual capture timestamps and count only once
  per pane. A repeated request cannot confirm its own score reading.
- Decoded image memory is bounded to two composite frames during OCR.
- Missing OCR, missing regions, missing frames and unreadable scoreboards
  have distinct diagnostic reasons. A finished worker is not a complete match.
- Saved reports display OCR observations, repeated score readings and
  candidate score transitions separately from analyst-confirmed statistics.
- Empty event counters export as unknown, not as a fictional 0–0 score.

## Build

Native Render build command (Python 3.12):

```sh
python source/scripts/apply_v12_patch.py && python source/scripts/install_dependencies.py
```

Docker and CI use the same dependency installer. It installs RapidOCR's model
wheel with `--no-deps` because the server provides `opencv-python-headless`,
not GUI OpenCV. The remaining dependencies are explicit in requirements.txt.
Model initialization is checked at build time; no video is sent to an OCR API.

## Deployment and existing matches

Before redeploying an instance that uses `/tmp` for SQLite or capture files,
back up its database **and** source/retained frames, or migrate to persistent
storage. A report ZIP contains references, not necessarily the underlying
frames. Do not redeploy assuming that ZIP alone can restore the video.

Old reports receive a truthful diagnosis when rendered by this code, but their
missing observations cannot be retroactively manufactured. Reanalysis requires
the original accessible video or retained capture frames. This patch does not
start unrequested analyses or overwrite analyst-confirmed events.

## Remaining capabilities

This is a scoreboard-based, partial analysis, not an exhaustive water-polo
event detector. It does not implement player/ball tracking, shot recognition,
assists, saves, exclusions or tactical formation recognition. A candidate goal
is a scoreboard transition in a time bracket, not a verified frame of a goal.
Left/right scoreboard order is not silently mapped to team/opponent. The total
10-minute target is not guaranteed by the OCR time budget.

Verification includes real rendered scoreboard pixels with Tesseract disabled,
score-transition inference, database persistence, report rendering, empty ZIP
exports and browser capture regression tests. These are controlled test images,
not evidence from the user's Granville–Choisy match.
