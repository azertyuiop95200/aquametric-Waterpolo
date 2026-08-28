from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = root / "main.py"
text = p.read_text(encoding="utf-8")

old_import = "from services.simulation import simulate_matchup, SIM_TEAMS\n"
new_import = old_import + "from extensions import install_extensions\nfrom security import install_security\n"
if "from extensions import install_extensions" not in text:
    if old_import not in text:
        raise SystemExit("main import anchor not found")
    text = text.replace(old_import, new_import, 1)

old_app = '''app = FastAPI(title=APP_NAME, lifespan=lifespan)\napp.add_middleware(\n    SessionMiddleware,\n    secret_key=os.getenv("SECRET_KEY", "dev-secret-change-me"),\n    same_site="lax",\n    https_only=os.getenv("COOKIE_SECURE", "0") == "1",\n)\n'''
new_app = '''app = FastAPI(title=APP_NAME, lifespan=lifespan)\ninstall_security(app)\nSESSION_SECRET = os.getenv("SECRET_KEY", "").strip()\nif not SESSION_SECRET:\n    if WEB_DEMO_MODE or os.getenv("COOKIE_SECURE", "0") == "1":\n        raise RuntimeError("SECRET_KEY is required for secured web deployments")\n    SESSION_SECRET = "dev-only-local-secret-change-me"\napp.add_middleware(\n    SessionMiddleware,\n    secret_key=SESSION_SECRET,\n    same_site="lax",\n    https_only=os.getenv("COOKIE_SECURE", "0") == "1",\n)\n'''
if "SESSION_SECRET = os.getenv" not in text:
    if old_app not in text:
        raise SystemExit("FastAPI/session anchor not found")
    text = text.replace(old_app, new_app, 1)

metadata_anchor = "Base.metadata.create_all(engine)\n"
if "install_extensions(app)" not in text:
    if metadata_anchor not in text:
        raise SystemExit("metadata anchor not found")
    text = text.replace(metadata_anchor, metadata_anchor + "install_extensions(app)\n", 1)

reg_anchor = '''    db.commit()\n    db.refresh(user)\n    request.session["user_id"] = user.id\n    return RedirectResponse("/dashboard", status_code=303)\n'''
reg_repl = '''    db.commit()\n    db.refresh(user)\n    request.session.clear()\n    request.session["user_id"] = user.id\n    return RedirectResponse("/dashboard", status_code=303)\n'''
if reg_anchor in text:
    text = text.replace(reg_anchor, reg_repl, 1)

login_anchor = '''    if not user or not verify_password(password, user.password_hash):\n        return render(request, "login.html", error="Invalid credentials.", status_code=400)\n    request.session["user_id"] = user.id\n'''
login_repl = '''    if not user or not verify_password(password, user.password_hash):\n        return render(request, "login.html", error="Invalid credentials.", status_code=400)\n    request.session.clear()\n    request.session["user_id"] = user.id\n'''
if login_anchor in text:
    text = text.replace(login_anchor, login_repl, 1)

demo_anchor = '''    ensure_granville_team(db, user.id)\n    request.session["user_id"] = user.id\n    request.session["web_demo"] = True\n'''
demo_repl = '''    ensure_granville_team(db, user.id)\n    request.session.clear()\n    request.session["user_id"] = user.id\n    request.session["web_demo"] = True\n'''
if demo_anchor in text:
    text = text.replace(demo_anchor, demo_repl, 1)

# Keep user-created clubs private while preserving shared/demo clubs.
teams_anchor = '''    teams = db.scalars(select(Team).where(Team.owner_id == user.id).order_by(Team.id.desc())).all()\n    clubs = db.scalars(select(Club).order_by(Club.country, Club.category, Club.name)).all()\n    return render(request, "teams.html", user=user, teams=teams, clubs=clubs)\n'''
teams_repl = '''    teams = db.scalars(select(Team).where(Team.owner_id == user.id).order_by(Team.id.desc())).all()\n    clubs = db.scalars(\n        select(Club)\n        .where(Club.owner_id.is_(None) | (Club.owner_id == user.id))\n        .order_by(Club.country, Club.category, Club.name)\n    ).all()\n    return render(request, "teams.html", user=user, teams=teams, clubs=clubs)\n'''
if teams_anchor in text:
    text = text.replace(teams_anchor, teams_repl, 1)
elif ".where(Club.owner_id.is_(None) | (Club.owner_id == user.id))" not in text:
    raise SystemExit("teams club-scope anchor not found")

club_anchor = '''    existing = db.scalar(select(Club).where(Club.name == name, Club.country == country, Club.category == category))\n    if existing:\n        return RedirectResponse(f"/teams?club_exists={existing.id}", status_code=303)\n'''
club_repl = '''    existing = db.scalar(\n        select(Club).where(\n            Club.name == name,\n            Club.country == country,\n            Club.category == category,\n            Club.owner_id.is_(None) | (Club.owner_id == user.id),\n        )\n    )\n    if existing:\n        return RedirectResponse(f"/teams?club_exists={existing.id}", status_code=303)\n'''
if club_anchor in text:
    text = text.replace(club_anchor, club_repl, 1)
