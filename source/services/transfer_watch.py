from sqlalchemy import select
from models import SourceWatch, TransferSignal, MatchResearchTarget

TRANSFER_SEASON = "2026-2027"

KNZB_URL = "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie"
WP360_CONFIRMED = "https://waterpolo360news.com/confirmed-transfers/"
WP360_HUB = "https://waterpolo360news.com/water-polo-confirmed-transfers-and-gossip/"
TOTAL_WP = "https://total-waterpolo.com/water-polo-transfers/"
TRIESTE_2026 = "https://www.pallanuototrieste.com/it/news/articolo/si-riparte-dall-ausonia-la-pallanuoto-trieste-femminile-e-pronta-a-scendere-in-campo-per-la-stagione-2026-27"
MATARO_FARAGO = "https://waterpolo360news.com/mataro-strengthens-its-project-with-the-signings-of-queralt-anton-and-kamilla-farago/"
MATARO_CARLA = "https://www.mundodeportivo.com/waterpolo/20260715/1004206746/carla-martin-nueva-jugadora-assolim-mataro.html"
VLV_NEMET = "https://vlv.hu/nemet-toni-torokorszagba-szerzodott/"

# Evidence hierarchy: official federation/league/club > official club social >
# specialist media confirmed > media report/rumour > community discovery only.
SOURCE_WATCHES = [
    ("FFN extraNat — Elite water polo", "federation", "web", "France — Elite clubs", "https://www.extranat.fr/waterpolo/", "primary", 6, "Official fixtures, match sheets, live scoring/statistics when published."),
    ("FFN — water-polo transfer rules", "federation", "web", "France — transfers and licences", "https://www.ffnatation.fr/reglements-du-water-polo", "primary", 12, "Official French regulations, including transfer rules and the 2026-27 competition framework."),
    ("RFEN — water polo", "federation", "web", "Spain", "https://rfen.es/especialidades/waterpolo/", "primary", 12, "Official Spanish federation competition and roster context."),
    ("LEWaterpolo — Spanish leagues", "league", "web", "Spain — División de Honor", "https://lewaterpolo.com/", "primary", 12, "League match, roster and club context; cross-check transfer claims with club/RFEN evidence."),
    ("Waterpolo.nl — confirmed transfer overview", "federation_media", "web", "Netherlands and Dutch players abroad", KNZB_URL, "primary", 12, "KNZB editorial overview explicitly listing confirmed 2026-27 transfers for women and men."),
    ("European Aquatics — transfer regulations", "federation", "web", "Europe — ITC rules", "https://europeanaquatics.org/wp-content/uploads/2024/10/WATER-POLO-TRANSFER-REGULATIONS.pdf", "primary", 24, "Official ITC rules; distinguishes transfer reporting from formal international eligibility."),
    ("European Aquatics — schedule/results", "federation", "web", "Europe", "https://europeanaquatics.org/events/schedule-and-results/", "primary", 6, "Official European calendar/results and competition rosters when published."),
    ("World Aquatics — competitions", "federation", "web", "International", "https://www.worldaquatics.com/competitions", "primary", 6, "Official competition pages, reports, videos and event rosters."),
    ("USA Water Polo — news", "federation", "web", "United States", "https://usawaterpolo.org/", "primary", 12, "Official USA Water Polo news and national-team/college context."),
    ("Waterpolo 360 — confirmed transfers", "media", "web", "International transfers", WP360_CONFIRMED, "media_confirmed", 6, "High-value specialist transfer source; upgrade with club/federation corroboration when available."),
    ("Waterpolo 360 — transfer hub", "media", "web", "International transfers and rumours", WP360_HUB, "media", 6, "Confirmed deals and rumours remain separate evidence states."),
    ("Waterpolo 360 — Instagram", "media_social", "instagram", "International water polo", "https://www.instagram.com/waterpolo360news/", "media", 6, "Fast public social signal; article/club evidence remains preferred."),
    ("Total Waterpolo — transfers", "media", "web", "International transfers", TOTAL_WP, "media_confirmed", 6, "Transfer timeline with explicit confirmed/rumour labels."),
    ("Total Waterpolo — Instagram", "media_social", "instagram", "International water polo", "https://www.instagram.com/total_waterpolo/", "media", 6, "Public specialist-media social feed for rapid discovery; confirm before roster updates."),
    ("Total Waterpolo — Facebook", "media_social", "facebook", "International water polo", "https://www.facebook.com/totalwaterpolonews", "media", 12, "Public specialist-media social feed; discovery/corroboration rather than registration evidence."),
    ("SO POLO — public social", "media_social", "instagram", "France water polo", "https://www.instagram.com/sopolo.news/", "media", 6, "French water-polo news signal; media reporting, not an official registration source."),
    ("Mundo Deportivo — water polo", "media", "web", "Spain", "https://www.mundodeportivo.com/waterpolo", "media_confirmed", 12, "Spanish water-polo reporting that frequently relays official club announcements."),
    ("VLV.hu — Hungarian water polo", "media", "web", "Hungary and Hungarian players abroad", "https://vlv.hu/", "media_confirmed", 12, "Specialist Hungarian source; direct player interviews can provide strong first-person transfer confirmation."),
    ("Water Polo Exchange — transfer portal discussions", "community", "web", "USA college water polo", "https://waterpoloexchange.com/latest", "discovery_only", 12, "Community/forum signal only. Never marks a transfer confirmed without official school/team evidence."),
    ("Granville Water Polo — official site", "club_official", "web", "Granville Water Polo", "https://www.granvillewaterpolo.com/", "primary", 12, "Club roster, schedules, announcements and links to public social pages."),
    ("Granville Water Polo — Facebook", "club_social", "facebook", "Granville Water Polo", "https://www.facebook.com/GRANVILLEWATERPOLO/", "club_public", 6, "Public official club posts; confirm roster changes with official club/FFN evidence when possible."),
    ("Granville Water Polo — Instagram", "club_social", "instagram", "Granville Water Polo", "https://www.instagram.com/granvillewaterpolo/", "club_public", 6, "Public official club account; useful for fast signing/departure announcements."),
    ("PAOK — women official news", "club_official", "web", "PAOK women", "https://acpaok.gr/news/womens-polo/", "primary", 12, "Official club announcements for the women's roster."),
    ("PAOK — men official news", "club_official", "web", "PAOK men", "https://acpaok.gr/news/mens-polo/", "primary", 12, "Official club announcements for the men's roster."),
    ("PAOK — Instagram", "club_social", "instagram", "PAOK water polo", "https://www.instagram.com/acpaok/", "club_public", 6, "Official multisport club social account; cross-check the website when available."),
    ("Pallanuoto Trieste — official news", "club_official", "web", "Pallanuoto Trieste", "https://www.pallanuototrieste.com/it/news/", "primary", 12, "Official club roster and signing announcements for women and men."),
    ("Pallanuoto Trieste — Instagram", "club_social", "instagram", "Pallanuoto Trieste", "https://www.instagram.com/pallanuoto_trieste/", "club_public", 6, "Official club social feed for fast roster signals."),
    ("Grand Nancy — official site/social hub", "club_official", "web", "Grand Nancy Aquatique Club", "https://www.grandnancyaquatiqueclub.com/contact/", "primary", 12, "Official site exposes public social links."),
    ("Taverny SN95 — official site", "club_official", "web", "Taverny Sports Nautiques 95", "https://tsn95.fr/", "primary", 12, "Official club information and public match posts."),
]


