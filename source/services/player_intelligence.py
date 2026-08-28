from sqlalchemy import select
from models import (
    PlayerIntelligenceProfile, PlayerSourceRecord, PlayerMatchMetric,
    MatchLibraryItem, LibraryPlayerMatchStat, TransferSignal, ScoutingPlayer, ScoutingTeam
)

WA_WC_2026_FINAL = "https://www.worldaquatics.com/news/4546786/usa-bolts-to-seventh-womens-world-cup-crown"
WA_WC_2026_VIDEO = "https://www.worldaquatics.com/videos/4547492/team-usa-takes-home-the-title-water-polo-world-cup-2026-sydney-usa-vs-spain"
WA_U20_2025_FINAL = "https://www.worldaquatics.com/news/4342802/usa-rumbles-spain-for-record-extending-fifth-u20-crown"
WA_U20_2025_SF = "https://www.worldaquatics.com/news/4342094/spain-makes-third-straight-u20-womens-final"
WA_EURO_2026 = "https://www.worldaquatics.com/news/4445408/netherlands-goes-back-to-back-for-european-crown"
GRANVILLE_RUMINA = "https://www.granvillewaterpolo.com/2025/10/24/effectif-saison-2025-2026/"
GRANVILLE_MORGANE = "https://www.granvillewaterpolo.com/2025/10/26/effectif-saison-2025-2026/"
GRANVILLE_CAPUCINE = "https://www.granvillewaterpolo.com/2025/10/28/effectif-saison-2025-2026/"
WP360_TRANSFERS = "https://waterpolo360news.com/water-polo-transfers-and-gossip/confirmed-transfers/"

PROFILE_SEEDS = [
    dict(name="Emily Ausmus", nationality="USA", role="Perimeter / attacker", club="", national="United States — Women Senior", status="current_national_team", season="2026", confidence=.98, source=WA_WC_2026_FINAL, note="World Cup 2026 top scorer; player of the final. Club affiliation intentionally left blank until a current official club source is attached."),
    dict(name="Elena Ruiz", nationality="ESP", role="Left-hander / perimeter", club="CN Atlètic-Barceloneta", national="Spain — Women Senior", status="media_confirmed_transfer", season="2026-2027", confidence=.92, source=WP360_TRANSFERS, note="Transfer is media-confirmed and described as confirmed by the destination club; AquaMetric keeps the evidence tier visible until a direct club/federation roster source is attached."),
    dict(name="Iva Rozic", nationality="CRO", role="Perimeter / scorer", club="SIS Roma", national="Croatia — Women Senior", status="media_confirmed_transfer", season="2026-2027", confidence=.92, source=WP360_TRANSFERS, note="Croatian scorer with U20 and senior international evidence. Transfer is stored separately from match-performance evidence."),
    dict(name="Isabel Piralkova", nationality="ESP", role="Perimeter / scorer", club="", national="Spain — Women U20", status="event_roster_evidence", season="2025", confidence=.96, source=WA_U20_2025_SF, note="U20 profile currently driven by official World Aquatics match reports; club affiliation awaits a current club source."),
    dict(name="Rumina Edgerton", nationality="CAN", role="Goalkeeper", club="Granville Water Polo", national="Canada — junior history", status="historical_club_confirmed_pending_2627", season="2025-2026", confidence=.98, source=GRANVILLE_RUMINA, note="Granville officially announced her for 2025-26. 2026-27 status remains pending until a new roster or match sheet confirms continuity."),
    dict(name="Morgane Le Berre", nationality="FRA", role="Field player", club="Granville Water Polo", national="France youth history", status="historical_club_confirmed_pending_2627", season="2025-2026", confidence=.98, source=GRANVILLE_MORGANE, note="Official Granville 2025-26 player presentation; current-season confirmation remains separate."),
    dict(name="Capucine Pillais", nationality="FRA", role="Centre defender / contre-pointe", club="Granville Water Polo", national="France youth pathway", status="historical_club_confirmed_pending_2627", season="2025-2026", confidence=.98, source=GRANVILLE_CAPUCINE, note="Official Granville 2025-26 player presentation identifies her role and youth honours."),
]


def _ensure_world_cup_final(db):
    item = db.scalar(select(MatchLibraryItem).where(MatchLibraryItem.external_key == "WA-WWC-2026-F-USA-ESP"))
    if not item:
        import json
        item = MatchLibraryItem(
            external_key="WA-WWC-2026-F-USA-ESP",
            title="United States vs Spain — Women's Water Polo World Cup 2026 final",
            competition="Women's Water Polo World Cup",
            season="2026", entity_type="national_team", team_a="United States", team_b="Spain",
            score_a=13, score_b=9, quarter_scores_json=json.dumps([[4,3],[3,2],[4,4],[2,0]]),
            video_url=WA_WC_2026_VIDEO, video_kind="official_highlights", official_source_url=WA_WC_2026_FINAL,
            analysis_status="officially_sourced",
            tactical_summary="USA broke an 8-8 tie into an 11-8 lead and held Spain scoreless in the fourth quarter. Official reporting identifies extra-player defence and Emily Ausmus' six-goal final as major differentiators.",
            team_stats_json=json.dumps({"United States":{"extra_player":"7/13","extra_player_defence":"11/14 stopped","goalkeeper_saves":13},"Spain":{"final_score":9}})
        )
        db.add(item); db.flush()
        db.add_all([
            LibraryPlayerMatchStat(library_match_id=item.id,team_name="United States",player_name="Emily Ausmus",goals=6,note="Player of the final; official report."),
            LibraryPlayerMatchStat(library_match_id=item.id,team_name="Spain",player_name="Elena Ruiz",goals=2,note="Two goals in the official final report."),
        ])
    return item


