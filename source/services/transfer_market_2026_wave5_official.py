"""Fifth verified market wave: official Greece/Croatia announcements + NCAA 2027.

Only genuine player movements are included. Contract renewals and staff changes are
excluded. Unknown previous/next clubs stay blank instead of being inferred.
"""

APOLLON_MOURIKIS = "https://apollonwaterpolo.gr/2026/07/14/%CE%B9%CF%83%CF%87%CF%85%CF%81%CE%BF%CF%80%CE%BF%CE%B9%CE%B5%CE%AF%CF%84%CE%B1%CE%B9-%CF%83%CF%84%CE%B1-2-%CE%BC-%CE%BC%CE%B5-%CF%84%CE%B7%CE%BD-%CF%80%CE%BF%CE%B9%CF%8C%CF%84%CE%B7%CF%84%CE%B1/"
APOLLON_LORANTOS = "https://apollonwaterpolo.gr/2026/08/04/%CE%B5%CE%BD%CE%AF%CF%83%CF%87%CF%85%CF%83%CE%B7-%CF%83%CF%84%CE%B7%CE%BD-%CF%80%CE%B5%CF%81%CE%B9%CF%86%CE%AD%CF%81%CE%B5%CE%B9%CE%B1-%CE%BC%CE%B5-%CF%84%CE%BF%CE%BD-%CE%AC%CE%BB%CE%BA%CE%B7-%CE%BB/"
APOLLON_BERDES = "https://apollonwaterpolo.gr/2026/08/13/%CF%83%CF%84%CE%BF%CE%BD-%CE%B1%CF%80%CF%8C%CE%BB%CE%BB%CF%89%CE%BD%CE%B1-%CF%83%CE%BC%CF%8D%CF%81%CE%BD%CE%B7%CF%82-%CE%BF-%CE%B4%CE%B9%CE%B5%CE%B8%CE%BD%CE%AE%CF%82-%CE%BC%CE%B5-%CF%8C%CE%BB%CE%B5/"
APOLLON_KECHALARIS = "https://apollonwaterpolo.gr/2026/08/18/%CF%83%CE%BF%CF%8D%CF%80%CE%B5%CF%81-%CE%B5%CE%BD%CE%AF%CF%83%CF%87%CF%85%CF%83%CE%B7-%CE%BC%CE%B5-%CE%BA%CE%B5%CF%87%CE%B1%CE%BB%CE%AC%CF%81%CE%B7-%CE%B3%CE%B9%CE%B1-%CF%84%CE%BF%CE%BD-%CE%B1%CF%80/"
APOLLON_ZOUZOUNIS = "https://apollonwaterpolo.gr/2026/08/20/%CE%BC%CE%B5%CF%84%CE%B1%CE%B3%CF%81%CE%B1%CF%86%CE%B9%CE%BA%CF%8C-%CF%86%CE%B9%CE%BD%CE%AC%CE%BB%CE%B5-%CE%BC%CE%B5-%CF%84%CE%BF%CE%BD-18%CF%87%CF%81%CE%BF%CE%BD%CE%BF-%CE%B1%CF%81%CE%B9%CF%83%CF%84/"
APOLLON_NEWS = "https://apollonwaterpolo.gr/news/"

JADRAN_ARRIVALS = "https://vkjadransplit.hr/2026/08/27/busic-pozaric-penava-i-katunaric-su-novi-igraci-jadrana/"
JADRAN_ROSTER = "https://vkjadransplit.hr/2026/08/26/seniori-krenuli-s-pripremama-za-novu-sezonu/"
JADRAN_EXITS = "https://sport.hrt.hr/vise-sportova/splitski-jadran-napustaju-bijac-fatovic-marinic-kragic-12808240"

CAL_AMOROSO = "https://calbears.com/news/2026/5/22/womens-water-polo-cal-signs-chiara-amoroso-as-transfer-addition.aspx"
STANFORD_DOYLE = "https://gostanford.com/news/2026/06/9/doyle-headed-to-the-farm"


def _row(gender, player, fr, to, date, source, url, tier="club_official",
         confidence=.99, note="", kind="confirmed", season="2026-2027"):
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
        "season": season,
    }