def _signal(gender, player, fr, to, date, source, url, tier, confidence, note="", kind="confirmed"):
    return {
        "gender": gender,
        "player": player,
        "from": fr,
        "to": to,
        "kind": kind,
        "date": date,
        "source": source,
        "url": url,
        "tier": tier,
        "confidence": confidence,
        "note": note,
    }


KNZB_WOMEN = [
    ("Indy Waltman", "ZPB H&L Productions", "GZC Donk"),
    ("Jolijn Joor", "ZVL-1886", "GZC Donk"),
    ("Linde Haksteen", "Polar Bears", "GZC Donk"),
    ("Anne Heidenrijk", "ZPC Amersfoort", "Het Ravijn"),
    ("Silvanne Slot", "ZV De Zaan", "ZPB H&L Productions"),
    ("Sam Jutte", "UZSC", "ZV De Zaan"),
    ("Melissa Schipper", "ZV De Ham ZC", "ZV De Zaan"),
    ("Anne Klein Langenhorst", "UZSC", "ZV De Zaan"),
    ("Nina van der Vorst", "PSV", "Het Ravijn"),
    ("Cynthia Mulder", "UZSC", "ZVL-1886"),
    ("Saloua Maafi", "UZSC", "ZVL-1886"),
    ("Lotte van Wingerden", "UZSC", "ZVL-1886"),
    ("Lisa Schep", "PSV", "ZVL-1886"),
    ("Maxine Schaap", "SIS Roma", "ZV De Zaan"),
    ("Britt van den Dobbelsteen", "Olympiakos", "ZV De Zaan"),
    ("Sanne Keijzer", "Arizona State University", "ZPB H&L Productions"),
    ("Vivian Sevenich", "L'Ekipe Orizzonte", "ZV De Zaan"),
    ("Tatum van der Elst", "Polar Bears", "Arizona State University"),
    ("Kiara Heerink", "Polar Bears", "Arizona State University"),
    ("Jill Oort", "Polar Bears", "Club Natació Rubí"),
    ("Maartje Keuning", "GZC Donk", "CN Sabadell"),
    ("Sarah Buis", "GZC Donk", "CN Sant Andreu"),
    ("Bente Rogge", "ZV De Zaan", "Vouliagmeni"),
    ("Esmee Ouwens", "GZC Donk", "California State University Long Beach"),
    ("Noa de Vries", "FTC Telekom", "Pallanuoto Trieste"),
    ("Fleurien Bosveld", "Alimos NAC", "SIS Roma"),
    ("Nikki Meijer", "Smile Cosenza Pallanuoto", "Rapallo Pallanuoto"),
]

