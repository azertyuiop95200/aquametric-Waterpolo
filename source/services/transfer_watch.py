from sqlalchemy import select
from models import SourceWatch, TransferSignal, MatchResearchTarget

TRANSFER_SEASON = "2026-2027"

# Trust policy:
# primary / federation_confirmed = federation, league or official club evidence
# club_public = official public club social account
# media_confirmed = specialised media explicitly labels the move confirmed
# media / media_rumour = reporting or rumour only; never upgrades a roster by itself
# discovery_only = forum/community signal; research lead only
SOURCE_WATCHES = [
    ("FFN extraNat — Elite water polo", "federation", "web", "France — Elite clubs", "https://www.extranat.fr/waterpolo/", "primary", 6, "Official fixtures, match sheets, live scoring/statistics when published."),
    ("FFN — water-polo transfer rules", "federation", "web", "France — transfers and licences", "https://www.ffnatation.fr/reglements-du-water-polo", "primary", 12, "Official French regulations, including the transfer-right annex and 2026-27 competition rules."),
    ("RFEN — water polo", "federation", "web", "Spain", "https://rfen.es/especialidades/waterpolo/", "primary", 12, "Official Spanish federation competition and roster context."),
    ("LEWaterpolo — Spanish leagues", "league", "web", "Spain — División de Honor", "https://lewaterpolo.com/", "primary", 12, "League match, roster and club context for Spain; cross-check transfer claims with club/RFEN evidence."),
    ("Waterpolo.nl — confirmed transfer overview", "federation_media", "web", "Netherlands and Dutch players abroad", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "primary", 12, "KNZB editorial overview explicitly listing confirmed 2026-27 transfers for women and men."),
    ("European Aquatics — transfer regulations", "federation", "web", "Europe — ITC rules", "https://europeanaquatics.org/wp-content/uploads/2024/10/WATER-POLO-TRANSFER-REGULATIONS.pdf", "primary", 24, "Official ITC rules. Useful to distinguish a media announcement from formal international eligibility."),
    ("European Aquatics — schedule/results", "federation", "web", "Europe", "https://europeanaquatics.org/events/schedule-and-results/", "primary", 6, "Official European calendar/results and competition rosters when published."),
    ("World Aquatics — competitions", "federation", "web", "International", "https://www.worldaquatics.com/competitions", "primary", 6, "Official competition pages, reports, videos and event rosters."),
    ("USA Water Polo — news", "federation", "web", "United States", "https://usawaterpolo.org/", "primary", 12, "Official USA Water Polo news and national-team/college context."),
    ("Waterpolo 360 — confirmed transfers", "media", "web", "International transfers", "https://waterpolo360news.com/confirmed-transfers/", "media_confirmed", 6, "High-value transfer discovery source; upgrade with club/federation corroboration when available."),
    ("Waterpolo 360 — transfer hub", "media", "web", "International transfers and rumours", "https://waterpolo360news.com/water-polo-confirmed-transfers-and-gossip/", "media", 6, "Confirmed deals and rumours remain separate evidence states."),
    ("Waterpolo 360 — Instagram", "media_social", "instagram", "International water polo", "https://www.instagram.com/waterpolo360news/", "media", 6, "Fast public social signal from the specialist outlet; article/club evidence remains preferred."),
    ("Total Waterpolo — transfers", "media", "web", "International transfers", "https://total-waterpolo.com/water-polo-transfers/", "media_confirmed", 6, "Transfer timeline with explicit confirmed/rumour labels."),
    ("Total Waterpolo — Instagram", "media_social", "instagram", "International water polo", "https://www.instagram.com/total_waterpolo/", "media", 6, "Public specialist-media social feed for rapid discovery; confirm before roster updates."),
    ("Total Waterpolo — Facebook", "media_social", "facebook", "International water polo", "https://www.facebook.com/totalwaterpolonews", "media", 12, "Public specialist-media social feed; discovery/corroboration rather than registration evidence."),
    ("SO POLO — public social", "media_social", "instagram", "France water polo", "https://www.instagram.com/sopolo.news/", "media", 6, "French water-polo news signal; media reporting, not an official registration source."),
    ("Water Polo Exchange — transfer portal discussions", "community", "web", "USA college water polo", "https://waterpoloexchange.com/latest", "discovery_only", 12, "Community/forum signal only. Never marks a transfer confirmed without official school/team evidence."),
    ("Granville Water Polo — official site", "club_official", "web", "Granville Water Polo", "https://www.granvillewaterpolo.com/", "primary", 12, "Club roster, schedules, announcements and links to public social pages."),
    ("Granville Water Polo — Facebook", "club_social", "facebook", "Granville Water Polo", "https://www.facebook.com/GRANVILLEWATERPOLO/", "club_public", 6, "Public official club posts; confirm roster changes with official club/FFN evidence when possible."),
    ("Granville Water Polo — Instagram", "club_social", "instagram", "Granville Water Polo", "https://www.instagram.com/granvillewaterpolo/", "club_public", 6, "Public official club account; useful for fast signing/departure announcements."),
    ("PAOK — women official news", "club_official", "web", "PAOK women", "https://acpaok.gr/news/womens-polo/", "primary", 12, "Official club announcements for the women's roster."),
    ("PAOK — men official news", "club_official", "web", "PAOK men", "https://acpaok.gr/news/mens-polo/", "primary", 12, "Official club announcements for the men's roster."),
    ("PAOK — Instagram", "club_social", "instagram", "PAOK water polo", "https://www.instagram.com/acpaok/", "club_public", 6, "Official multisport club social account; use as club-public evidence and cross-check the website when available."),
    ("Pallanuoto Trieste — official news", "club_official", "web", "Pallanuoto Trieste", "https://www.pallanuototrieste.com/it/news/", "primary", 12, "Official club roster and signing announcements for women and men."),
    ("Pallanuoto Trieste — Instagram", "club_social", "instagram", "Pallanuoto Trieste", "https://www.instagram.com/pallanuoto_trieste/", "club_public", 6, "Official club social feed for fast roster signals."),
    ("Grand Nancy — official site/social hub", "club_official", "web", "Grand Nancy Aquatique Club", "https://www.grandnancyaquatiqueclub.com/contact/", "primary", 12, "Official site exposes public social links."),
    ("Taverny SN95 — official site", "club_official", "web", "Taverny Sports Nautiques 95", "https://tsn95.fr/", "primary", 12, "Official club information and public match posts."),
]