def _profile(db, seed):
    p = db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name == seed["name"]))
    if not p:
        p = PlayerIntelligenceProfile(canonical_name=seed["name"])
        db.add(p); db.flush()
    p.nationality=seed["nationality"]; p.role=seed["role"]; p.current_club=seed["club"]
    p.current_national_team=seed["national"]; p.roster_status=seed["status"]; p.roster_season=seed["season"]
    p.confidence_score=seed["confidence"]; p.primary_source_url=seed["source"]; p.note=seed["note"]
    return p


def _source_once(db, profile, source_type, label, url, season, trust, claim):
    existing = db.scalar(select(PlayerSourceRecord).where(PlayerSourceRecord.profile_id==profile.id, PlayerSourceRecord.url==url, PlayerSourceRecord.label==label))
    if not existing:
        db.add(PlayerSourceRecord(profile_id=profile.id,source_type=source_type,label=label,url=url,season=season,trust_level=trust,claim_text=claim))


def _metric_once(db, profile, library_match_id, metric, value, text_value, unit, provenance, confidence, source_url, note=""):
    existing = db.scalar(select(PlayerMatchMetric).where(PlayerMatchMetric.profile_id==profile.id,PlayerMatchMetric.library_match_id==library_match_id,PlayerMatchMetric.metric==metric))
    if not existing:
        db.add(PlayerMatchMetric(profile_id=profile.id,library_match_id=library_match_id,metric=metric,value=value,text_value=text_value,unit=unit,provenance=provenance,confidence_score=confidence,source_url=source_url,note=note))


