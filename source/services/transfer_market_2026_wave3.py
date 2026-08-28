"""Third verified 2026-27 transfer wave: Spain and women's market upgrades.

This wave prioritises club-announced/confirmed Spanish moves and roster exits.
Rows matching earlier reported moves intentionally upgrade the existing database row
through transfer_watch_core's same-player/same-destination merge logic.
"""

KYRA_URL = "https://waterpolo360news.com/ethnikos-signs-canadian-olympian-kyra-christmas/"
WP360_CONFIRMED = "https://waterpolo360news.com/confirmed-transfers/"
SABA_WOMEN_URL = "https://www.isabadell.cat/esports/waterpolo/comencen-les-presentacions-dels-fitxatges-del-club-terre-camus-i-perez-331726/"
SABA_EXITS_URL = "https://radiosabadell.fm/esports/waterpolo/baixes-club-natacio-sabadell-2025-26"
SABA_MEN_EXITS_URL = "https://www.diaridesabadell.com/esports/club-natacio-sabadell-waterpolo-baixes-barroso-famera-asensio-panerai-soler.html"
TERRASSA_URL = "https://monterrassa.cat/esports/natacio/equips-waterpolo-cn-terrassa-reforcen-seves-plantilles-523861/"
TERRASSA_CURRENT_URL = "https://clubnatacioterrassa.cat/el-cn-terrassa-protagonista-de-lestiu-internacional-del-waterpolo-espanyol-amb-set-representants/"
TERRASSA_MEN_URL = "https://www.mundodeportivo.com/waterpolo/20260704/1004202787/saul-granados-primera-incorporacion-terrassa.html"


def _row(gender, player, fr, to, date, source, url, tier="media_confirmed",
         confidence=.95, note="", kind="confirmed"):
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