elif "Club.owner_id.is_(None) | (Club.owner_id == user.id)," not in text:
    raise SystemExit("club duplicate-scope anchor not found")

team_create_anchor = '''    club = db.get(Club, club_id)\n    if not club:\n        raise HTTPException(400, detail="Selected club does not exist.")\n    name = clean_text(name)\n'''
team_create_repl = '''    club = db.get(Club, club_id)\n    if not club or (club.owner_id is not None and club.owner_id != user.id):\n        raise HTTPException(400, detail="Selected club does not exist or is not available.")\n    name = clean_text(name)\n'''
if team_create_anchor in text:
    text = text.replace(team_create_anchor, team_create_repl, 1)
elif "club.owner_id is not None and club.owner_id != user.id" not in text:
    raise SystemExit("team club-ownership anchor not found")

# report.json must use candidates from the latest autonomous run only.
report_anchor = '''    candidates = db.scalars(select(AutonomousEventCandidate).where(AutonomousEventCandidate.match_id == match.id).order_by(AutonomousEventCandidate.second)).all() if auto else []\n    report = build_match_report(match, auto, candidates)\n'''
report_repl = '''    candidates = db.scalars(\n        select(AutonomousEventCandidate)\n        .where(AutonomousEventCandidate.analysis_id == auto.id)\n        .order_by(AutonomousEventCandidate.second)\n    ).all() if auto else []\n    report = build_match_report(match, auto, candidates)\n'''
if report_anchor in text:
    text = text.replace(report_anchor, report_repl, 1)
elif "AutonomousEventCandidate.analysis_id == auto.id" not in text:
    raise SystemExit("report candidate-scope anchor not found")

health_anchor = '''@app.get("/health")\ndef health():\n    return {"ok": True, "app": APP_NAME}\n'''
health_repl = '''@app.get("/health")\ndef health():\n    payload = {"ok": True, "app": APP_NAME}\n    render_commit = os.getenv("RENDER_GIT_COMMIT", "").strip()\n    if render_commit:\n        payload["git_commit"] = render_commit\n    return payload\n'''
if health_anchor in text:
    text = text.replace(health_anchor, health_repl, 1)
elif 'payload["git_commit"] = render_commit' not in text:
    raise SystemExit("health deploy-identity anchor not found")

text = text.replace("calculate_player_rating(events)\n    return render(request, \"player_detail.html\"", "calculate_player_rating(events, role=player.primary_role)\n    return render(request, \"player_detail.html\"", 1)
text = text.replace("calculate_player_rating(pevents)\n        ratings.append", "calculate_player_rating(pevents, role=p.primary_role)\n        ratings.append", 1)
p.write_text(text, encoding="utf-8")

# Shared dossier extension: preserve tenant isolation, seed match evidence and expose
# a global evidence-coverage dashboard across every tracked club/national team.
extensions = root / "extensions.py"
e = extensions.read_text(encoding="utf-8")
eval_anchor = '''        evaluations = db.scalars(select(PlayerMatchEvaluation).where(PlayerMatchEvaluation.player_id.in_(local_ids)).order_by(PlayerMatchEvaluation.generated_at.desc())).all()\n'''
eval_repl = '''        evaluations = db.scalars(\n            select(PlayerMatchEvaluation)\n            .join(Match, PlayerMatchEvaluation.match_id == Match.id)\n            .where(\n                PlayerMatchEvaluation.player_id.in_(local_ids),\n                Match.owner_id == user.id,\n            )\n            .order_by(PlayerMatchEvaluation.generated_at.desc())\n        ).all()\n'''
if eval_anchor in e:
    e = e.replace(eval_anchor, eval_repl, 1)
elif "Match.owner_id == user.id" not in e:
    raise SystemExit("player evaluation tenant-scope anchor not found")
if "from services.granville_match_evidence import seed_granville_match_evidence" not in e:
    anchor = "from services.elite_match_evidence import seed_elite_match_evidence\n"
    if anchor not in e:
        raise SystemExit("elite evidence import anchor not found")
    e = e.replace(anchor, anchor + "from services.granville_match_evidence import seed_granville_match_evidence\n", 1)
if "seed_granville_match_evidence(db)" not in e:
    anchor = "        seed_elite_match_evidence(db)\n"
    if anchor not in e:
        raise SystemExit("elite evidence seed anchor not found")
    e = e.replace(anchor, anchor + "        seed_granville_match_evidence(db)\n", 1)
if "from evidence_coverage_routes import router as evidence_coverage_router" not in e:
    anchor = "from services.public_match_ratings import public_profile_evaluations\n"
    if anchor not in e:
        raise SystemExit("public ratings import anchor not found")
    e = e.replace(anchor, anchor + "from evidence_coverage_routes import router as evidence_coverage_router\n", 1)
