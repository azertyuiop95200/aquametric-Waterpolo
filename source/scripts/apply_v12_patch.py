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

text = text.replace("calculate_player_rating(events)\n    return render(request, \"player_detail.html\"", "calculate_player_rating(events, role=player.primary_role)\n    return render(request, \"player_detail.html\"", 1)
text = text.replace("calculate_player_rating(pevents)\n        ratings.append", "calculate_player_rating(pevents, role=p.primary_role)\n        ratings.append", 1)
p.write_text(text, encoding="utf-8")

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
