from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_elite_video_library_has_real_embeds_schemas_and_coach_mode():
    page = (ROOT / 'static' / 'video-session-elite.html').read_text(encoding='utf-8')
    assert 'Analyse vidéo haut niveau' in page
    assert page.count('youtube-nocookie.com/embed/') >= 4
    for video_id in ('HfkCCOpLIBA', 'Ek1kBvUjivc', 'TseN9CGbfQw', 'bF-Am10VtF4'):
        assert video_id in page
    assert page.count('class="frame"') >= 9
    assert 'Stop avant la décision' in page
    assert 'Israël féminin U20' in page
    assert 'Pas de tactique inventée' in page


def test_knowledge_and_tactical_chess_expose_fast_video_entry():
    app_js = (ROOT / 'static' / 'app.js').read_text(encoding='utf-8')
    assert "['/knowledge','/tactical-chess']" in app_js
    assert '/static/video-session-elite.html' in app_js
    assert 'Analyse vidéo élite' in app_js