KNZB_MEN = [
    ("Roko Mujan", "ZPC Amersfoort", "ZPB H&L Productions"),
    ("George Athymaritis", "UZSC", "SWOL 1894"),
    ("Dynand Muller", "ZPC Amersfoort", "OZ&PC"),
    ("Alex Horvath", "EZC", "OZ&PC"),
    ("Ruben van Vierzen", "ZV De Ham ZC", "ZV De Zaan"),
    ("Paul Kerstens", "ESTA", "SWOL 1894"),
    ("Pim Hageman", "Het Ravijn", "OZ&PC"),
    ("Mitchell Budding", "HZC De Robben", "ZPC Amersfoort"),
    ("Jorrit van der Weijden", "GZC Donk", "PAOK"),
    ("Daan Bakker", "ZV De Zaan", "Montpellier Water-Polo"),
    ("Bas Grummer", "ZVL-1886", "ASC Duisburg"),
    ("Fabio Jukic", "PSV", "IREN Genova Quinto 1921"),
    ("Stan Schuring", "Orange Coast College", "SWOL 1894"),
    ("Jeroen Rouwenhorst", "Rari Nantes Florentia", "AN Brescia"),
    ("Marnick Snel", "VK Primorje", "CC Ortigia"),
    ("Tim de Mey", "Rari Nantes Florentia", "Douaisis Agglo Water-Polo"),
]

