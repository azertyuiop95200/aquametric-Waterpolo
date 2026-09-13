from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path, transform):
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    new = transform(text)
    if new != text:
        p.write_text(new, encoding="utf-8")
        print("patched", path)
    else:
        print("unchanged", path)


def add_performance_router(text):
    marker = "from performance_routes import router as performance_router"
    if marker in text:
        return text
    return text.rstrip() + "\n\n# V12.2 team/player performance intelligence API.\nfrom performance_routes import router as performance_router\nrouter.include_router(performance_router)\n"


def add_match_performance_ui(text):
    if "id=\"performance-intelligence\"" in text:
        return text
    anchor = '<section class="panel limitations">'
    block = r'''
<section class="panel performance-intelligence" id="performance-intelligence" data-match-id="{{match.id}}">
  <div class="section-head"><div><span class="eyebrow">TEAM + INDIVIDUAL PERFORMANCE</span><h2>Technical, tactical and individual match intelligence</h2><p class="muted">Scores below use only evidence attached to this match. Missing dimensions stay unavailable.</p></div><div id="team-performance-score" class="performance-total">—<small>/100 team</small></div></div>
  <div id="team-performance-dimensions" class="performance-dimensions"><div class="empty-state"><b>Loading performance evidence…</b></div></div>
  <div class="performance-columns"><div><h3>Evidence-supported strengths</h3><div id="team-strengths" class="compact-insights"></div></div><div><h3>Priority review areas</h3><div id="team-reviews" class="compact-insights"></div></div></div>
</section>

<section class="panel integrated-media" id="integrated-media">
  <div class="section-head"><div><span class="eyebrow">INTEGRATED VIDEO + IMAGES</span><h2>Match film, tactical clips and key frames</h2><p class="muted">Uploaded video is played inside AquaMetric. YouTube remains embedded from the provider. Third-party media is not copied.</p></div></div>
  <div id="main-match-media" class="main-match-media"><div class="empty-state"><b>Loading match media…</b></div></div>
  <div id="match-media-gallery" class="integrated-media-grid"></div>
</section>

<section class="panel"><div class="section-head"><div><span class="eyebrow">PLAYER PERFORMANCE LAB</span><h2>Match-by-match technical and tactical detail</h2></div><span class="pill">rating-v3 + evidence map</span></div>
  <div id="player-performance-lab" class="player-performance-lab"><div class="empty-state"><b>Loading individual evidence…</b></div></div>
</section>
'''
    text = text.replace(anchor, block + "\n" + anchor, 1)
    script = r'''
<script>
(async function(){
  const root=document.getElementById('performance-intelligence'); if(!root)return;
  const matchId=root.dataset.matchId;
  const esc=(v)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const bar=(label,score,evidence,available=true)=>`<div class="performance-dimension ${available?'':'unavailable'}"><div><b>${esc(label)}</b><small>${esc(evidence)}</small></div><div class="bar"><i style="width:${available?score:0}%"></i></div><strong>${available?esc(score):'—'}</strong></div>`;
  try{
    const r=await fetch(`/api/matches/${matchId}/performance`,{credentials:'same-origin'}); if(!r.ok)throw new Error('performance '+r.status); const d=await r.json();
    const t=d.team_performance;
    document.getElementById('team-performance-score').innerHTML=`${t.overall??'—'}<small>/100 team · ${esc(t.confidence_label)}</small>`;
    document.getElementById('team-performance-dimensions').innerHTML=t.dimensions.map(x=>bar(x.label,x.score,x.evidence,x.available)).join('');
    const insight=(x,empty)=>x.length?x.map(v=>`<div class="compact-insight"><b>${esc(v.label)}</b><span>${esc(v.score)}/100</span><p>${esc(v.evidence)}</p></div>`).join(''):`<p class="muted">${empty}</p>`;
    document.getElementById('team-strengths').innerHTML=insight(t.strengths,'No strong conclusion yet from the current sample.');
    document.getElementById('team-reviews').innerHTML=insight(t.reviews,'No low dimension is asserted from the current sample.');

    const media=document.getElementById('main-match-media');
    if(d.video.local_url){media.innerHTML=`<video controls playsinline preload="metadata" src="${esc(d.video.local_url)}"></video>`;}
    else if(d.video.embed_url){media.innerHTML=`<div class="video-wrap"><iframe id="yt-performance" src="${esc(d.video.embed_url)}?enablejsapi=1" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe></div>`;}
    else if(d.video.external_url){media.innerHTML=`<a class="video-bookmark" href="${esc(d.video.external_url)}" target="_blank" rel="noopener"><b>▶</b><span>Open the provider video</span></a>`;}
    else{media.innerHTML='<div class="empty-state"><b>No match video attached yet</b><p>Add an owned video upload or a lawful video link from the match workspace.</p></div>';}
    const gallery=document.getElementById('match-media-gallery');
    const visible=d.media.filter(x=>['clip','screenshot','contact_sheet'].includes(x.type));
    gallery.innerHTML=visible.length?visible.map(x=>`<article class="integrated-media-card"><div class="integrated-media-preview">${x.type==='clip'?`<video controls playsinline preload="metadata" src="${esc(x.url)}"></video>`:`<a href="${esc(x.url)}" target="_blank"><img src="${esc(x.url)}" loading="lazy" alt="${esc(x.title)}"></a>`}</div><div><b>${esc(x.title||x.type)}</b><small>${Math.floor(x.second/60).toString().padStart(2,'0')}:${Math.floor(x.second%60).toString().padStart(2,'0')} · ${esc(x.analysis_type||'evidence')}</small><p>${esc(x.note||'')}</p></div></article>`).join(''):'<p class="muted">No generated key frames or clips yet. Use the tactical study pack on an uploaded match to generate them.</p>';

    const lab=document.getElementById('player-performance-lab');
    lab.innerHTML=d.players.map(p=>{
      const dims=p.dimensions||{}; const pref=p.shot_preference||{}; const cards=(p.breakdown?.cards||[]).map(c=>`<div class="player-micro-kpi"><b>${esc(c.value)}</b><span>${esc(c.label)}</span><small>${esc(c.detail)}</small></div>`).join('');
      const phaseEntries=Object.entries(p.breakdown?.phases||{}); const phases=phaseEntries.length?phaseEntries.map(([k,v])=>`<span class="chip">${esc(k.replaceAll('_',' '))}: ${esc(v)}</span>`).join(''):'<span class="muted">No explicit phase attribution yet.</span>';
      return `<article class="player-performance-card"><div class="evaluation-top"><div><a class="profile-link" href="${esc(p.profile_url)}"><h3>#${p.cap??'—'} ${esc(p.name)}</h3></a><small>${esc(p.role)} · ${esc(p.confidence||'INSUFFICIENT DATA')}</small></div><div class="evaluation-score">${p.rating??'—'}${p.rating!=null?'<span>/100</span>':''}</div></div><div class="player-micro-grid">${cards}</div><div class="triad"><div>${bar('Technique',dims.technique,'execution from tagged actions',p.rating!=null)}</div><div>${bar('Tactics',dims.tactics,'phase/context decisions',p.rating!=null)}</div><div>${bar('Decision',dims.decision,'choices around tagged actions',p.rating!=null)}</div></div><div class="player-evidence-footer"><div><b>Phase involvement</b><div class="tag-cloud">${phases}</div></div><div><b>Shooting preference</b><p>${pref.available?`${esc(pref.origin)} · ${esc(pref.target)} · ${esc(pref.count)} located shots`:'Not enough reliable located shots yet.'}</p></div></div><a class="mini-link" href="${esc(p.profile_url)}">Open complete player file →</a></article>`;
    }).join('')||'<div class="empty-state"><b>No players in this match roster.</b></div>';
  }catch(e){
    document.getElementById('team-performance-dimensions').innerHTML='<div class="empty-state"><b>Performance intelligence unavailable</b><p>The underlying match page remains usable.</p></div>';
    document.getElementById('player-performance-lab').innerHTML='<div class="empty-state"><b>Individual performance data unavailable</b></div>';
  }
})();
</script>
'''
    return text.replace("{% endblock %}", script + "\n{% endblock %}", 1)


