"""Verified French 2026-27 mercato additions and source upgrades.

French clubs often announce roster changes first on public social feeds. These rows
use club-public signals when the wording is explicit and federation/national-team
context when it independently confirms the player's new club.
"""

MWP_PUBLIC = "https://www.boutiquemontpellierwaterpolo.com/"
FRANCE_TEAM = "https://www.equipedefrance.com/article/jeux-mediterraneens-de-tarente-2026-decouvrez-la-delegation-francaise-engagee"
SPAIC_URL = "https://waterpolo360news.com/vouliagmeni-strengthen-centre-forward-position-with-vladan-spaic-signing/"


def _row(player, fr, to, date, source, url, tier="club_public", confidence=.95,
         note="", kind="confirmed"):
    return {
        "gender": "Men",
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


WAVE4_FRANCE_SIGNALS = [
    _row("Lylian Michel", "CN Marseille", "Montpellier Water-Polo", "2026-08-13",
         "Montpellier Water-Polo — public club feed", MWP_PUBLIC, confidence=.97,
         note="Montpellier's public club feed explicitly announces Michel as a new signing from Marseille; observation current by 13 Aug 2026."),
    _row("Ilija Mustur", "Montpellier Water-Polo", "", "2026-08-13",
         "Montpellier Water-Polo — public club feed", MWP_PUBLIC, confidence=.97,
         note="Club farewell confirms Mustur leaves after 14 seasons; destination not asserted."),
    _row("Charly Ben Romdhane", "Montpellier Water-Polo", "", "2026-08-13",
         "Montpellier Water-Polo — public club feed", MWP_PUBLIC, confidence=.97,
         note="Club farewell confirms Ben Romdhane leaves after four seasons; destination not asserted."),
    _row("Pál Antal Irmes", "Montpellier Water-Polo", "", "2026-08-13",
         "Montpellier Water-Polo — public club feed", MWP_PUBLIC, confidence=.97,
         note="Club farewell confirms Irmes leaves after two seasons; destination not asserted."),
    _row("Denis Do Carmo", "Rari Nantes Salerno", "Sète Natation", "2026-08-06",
         "Équipe de France / Salerno roster cross-check", FRANCE_TEAM, "national_team_current", .97,
         "The current French Mediterranean Games delegation lists Do Carmo at Sète; Salerno's 2025-26 official roster identifies him as arriving there from Sète."),
    _row("Vladan Spaic", "CN Marseille", "Vouliagmeni", "2026-06-20",
         "Waterpolo 360 / Vouliagmeni announcement", SPAIC_URL, "media_confirmed", .97,
         "Confirmed signing article explicitly states Spaic arrives from CN Marseille."),
]