def seed_player_intelligence(db):
    wc_final = _ensure_world_cup_final(db)
    profiles = {s["name"]:_profile(db,s) for s in PROFILE_SEEDS}
    db.flush()

    # Generic expansion: any newly discovered roster player, transfer subject, or match-stat player
    # gets a canonical profile. This is the path from a small curated demo to a large player registry.
    scouting_rows = db.scalars(select(ScoutingPlayer)).all()
    for sp in scouting_rows:
        if sp.name in profiles:
            continue
        team = db.get(ScoutingTeam, sp.scouting_team_id)
        existing = db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name==sp.name))
        if not existing:
            existing = PlayerIntelligenceProfile(
                canonical_name=sp.name, nationality=sp.nationality or "", role=sp.role or "Role to confirm",
                current_club=(team.name.split(" — ")[0] if team and team.team_type=="club" else ""),
                current_national_team=(team.name if team and team.team_type=="national_team" else ""),
                roster_status=sp.current_status or "research_required", roster_season=sp.source_season or "",
                confidence_score=.86 if sp.source_quality.startswith("official") else .70,
                primary_source_url=sp.source_url or "", note=sp.note or "Roster-derived canonical profile."
            )
            db.add(existing); db.flush()
        profiles[sp.name]=existing
        if sp.source_url:
            _source_once(db,existing,"roster",f"Roster evidence — {team.name if team else 'team'}",sp.source_url,sp.source_season,"official" if sp.source_quality.startswith("official") else "secondary",sp.note or "Player observed in roster source.")

    transfer_rows = db.scalars(select(TransferSignal)).all()
    for tr in transfer_rows:
        p=profiles.get(tr.player_name) or db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name==tr.player_name))
        if not p:
            p=PlayerIntelligenceProfile(canonical_name=tr.player_name,current_club=tr.to_team if tr.signal_type=="confirmed" else "",roster_status="media_confirmed_transfer" if tr.signal_type=="confirmed" else "transfer_rumour_only",roster_season=tr.season,confidence_score=tr.confidence_score,primary_source_url=tr.source_url,note="Profile created automatically from transfer monitoring; identity/role/nationality still require enrichment.")
            db.add(p); db.flush()
        profiles[tr.player_name]=p
        _source_once(db,p,"media_transfer",f"{tr.source_name} — {tr.signal_type} transfer signal",tr.source_url,tr.season,tr.source_tier,tr.note or f"{tr.from_team} → {tr.to_team}")

    # Match-stat-only names are also promoted into the canonical registry.
    for row in db.scalars(select(LibraryPlayerMatchStat)).all():
        if row.player_name not in profiles:
            p=db.scalar(select(PlayerIntelligenceProfile).where(PlayerIntelligenceProfile.canonical_name==row.player_name))
            if not p:
                p=PlayerIntelligenceProfile(canonical_name=row.player_name,roster_status="match_evidence_only",confidence_score=.82,note="Profile created from official match evidence; roster identity enrichment is pending.")
                db.add(p); db.flush()
            profiles[row.player_name]=p

    _source_once(db,profiles["Emily Ausmus"],"official_match","World Aquatics — World Cup 2026 final",WA_WC_2026_FINAL,"2026","official","Six goals in the final; tournament top scorer with 11 goals.")
    _source_once(db,profiles["Emily Ausmus"],"official_video","World Aquatics — USA vs Spain final video",WA_WC_2026_VIDEO,"2026","official","Official video/clip page for final evidence.")
    _source_once(db,profiles["Elena Ruiz"],"media_transfer","Waterpolo 360 — confirmed transfer",WP360_TRANSFERS,"2026-2027","media_confirmed","Transfer to CN Atlètic-Barceloneta reported as confirmed.")
    _source_once(db,profiles["Elena Ruiz"],"official_match","World Aquatics — World Cup 2026 final",WA_WC_2026_FINAL,"2026","official","Two goals for Spain in the final.")
    _source_once(db,profiles["Iva Rozic"],"media_transfer","Waterpolo 360 — confirmed transfer",WP360_TRANSFERS,"2026-2027","media_confirmed","Transfer to SIS Roma reported as confirmed.")
    _source_once(db,profiles["Iva Rozic"],"official_competition","World Aquatics / European championship report",WA_EURO_2026,"2026","official","Finished second on the scoring ladder with 24 goals in the cited senior European championship report.")
    _source_once(db,profiles["Rumina Edgerton"],"club_announcement","Granville Water Polo — player announcement",GRANVILLE_RUMINA,"2025-2026","club_official","Granville announced Edgerton as its new goalkeeper for 2025-26.")
    _source_once(db,profiles["Morgane Le Berre"],"club_announcement","Granville Water Polo — player announcement",GRANVILLE_MORGANE,"2025-2026","club_official","Granville official player presentation.")
    _source_once(db,profiles["Capucine Pillais"],"club_announcement","Granville Water Polo — player announcement",GRANVILLE_CAPUCINE,"2025-2026","club_official","Granville official player presentation and role information.")

    # Convert every known library stat for a canonical profile into provenance-aware metrics.
    library_rows = db.scalars(select(LibraryPlayerMatchStat)).all()
    for row in library_rows:
        p = profiles.get(row.player_name)
        if not p:
            # small alias bridge for World Aquatics naming currently used in the library
            if row.player_name == "Iva Rozic": p = profiles.get("Iva Rozic")
            elif row.player_name == "Isabel Piralkova": p = profiles.get("Isabel Piralkova")
        if not p: continue
        match = db.get(MatchLibraryItem,row.library_match_id)
        src = match.official_source_url if match else ""
        _metric_once(db,p,row.library_match_id,"appearance",1.0,"","match",row.source_quality or "official_match_sheet",1.0,src,row.note)
        if row.goals is not None: _metric_once(db,p,row.library_match_id,"goals",float(row.goals),"","goals","official_report",1.0,src,row.note)
        if row.saves is not None: _metric_once(db,p,row.library_match_id,"saves",float(row.saves),"","saves","official_report",1.0,src,row.note)
        if row.shots is not None: _metric_once(db,p,row.library_match_id,"shots",float(row.shots),"","shots","official_report",1.0,src,row.note)
        if row.assists is not None: _metric_once(db,p,row.library_match_id,"assists",float(row.assists),"","assists","official_report",1.0,src,row.note)
        if row.steals is not None: _metric_once(db,p,row.library_match_id,"steals",float(row.steals),"","steals","official_report",1.0,src,row.note)
    _metric_once(db,profiles["Emily Ausmus"],wc_final.id,"tournament_goals",11.0,"","goals","official_report",1.0,WA_WC_2026_FINAL,"Highest goal-scorer of the Women's Water Polo World Cup 2026.")
    _metric_once(db,profiles["Iva Rozic"],None,"senior_european_tournament_goals",24.0,"","goals","official_report",1.0,WA_EURO_2026,"Second on scoring ladder in the cited senior European championship report.")
    db.commit()


def profile_snapshot(db, profile):
    metrics = db.scalars(select(PlayerMatchMetric).where(PlayerMatchMetric.profile_id==profile.id)).all()
    documented_match_ids = {m.library_match_id for m in metrics if m.library_match_id}
    stat_match_ids = {m.library_match_id for m in metrics if m.library_match_id and m.metric != "appearance"}
    total_goals = sum((m.value or 0) for m in metrics if m.metric == "goals")
    total_saves = sum((m.value or 0) for m in metrics if m.metric == "saves")
    return {
        "matches": len(stat_match_ids), "documented_matches": len(documented_match_ids),
        "goals": int(total_goals), "saves": int(total_saves),
        "sources": db.query(PlayerSourceRecord).filter(PlayerSourceRecord.profile_id==profile.id).count(),
        "metrics": len(metrics),
    }
