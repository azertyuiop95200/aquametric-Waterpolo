"""Second verified 2026-27 transfer wave: Balkans, Hungary and Germany.

Only player/roster movements are included here. Coaching changes are intentionally
excluded from TransferSignal. Unknown destinations remain blank instead of guessed.
"""

TOTAL_WP = "https://total-waterpolo.com/water-polo-transfers/"
LONCAR_URL = "https://total-waterpolo.com/confirmed-luka-loncar-to-olympiacos-two-croats-to-follow-him/"
LUKIC_URL = "https://total-waterpolo.com/confirmed-nikola-lukic-to-radnicki2/"
MARCELIC_URL = "https://total-waterpolo.com/confirmed-ivan-marcelic-to-radnicki/"
VRLIC_URL = "https://total-waterpolo.com/confirmed-josip-vrlic-to-radnicki/"
VASAS_IN_URL = "https://total-waterpolo.com/confirmed-two-hungarians-serb-and-dutch-to-vasas/"
VASAS_OUT_URL = "https://total-waterpolo.com/confirmed-seven-players-leave-vasas/"
SPANDAU_URL = "https://total-waterpolo.com/confirmed-nikola-kojic-to-novi-beograd-five-players-leave-spandau/"
JADRAN_HN_URL = "https://total-waterpolo.com/confirmed-two-hungarians-serb-and-dutch-to-vasas-2/"
JUG_TATRAI_URL = "https://vlv.hu/tatrai-david-is-dubrovniki-lett-vlv-interju/"
JUG_SIMIC_URL = "https://jug.hr/category/top-objava/"
JUG_ROSTER_URL = "https://dubrovackidnevnik.net.hr/sport/prvi-trening-juga-uoci-nove-sezone-cetiri-nova-lica-nova-jedinica-na-vratima-ova-sezona-mora-biti-bolja-nego-prosla"
FILIPOVIC_URL = "https://total-waterpolo.com/confirmed-filip-filipovic-to-retirement-final-decision/"
WP360_MEN = "https://waterpolo360news.com/water-polo-transfers-and-gossip/mens-transfers-and-gossip/"


def _row(player, fr, to, date, source, url, tier="media_confirmed", confidence=.94,
         note="", kind="confirmed", gender="Men"):
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