if "app.include_router(evidence_coverage_router)" not in e:
    anchor = "    app.include_router(router)\n"
    if anchor not in e:
        raise SystemExit("extension router anchor not found")
    e = e.replace(anchor, anchor + "    app.include_router(evidence_coverage_router)\n", 1)
extensions.write_text(e, encoding="utf-8")

# Every official library row verifies at least a match appearance. Appearance-only
# evidence is kept separate from matches that contain actual individual statistics.
player_intel = root / "services" / "player_intelligence.py"
pi = player_intel.read_text(encoding="utf-8")
appearance_anchor = '''        match = db.get(MatchLibraryItem,row.library_match_id)\n        src = match.official_source_url if match else ""\n        if row.goals is not None: _metric_once(db,p,row.library_match_id,"goals",float(row.goals),"","goals","official_report",1.0,src,row.note)\n'''
appearance_repl = '''        match = db.get(MatchLibraryItem,row.library_match_id)\n        src = match.official_source_url if match else ""\n        _metric_once(db,p,row.library_match_id,"appearance",1.0,"","match",row.source_quality or "official_match_sheet",1.0,src,row.note)\n        if row.goals is not None: _metric_once(db,p,row.library_match_id,"goals",float(row.goals),"","goals","official_report",1.0,src,row.note)\n'''
if appearance_anchor in pi:
    pi = pi.replace(appearance_anchor, appearance_repl, 1)
elif 'row.library_match_id,"appearance",1.0' not in pi:
    raise SystemExit("player appearance metric anchor not found")

snapshot_anchor = '''def profile_snapshot(db, profile):\n    metrics = db.scalars(select(PlayerMatchMetric).where(PlayerMatchMetric.profile_id==profile.id)).all()\n    match_ids = {m.library_match_id for m in metrics if m.library_match_id}\n    total_goals = sum((m.value or 0) for m in metrics if m.metric == "goals")\n    total_saves = sum((m.value or 0) for m in metrics if m.metric == "saves")\n    return {\n        "matches": len(match_ids), "goals": int(total_goals), "saves": int(total_saves),\n        "sources": db.query(PlayerSourceRecord).filter(PlayerSourceRecord.profile_id==profile.id).count(),\n        "metrics": len(metrics),\n    }\n'''
snapshot_repl = '''def profile_snapshot(db, profile):\n    metrics = db.scalars(select(PlayerMatchMetric).where(PlayerMatchMetric.profile_id==profile.id)).all()\n    documented_match_ids = {m.library_match_id for m in metrics if m.library_match_id}\n    stat_match_ids = {m.library_match_id for m in metrics if m.library_match_id and m.metric != "appearance"}\n    total_goals = sum((m.value or 0) for m in metrics if m.metric == "goals")\n    total_saves = sum((m.value or 0) for m in metrics if m.metric == "saves")\n    return {\n        "matches": len(stat_match_ids), "documented_matches": len(documented_match_ids),\n        "goals": int(total_goals), "saves": int(total_saves),\n        "sources": db.query(PlayerSourceRecord).filter(PlayerSourceRecord.profile_id==profile.id).count(),\n        "metrics": len(metrics),\n    }\n'''
if snapshot_anchor in pi:
    pi = pi.replace(snapshot_anchor, snapshot_repl, 1)
elif '"documented_matches": len(documented_match_ids)' not in pi:
    raise SystemExit("profile snapshot precision anchor not found")
player_intel.write_text(pi, encoding="utf-8")

# Keep base template changes tiny and idempotent to avoid replacing the whole shell.
base = root / "templates" / "base.html"
b = base.read_text(encoding="utf-8")
if "/static/v12.css" not in b:
    b = b.replace('<link rel="stylesheet" href="/static/style.css">', '<link rel="stylesheet" href="/static/style.css">\n  <link rel="stylesheet" href="/static/v12.css">', 1)
if 'href="/coaches"' not in b:
    anchor = '      <a class="{% if request.url.path.startswith(\'/national-teams\') %}active{% endif %}" href="/national-teams"><span>N</span>National teams</a>'
    coach = '      <a class="{% if request.url.path.startswith(\'/coaches\') or request.url.path.startswith(\'/coach-intelligence\') %}active{% endif %}" href="/coaches"><span>HC</span>Coaches</a>\n'
    if anchor in b:
        b = b.replace(anchor, coach + anchor, 1)
if 'href="/evidence-coverage"' not in b:
    anchor = '      <a class="{% if request.url.path.startswith(\'/scouting\') %}active{% endif %}" href="/scouting"><span>S</span><b class="nav-label" data-i18n="nav.scouting">Scouting</b></a>\n'
    coverage = '      <a class="{% if request.url.path == \'/evidence-coverage\' %}active{% endif %}" href="/evidence-coverage"><span>Σ</span><b class="nav-label">Evidence coverage</b></a>\n'
    if anchor in b:
        b = b.replace(anchor, anchor + coverage, 1)
base.write_text(b, encoding="utf-8")

print("Applied AquaMetric V12 server + shell patch")