# gender, player, from, to, signal type, published date, source, url, tier, confidence, note
TRANSFER_SIGNALS = [
    # Women — specialist media / official club evidence
    ("Women", "Izabella Chiappini", "", "Sori Pool Beach", "confirmed", "2026-08-05", "Waterpolo 360", "https://waterpolo360news.com/water-polo-confirmed-transfers-and-gossip/", "media_confirmed", .92, "Major signing for newly promoted Italian side."),
    ("Women", "Elena Ruiz", "", "CN Atlètic-Barceloneta", "confirmed", "2026-08-04", "Waterpolo 360", "https://waterpolo360news.com/water-polo-confirmed-transfers-and-gossip/", "media_confirmed", .92, "Spain international move signal."),
    ("Women", "Maryn Dempsey", "", "CN Atlètic-Barceloneta", "confirmed", "2026-07-22", "Waterpolo 360", "https://waterpolo360news.com/confirmed-transfers/", "media_confirmed", .92, "USA attacker signed by CNAB."),
    ("Women", "Anna Pearson", "", "CE Mediterrani", "confirmed", "2026-07-21", "Waterpolo 360", "https://waterpolo360news.com/confirmed-transfers/", "media_confirmed", .92, "Women's first-team signing."),
    ("Women", "Emma Lineback", "", "CE Mediterrani", "confirmed", "2026-07-21", "Waterpolo 360", "https://waterpolo360news.com/confirmed-transfers/", "media_confirmed", .92, "Women's first-team signing."),
    ("Women", "Isabel Williams", "CN Sabadell", "Rapallo", "confirmed", "2026-07-17", "Waterpolo 360", "https://waterpolo360news.com/confirmed-transfers/", "media_confirmed", .92, "USA goalkeeper move."),
    ("Women", "Kata Hajdu", "UVSE", "Olympiacos", "confirmed", "2026-07-13", "Waterpolo 360", "https://waterpolo360news.com/confirmed-transfers/", "media_confirmed", .92, "Hungary international move."),
    ("Women", "Nikoleta Eleftheriadou", "", "Vouliagmeni", "confirmed", "2026-07-11", "Waterpolo 360", "https://waterpolo360news.com/confirmed-transfers/", "media_confirmed", .92, "High-profile Greek signing."),
    ("Women", "Sinia Plotz", "", "SIS Roma", "confirmed", "2026-07-08", "Waterpolo 360", "https://waterpolo360news.com/confirmed-transfers/", "media_confirmed", .92, "Women's roster reinforcement."),
    ("Women", "Iva Rozic", "", "SIS Roma", "confirmed", "2026-07-08", "Waterpolo 360", "https://waterpolo360news.com/confirmed-transfers/", "media_confirmed", .92, "Croatian U20 standout joins SIS Roma."),
    ("Women", "Sofia Giustini", "", "Pallanuoto Trieste", "confirmed", "2026-07-01", "Waterpolo 360", "https://waterpolo360news.com/confirmed-transfers/", "media_confirmed", .92, "Italy international signing."),
    ("Women", "Paola Di Maria", "", "Pallanuoto Trieste", "confirmed", "2026-08-25", "Pallanuoto Trieste", "https://www.pallanuototrieste.com/it/news/articolo/si-riparte-dall-ausonia-la-pallanuoto-trieste-femminile-e-pronta-a-scendere-in-campo-per-la-stagione-2026-27", "club_official", .99, "Official 2026-27 squad presentation lists Di Maria among five summer additions."),
    ("Women", "Malika Gaia Bovo", "", "Pallanuoto Trieste", "confirmed", "2026-08-25", "Pallanuoto Trieste", "https://www.pallanuototrieste.com/it/news/articolo/si-riparte-dall-ausonia-la-pallanuoto-trieste-femminile-e-pronta-a-scendere-in-campo-per-la-stagione-2026-27", "club_official", .99, "Official 2026-27 squad presentation lists Bovo among five summer additions."),
    ("Women", "Anna Mamoglou", "", "PAOK", "confirmed", "2026-08-07", "AC PAOK", "https://acpaok.gr/%CE%AC%CE%BD%CE%BD%CE%B1-%CE%BC%CE%B1%CE%BC%CF%8C%CE%B3%CE%BB%CE%BF%CF%85-%CE%BC%CE%AF%CE%B1-%CE%BC%CE%B5%CF%84%CE%B1%CE%B3%CF%81%CE%B1%CF%86%CE%AE-%CE%B5%CE%BC%CF%80%CE%B5%CE%B9%CF%81%CE%AF%CE%B1/", "club_official", .99, "Official PAOK announcement for the 2026-27 season."),
    ("Women", "Margarita Bitsakou", "", "PAOK", "confirmed", "2026-07-29", "AC PAOK", "https://acpaok.gr/%CF%83%CF%80%CE%BF%CF%85%CE%B4%CE%B1%CE%AF%CE%B1-%CE%B5%CE%BD%CE%AF%CF%83%CF%87%CF%85%CF%83%CE%B7-%CF%83%CF%84%CE%BF%CE%BD-%CF%86%CE%BF%CF%85%CE%BD%CF%84%CE%B1%CF%81%CE%B9%CF%83%CF%84%CF%8C-%CE%BC/", "club_official", .99, "Official PAOK announcement for the 2026-27 season."),
    ("Women", "Kamilla Farago", "UVSE", "CN Mataró", "rumour", "2026-07-08", "Waterpolo 360", "https://waterpolo360news.com/", "media_rumour", .72, "Newer media report points to Mataró. Kept as a rumour until club/federation evidence is captured."),

    # Women — KNZB/Waterpolo.nl confirmed 2026-27 overview
    ("Women", "Indy Waltman", "ZPB H&L Productions", "GZC Donk", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Women", "Jolijn Joor", "ZVL-1886", "GZC Donk", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Women", "Linde Haksteen", "Polar Bears", "GZC Donk", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Women", "Anne Heidenrijk", "ZPC Amersfoort", "Het Ravijn", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Women", "Silvanne Slot", "ZV De Zaan", "ZPB H&L Productions", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Women", "Sam Jutte", "UZSC", "ZV De Zaan", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Women", "Melissa Schipper", "ZV De Ham ZC", "ZV De Zaan", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Women", "Anne Klein Langenhorst", "UZSC", "ZV De Zaan", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Women", "Nina van der Vorst", "PSV", "Het Ravijn", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Women", "Cynthia Mulder", "UZSC", "ZVL-1886", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Women", "Saloua Maafi", "UZSC", "ZVL-1886", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Women", "Lotte van Wingerden", "UZSC", "ZVL-1886", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Women", "Lisa Schep", "PSV", "ZVL-1886", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Women", "Maxine Schaap", "SIS Roma", "ZV De Zaan", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Return to the Netherlands, confirmed by the KNZB overview."),
    ("Women", "Britt van den Dobbelsteen", "Olympiakos", "ZV De Zaan", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Return to the Netherlands, confirmed by the KNZB overview."),
    ("Women", "Sanne Keijzer", "Arizona State University", "ZPB H&L Productions", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Return to the Netherlands, confirmed by the KNZB overview."),
    ("Women", "Vivian Sevenich", "L'Ekipe Orizzonte", "ZV De Zaan", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Return to the Netherlands, confirmed by the KNZB overview."),
    ("Women", "Tatum van der Elst", "Polar Bears", "Arizona State University", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Move abroad listed in the KNZB transfer overview."),
    ("Women", "Kiara Heerink", "Polar Bears", "Arizona State University", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Move abroad listed in the KNZB transfer overview."),
    ("Women", "Jill Oort", "Polar Bears", "Club Natació Rubí", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Move abroad listed in the KNZB transfer overview."),
    ("Women", "Maartje Keuning", "GZC Donk", "CN Sabadell", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Move abroad listed in the KNZB transfer overview."),
    ("Women", "Sarah Buis", "GZC Donk", "CN Sant Andreu", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Move abroad listed in the KNZB transfer overview."),
    ("Women", "Bente Rogge", "ZV De Zaan", "Vouliagmeni", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Move abroad listed in the KNZB transfer overview."),
    ("Women", "Esmee Ouwens", "GZC Donk", "California State University Long Beach", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Move abroad listed in the KNZB transfer overview."),
    ("Women", "Noa de Vries", "FTC Telekom", "Pallanuoto Trieste", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Transfer between foreign clubs listed in the KNZB overview; later corroborated by Trieste's official squad presentation."),
    ("Women", "Fleurien Bosveld", "Alimos NAC", "SIS Roma", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Transfer between foreign clubs listed in the KNZB overview."),
    ("Women", "Nikki Meijer", "Smile Cosenza Pallanuoto", "Rapallo Pallanuoto", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Transfer between foreign clubs listed in the KNZB overview."),

    # Men — KNZB/Waterpolo.nl confirmed 2026-27 overview
    ("Men", "Roko Mujan", "ZPC Amersfoort", "ZPB H&L Productions", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Men", "George Athymaritis", "UZSC", "SWOL 1894", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Men", "Dynand Muller", "ZPC Amersfoort", "OZ&PC", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Men", "Alex Horvath", "EZC", "OZ&PC", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Men", "Ruben van Vierzen", "ZV De Ham ZC", "ZV De Zaan", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Men", "Paul Kerstens", "ESTA", "SWOL 1894", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Men", "Pim Hageman", "Het Ravijn", "OZ&PC", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Listed in the KNZB transfer overview for 2026-27."),
    ("Men", "Mitchell Budding", "HZC De Robben", "ZPC Amersfoort", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Return listed in the updated KNZB transfer overview."),
    ("Men", "Jorrit van der Weijden", "GZC Donk", "PAOK", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .98, "Move to PAOK listed by KNZB and subsequently announced by PAOK."),
    ("Men", "Daan Bakker", "ZV De Zaan", "Montpellier Water-Polo", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Move to the French league listed in the KNZB transfer overview."),
    ("Men", "Bas Grummer", "ZVL-1886", "ASC Duisburg", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Move abroad listed in the KNZB transfer overview."),
    ("Men", "Fabio Jukic", "PSV", "IREN Genova Quinto 1921", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Move abroad listed in the KNZB transfer overview."),
    ("Men", "Stan Schuring", "Orange Coast College", "SWOL 1894", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Return to the Netherlands listed in the KNZB overview."),
    ("Men", "Jeroen Rouwenhorst", "Rari Nantes Florentia", "AN Brescia", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Transfer between foreign clubs listed in the KNZB overview."),
    ("Men", "Marnick Snel", "VK Primorje", "CC Ortigia", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Transfer between foreign clubs listed in the KNZB overview."),
    ("Men", "Tim de Mey", "Rari Nantes Florentia", "Douaisis Agglo Water-Polo", "confirmed", "2026-07-20", "Waterpolo.nl / KNZB", "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie", "federation_confirmed", .97, "Move to the French league listed in the KNZB transfer overview."),

    # Men — current international specialist-media confirmations
    ("Men", "Angelos Foskolos", "", "CN Posillipo", "confirmed", "2026-08-08", "Waterpolo 360", "https://waterpolo360news.com/water-polo-confirmed-transfers-and-gossip/", "media_confirmed", .92, "Specialist outlet reports Posillipo signing the Greek centre-forward."),
    ("Men", "Nemanja Ubovic", "", "Primorac Kotor", "confirmed", "2026-08-02", "Waterpolo 360", "https://waterpolo360news.com/confirmed-transfers/", "media_confirmed", .92, "Olympic champion joins Primorac Kotor."),
    ("Men", "Nika Shushiashvili", "BVSC", "Novi Beograd", "confirmed", "2026-07-30", "Waterpolo 360", "https://waterpolo360news.com/confirmed-transfers/", "media_confirmed", .92, "Return to Novi Beograd after BVSC spell."),
    ("Men", "Lukas Durik", "Pro Recco", "Jadran Herceg Novi", "confirmed", "2026-07-30", "Waterpolo 360", "https://waterpolo360news.com/confirmed-transfers/", "media_confirmed", .92, "Move after two years at Pro Recco."),
    ("Men", "Nicolas Saveljic", "", "Dinamo Bucharest", "confirmed", "2026-07-29", "Waterpolo 360", "https://waterpolo360news.com/confirmed-transfers/", "media_confirmed", .92, "USA international signing."),
    ("Men", "Jerko Marinic Kragic", "", "Steaua Bucharest", "confirmed", "2026-07-28", "Waterpolo 360", "https://waterpolo360news.com/confirmed-transfers/", "media_confirmed", .92, "Croatian international completes return to Steaua."),
    ("Men", "Joao Pedro", "", "Pallanuoto Trieste", "confirmed", "2026-07-17", "Waterpolo 360", "https://waterpolo360news.com/confirmed-transfers/", "media_confirmed", .92, "Trieste signing reported as a two-year deal."),
    ("Men", "Francesco Di Fulvio", "", "CN Atlètic-Barceloneta", "confirmed", "2026-07-16", "Total Waterpolo", "https://total-waterpolo.com/water-polo-transfers/", "media_confirmed", .92, "Listed as confirmed on Total Waterpolo's 2026 transfer timeline."),
    ("Men", "Vincenzo Dolce", "", "Panathinaikos", "confirmed", "2026-07-13", "Total Waterpolo", "https://total-waterpolo.com/water-polo-transfers/", "media_confirmed", .92, "Listed as confirmed on Total Waterpolo's 2026 transfer timeline."),
    ("Men", "Tommaso Gianazza", "", "Pro Recco", "confirmed", "2026-07-13", "Total Waterpolo", "https://total-waterpolo.com/water-polo-transfers/", "media_confirmed", .92, "Listed as confirmed on Total Waterpolo's 2026 transfer timeline."),
    ("Men", "Marko Bijac", "", "Pro Recco", "confirmed", "2026-07-11", "Total Waterpolo", "https://total-waterpolo.com/water-polo-transfers/", "media_confirmed", .92, "Listed as confirmed on Total Waterpolo's 2026 transfer timeline."),
    ("Men", "Toni Popadic", "", "Jadran Split", "confirmed", "2026-07-07", "Total Waterpolo", "https://total-waterpolo.com/water-polo-transfers/", "media_confirmed", .92, "Listed as confirmed on Total Waterpolo's 2026 transfer timeline."),
    ("Men", "Gergo Zalanki", "", "Pro Recco", "confirmed", "2026-07-03", "Total Waterpolo", "https://total-waterpolo.com/water-polo-transfers/", "media_confirmed", .92, "Listed as confirmed on Total Waterpolo's 2026 transfer timeline."),
    ("Men", "Loren Fatovic", "", "Olympiacos", "confirmed", "2026-07-01", "Total Waterpolo", "https://total-waterpolo.com/water-polo-transfers/", "media_confirmed", .92, "Listed as confirmed on Total Waterpolo's 2026 transfer timeline."),
    ("Men", "Konstantin Kharkov", "", "Olympiacos", "confirmed", "2026-06-29", "Total Waterpolo", "https://total-waterpolo.com/water-polo-transfers/", "media_confirmed", .92, "Listed as confirmed on Total Waterpolo's 2026 transfer timeline."),
    ("Men", "Gergely Burian", "", "VK Jug", "confirmed", "2026-06-23", "Total Waterpolo", "https://total-waterpolo.com/water-polo-transfers/", "media_confirmed", .92, "Listed as confirmed on Total Waterpolo's 2026 transfer timeline."),
    ("Men", "Vladan Spaic", "", "Vouliagmeni", "confirmed", "2026-06-20", "Total Waterpolo", "https://total-waterpolo.com/water-polo-transfers/", "media_confirmed", .92, "Listed as confirmed on Total Waterpolo's 2026 transfer timeline."),
    ("Men", "Dmitri Kholod", "", "Oradea", "confirmed", "2026-06-18", "Total Waterpolo", "https://total-waterpolo.com/water-polo-transfers/", "media_confirmed", .92, "Listed as confirmed on Total Waterpolo's 2026 transfer timeline."),
    ("Men", "Konstantinos Kakaris", "", "Ferencvaros", "confirmed", "2026-06-17", "Total Waterpolo", "https://total-waterpolo.com/water-polo-transfers/", "media_confirmed", .92, "Listed as confirmed on Total Waterpolo's 2026 transfer timeline."),
    ("Men", "Marko Vavic", "", "Apollon Smyrnis", "confirmed", "2026-06-11", "Total Waterpolo", "https://total-waterpolo.com/water-polo-transfers/", "media_confirmed", .92, "Listed as confirmed on Total Waterpolo's 2026 transfer timeline."),
    ("Men", "Djordje Lazic", "", "Panionios", "confirmed", "2026-06-08", "Total Waterpolo", "https://total-waterpolo.com/water-polo-transfers/", "media_confirmed", .92, "Listed as confirmed on Total Waterpolo's 2026 transfer timeline."),
    ("Men", "Nikola Kojic", "", "Novi Beograd", "confirmed", "2026-06-06", "Total Waterpolo", "https://total-waterpolo.com/water-polo-transfers/", "media_confirmed", .92, "Listed as confirmed on Total Waterpolo's 2026 transfer timeline."),
    ("Men", "Dimitrije Risticevic", "", "Panionios", "confirmed", "2026-06-06", "Total Waterpolo", "https://total-waterpolo.com/water-polo-transfers/", "media_confirmed", .92, "Listed as confirmed on Total Waterpolo's 2026 transfer timeline."),
    ("Men", "Toni Nemet", "", "ENKA Istanbul", "rumour", "2026-08-20", "Waterpolo 360", "https://waterpolo360news.com/water-polo-transfers-and-gossip/mens-transfers-and-gossip/", "media_rumour", .58, "Rumour only; keep isolated until official club/federation evidence appears."),
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
    if addition in current:
        return current
    return f"{current} {addition}".strip()


def seed_transfer_watch(db):
    # Upsert watches so the monitored-source catalogue can evolve between releases.
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

    # Upsert signals. A later signal can correct missing from-club/source details without duplicating the row.
    for gender, player, fr, to, kind, date, sname, url, tier, conf, note in TRANSFER_SIGNALS:
        signal = db.scalar(select(TransferSignal).where(
            TransferSignal.player_name == player,
            TransferSignal.to_team == to,
            TransferSignal.published_date == date,
        ))
        if not signal:
            signal = TransferSignal(
                player_name=player,
                gender=gender,
                from_team=fr,
                to_team=to,
                signal_type=kind,
                season=TRANSFER_SEASON,
                published_date=date,
                source_name=sname,
                source_url=url,
                source_tier=tier,
                confidence_score=conf,
                note=note,
            )
            db.add(signal)
        else:
            signal.gender = gender
            signal.from_team = fr or signal.from_team
            signal.to_team = to
            signal.signal_type = kind
            signal.season = TRANSFER_SEASON
            signal.source_name = sname
            signal.source_url = url
            signal.source_tier = tier
            signal.confidence_score = conf
            signal.note = note

        # Keep an audit trail but remove an older contradictory rumour from the active board.
        older_rumours = db.scalars(select(TransferSignal).where(
            TransferSignal.player_name == player,
            TransferSignal.season == TRANSFER_SEASON,
            TransferSignal.signal_type == "rumour",
        )).all()
        for older in older_rumours:
            if older is signal or older.to_team == to:
                continue
            if not older.published_date or older.published_date <= date:
                older.signal_type = "superseded"
                older.note = _append_note(older.note, f"Superseded by newer evidence pointing to {to} ({sname}, {date}).")

    for key, comp, season, a, b, date, score, src, video, status, priority, note in MATCH_TARGETS:
        target = db.scalar(select(MatchResearchTarget).where(MatchResearchTarget.external_key == key))
        if not target:
            db.add(MatchResearchTarget(external_key=key, competition=comp, season=season, team_a=a, team_b=b, event_date=date, score_text=score, source_url=src, video_url=video, research_status=status, priority=priority, note=note))
    db.commit()