WAVE2_TRANSFER_SIGNALS = [
    _row("Luka Loncar", "Mladost Zagreb", "Olympiacos", "2026-04-17", "Total Waterpolo", LONCAR_URL,
         note="Confirmed return to Olympiacos on a two-year deal."),
    _row("Nikola Lukic", "Novi Beograd", "Radnicki Kragujevac", "2026-04-17", "Total Waterpolo / Radnicki", LUKIC_URL,
         note="Radnicki source confirmed Lukic's return for 2026-27.", confidence=.96),
    _row("Ivan Marcelic", "Mladost Zagreb", "Radnicki Kragujevac", "2026-06-01", "Total Waterpolo / Radnicki", MARCELIC_URL,
         note="Radnicki confirmed the Croatian goalkeeper's arrival.", confidence=.96),
    _row("Josip Vrlic", "Mladost Zagreb", "Radnicki Kragujevac", "2026-06-04", "Total Waterpolo / Radnicki", VRLIC_URL,
         note="Radnicki confirmed Vrlic's return to the club.", confidence=.96),
    _row("Mate Aranyi", "CC Ortigia", "Vasas", "2026-06-11", "Total Waterpolo / Vasas", VASAS_IN_URL,
         note="Vasas head coach announced the four new recruits.", confidence=.96),
    _row("Marton Nagy", "Spandau 04", "Vasas", "2026-06-11", "Total Waterpolo / Vasas", VASAS_IN_URL,
         note="Vasas head coach announced the four new recruits.", confidence=.96),
    _row("Andrej Barac", "Sabac", "Vasas", "2026-06-11", "Total Waterpolo / Vasas", VASAS_IN_URL,
         note="Vasas head coach announced the four new recruits.", confidence=.96),
    _row("Benjamin Hessels", "OSC Budapest", "Vasas", "2026-06-11", "Total Waterpolo / Vasas", VASAS_IN_URL,
         note="Vasas head coach announced the four new recruits.", confidence=.96),
    _row("Bogdan Djurdjic", "Vasas", "", "2026-06-02", "Total Waterpolo / Vasas", VASAS_OUT_URL,
         note="Vasas confirmed the departure; reported Budva links were not treated as confirmed."),
    _row("Angelos Foskolos", "Vasas", "CN Posillipo", "2026-08-08", "Waterpolo 360 / Vasas exit record", WP360_MEN,
         note="Adds the known previous club to the already confirmed Posillipo signing."),
    _row("Joao Coimbra Fernandes", "Vasas", "", "2026-06-02", "Total Waterpolo / Vasas", VASAS_OUT_URL,
         note="Vasas confirmed the departure; Jadran HN links remained unconfirmed in this source."),
    _row("Kristof Varnai", "Vasas", "", "2026-06-02", "Total Waterpolo / Vasas", VASAS_OUT_URL,
         note="Vasas confirmed Varnai retired at age 31."),
    _row("Domonkos Selley-Rauscher", "Vasas", "", "2026-06-02", "Total Waterpolo / Vasas", VASAS_OUT_URL,
         note="Vasas confirmed the departure after eight seasons."),
    _row("Lorinc Gabor", "Vasas", "", "2026-06-02", "Total Waterpolo / Vasas", VASAS_OUT_URL,
         note="Vasas confirmed the roster exit."),
    _row("Tomas Csorba", "Vasas", "", "2026-06-02", "Total Waterpolo / Vasas", VASAS_OUT_URL,
         note="Vasas confirmed the roster exit."),
    _row("Nikola Kojic", "Spandau 04", "Novi Beograd", "2026-06-06", "Total Waterpolo / Spandau 04", SPANDAU_URL,
         note="Adds Spandau 04 as the previous club to the confirmed Novi Beograd move."),
    _row("Laszlo Baksa", "Spandau 04", "", "2026-06-06", "Total Waterpolo / Spandau 04", SPANDAU_URL,
         note="Spandau confirmed the goalkeeper's retirement."),
    _row("Yannek Chiru", "Spandau 04", "Waspo 98 Hannover", "2026-06-06", "Total Waterpolo / Spandau 04", SPANDAU_URL,
         note="Spandau confirmed Chiru would join Waspo 98 Hannover."),
    _row("Moritz Ostmann", "Spandau 04", "", "2026-06-06", "Total Waterpolo / Spandau 04", SPANDAU_URL,
         note="Spandau confirmed Ostmann ended his career."),
    _row("Danilo Radovic", "CN Posillipo", "Jadran Herceg Novi", "2026-07-01", "Total Waterpolo", JADRAN_HN_URL,
         note="Confirmed return to Jadran after one season at Posillipo."),
    _row("Luka Murisic", "Primorac Kotor", "Jadran Herceg Novi", "2026-07-01", "Total Waterpolo", JADRAN_HN_URL,
         note="Confirmed move from Primorac to Jadran Herceg Novi."),
    _row("Dusan Trtovic", "Novi Beograd", "Jadran Herceg Novi", "2026-07-01", "Total Waterpolo", JADRAN_HN_URL,
         note="Included in Total Waterpolo's confirmed Jadran HN reinforcement report."),
    _row("David Tatrai", "BVSC", "VK Jug", "2026-06-24", "VLV / BVSC announcement", JUG_TATRAI_URL,
         tier="first_person_media", confidence=.97,
         note="Player interview follows BVSC announcement of his first transfer to Jug."),
    _row("Vukasin Simic", "ASC Duisburg", "VK Jug", "2026-07-17", "VK Jug", JUG_SIMIC_URL,
         tier="club_official", confidence=.99,
         note="Official Jug archive lists Simic as a new reinforcement from ASC Duisburg."),
    _row("Ante Jerkovic", "VK Jug", "", "2026-08-24", "Dubrovacki Dnevnik — Jug first training", JUG_ROSTER_URL,
         tier="current_roster_media", confidence=.92, kind="reported",
         note="Current first-team training report lists Jerkovic among five players who left Jug."),
    _row("Toni Mozara", "VK Jug", "", "2026-08-24", "Dubrovacki Dnevnik — Jug first training", JUG_ROSTER_URL,
         tier="current_roster_media", confidence=.92, kind="reported",
         note="Current first-team training report lists Mozara among five players who left Jug."),
    _row("Petar Kulas", "VK Jug", "", "2026-08-24", "Dubrovacki Dnevnik — Jug first training", JUG_ROSTER_URL,
         tier="current_roster_media", confidence=.92, kind="reported",
         note="Current first-team training report lists Kulas among five players who left Jug."),
    _row("Bogdan Djerkovic", "VK Jug", "", "2026-08-24", "Dubrovacki Dnevnik — Jug first training", JUG_ROSTER_URL,
         tier="current_roster_media", confidence=.92, kind="reported",
         note="Current first-team training report lists Djerkovic among five players who left Jug."),
    _row("Filip Filipovic", "Los Angeles Athletic Club", "", "2026-05-06", "Total Waterpolo / USA Water Polo interview", FILIPOVIC_URL,
         note="Filipovic explicitly confirmed his final retirement after LAAC's National League title.", confidence=.98),
]