TOTAL_WP_MEN = [
    ("Francesco Di Fulvio", "", "CN Atlètic-Barceloneta", "2026-07-16"),
    ("Vincenzo Dolce", "", "Panathinaikos", "2026-07-13"),
    ("Tommaso Gianazza", "", "Pro Recco", "2026-07-13"),
    ("Marko Bijac", "", "Pro Recco", "2026-07-11"),
    ("Toni Popadic", "", "Jadran Split", "2026-07-07"),
    ("Gergo Zalanki", "", "Pro Recco", "2026-07-03"),
    ("Loren Fatovic", "", "Olympiacos", "2026-07-01"),
    ("Konstantin Kharkov", "", "Olympiacos", "2026-06-29"),
    ("Gergely Burian", "", "VK Jug", "2026-06-23"),
    ("Vladan Spaic", "", "Vouliagmeni", "2026-06-20"),
    ("Dmitri Kholod", "", "Oradea", "2026-06-18"),
    ("Konstantinos Kakaris", "", "Ferencvaros", "2026-06-17"),
    ("Marko Vavic", "", "Apollon Smyrnis", "2026-06-11"),
    ("Djordje Lazic", "", "Panionios", "2026-06-08"),
    ("Nikola Kojic", "", "Novi Beograd", "2026-06-06"),
    ("Dimitrije Risticevic", "", "Panionios", "2026-06-06"),
]