def remove_refresh_calendar(text):
    text = text.replace('<form method="post" action="/official-data/refresh"><input type="hidden" name="force" value="1"><button class="btn">Refresh official data</button></form>', '')
    text = text.replace('Manual refresh works now. Set AUTO_REFRESH_OFFICIAL_DATA=1 on an online deployment for recurring refresh.', 'The page displays the latest cached official data automatically; the online updater can refresh supported feeds in the background.')
    text = text.replace('Run a refresh. RFEN competition discovery can populate Spanish national divisions; other official adapters are added only when a stable lawful feed/parser exists.', 'Supported official feeds appear here automatically after a successful sync. Unsupported sources stay absent rather than guessed.')
    return text


def remove_refresh_competitions(text):
    text = text.replace('<form method="post" action="/official-data/refresh"><input type="hidden" name="force" value="1"><button class="btn">Refresh</button></form>', '')
    text = text.replace('Use Refresh to discover/update supported official feeds. The app keeps the last valid data if a federation page is temporarily unavailable.', 'Supported official feeds appear automatically when synchronized. The app keeps the last valid data if a federation page is temporarily unavailable.')
    return text


def link_team_players(text):
    old = '{% for p in team.players %}<div class="listrow"><b>#{{p.cap_number or \'—\'}} {{p.name}}</b><span>{{p.primary_role}}</span></div>{% else %}'
    new = '{% for p in team.players %}<a class="listrow" href="/players/{{p.id}}"><b>#{{p.cap_number or \'—\'}} {{p.name}}</b><span>{{p.primary_role}} · open profile →</span></a>{% else %}'
    return text.replace(old, new)


