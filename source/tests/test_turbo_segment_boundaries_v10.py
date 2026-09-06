from capture_turbo_routes_v6 import _patch_segment_end_guard


def test_each_turbo_player_stops_at_its_own_segment_end():
    html = (
        "function pollPlayers(){for(let i=0;i<parallelSegments;i++){try{"
        "if(ytReady[i]&&ytPlayers[i]&&ytPlayers[i].getCurrentTime)"
        "currentTimes[i]=Number(ytPlayers[i].getCurrentTime())||currentTimes[i]"
        "}catch(_){}}}"
        "playerTick=setInterval(pollPlayers,400);"
        "labels[index].textContent=`Segment ${index+1} · ${fmt(start)}`;"
    )
    patched = _patch_segment_end_guard(html)
    assert "now>=end-0.08" in patched
    assert "ytPlayers[i].pauseVideo()" in patched
    assert "currentTimes[i]=end" in patched
    assert "playerTick=setInterval(pollPlayers,100)" in patched
    assert "labels[index].dataset.done=''" in patched


def test_segment_guard_does_not_duplicate_next_source_window():
    html = (
        "function pollPlayers(){for(let i=0;i<parallelSegments;i++){try{"
        "if(ytReady[i]&&ytPlayers[i]&&ytPlayers[i].getCurrentTime)"
        "currentTimes[i]=Number(ytPlayers[i].getCurrentTime())||currentTimes[i]"
        "}catch(_){}}}"
    )
    patched = _patch_segment_end_guard(html)
    assert "end>segmentStarts[i]" in patched
    assert "currentTimes[i]=end" in patched
