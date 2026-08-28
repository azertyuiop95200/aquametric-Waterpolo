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

# Publish a non-secret deploy identity so the live verifier can prove that
# Render is serving the actual current commit, not merely an older V12.1 build.
health_anchor = '''@app.get("/health")\ndef health():\n    return {"ok": True, "app": APP_NAME}\n'''
health_repl = '''@app.get("/health")\ndef health():\n    payload = {"ok": True, "app": APP_NAME}\n    render_commit = os.getenv("RENDER_GIT_COMMIT", "").strip()\n    if render_commit:\n        payload["git_commit"] = render_commit\n    return payload\n'''
if health_anchor in text:
    text = text.replace(health_anchor, health_repl, 1)
elif 'payload["git_commit"] = render_commit' not in text:
    raise SystemExit("health deploy-identity anchor not found")

text = text.replace("calculate_player_rating(events)\n    return render(request, \"player_detail.html\"", "calculate_player_rating(events, role=player.primary_role)\n    return render(request, \"player_detail.html\"", 1)
text = text.replace("calculate_player_rating(pevents)\n        ratings.append", "calculate_player_rating(pevents, role=p.primary_role)\n        ratings.append", 1)
p.write_text(text, encoding="utf-8")

# Match-derived evaluations are private tenant data even when the scouting
# identity/profile itself is global and shared.
extensions = root / "extensions.py"
e = extensions.read_text(encoding="utf-8")
eval_anchor = '''        evaluations = db.scalars(select(PlayerMatchEvaluation).where(PlayerMatchEvaluation.player_id.in_(local_ids)).order_by(PlayerMatchEvaluation.generated_at.desc())).all()\n'''
eval_repl = '''        evaluations = db.scalars(\n            select(PlayerMatchEvaluation)\n            .join(Match, PlayerMatchEvaluation.match_id == Match.id)\n            .where(\n                PlayerMatchEvaluation.player_id.in_(local_ids),\n                Match.owner_id == user.id,\n            )\n            .order_by(PlayerMatchEvaluation.generated_at.desc())\n        ).all()\n'''
if eval_anchor in e:
    e = e.replace(eval_anchor, eval_repl, 1)
elif "Match.owner_id == user.id" not in e:
    raise SystemExit("player evaluation tenant-scope anchor not found")
extensions.write_text(e, encoding="utf-8")

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
base.write_text(b, encoding="utf-8")

print("Applied AquaMetric V12 server + shell patch")
