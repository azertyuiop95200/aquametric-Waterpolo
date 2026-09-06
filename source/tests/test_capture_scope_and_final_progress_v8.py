from urllib.parse import parse_qs

from analysis_input_routes_v3 import _scope_query
from capture_turbo_routes_v6 import _patch_final_progress_polling, _patch_full_match_scope


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