def link_my_team_roster(text):
    old = '<div class="roster-row"><b>#{{ p.cap_number if p.cap_number is not none else \'—\' }}</b><strong>{{ p.name }}</strong><span>{{ p.birth_year or \'—\' }}</span><span>{{ p.nationality or \'—\' }}</span><small>{{ p.role }} · {{ p.current_status|replace(\'_\',\' \') }}</small></div>'
    new = '<a class="roster-row roster-link" href="/intelligence/player?name={{p.name|urlencode}}"><b>#{{ p.cap_number if p.cap_number is not none else \'—\' }}</b><strong>{{ p.name }} <small>→ profile</small></strong><span>{{ p.birth_year or \'—\' }}</span><span>{{ p.nationality or \'—\' }}</span><small>{{ p.role }} · {{ p.current_status|replace(\'_\',\' \') }}</small></a>'
    return text.replace(old, new)


def link_player_data(text):
    old = '<div class="coverage-row"><b>{{ r.name }}</b><span>{{ r.nationality or \'—\' }}</span>'
    new = '<a class="coverage-row coverage-link" href="/intelligence/player?name={{r.name|urlencode}}"><b>{{ r.name }}</b><span>{{ r.nationality or \'—\' }}</span>'
    text = text.replace(old, new)
    text = text.replace('<span class="coverage-state {{ \'good\' if r.matches else \'warn\' }}">{{ r.coverage }}</span></div>{% endfor %}', '<span class="coverage-state {{ \'good\' if r.matches else \'warn\' }}">{{ r.coverage }}</span></a>{% endfor %}')
    return text


def append_css(text):
    if ".performance-intelligence{" in text:
        return text
    return text + r'''

/* V12.2 Performance + Tactical Media */
.performance-total{min-width:118px;text-align:center;font-size:2.15rem;font-weight:900;color:var(--accent2);border:1px solid var(--line);border-radius:16px;padding:12px;background:#0a202b}.performance-total small{display:block;font-size:.68rem;font-weight:600;margin-top:3px}.performance-dimensions{display:grid;gap:9px}.performance-dimension{display:grid;grid-template-columns:minmax(210px,1.2fr) minmax(120px,1fr) 48px;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}.performance-dimension>div:first-child{display:grid;gap:3px}.performance-dimension .bar{height:8px;background:rgba(255,255,255,.07);border-radius:99px;overflow:hidden}.performance-dimension .bar i{display:block;height:100%;background:linear-gradient(90deg,var(--accent),var(--accent2));border-radius:99px}.performance-dimension strong{text-align:right}.performance-dimension.unavailable{opacity:.55}.performance-columns{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:20px}.compact-insights{display:grid;gap:8px}.compact-insight{border:1px solid var(--line);border-radius:12px;padding:11px;background:#091c26}.compact-insight span{float:right;color:var(--accent2);font-weight:800}.compact-insight p{color:var(--muted);font-size:.78rem;margin:5px 0 0}.main-match-media{margin:12px 0 18px}.main-match-media>video{max-height:68vh;object-fit:contain}.integrated-media-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:13px}.integrated-media-card{padding:0;overflow:hidden;box-shadow:none}.integrated-media-preview{background:#02080c;min-height:160px;display:grid;place-items:center}.integrated-media-preview img,.integrated-media-preview video{width:100%;height:210px;object-fit:cover;border-radius:0}.integrated-media-card>div:last-child{padding:13px;display:grid;gap:4px}.integrated-media-card p{color:var(--muted);font-size:.8rem}.player-performance-lab{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}.player-performance-card{box-shadow:none}.player-performance-card h3{margin:0}.player-micro-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin:14px 0}.player-micro-kpi{padding:10px;border-radius:11px;background:#091d27;border:1px solid var(--line);display:grid}.player-micro-kpi>b{font-size:1.15rem;color:var(--accent2)}.player-micro-kpi span{font-size:.75rem;font-weight:800}.player-micro-kpi small{font-size:.68rem;margin-top:3px}.triad{display:grid;gap:2px}.triad .performance-dimension{grid-template-columns:80px 1fr 38px;padding:6px 0}.triad .performance-dimension small{display:none}.player-evidence-footer{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0}.player-evidence-footer p{color:var(--muted);font-size:.8rem}.coverage-link{color:inherit;text-decoration:none}.coverage-link:hover{background:rgba(103,221,255,.05)}
@media(max-width:760px){.performance-columns,.player-evidence-footer{grid-template-columns:1fr}.performance-dimension{grid-template-columns:1fr 88px 40px}.performance-dimension>div:first-child small{font-size:.7rem}.player-performance-lab{grid-template-columns:1fr}.player-micro-grid{grid-template-columns:1fr 1fr}.integrated-media-grid{grid-template-columns:1fr}}
'''


patch("tactical_media_routes.py", add_performance_router)
patch("templates/match_intelligence.html", add_match_performance_ui)
patch("templates/calendar.html", remove_refresh_calendar)
patch("templates/competitions.html", remove_refresh_competitions)
patch("templates/team_detail.html", link_team_players)
patch("templates/my_team.html", link_my_team_roster)
patch("templates/player_data.html", link_player_data)
patch("static/v12.css", append_css)
print("Applied AquaMetric V12.2 performance/media/UX patch")
