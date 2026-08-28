"""Curated 2026-27 water-polo transfer / roster-change expansion.

This module deliberately separates broad market coverage from the core seed logic.
Rows may be exact transfers, arrivals with unknown previous club, or roster exits
with unknown destination. Evidence state reflects the source strength; unknown
fields stay blank rather than being guessed.
"""

TRANSFER_SEASON = "2026-2027"

KNZB_URL = "https://www.waterpolo.nl/nieuws/transferoverzicht-wie-speelt-waar-komend-seizoen/?type=Eredivisie"
OA_MEN_URL = "https://www.oasport.it/2026/07/pallanuoto-come-sono-cambiate-le-squadre-di-a1-i-colpi-di-mercato-e-le-partenze-per-la-stagione-2026-2027/"
OA_WOMEN_URL = "https://www.oasport.it/2026/07/pallanuoto-femminile-come-sono-cambiate-le-squadre-di-a1-i-colpi-di-mercato-e-le-partenze-per-la-stagione-2026-2027/"
HA10_AUG_URL = "https://www.ha10.es/agosto-2026.html"
WP360_CONFIRMED = "https://waterpolo360news.com/confirmed-transfers/"


def _row(gender, player, fr, to, date, source, url, tier, confidence, note="", kind="reported"):
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


# KNZB page is explicitly a confirmed 2026-27 transfer overview and was updated
# on 25 August 2026. The stop/lower-level rows are roster changes, not signings.
KNZB_CONFIRMED = [
    ("Women", "Dian Scholten", "Het Ravijn, dames 3", "Het Ravijn"),
    ("Women", "Renée de Kleer", "Tenerife Echeyde", "ZPB H&L Productions"),
    ("Women", "Lotte Boxsem", "California State University", "LUC Métropole Waterpolo"),
    ("Women", "Storm Willemsen", "Rapallo Pallanuoto", "Ekipe Orizzonte"),
    ("Men", "Alexandros Ioannou", "Limassol Nautical Club", "Polar Bears"),
    ("Men", "Liam Sterne", "Ottawa Titans Water Polo Club", "ZPC Amersfoort"),
    ("Men", "Jackson Taylor", "Ottawa Titans Water Polo Club", "ZPC Amersfoort"),
]

KNZB_ROSTER_EXITS = [
    ("Women", "Anne Collas", "ZV De Ham ZC", "", "Retirement/exit from the top level."),
    ("Women", "Noha Zwiers", "ZV De Ham ZC", "", "Retirement/exit from the top level."),
    ("Women", "Anouk Bergsma", "GZC Donk", "GZC Donk, lower level", "Moves to a lower level at the same club."),
    ("Women", "Janieke Oosting", "ZVL-1886", "", "Retirement/exit from the top level."),
    ("Women", "Roline Schuijt", "ZV De Zaan", "", "Retirement/exit from the top level."),
    ("Women", "Yara Maaskant", "ZPB H&L Productions", "", "Retirement/exit from the top level."),
    ("Women", "Isa van der Windt", "ZPB H&L Productions", "", "Retirement/exit from the top level."),
    ("Women", "Isis Keijzer", "UZSC", "UZSC, dames 3", "Moves to a lower level at the same club."),
    ("Men", "Kjeld Veenhuis", "GZC Donk", "", "Retirement/exit from the top level."),
]

