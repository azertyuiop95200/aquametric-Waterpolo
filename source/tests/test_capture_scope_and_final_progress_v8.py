import re
from urllib.parse import parse_qs

from fastapi.testclient import TestClient

from analysis_input_routes_v3 import _scope_query
from capture_turbo_routes_v6 import _patch_final_progress_polling, _patch_full_match_scope
from main import app


client = TestClient(app)


def test_auto_scope_never_uses_youtube_timestamp_as_match_start():
    query = parse_qs(_scope_query("auto", 465.0, 0.0))
    assert query["scope_mode"] == ["auto"]
    assert query["scope_start"] == ["0.000"]
    assert query["scope_end"] == ["0.000"]


def test_manual_scope_can_still_trim_match_explicitly():
    query = parse_qs(_scope_query("manual", 465.0, 1250.0))
    assert query["scope_start"] == ["465.000"]
    assert query["scope_end"] == ["1250.000"]


def test_existing_match_page_ignores_embedded_cursor_in_auto_mode():
    html = (
        '<input id="sourceStart" type="number" value="465.0">'
        '<script>let requestedScopeMode="auto",requestedScopeStart=465.000,requestedScopeEnd=0.000;</script>'
        'Si la vidéo contient plusieurs rencontres, AquaMetric compare les bandeaux OCR et demande une plage avant de mélanger deux matchs.'
    )
    patched = _patch_full_match_scope(html, mode="auto", embedded_start=465.0)
    assert 'value="0.0"' in patched
    assert "requestedScopeStart=0.000" in patched
    assert "requestedScopeEnd=0.000" in patched
    assert "départ réel 0.0 s" in patched


def test_manual_existing_match_page_keeps_selected_start():
    html = '<input id="sourceStart" type="number" value="465.0"><script>requestedScopeStart=465.000;</script>'
    assert _patch_full_match_scope(html, mode="manual", embedded_start=465.0) == html


def test_finalization_keeps_status_polling_until_finish_response():
    html = (
        "recorder.onstop=async()=>{clearInterval(tick);clearInterval(statusTick);clearInterval(frameTick);clearInterval(playerTick);"
        "try{const payload=await finishAnalysis();if(payload.needs_match_selection){return;}"
        "}catch(err){leaveStudio();setStatus(`Échec de l’analyse Vision : ${err.message||err}`)}};"
        "setBars(100,analysisPercent,'Lecture terminée','Consolidation finale Vision/OCR + tactique…');"
    )
    patched = _patch_final_progress_polling(html)
    assert "clearInterval(tick);clearInterval(frameTick);clearInterval(playerTick);" in patched
    assert "clearInterval(tick);clearInterval(statusTick);clearInterval(frameTick)" not in patched
    assert "const payload=await finishAnalysis();clearInterval(statusTick);statusTick=null;" in patched
    assert "Finalisation serveur en cours · progression 88–99 % suivie en direct" in patched


def test_exact_reference_youtube_link_renders_full_match_from_zero_and_live_final_progress():
    email = "scope-v8@example.com"
    password = "strongpass123"
    client.post(
        "/register",
        data={"email": email, "password": password, "name": "Scope V8"},
        follow_redirects=True,
    )
    client.post("/login", data={"email": email, "password": password}, follow_redirects=True)

    created = client.post(
        "/analysis/url/create",
        data={
            "team_name": "Granville Water Polo",
            "opponent": "Choisy le Roi",
            "category": "Women",
            "competition": "Friendly",
            "match_date": "2026-09-05",
            "video_url": "https://www.youtube.com/watch?v=Guo_UU282pI&t=465s",
            "scope_mode": "auto",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    location = created.headers["location"]
    assert "scope_mode=auto" in location
    assert "scope_start=0.000" in location
    assert "scope_end=0.000" in location

    page = client.get(location)
    assert page.status_code == 200
    body = page.text
    assert re.search(r'id="sourceStart"[^>]*value="0\.0"', body)
    assert "requestedScopeStart=0.000" in body
    assert "requestedScopeEnd=0.000" in body
    assert "Curseur YouTube ignoré pour l’analyse : 465.0 s → départ réel 0.0 s." in body
    assert "clearInterval(tick);clearInterval(statusTick);clearInterval(frameTick)" not in body
    assert "Consolidation rapide lancée · progression suivie en direct" in body
    assert "waitForFinalReport" in body
    assert "Pause qualité automatique" in body