TRANSFER_SIGNALS = [
    # Current women — official/strong confirmations.
    _signal("Women", "Paola Di Maria", "", "Pallanuoto Trieste", "2026-08-25", "Pallanuoto Trieste", TRIESTE_2026, "club_official", .99, "Official 2026-27 squad presentation lists Di Maria among five summer additions."),
    _signal("Women", "Malika Gaia Bovo", "", "Pallanuoto Trieste", "2026-08-25", "Pallanuoto Trieste", TRIESTE_2026, "club_official", .99, "Official 2026-27 squad presentation lists Bovo among five summer additions."),
    _signal("Women", "Anna Mamoglou", "", "PAOK", "2026-08-07", "AC PAOK", "https://acpaok.gr/%CE%AC%CE%BD%CE%BD%CE%B1-%CE%BC%CE%B1%CE%BC%CF%8C%CE%B3%CE%BB%CE%BF%CF%85-%CE%BC%CE%AF%CE%B1-%CE%BC%CE%B5%CF%84%CE%B1%CE%B3%CF%81%CE%B1%CF%86%CE%AE-%CE%B5%CE%BC%CF%80%CE%B5%CE%B9%CF%81%CE%AF%CE%B1/", "club_official", .99, "Official PAOK announcement for 2026-27."),
    _signal("Women", "Izabella Chiappini", "", "Sori Pool Beach", "2026-08-05", "Waterpolo 360", WP360_HUB, "media_confirmed", .92),
    _signal("Women", "Elena Ruiz", "", "CN Atlètic-Barceloneta", "2026-08-04", "Waterpolo 360", WP360_HUB, "media_confirmed", .92),
    _signal("Women", "Margarita Bitsakou", "", "PAOK", "2026-07-29", "AC PAOK", "https://acpaok.gr/%CF%83%CF%80%CE%BF%CF%85%CE%B4%CE%B1%CE%AF%CE%B1-%CE%B5%CE%BD%CE%AF%CF%83%CF%87%CF%85%CF%83%CE%B7-%CF%83%CF%84%CE%BF%CE%BD-%CF%86%CE%BF%CF%85%CE%BD%CF%84%CE%B1%CF%81%CE%B9%CF%83%CF%84%CF%8C-%CE%BC/", "club_official", .99, "Official PAOK announcement for 2026-27."),
    _signal("Women", "Maryn Dempsey", "", "CN Atlètic-Barceloneta", "2026-07-22", "Waterpolo 360", WP360_CONFIRMED, "media_confirmed", .92),
    _signal("Women", "Anna Pearson", "", "CE Mediterrani", "2026-07-21", "Waterpolo 360", WP360_CONFIRMED, "media_confirmed", .92),
    _signal("Women", "Emma Lineback", "", "CE Mediterrani", "2026-07-21", "Waterpolo 360", WP360_CONFIRMED, "media_confirmed", .92),
    _signal("Women", "Isabel Williams", "CN Sabadell", "Rapallo", "2026-07-17", "Waterpolo 360", WP360_CONFIRMED, "media_confirmed", .92),
    _signal("Women", "Kamilla Farago", "UVSE", "CN Mataró", "2026-07-16", "Waterpolo 360 / CN Mataró announcement", MATARO_FARAGO, "media_confirmed", .97, "CN Mataró officially announced the signing; later Spanish reporting also confirmed it."),
    _signal("Women", "Carla Martín", "Tenerife Echeyde", "CN Mataró", "2026-07-15", "Mundo Deportivo / CN Mataró announcement", MATARO_CARLA, "media_confirmed", .97, "Mataró-announced return after three seasons at Tenerife Echeyde."),
    _signal("Women", "Kata Hajdu", "UVSE", "Olympiacos", "2026-07-13", "Waterpolo 360", WP360_CONFIRMED, "media_confirmed", .92),
    _signal("Women", "Nikoleta Eleftheriadou", "", "Vouliagmeni", "2026-07-11", "Waterpolo 360", WP360_CONFIRMED, "media_confirmed", .92),
    _signal("Women", "Queralt Anton", "CN Sant Andreu", "CN Mataró", "2026-07-08", "Waterpolo 360 / CN Mataró announcement", MATARO_FARAGO, "media_confirmed", .97, "Article states CN Mataró officially announced Anton for 2026-27."),
    _signal("Women", "Sinia Plotz", "", "SIS Roma", "2026-07-08", "Waterpolo 360", WP360_CONFIRMED, "media_confirmed", .92),
    _signal("Women", "Iva Rozic", "", "SIS Roma", "2026-07-08", "Waterpolo 360", WP360_CONFIRMED, "media_confirmed", .92),
    _signal("Women", "Sofia Giustini", "", "Pallanuoto Trieste", "2026-07-01", "Waterpolo 360", WP360_CONFIRMED, "media_confirmed", .92),
    _signal("Women", "Nic Porter", "", "CN Marseille", "2026-06-04", "Waterpolo 360", WP360_HUB, "media_rumour", .52, "Rumour only; never use as confirmed roster evidence.", "rumour"),
    _signal("Women", "Athina Giannopoulou", "CN Sabadell", "Vouliagmeni", "2026-06-02", "Waterpolo 360", WP360_HUB, "media_rumour", .55, "Rumour only; requires official corroboration.", "rumour"),

    # Men — current confirmations.
    _signal("Men", "Toni Nemet", "Jadran Split", "ENKA Istanbul", "2026-08-20", "VLV.hu — player interview", VLV_NEMET, "first_person_media", .98, "Nemet directly confirms in interview that he decided to join ENKA Istanbul."),
    _signal("Men", "Angelos Foskolos", "", "CN Posillipo", "2026-08-08", "Waterpolo 360", WP360_HUB, "media_confirmed", .92),
    _signal("Men", "Nemanja Ubovic", "", "Primorac Kotor", "2026-08-02", "Waterpolo 360", WP360_CONFIRMED, "media_confirmed", .92),
    _signal("Men", "Nika Shushiashvili", "BVSC", "Novi Beograd", "2026-07-30", "Waterpolo 360", WP360_CONFIRMED, "media_confirmed", .92),
    _signal("Men", "Lukas Durik", "Pro Recco", "Jadran Herceg Novi", "2026-07-30", "Waterpolo 360", WP360_CONFIRMED, "media_confirmed", .92),
    _signal("Men", "Nicolas Saveljic", "", "Dinamo Bucharest", "2026-07-29", "Waterpolo 360", WP360_CONFIRMED, "media_confirmed", .92),
    _signal("Men", "Jerko Marinic Kragic", "", "Steaua Bucharest", "2026-07-28", "Waterpolo 360", WP360_CONFIRMED, "media_confirmed", .92),
    _signal("Men", "Joao Pedro", "", "Pallanuoto Trieste", "2026-07-17", "Waterpolo 360", WP360_CONFIRMED, "media_confirmed", .92),

    *[_signal("Women", player, fr, to, "2026-07-20", "Waterpolo.nl / KNZB", KNZB_URL, "federation_confirmed", .97, "Listed in the KNZB confirmed 2026-27 transfer overview.") for player, fr, to in KNZB_WOMEN],
    *[_signal("Men", player, fr, to, "2026-07-20", "Waterpolo.nl / KNZB", KNZB_URL, "federation_confirmed", .97, "Listed in the KNZB confirmed 2026-27 transfer overview.") for player, fr, to in KNZB_MEN],
    *[_signal("Men", player, fr, to, date, "Total Waterpolo", TOTAL_WP, "media_confirmed", .92, "Listed as confirmed on Total Waterpolo's 2026 transfer timeline.") for player, fr, to, date in TOTAL_WP_MEN],
]