# OA Sport's 28 July A1 men roundup explicitly describes these arrivals/departures.
# We keep these as media-reported until a club/federation source upgrades the row.
ITALY_MEN_REPORTED = [
    ("Andrea Fondelli", "Pro Recco", "", "Retirement reported in the A1 market roundup."),
    ("Tommaso Negri", "Pro Recco", "", "Retirement reported in the A1 market roundup."),
    ("Lorenzo De Marchi", "Pro Recco", "", "Roster departure; destination not stated."),
    ("Luc Pavillard", "Pro Recco", "", "Roster departure; destination not stated."),
    ("Alessandro Carnesecchi", "CC Ortigia", "Pro Recco", "Arrival reported by OA Sport."),
    ("Mattia Giorgio Di Corato", "Roma Vis Nova", "Pro Recco", "Arrival reported by OA Sport."),
    ("Ante Viskovic", "AN Brescia", "", "Roster departure; destination not stated."),
    ("Alessandro Balzarini", "AN Brescia", "", "Brescia departure; Posillipo was described as likely, so destination is intentionally left blank here."),
    ("Nicolò Casanova", "AN Brescia", "Training Academy Olympic Roma", "Arrival at Olympic Roma reported in the roundup."),
    ("Oliver Leinweber", "", "AN Brescia", "Arrival reported; previous club not stated in this source."),
    ("Antonio De Simone", "Rari Nantes Salerno", "AN Brescia", "Arrival reported by OA Sport."),
    ("Valerio Rizzo", "Rari Nantes Savona", "", "Roster departure; destination not stated."),
    ("Pietro Figlioli", "Rari Nantes Savona", "Chiavari Nuoto", "Move reported by OA Sport."),
    ("Luca Damonte", "Rari Nantes Savona", "Pallanuoto Trieste", "Move reported by OA Sport."),
    ("Mario Guidi", "Rari Nantes Savona", "Chiavari Nuoto", "Move reported by OA Sport."),
    ("Lorenzo Giribaldi", "CC Ortigia", "Rari Nantes Savona", "Move reported by OA Sport."),
    ("Giobatta Valle", "", "Rari Nantes Savona", "Arrival reported; previous club not stated in this source."),
    ("Gerard Gil", "", "Rari Nantes Savona", "Arrival reported; previous club not stated in this source."),
    ("Hugo Castro", "", "Rari Nantes Savona", "Arrival reported; previous club not stated in this source."),
    ("Vuk Milojevic", "Novi Beograd", "CN Posillipo", "Arrival reported by OA Sport."),
    ("Rey Petronio", "Pallanuoto Trieste", "", "Retirement reported in the A1 market roundup."),
    ("Andrea Razzi", "Pallanuoto Trieste", "", "Retirement reported in the A1 market roundup."),
    ("Dejan Lazovic", "Pallanuoto Trieste", "", "Leaves Trieste; the article only says he returns to Montenegro."),
    ("Vuk Draskovic", "Pallanuoto Trieste", "", "Roster departure; destination not stated."),
    ("Stefano Sordini", "", "Pallanuoto Trieste", "Arrival reported; previous club not stated in this source."),
    ("Benedek Baksa", "CC Ortigia", "Pallanuoto Trieste", "Move reported by OA Sport."),
    ("Carson Gray", "US college", "Pallanuoto Trieste", "Arrival from US college water polo; precise previous school not stated."),
    ("Rocco Valle", "De Akker Bologna", "Telimar", "Move reported by OA Sport."),
    ("Andrea Urbinati", "De Akker Bologna", "Roma Vis Nova", "Move reported by OA Sport."),
    ("Nicolò Gambacciani", "Iren Genova Quinto", "", "Retirement reported in the A1 market roundup."),
    ("Alessandro Nora", "Iren Genova Quinto", "Sori", "Move reported by OA Sport."),
    ("Matteo Bisso", "", "Iren Genova Quinto", "Arrival reported; previous club not stated in this source."),
    ("Matteo Villa", "", "Iren Genova Quinto", "Arrival reported; previous club not stated in this source."),
    ("Francesco Massaro", "Telimar", "Roma Vis Nova", "Move reported by OA Sport."),
    ("Dory Farkas", "", "Training Academy Olympic Roma", "Arrival reported; previous club not stated in this source."),
    ("Andrea Grossi", "", "Training Academy Olympic Roma", "Arrival reported; previous club not stated in this source."),
    ("Matteo Leporale", "Training Academy Olympic Roma", "", "Roster departure; destination not stated."),
    ("Luka Stahor", "Training Academy Olympic Roma", "", "Roster departure; destination not stated."),
    ("Lorenzo Cotugno", "Training Academy Olympic Roma", "", "Roster departure; destination not stated."),
    ("Eugenio Russo", "", "Telimar", "Arrival reported; previous club not stated in this source."),
    ("Roberto De Freitas", "Rari Nantes Salerno", "Telimar", "Move reported by OA Sport."),
    ("Alessio Privitera", "Rari Nantes Salerno", "Telimar", "Move reported by OA Sport."),
    ("Andrija Vlahovic", "", "Telimar", "Arrival reported; previous club not stated in this source."),
    ("Jake Muscat", "Telimar", "", "Roster departure; destination not stated."),
    ("Giorgio Boggiano", "Telimar", "", "Roster departure; destination not stated."),
    ("Pietro Mangiante", "Telimar", "", "Roster departure; destination not stated."),
    ("Roberto Spinelli", "CN Posillipo", "Canottieri Napoli", "Move reported by OA Sport."),
    ("Emanuele Miraldi", "", "Canottieri Napoli", "Return/arrival reported; previous club not stated in this source."),
    ("Sandro Adeishvili", "", "Canottieri Napoli", "Arrival reported; previous club not stated in this source."),
    ("Edoardo Manzi", "Pallanuoto Trieste", "Canottieri Napoli", "Move reported by OA Sport."),
    ("Marko Radovic", "", "CC Ortigia", "Arrival reported; previous club not stated in this source."),
    ("Mate Aranyi", "CC Ortigia", "", "Roster departure; destination not stated."),
    ("Roberto Radic", "CC Ortigia", "", "Roster departure; destination not stated."),
    ("Federico Panerai", "CN Sabadell", "Chiavari Nuoto", "Move reported by OA Sport."),
]