WAVE5_TRANSFER_SIGNALS = [
    # Apollon Smyrnis — official club announcements. Renewals are deliberately omitted.
    _row("Men", "Kostas Mourikis", "Panionios", "Apollon Smyrnis", "2026-07-14",
         "Apollon Smyrnis", APOLLON_MOURIKIS, confidence=.98,
         note="Official Apollon signing for 2026-27; Panionios had announced the end of its spell with Mourikis earlier in the summer."),
    _row("Men", "Alkis Lorantos", "Taverny SN95", "Apollon Smyrnis", "2026-08-04",
         "Apollon Smyrnis", APOLLON_LORANTOS,
         note="Official signing. Apollon's announcement states Lorantos returns to Greece after two seasons at Taverny SN95."),
    _row("Men", "Dimitris Berdes", "Palaio Faliro", "Apollon Smyrnis", "2026-08-13",
         "Apollon Smyrnis", APOLLON_BERDES,
         note="Official signing. The club biography states the goalkeeper moved to Palaio Faliro at age 13 and already had three Water Polo League seasons there."),
    _row("Men", "Giannis Kechalaris", "PAOK", "Apollon Smyrnis", "2026-08-18",
         "Apollon Smyrnis", APOLLON_KECHALARIS, confidence=.98,
         note="Official Apollon signing; Kechalaris captained PAOK during the 2025-26 season."),
    _row("Men", "Stavros Zouzounis", "NO Chania", "Apollon Smyrnis", "2026-08-20",
         "Apollon Smyrnis", APOLLON_ZOUZOUNIS,
         note="Official signing. Apollon identifies Zouzounis as a product of NO Chania and calls this the close of its summer transfer reinforcement."),

    # Jadran Split — official current roster / reinforcement announcements.
    _row("Men", "Mate Anic", "Zadar 1952", "Jadran Split", "2026-07-10",
         "VK Jadran Split", JADRAN_ARRIVALS,
         note="Jadran's Aug. 27 official announcement confirms Anic among the previously completed reinforcements; his Zadar exit was public in July."),
    _row("Men", "Lukas Seman", "Primorje Rijeka", "Jadran Split", "2026-07-10",
         "VK Jadran Split", JADRAN_ARRIVALS, confidence=.98,
         note="Jadran officially confirms Seman among its first three reinforcements; specialist reporting identifies Primorje Rijeka as his previous club."),
    _row("Men", "Jan Busic", "", "Jadran Split", "2026-08-27",
         "VK Jadran Split", JADRAN_ARRIVALS,
         note="Official Jadran reinforcement. The club describes years at Mladost plus one season at Medvescak, so the immediate previous club is intentionally left blank."),
    _row("Men", "Roko Pozaric", "Princeton", "Jadran Split", "2026-08-27",
         "VK Jadran Split", JADRAN_ARRIVALS,
         note="Official Jadran signing after four collegiate seasons at Princeton."),
    _row("Men", "Luka Penava", "Mornar Split", "Jadran Split", "2026-08-27",
         "VK Jadran Split", JADRAN_ARRIVALS,
         note="Official Jadran signing; the club explicitly states Penava arrives from Mornar."),
    _row("Men", "Duje Katunaric", "Mornar Split", "Jadran Split", "2026-08-27",
         "VK Jadran Split", JADRAN_ARRIVALS, confidence=.98,
         note="Official Jadran signing; the club states Katunaric developed at Mornar and had begun gaining senior experience there."),

    # Jadran departures — HRT reports that Jadran itself confirmed all seven exits.
    _row("Men", "Antonio Duzevic", "Jadran Split", "", "2026-07-09",
         "HRT / VK Jadran Split confirmation", JADRAN_EXITS, tier="club_confirmed_media", confidence=.97,
         note="Jadran confirmed the roster exit; no destination is asserted."),
    _row("Men", "Martin Celar", "Jadran Split", "", "2026-07-09",
         "HRT / VK Jadran Split confirmation", JADRAN_EXITS, tier="club_confirmed_media", confidence=.97,
         note="Jadran confirmed the roster exit; no destination is asserted."),
    _row("Men", "Duje Djula", "Jadran Split", "Solaris Sibenik", "2026-07-09",
         "HRT / VK Jadran Split confirmation", JADRAN_EXITS, tier="club_confirmed_media", confidence=.97,
         note="HRT reports Jadran's confirmed exit and states Djula signed for Solaris Sibenik."),

    # NCAA women's water polo — next competition campaign is 2027.
    _row("Women", "Chiara Amoroso", "Long Beach State", "California", "2026-05-22",
         "California Golden Bears Athletics", CAL_AMOROSO, tier="team_official", confidence=.99,
         note="Official Cal transfer announcement after the 2026 NCAA season; recorded under the next NCAA competition campaign.",
         season="2027"),
    _row("Women", "Gabrielle Doyle", "Hawai'i", "Stanford", "2026-06-09",
         "Stanford Athletics", STANFORD_DOYLE, tier="team_official", confidence=.99,
         note="Stanford explicitly announced Doyle as a transfer for the 2027 campaign.", season="2027"),
]
