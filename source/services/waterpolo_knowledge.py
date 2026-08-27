"""Curated international reference registry and analysis ontology.

This module deliberately stores metadata and analysis concepts rather than copying
large rule texts. Competition-specific rules must be versioned and verified against
official sources before automated adjudication.
"""

OFFICIAL_REFERENCES = [
    {
        "name": "World Aquatics — Competition Regulations",
        "region": "International",
        "scope": "Primary global rules and competition regulations",
        "version": "February 2026 (updated 18 Feb 2026)",
        "url": "https://www.worldaquatics.com/rules/competition-regulations",
        "priority": 1,
    },
    {
        "name": "World Aquatics — Water Polo Rules Hub",
        "region": "International",
        "scope": "Water polo rules and ranking rule links",
        "version": "Current official hub",
        "url": "https://www.worldaquatics.com/water-polo/rules",
        "priority": 1,
    },
    {
        "name": "European Aquatics — Water Polo Rules",
        "region": "Europe",
        "scope": "European championships, club competitions, VAR, tie-break and discipline",
        "version": "2025/2026 competition materials",
        "url": "https://europeanaquatics.org/sports/water-polo/water-polo-rules/",
        "priority": 2,
    },
    {
        "name": "FFN — Règlements du Water-Polo",
        "region": "France",
        "scope": "French competition regulations, official documents and World Aquatics adaptation",
        "version": "2026/2027 page with current federation materials",
        "url": "https://www.ffnatation.fr/reglements-du-water-polo",
        "priority": 3,
    },
    {
        "name": "Federazione Italiana Nuoto — Pallanuoto norme e documenti",
        "region": "Italy",
        "scope": "Technical rules, Serie A1/A2 and national competition regulations",
        "version": "2025/2026",
        "url": "https://www.federnuoto.it/home/pallanuoto/norme-e-documenti-pallanuoto/pallanuoto-norme-e-documenti-2025-2026.html",
        "priority": 3,
    },
    {
        "name": "Magyar Vízilabda Szövetség — Szabályzatok",
        "region": "Hungary",
        "scope": "Hungarian competition regulations and league documents",
        "version": "2025/2026 and 2026/2027 materials",
        "url": "https://waterpolo.hu/szovetseg/szabalyzatok",
        "priority": 3,
    },
    {
        "name": "NCAA — Men's and Women's Water Polo Playing Rules",
        "region": "United States collegiate",
        "scope": "NCAA rules, interpretations and rule changes",
        "version": "2026-27 interpretations / current hub",
        "url": "https://www.ncaa.org/championships/playing-rules/water-polo-playing-rules/",
        "priority": 3,
    },
    {
        "name": "USA Water Polo — Playing Rules",
        "region": "United States",
        "scope": "USAWP rules, interpretations and referee signals",
        "version": "Current official hub",
        "url": "https://usawaterpolo.org/sports/2018/12/19/playing-rules.aspx",
        "priority": 3,
    },
    {
        "name": "Water Polo Australia — Sport Rules",
        "region": "Australia",
        "scope": "Australian rules framework aligned to World Aquatics and event manuals",
        "version": "Current official hub",
        "url": "https://waterpoloaustralia.com.au/info-hub/rules",
        "priority": 3,
    },
]

TACTICAL_PHASES = [
    ("even_attack", "Even-strength attack", "Structured 6v6 possession, spacing, centre entry, perimeter circulation and shot creation."),
    ("even_defence", "Even-strength defence", "Press/zone/hybrid coverage, help, blocks, centre defence and goalkeeper coordination."),
    ("counterattack", "Counterattack", "Defence-to-attack transition after recovery/save, lane occupation, numerical advantage and first-shot timing."),
    ("defensive_recovery", "Defensive recovery", "Attack-to-defence transition after turnover/shot with recovery timing and dangerous-space protection."),
    ("power_play", "Power play / Zone+", "Numerical-advantage attack after exclusion: shape, circulation, extra pass, cross-pool action and shot quality."),
    ("penalty_kill", "5-on-6 defence / Zone−", "Numerical-disadvantage defence: rotation, lanes, blocking, goalkeeper view and re-entry management."),
    ("centre_play", "Centre / 2m play", "Entry quality, body position, defender relation, earned exclusions, turns and finishing."),
    ("restart", "Restart / dead-ball phase", "Free throws, corner throws, after-goal restarts, timeout restarts and organized set-up."),
]

ANALYSIS_DIMENSIONS = [
    "possession", "passing", "shooting", "goalkeeping", "transition", "positioning",
    "spacing", "defensive_pressure", "blocks", "exclusions", "whistles", "shot_clock",
    "player_tracking", "ball_tracking", "swimming_speed", "shot_speed", "tactical_shape",
]