ITALY_WOMEN_REPORTED = [
    ("Giulia Viacava", "Ekipe Orizzonte Catania", "", "Retirement reported in the A1 women market roundup."),
    ("Daniela Jackovich", "Ekipe Orizzonte Catania", "", "Roster departure; destination not stated."),
    ("Carlotta Meggiato", "Ekipe Orizzonte Catania", "", "Roster departure; later Padova interest remained unconfirmed in this source."),
    ("Lavinia Papi", "SIS Roma", "Ekipe Orizzonte Catania", "Move reported by OA Sport."),
    ("Anna Beatriz Mantellato", "UCLA", "Ekipe Orizzonte Catania", "Move reported by OA Sport."),
    ("Sienna Hearn", "SIS Roma", "", "Roster departure; destination not stated."),
    ("Ginevra Aprea", "SIS Roma", "Rapallo Pallanuoto", "Move reported by OA Sport."),
    ("Sara Centanni", "SIS Roma", "", "Roster departure; destination not stated."),
    ("Helga Santapaola", "Rapallo Pallanuoto", "Plebiscito Padova", "Move reported by OA Sport."),
    ("Grace Marussi", "Pallanuoto Trieste", "", "Roster departure; destination not stated."),
    ("Ana Milicevic", "", "Plebiscito Padova", "Arrival reported; previous club not stated in this source."),
    ("Marta Misiti", "Cosenza", "Plebiscito Padova", "Move reported by OA Sport."),
    ("Taylor Cole Smith", "UCLA", "Bogliasco 1951", "Move reported by OA Sport."),
    ("Hristina Ilic", "", "Nautilus Civitavecchia", "Arrival reported; previous club not stated in this source."),
    ("Magdalena Butic", "", "Nautilus Civitavecchia", "Arrival reported; previous club not stated in this source."),
    ("Ivet Dimitrova", "Aquatica Torino", "Nautilus Civitavecchia", "Move reported by OA Sport."),
    ("Sára Keszthelyi", "", "Sori Pool Beach", "Arrival reported; previous club not stated in this source."),
    ("Giulia Lombella", "Civitavecchia", "Sori Pool Beach", "Move reported by OA Sport."),
]

