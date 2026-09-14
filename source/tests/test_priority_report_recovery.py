from __future__ import annotations

from types import SimpleNamespace

import priority_analysis_routes as routes


def test_capture_failure_redirect_opens_report_diagnostic():
    html = "before catch(err){leaveStudio();setStatus(`Échec de l’analyse Vision : ${err.message||err}`)} after"
    patched = routes._patch_capture_failure_redirect(html, 42)
    assert "/matches/42/analysis/result?capture_interrupted=1" in patched
    assert "Ouverture du rapport de diagnostic" in patched


def test_live_frame_route_blocks_native_ocr_but_restores_gates(monkeypatch):
    original_base = lambda: True
    original_banner = lambda: True
    monkeypatch.setattr(routes._capture_base, "ocr_available", original_base)
    monkeypatch.setattr(routes._capture_v5, "ocr_available", original_banner)
    monkeypatch.setattr(routes, "tesseract_available", lambda: False)

    seen = {}

    def fake_frame(**kwargs):
        seen["base"] = routes._capture_base.ocr_available()
        seen["banner"] = routes._capture_v5.ocr_available()
        return "ok"

    monkeypatch.setattr(routes, "_turbo_progress_frame_v16", fake_frame)
    assert routes.turbo_progress_frame(1, SimpleNamespace(), "session", 0.0, object(), None) == "ok"
    assert seen == {"base": False, "banner": False}
    assert routes._capture_base.ocr_available is original_base
    assert routes._capture_v5.ocr_available is original_banner


def test_interrupted_capture_clears_infinite_running_report(monkeypatch):
    match = SimpleNamespace(status="browser_capture_running")
    commits = []
    db = SimpleNamespace(commit=lambda: commits.append(True))
    request = SimpleNamespace(query_params={"capture_interrupted": "1"})

    monkeypatch.setattr(routes, "_owned_match", lambda *args, **kwargs: (SimpleNamespace(), match))
    monkeypatch.setattr(routes, "_clean_analysis_result_v2", lambda **kwargs: "report")

    assert routes.clean_analysis_result(7, request, db) == "report"
    assert match.status == "browser_capture_failed"
    assert commits == [True]


def test_hosted_live_frame_skips_ocr_even_when_tesseract_is_installed(monkeypatch):
    monkeypatch.setenv('CAPTURE_LIVE_OCR', '0')
    monkeypatch.setattr(routes, 'tesseract_available', lambda: True)
    seen = []
    def frame(**kwargs):
        seen.append(routes._capture_base.ocr_available())
        seen.append(routes._capture_v5.ocr_available())
        return 'pixels retained'
    monkeypatch.setattr(routes, '_turbo_progress_frame_v16', frame)
    assert routes.turbo_progress_frame(1, SimpleNamespace(), 'session', 0, object(), None) == 'pixels retained'
    assert seen == [False, False]
