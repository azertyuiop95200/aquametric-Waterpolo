from fastapi import Request
from fastapi.responses import HTMLResponse

import secure_entry as secure
import models
from db import SessionLocal

app = secure.app

# Replace only the legacy scouting index; team detail/person routes stay in
# secure_entry.py.
for _route in list(app.router.routes):
    if getattr(_route, "path", None) == "/scouting" and "GET" in (getattr(_route, "methods", set()) or set()):
        app.router.routes.remove(_route)


@app.get("/scouting", response_class=HTMLResponse)
def refreshed_scouting_index(request: Request):
    db = SessionLocal()
    try:
        Team = getattr(models, "ScoutingTeam")
        Player = getattr(models, "ScoutingPlayer")
        teams = db.query(Team).order_by(Team.team_type, Team.country, Team.name).all()
        cards = []
        for team in teams:
            _, catalog = secure._catalog_for_team(team.name)
            if catalog:
                player_count = len(catalog.get("players", []))
                status = catalog.get("status")
                season = catalog.get("season")
                refreshed = True
            else:
                player_count = db.query(Player).filter(Player.scouting_team_id == team.id).count()
                status = getattr(team, "roster_status", None) or "Evidence pending refresh"
                season = getattr(team, "season_label", None) or "—"
                refreshed = False
            cards.append({
                "id": team.id,
                "name": team.name,
                "country": getattr(team, "country", None),
                "team_type": getattr(team, "team_type", None),
                "competition": getattr(team, "competition", None),
                "category": getattr(team, "category", None),
                "player_count": player_count,
                "coach_count": len(secure._coaches_for_team(team.name)),
                "status": status,
                "season": season,
                "refreshed": refreshed,
            })
        return secure.core.templates.TemplateResponse("scouting_index_refresh.html", {"request": request, "teams": cards})
    finally:
        db.close()