# HA10 relays LEWaterpolo's August 2026 "new faces" market graphics for Spain.
# These remain reported until club/RFEN corroboration upgrades them.
SPAIN_REPORTED = [
    ("Women", "Claudia Valdés", "", "CE Mediterrani"),
    ("Women", "Lucía Latorre", "", "CE Mediterrani"),
    ("Women", "Irene Briceño", "Real Canoe", "CN Terrassa"),
    ("Women", "Alba Doñágueda", "CN Sant Feliu", "CN Catalunya"),
    ("Women", "Naia Sánchez", "CW Dos Hermanas", "CN Rubí"),
    ("Women", "Nada Mandić", "CN Atlètic-Barceloneta", "CN Sant Feliu"),
    ("Women", "Daniela Moreno", "", "CN Sant Feliu"),
    ("Women", "Lucía Álvaro", "Waterpolo Dos Hermanas", "Geodesic Real Canoe"),
    ("Women", "Carlota Peñalver", "CE Mediterrani", "CN Terrassa"),
    ("Women", "Alice Williams", "CN Sant Andreu", "CN Terrassa"),
    ("Women", "Paula Nieto", "CN Terrassa", ""),
    ("Women", "Pili Peña", "CN Terrassa", ""),
    ("Women", "Emily Nicholson", "CN Terrassa", ""),
    ("Women", "Miriam Ciudad", "CN Terrassa", ""),
    ("Men", "Saúl Granados", "CN Catalunya", "CN Terrassa"),
    ("Men", "Álvaro García", "CE Mediterrani", "CN Terrassa"),
    ("Men", "Iván Castaño", "", "Santa Cruz Tenerife Echeyde"),
    ("Men", "Alberto Barroso", "", "Santa Cruz Tenerife Echeyde"),
    ("Men", "Miguel de Toro", "", "CN Sabadell"),
    ("Men", "Fran Valera", "", "CN Sabadell"),
]

# Additional confirmed deals that were missing from the compact seed.
EUROPE_CONFIRMED = [
    ("Men", "Dimitrios Nikolaidis", "Olympiacos", "Panathinaikos", "2026-07-13"),
    ("Men", "Efstathios Kalogeropoulos", "CN Marseille", "Panathinaikos", "2026-07-13"),
    ("Men", "Dusan Banicevic", "Panathinaikos", "Primorac Kotor", "2026-07-13"),
    ("Men", "Erik Molnar", "FTC Telekom", "VK Jug", "2026-07-14"),
    ("Men", "Dylan Woodhead", "", "Panathinaikos", "2026-07-13"),
    ("Men", "Chase Dodd", "", "BVSC", "2026-07-05"),
    ("Men", "Aleksa Ukropina", "", "Jadran Herceg Novi", "2026-07-04"),
    ("Women", "Alejandra Aznar", "", "Pallanuoto Trieste", "2026-07-13"),
]


EXTRA_TRANSFER_SIGNALS = [
    *[
        _row(gender, player, fr, to, "2026-08-25", "Waterpolo.nl / KNZB", KNZB_URL,
             "federation_confirmed", .97,
             "Listed in the KNZB confirmed 2026-27 transfer overview (updated 25 Aug 2026).",
             "confirmed")
        for gender, player, fr, to in KNZB_CONFIRMED
    ],
    *[
        _row(gender, player, fr, to, "2026-08-25", "Waterpolo.nl / KNZB", KNZB_URL,
             "federation_confirmed", .97, note, "reported")
        for gender, player, fr, to, note in KNZB_ROSTER_EXITS
    ],
    *[
        _row("Men", player, fr, to, "2026-07-28", "OA Sport — A1 mercato", OA_MEN_URL,
             "media_roundup", .88, note, "reported")
        for player, fr, to, note in ITALY_MEN_REPORTED
    ],
    *[
        _row("Women", player, fr, to, "2026-07-29", "OA Sport — A1 women mercato", OA_WOMEN_URL,
             "media_roundup", .88, note, "reported")
        for player, fr, to, note in ITALY_WOMEN_REPORTED
    ],
    *[
        _row(gender, player, fr, to, "2026-08-27" if gender == "Men" else "2026-08-22",
             "HA10 / LEWaterpolo", HA10_AUG_URL, "league_media", .90,
             "Reported in LEWaterpolo's 2026-27 summer market/new-faces coverage.", "reported")
        for gender, player, fr, to in SPAIN_REPORTED
    ],
    *[
        _row(gender, player, fr, to, date, "Waterpolo 360 / Total Waterpolo",
             WP360_CONFIRMED, "media_confirmed", .93,
             "Listed as a confirmed 2026-27 move by specialist transfer media.", "confirmed")
        for gender, player, fr, to, date in EUROPE_CONFIRMED
    ],
]