WAVE3_TRANSFER_SIGNALS = [
    # Greece / women.
    _row("Women", "Kyra Christmas", "Vouliagmeni", "Ethnikos", "2026-06-07",
         "Waterpolo 360 / Ethnikos announcement", KYRA_URL, confidence=.97,
         note="Ethnikos announced the Canadian international for the 2026-27 season."),

    # Sabadell women — announced and subsequently presented by the club.
    _row("Women", "Ryann Neushul", "Stanford", "CN Sabadell", "2026-06-18",
         "Waterpolo 360 / CN Sabadell", WP360_CONFIRMED, confidence=.96,
         note="Sabadell announced Neushul as the first reinforcement of the new project."),
    _row("Women", "Paula Camus", "CN Sant Andreu", "CN Sabadell", "2026-06-22",
         "CN Sabadell presentation / local media", SABA_WOMEN_URL, confidence=.97,
         note="Club presentation confirms Camus arrives from CN Sant Andreu."),
    _row("Women", "Nona Pérez", "CN Sant Andreu", "CN Sabadell", "2026-06-23",
         "CN Sabadell presentation / local media", SABA_WOMEN_URL, confidence=.97,
         note="Club presentation confirms Pérez returns to Sabadell from CN Sant Andreu."),
    _row("Women", "Martina Terré", "CN Sant Andreu", "CN Sabadell", "2026-06-25",
         "CN Sabadell presentation / local media", SABA_WOMEN_URL, confidence=.98,
         note="Sabadell announced and presented Terré as its new goalkeeper."),

    # Sabadell women roster exits. Destinations stay blank unless independently established.
    _row("Women", "Nataša Rybanská", "CN Sabadell", "", "2026-06-15",
         "Ràdio Sabadell / club announcement", SABA_EXITS_URL, "club_reported", .96,
         "Sabadell announced Rybanská would not continue for 2026-27."),
    _row("Women", "Helena Dalmases", "CN Sabadell", "", "2026-06-15",
         "Ràdio Sabadell / club announcement", SABA_EXITS_URL, "club_reported", .96,
         "Sabadell announced Dalmases would not continue for 2026-27."),

    # Terrassa women — upgrades to earlier league-media rows.
    _row("Women", "Carlota Peñalver", "CE Mediterrani", "CN Terrassa", "2026-07-08",
         "CN Terrassa announcement / local media", TERRASSA_URL, confidence=.97,
         note="Terrassa announced Peñalver as a 2026-27 signing."),
    _row("Women", "Alice Williams", "CN Sant Andreu", "CN Terrassa", "2026-07-08",
         "Waterpolo 360 / CN Terrassa", WP360_CONFIRMED, confidence=.96,
         note="Listed in Waterpolo 360 confirmed transfers as part of Terrassa's new project."),
    _row("Women", "Irene Briceño", "Real Canoe", "CN Terrassa", "2026-08-24",
         "CN Terrassa", TERRASSA_CURRENT_URL, "club_official", .98,
         "Current club report identifies Briceño as a new 2026-27 addition."),

    # Terrassa men — upgrades to earlier league-media rows.
    _row("Men", "Saúl Granados", "CN Catalunya", "CN Terrassa", "2026-07-04",
         "CN Terrassa announcement / Mundo Deportivo", TERRASSA_MEN_URL, confidence=.97,
         note="Terrassa announced Granados as its first men's signing for 2026-27."),
    _row("Men", "Álvaro García", "CE Mediterrani", "CN Terrassa", "2026-07-08",
         "CN Terrassa announcement / local media", TERRASSA_URL, confidence=.97,
         note="Terrassa officially announced García's arrival from CE Mediterrani."),

    # Sabadell men — announced exits / known destinations.
    _row("Men", "Òscar Asensio", "CN Sabadell", "CN Barcelona", "2026-06-12",
         "Diari de Sabadell / club announcement", SABA_MEN_EXITS_URL, confidence=.96,
         note="Sabadell announced the exit; the report confirms Asensio returns to CN Barcelona."),
    _row("Men", "Alberto Barroso", "CN Sabadell", "Santa Cruz Tenerife Echeyde", "2026-06-12",
         "Diari de Sabadell / club announcement", SABA_MEN_EXITS_URL, confidence=.96,
         note="Sabadell announced the exit and the report confirms Barroso will play for Echeyde."),
    _row("Men", "Martin Famera", "CN Sabadell", "", "2026-06-12",
         "Diari de Sabadell / club announcement", SABA_MEN_EXITS_URL, "club_reported", .95,
         "Confirmed roster exit; professional retirement was described as expected, so no destination is asserted."),
    _row("Men", "Tomàs Soler", "CN Sabadell", "", "2026-06-12",
         "Diari de Sabadell / club announcement", SABA_MEN_EXITS_URL, "club_reported", .95,
         "Confirmed Sabadell roster exit; destination not established in this source."),

    # Terrassa men roster exits from the club's announced continuity list.
    _row("Men", "Agustí Pericas", "CN Terrassa", "", "2026-07-04",
         "CN Terrassa / Mundo Deportivo", TERRASSA_MEN_URL, "club_reported", .94,
         "Terrassa's announced 2026-27 continuity list confirms Pericas will not continue."),
    _row("Men", "Nacho Bargalló", "CN Terrassa", "", "2026-07-04",
         "CN Terrassa / Mundo Deportivo", TERRASSA_MEN_URL, "club_reported", .94,
         "Terrassa's announced 2026-27 continuity list confirms Bargalló will not continue."),
    _row("Men", "Marc Salvador", "CN Terrassa", "", "2026-07-04",
         "CN Terrassa / Mundo Deportivo", TERRASSA_MEN_URL, "club_reported", .94,
         "Terrassa's announced 2026-27 continuity list confirms Salvador will not continue."),
    _row("Men", "Iván Sánchez", "CN Terrassa", "", "2026-07-04",
         "CN Terrassa / Mundo Deportivo", TERRASSA_MEN_URL, "club_reported", .94,
         "Terrassa's announced 2026-27 continuity list confirms Sánchez will not continue."),
]
