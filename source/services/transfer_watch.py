from sqlalchemy import select
from models import SourceWatch, TransferSignal, MatchResearchTarget
SOURCE_WATCHES=[
("FFN extraNat — Elite water polo","federation","web","France — Elite clubs","https://www.extranat.fr/waterpolo/","primary",6,"Official fixtures, match sheets, live scoring/statistics when published."),
("Granville Water Polo — official site","club_official","web","Granville Water Polo","https://www.granvillewaterpolo.com/","primary",12,"Club roster, schedules, announcements and links to public social pages."),
("Granville Water Polo — Facebook","club_social","facebook","Granville Water Polo","https://www.facebook.com/GRANVILLEWATERPOLO/","club_public",12,"Public club posts only; confirm roster changes with official club/FFN evidence when possible."),
("Granville Water Polo — Instagram","club_social","instagram","Granville Water Polo","https://www.instagram.com/granvillewaterpolo/","club_public",12,"Public club account listed by Granville/HelloAsso."),
("Waterpolo 360 — confirmed transfers","media","web","International transfers","https://waterpolo360news.com/confirmed-transfers/","media_confirmed",12,"High-value transfer discovery source; upgrade with club/federation corroboration when available."),
("Waterpolo 360 — women transfers","media","web","Women's transfers","https://waterpolo360news.com/water-polo-transfers-and-gossip/womens-transfers-and-gossip/","media",12,"Confirmed deals and rumours remain separate evidence states."),
("Total Waterpolo — transfers","media","web","International transfers","https://total-waterpolo.com/water-polo-transfers/","media_confirmed",12,"Transfer timeline and confirmed/rumour labels."),
("SO POLO — public social","media_social","instagram","France water polo","https://www.instagram.com/sopolo.news/","media",12,"French water-polo news signal; media reporting, not an official registration source."),
("World Aquatics — competitions","federation","web","International","https://www.worldaquatics.com/competitions","primary",6,"Official competition pages, reports, videos and event rosters."),
("European Aquatics — schedule/results","federation","web","Europe","https://europeanaquatics.org/events/schedule-and-results/","primary",6,"Official European calendar/results."),
("Grand Nancy — official site/social hub","club_official","web","Grand Nancy Aquatique Club","https://www.grandnancyaquatiqueclub.com/contact/","primary",12,"Official site exposes public social links."),
("Taverny SN95 — official site","club_official","web","Taverny Sports Nautiques 95","https://tsn95.fr/","primary",12,"Official club information and public match posts."),]
TRANSFER_SIGNALS=[
("Elena Ruiz","","CN Atlètic-Barceloneta","confirmed","2026-08-04","Waterpolo 360","https://waterpolo360news.com/water-polo-confirmed-transfers-and-gossip/","media_confirmed",.92,"Spain international move signal."),
("Izabella Chiappini","","Sori Pool Beach","confirmed","2026-08-05","Waterpolo 360","https://waterpolo360news.com/water-polo-confirmed-transfers-and-gossip/","media_confirmed",.92,"Major signing for newly promoted Italian side."),
("Maryn Dempsey","","CN Atlètic-Barceloneta","confirmed","2026-07-22","Waterpolo 360","https://waterpolo360news.com/confirmed-transfers/","media_confirmed",.92,"USA attacker signed by CNAB."),
("Anna Pearson","","CE Mediterrani","confirmed","2026-07-21","Waterpolo 360","https://waterpolo360news.com/confirmed-transfers/","media_confirmed",.92,"Women's first-team signing."),
("Emma Lineback","","CE Mediterrani","confirmed","2026-07-21","Waterpolo 360","https://waterpolo360news.com/confirmed-transfers/","media_confirmed",.92,"Women's first-team signing."),
("Isabel Williams","CN Sabadell","Rapallo","confirmed","2026-07-17","Waterpolo 360","https://waterpolo360news.com/confirmed-transfers/","media_confirmed",.92,"USA goalkeeper move."),
("Maxine Schaap","","De Zaan","confirmed","2026-07-15","Waterpolo 360","https://waterpolo360news.com/confirmed-transfers/","media_confirmed",.92,"Return to De Zaan."),
("Britt van den Dobbelsteen","","De Zaan","confirmed","2026-07-15","Waterpolo 360","https://waterpolo360news.com/confirmed-transfers/","media_confirmed",.92,"Return to De Zaan."),
("Noa de Vries","","Pallanuoto Trieste","confirmed","2026-07-15","Waterpolo 360","https://waterpolo360news.com/confirmed-transfers/","media_confirmed",.92,"Netherlands centre joins Trieste."),
("Kata Hajdu","UVSE","Olympiacos","confirmed","2026-07-13","Waterpolo 360","https://waterpolo360news.com/confirmed-transfers/","media_confirmed",.92,"Hungary international move."),
("Alejandra Aznar","","Pallanuoto Trieste","confirmed","2026-07-13","Waterpolo 360","https://waterpolo360news.com/confirmed-transfers/","media_confirmed",.92,"Spanish left-hander joins Trieste."),
("Nikoleta Eleftheriadou","","Vouliagmeni","confirmed","2026-07-11","Waterpolo 360","https://waterpolo360news.com/confirmed-transfers/","media_confirmed",.92,"High-profile Greek signing."),
("Sinia Plotz","","SIS Roma","confirmed","2026-07-08","Waterpolo 360","https://waterpolo360news.com/confirmed-transfers/","media_confirmed",.92,"Women's roster reinforcement."),
("Iva Rozic","","SIS Roma","confirmed","2026-07-08","Waterpolo 360","https://waterpolo360news.com/confirmed-transfers/","media_confirmed",.92,"Croatian U20 standout joins SIS Roma."),
("Sofia Giustini","","Pallanuoto Trieste","confirmed","2026-07-01","Waterpolo 360","https://waterpolo360news.com/confirmed-transfers/","media_confirmed",.92,"Italy international signing."),
("Kamilla Farago","UVSE","CN Sant Andreu","rumour","2026-05-07","Waterpolo 360","https://waterpolo360news.com/water-polo-transfers-and-gossip/womens-transfers-and-gossip/","media_rumour",.55,"Rumour only. Never treat as roster confirmation without later evidence."),]
MATCH_TARGETS=[
("WA-WWC-2026-F-USA-ESP","Women’s Water Polo World Cup 2026 — Final","2026","United States","Spain","2026-07-26","13-9","https://www.worldaquatics.com/news/4546786/usa-bolts-to-seventh-womens-world-cup-crown","https://www.worldaquatics.com/videos/4547492/team-usa-takes-home-the-title-water-polo-world-cup-2026-sydney-usa-vs-spain","official_report_available",100,"Priority benchmark: official report and video page available."),
("WA-WWC-2026-SF-USA-AUS","Women’s Water Polo World Cup 2026 — Final","2026","United States","Australia","2026-07-24","10-6","https://www.worldaquatics.com/news/4544409/italy-and-hungary-win-5-8-womens-semifinals","","official_report_available",95,"Semifinal; official match narrative and score."),
("WA-WWC-2026-SF-ESP-RUS","Women’s Water Polo World Cup 2026 — Final","2026","Spain","Russia","2026-07-24","15-13 SO","https://www.worldaquatics.com/news/4544409/italy-and-hungary-win-5-8-womens-semifinals","","official_report_available",95,"Semifinal decided by shootout after 10-10 regulation."),
("WA-WWC-2026-QF-ESP-HUN","Women’s Water Polo World Cup 2026 — Final","2026","Spain","Hungary","2026-07-22","8-7","https://www.worldaquatics.com/news/4540526/russia-stuns-european-champion-in-world-cup-quarterfinals","","official_report_available",90,"Quarterfinal useful for Spain scouting."),
("WA-WWC-2026-QF-USA-CHN","Women’s Water Polo World Cup 2026 — Final","2026","United States","China","2026-07-22","14-8","https://www.worldaquatics.com/news/4540526/russia-stuns-european-champion-in-world-cup-quarterfinals","","official_report_available",90,"Quarterfinal useful for USA scouting."),
("WA-U18W-2026-SF-ESP-HUN","World Aquatics U18 Women’s Championships","2026","Spain","Hungary","2026-08-22","13-10","https://www.worldaquatics.com/news/4564707/spain-to-defend-u18-crown-against-australia","","official_report_available",85,"Current youth generation; useful forward-looking U20 scouting."),
("WA-U18W-2026-SF-AUS-USA","World Aquatics U18 Women’s Championships","2026","Australia","United States","2026-08-22","14-10","https://www.worldaquatics.com/news/4564707/spain-to-defend-u18-crown-against-australia","","official_report_available",85,"Current youth generation; useful forward-looking U20 scouting."),]
def seed_transfer_watch(db):
    for name,stype,platform,scope,url,trust,hours,note in SOURCE_WATCHES:
        if not db.scalar(select(SourceWatch).where(SourceWatch.name==name)):
            db.add(SourceWatch(name=name,source_type=stype,platform=platform,entity_scope=scope,url=url,trust_level=trust,refresh_hours=hours,note=note))
    for player,fr,to,kind,date,sname,url,tier,conf,note in TRANSFER_SIGNALS:
        if not db.scalar(select(TransferSignal).where(TransferSignal.player_name==player,TransferSignal.to_team==to,TransferSignal.published_date==date)):
            db.add(TransferSignal(player_name=player,from_team=fr,to_team=to,signal_type=kind,published_date=date,source_name=sname,source_url=url,source_tier=tier,confidence_score=conf,note=note))
    for key,comp,season,a,b,date,score,src,video,status,priority,note in MATCH_TARGETS:
        if not db.scalar(select(MatchResearchTarget).where(MatchResearchTarget.external_key==key)):
            db.add(MatchResearchTarget(external_key=key,competition=comp,season=season,team_a=a,team_b=b,event_date=date,score_text=score,source_url=src,video_url=video,research_status=status,priority=priority,note=note))
    db.commit()