MATCH_TARGETS = [
    ("WA-WWC-2026-F-USA-ESP", "Women’s Water Polo World Cup 2026 — Final", "2026", "United States", "Spain", "2026-07-26", "13-9", "https://www.worldaquatics.com/news/4546786/usa-bolts-to-seventh-womens-world-cup-crown", "https://www.worldaquatics.com/videos/4547492/team-usa-takes-home-the-title-water-polo-world-cup-2026-sydney-usa-vs-spain", "official_report_available", 100, "Priority benchmark: official report and video page available."),
    ("WA-WWC-2026-SF-USA-AUS", "Women’s Water Polo World Cup 2026 — Final", "2026", "United States", "Australia", "2026-07-24", "10-6", "https://www.worldaquatics.com/news/4544409/italy-and-hungary-win-5-8-womens-semifinals", "", "official_report_available", 95, "Semifinal; official match narrative and score."),
    ("WA-WWC-2026-SF-ESP-RUS", "Women’s Water Polo World Cup 2026 — Final", "2026", "Spain", "Russia", "2026-07-24", "15-13 SO", "https://www.worldaquatics.com/news/4544409/italy-and-hungary-win-5-8-womens-semifinals", "", "official_report_available", 95, "Semifinal decided by shootout after 10-10 regulation."),
    ("WA-WWC-2026-QF-ESP-HUN", "Women’s Water Polo World Cup 2026 — Final", "2026", "Spain", "Hungary", "2026-07-22", "8-7", "https://www.worldaquatics.com/news/4540526/russia-stuns-european-champion-in-world-cup-quarterfinals", "", "official_report_available", 90, "Quarterfinal useful for Spain scouting."),
    ("WA-WWC-2026-QF-USA-CHN", "Women’s Water Polo World Cup 2026 — Final", "2026", "United States", "China", "2026-07-22", "14-8", "https://www.worldaquatics.com/news/4540526/russia-stuns-european-champion-in-world-cup-quarterfinals", "", "official_report_available", 90, "Quarterfinal useful for USA scouting."),
    ("WA-U18W-2026-SF-ESP-HUN", "World Aquatics U18 Women’s Championships", "2026", "Spain", "Hungary", "2026-08-22", "13-10", "https://www.worldaquatics.com/news/4564707/spain-to-defend-u18-crown-against-australia", "", "official_report_available", 85, "Current youth generation; useful forward-looking U20 scouting."),
    ("WA-U18W-2026-SF-AUS-USA", "World Aquatics U18 Women’s Championships", "2026", "Australia", "United States", "2026-08-22", "14-10", "https://www.worldaquatics.com/news/4564707/spain-to-defend-u18-crown-against-australia", "", "official_report_available", 85, "Current youth generation; useful forward-looking U20 scouting."),
]


