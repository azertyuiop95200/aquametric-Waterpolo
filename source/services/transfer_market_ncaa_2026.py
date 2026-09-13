"""Official NCAA water-polo transfers for the 2026 collegiate season.

NCAA water polo uses a calendar-year season label, so these rows explicitly carry
season="2026" rather than inheriting the European 2026-27 market label.
"""

UCLA_MEN_URL = "https://uclabruins.com/news/2026/08/26/no-1-mens-water-polo-begins-2026-season-saturday"
UCLA_WOMEN_URL = "https://uclabruins.com/news/2026/04/08/womens-water-polo-heads-to-cal-for-mpsf-tournament"
USC_MEN_URL = "https://usctrojans.com/news/2026/8/6/mens-water-polo-usc-mens-water-polo-unveils-2026-schedule"
STANFORD_HERZER_URL = "https://gostanford.com/news/2026/04/1/card-adds-bernardo-herzer"
STANFORD_ROZOLIS_URL = "https://gostanford.com/news/2026/04/8/rozolis-hill-joins-the-cardinal"


def _row(gender, player, fr, to, date, source, url, note=""):
    return {
        "gender": gender,
        "player": player,
        "from": fr,
        "to": to,
        "kind": "confirmed",
        "date": date,
        "source": source,
        "url": url,
        "tier": "team_official",
        "confidence": .99,
        "note": note,
        "season": "2026",
    }


NCAA_2026_TRANSFER_SIGNALS = [
    # UCLA men — official Aug. 26 season preview identifies four transfers plus
    # Luka Gladovic as a first-year Bruin arriving after VK Novi Beograd.
    _row("Men", "Luka Gladovic", "VK Novi Beograd", "UCLA", "2026-08-26", "UCLA Athletics", UCLA_MEN_URL,
         "Official UCLA 2026 preview lists Gladovic among the nine new Bruins; this row corrects the market season to NCAA 2026."),
    _row("Men", "Danilo Dragovic", "UC Santa Barbara", "UCLA", "2026-08-26", "UCLA Athletics", UCLA_MEN_URL,
         "Official UCLA preview identifies Dragovic as a UC Santa Barbara transfer."),
    _row("Men", "Chase McFarland", "Stanford", "UCLA", "2026-08-26", "UCLA Athletics", UCLA_MEN_URL,
         "Official UCLA preview identifies McFarland as one of three Stanford transfers."),
    _row("Men", "Jack Merrill", "Stanford", "UCLA", "2026-08-26", "UCLA Athletics", UCLA_MEN_URL,
         "Official UCLA preview identifies Merrill as one of three Stanford transfers."),
    _row("Men", "Griffen Price", "Stanford", "UCLA", "2026-08-26", "UCLA Athletics", UCLA_MEN_URL,
         "Official UCLA preview identifies Price as one of three Stanford transfers."),

    # UCLA women — the official 2026 notes explicitly identify all three portal additions.
    _row("Women", "Janna Tauscher", "California", "UCLA", "2026-02-05", "UCLA Athletics", UCLA_WOMEN_URL,
         "Official UCLA 2026 notes identify Tauscher as a transfer from California."),
    _row("Women", "Zoë Frangieh", "Arizona State", "UCLA", "2026-02-05", "UCLA Athletics", UCLA_WOMEN_URL,
         "Official UCLA 2026 notes identify Frangieh as a transfer from Arizona State."),
    _row("Women", "Fanni Muzsnay", "USC", "UCLA", "2026-02-05", "UCLA Athletics", UCLA_WOMEN_URL,
         "Official UCLA 2026 notes identify Muzsnay as a transfer from USC."),

    # USC men — official schedule release calls Georgaras the lone incoming transfer.
    _row("Men", "Apostolos Georgaras", "University of the Pacific", "USC", "2026-08-06", "USC Athletics", USC_MEN_URL,
         "USC's official 2026 preview identifies Georgaras as the lone incoming transfer, from Pacific."),

    # Stanford men — direct official transfer announcements.
    _row("Men", "Bernardo Herzer", "USC", "Stanford", "2026-04-01", "Stanford Athletics", STANFORD_HERZER_URL,
         "Stanford officially announced former USC goalkeeper Bernardo Herzer."),
    _row("Men", "James Rozolis-Hill", "Harvard", "Stanford", "2026-04-08", "Stanford Athletics", STANFORD_ROZOLIS_URL,
         "Stanford officially announced the three-time Harvard All-American transfer."),
]