def _append_note(current, addition):
    current = (current or "").strip()
    addition = (addition or "").strip()
    if not addition or addition in current:
        return current
    return f"{current} {addition}".strip()


def _rank(kind):
    return {"superseded": 0, "rumour": 1, "reported": 2, "confirmed": 3}.get(kind, 1)


def seed_transfer_watch(db):
    # Upsert source catalogue so trust tiers, URLs and refresh rates evolve cleanly.
    for name, stype, platform, scope, url, trust, hours, note in SOURCE_WATCHES:
        watch = db.scalar(select(SourceWatch).where(SourceWatch.name == name))
        if not watch:
            db.add(SourceWatch(name=name, source_type=stype, platform=platform, entity_scope=scope, url=url, trust_level=trust, refresh_hours=hours, note=note))
        else:
            watch.source_type = stype
            watch.platform = platform
            watch.entity_scope = scope
            watch.url = url
            watch.trust_level = trust
            watch.refresh_hours = hours
            watch.note = note
            watch.enabled = True

    # Merge corroborating reports for the same move and retain the strongest evidence.
    for item in TRANSFER_SIGNALS:
        same_move = db.scalars(select(TransferSignal).where(
            TransferSignal.player_name == item["player"],
            TransferSignal.to_team == item["to"],
            TransferSignal.season == TRANSFER_SEASON,
        ).order_by(TransferSignal.id.asc())).all()

        if same_move:
            signal = same_move[0]
            dates = [d for d in [signal.published_date, item["date"]] if d]
            signal.published_date = min(dates) if dates else item["date"]
            signal.gender = item["gender"]
            signal.from_team = item["from"] or signal.from_team
            signal.to_team = item["to"]
            signal.season = TRANSFER_SEASON
            if _rank(item["kind"]) >= _rank(signal.signal_type):
                signal.signal_type = item["kind"]
            if item["confidence"] >= float(signal.confidence_score or 0):
                signal.source_name = item["source"]
                signal.source_url = item["url"]
                signal.source_tier = item["tier"]
                signal.confidence_score = item["confidence"]
            signal.note = _append_note(signal.note, item["note"])
            for duplicate in same_move[1:]:
                signal.note = _append_note(signal.note, duplicate.note)
                db.delete(duplicate)
        else:
            signal = TransferSignal(
                player_name=item["player"], gender=item["gender"], from_team=item["from"], to_team=item["to"],
                signal_type=item["kind"], season=TRANSFER_SEASON, published_date=item["date"],
                source_name=item["source"], source_url=item["url"], source_tier=item["tier"],
                confidence_score=item["confidence"], note=item["note"],
            )
            db.add(signal)

        # Newer contradictory evidence removes stale rumours from the active board but preserves the audit row.
        if item["kind"] in {"confirmed", "reported", "rumour"}:
            older_rumours = db.scalars(select(TransferSignal).where(
                TransferSignal.player_name == item["player"],
                TransferSignal.season == TRANSFER_SEASON,
                TransferSignal.signal_type == "rumour",
            )).all()
            for older in older_rumours:
                if older is signal or older.to_team == item["to"]:
                    continue
                if not older.published_date or older.published_date <= item["date"]:
                    older.signal_type = "superseded"
                    older.note = _append_note(older.note, f"Superseded by newer evidence pointing to {item['to']} ({item['source']}, {item['date']}).")

    for key, comp, season, a, b, date, score, src, video, status, priority, note in MATCH_TARGETS:
        target = db.scalar(select(MatchResearchTarget).where(MatchResearchTarget.external_key == key))
        if not target:
            db.add(MatchResearchTarget(external_key=key, competition=comp, season=season, team_a=a, team_b=b, event_date=date, score_text=score, source_url=src, video_url=video, research_status=status, priority=priority, note=note))
    db.commit()
