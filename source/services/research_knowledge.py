"""Research and coaching knowledge registry.

Only bibliographic metadata and short product implications are stored here. The app
must never reproduce copyrighted book/article text. Findings are treated as evidence
for metric design and benchmarking, not as universal causal truths.
"""

RESEARCH_REFERENCES = [
    {
        "kind": "research-project", "year": 2026,
        "title": "Door het Water Heen Kijken: Computer Vision voor Waterpolo Analyse",
        "source": "Vrije Universiteit Amsterdam / KNZB / TeamNL", "url": "https://research.vu.nl/en/projects/door-het-water-heen-kijken-computer-vision-voor-waterpolo-analyse/",
        "implication": "Directly validates AquaMetric's architecture: use ordinary match video to track players, quantify movement and discover recurring tactical patterns, with a coach-facing dashboard."
    },
    {
        "kind": "science", "year": 2026,
        "title": "Quantifying women's water polo overhead movement volumes using inertial measurement units and machine learning techniques",
        "source": "Scientific Reports / PubMed", "url": "https://pubmed.ncbi.nlm.nih.gov/41554918/",
        "implication": "Keep pass, high-intensity throw/shot, swimming, block with ball contact and block without ball contact as distinct labels; multimodal sensor data can later complement video when available."
    },
    {
        "kind": "science", "year": 2022,
        "title": "Automatic detection of passing and shooting in water polo using machine learning: a feasibility study",
        "source": "Sports Biomechanics / PubMed", "url": "https://pubmed.ncbi.nlm.nih.gov/35225158/",
        "implication": "Automatic pass/shot classification is feasible with labelled synchronized data; AquaMetric should build a correction/label pipeline now so future models can be evaluated with sensitivity/specificity rather than subjective impressions."
    },
    {
        "kind": "science", "year": 2021,
        "title": "New aspects for match analysis to improve understanding of game scenario and training organization in top-level male water polo players",
        "source": "PubMed / Journal of Sports Medicine and Physical Fitness", "url": "https://pubmed.ncbi.nlm.nih.gov/33871237/",
        "implication": "Analyze actions as sequences/trains, not isolated tags; sequence duration and continuity matter."
    },
    {
        "kind": "science", "year": 2008,
        "title": "A time-motion analysis of international women's water polo match play",
        "source": "PubMed / International Journal of Sports Physiology and Performance", "url": "https://pubmed.ncbi.nlm.nih.gov/19211943/",
        "implication": "Role-aware physical benchmarks: perimeter and centre players have different movement/contact profiles."
    },
    {
        "kind": "science", "year": 2009,
        "title": "Activity profiles and physical demands of elite women's water polo match play",
        "source": "PubMed / Journal of Sports Sciences", "url": "https://pubmed.ncbi.nlm.nih.gov/19847693/",
        "implication": "Track high-intensity bouts, distance, quarter-by-quarter changes and role-specific movement demands."
    },
    {
        "kind": "science", "year": 2012,
        "title": "Water Polo Game-Related Statistics in Women's International Championships: Differences and Discriminatory Power",
        "source": "PubMed / Journal of Sports Science & Medicine", "url": "https://pubmed.ncbi.nlm.nih.gov/24149356/",
        "implication": "Include offensive and defensive indicators such as power-play goals, counterattack goals, steals, blocked shots and goalkeeper saves."
    },
    {
        "kind": "science", "year": 2014,
        "title": "Women's water polo world championships: technical and tactical aspects of winning and losing teams in close and unbalanced games",
        "source": "PubMed / Journal of Strength & Conditioning Research", "url": "https://pubmed.ncbi.nlm.nih.gov/23588481/",
        "implication": "Interpret tactics differently in close versus unbalanced games; context and score margin matter."
    },
    {
        "kind": "science", "year": 2020,
        "title": "Water Polo Shooting Performance: Differences Between World Championship Winning, Drawing and Losing Teams",
        "source": "PubMed", "url": "https://pubmed.ncbi.nlm.nih.gov/32269661/",
        "implication": "Model shot origin, defensive block, target zone, tactical phase and efficacy rather than raw shot count alone."
    },
    {
        "kind": "science", "year": 2023,
        "title": "Assessment of the Offensive Play in Elite Water Polo Using the Team Sport Assessment Procedure (TSAP)",
        "source": "PubMed", "url": "https://pubmed.ncbi.nlm.nih.gov/37754963/",
        "implication": "Use possession gain/disposal, lost balls, successful shots, volume of play and efficiency with position-aware interpretation."
    },
    {
        "kind": "science", "year": 2014,
        "title": "Water polo throwing velocity and kinematics: differences between competitive levels in male players",
        "source": "PubMed", "url": "https://pubmed.ncbi.nlm.nih.gov/25369278/",
        "implication": "Shot-speed/technique feedback needs calibrated video and should separate observed kinematics from inferred physical power."
    },
    {
        "kind": "science", "year": 2011,
        "title": "Throwing velocity and kinematics in elite male water polo players",
        "source": "PubMed", "url": "https://pubmed.ncbi.nlm.nih.gov/22212254/",
        "implication": "Benchmark ball-release velocity carefully by role/context; do not use body size as a shortcut for throwing performance."
    },
    {
        "kind": "science", "year": 2025,
        "title": "Water polo coaches believe they gain an advantage by calling time-out before playing power-play, but is that really true?",
        "source": "PubMed", "url": "https://pubmed.ncbi.nlm.nih.gov/40191572/",
        "implication": "Avoid simplistic coaching assumptions; compare time-out and non-time-out power plays empirically."
    },
    {
        "kind": "coaching", "year": 2018,
        "title": "USA Water Polo Digital Coaching Manual",
        "source": "USA Water Polo", "url": "https://usawaterpolo.org/sports/2018/11/28/genrel-100818aaa-html.aspx",
        "implication": "Use federation coaching education as a practical complement to peer-reviewed research for technique/tactics ontology."
    },
    {
        "kind": "book", "year": 2011,
        "title": "Secrets of a Serbian Water Polo Coach",
        "source": "Ivan Ivovic / bibliographic reference", "url": "https://books.google.com/books/about/Secrets_of_a_Serbian_Water_Polo_Coach.html?id=Unr3BgAAQBAJ",
        "implication": "Serbian coaching literature explicitly covers offense/defense, man-down, man-up, zone and pressure-defense concepts; use as one school among many."
    },
    {
        "kind": "coaching", "year": 2009,
        "title": "6-5 Attack — Simple Shifting",
        "source": "Water Polo Planet", "url": "https://www.waterpoloplanet.com/HTML_Dave_pages/dm10_water_polo_tactics.html",
        "implication": "Represent common 4-2 power-play geometry and ball/defender shifts as configurable tactical patterns, not mandatory rules."
    },
    {
        "kind": "coaching", "year": 2009,
        "title": "The 3-3 Attack",
        "source": "Water Polo Planet", "url": "https://www.waterpoloplanet.com/HTML_Dave_pages/dm11_water_polo_tactics.html",
        "implication": "Detect/allow alternative 3-3 numerical-advantage structures and transitions between structures."
    },
    {
        "kind": "coaching", "year": 2010,
        "title": "The M-Zone Defense",
        "source": "Water Polo Planet", "url": "https://www.waterpoloplanet.com/HTML_Dave_pages/dm15_water_polo_tactics.html",
        "implication": "Add M-zone/drop concepts to the defensive ontology; evaluate ball-side shifts, centre protection and outside-shot concessions."
    },
    {
        "kind": "science", "year": 2011,
        "title": "Discriminatory power of water polo game-related statistics at the 2008 Olympic Games",
        "source": "PubMed / Journal of Sports Sciences", "url": "https://pubmed.ncbi.nlm.nih.gov/21170797/",
        "implication": "Do not use the same success model for men and women; discriminating indicators differed by sex in this Olympic sample."
    },
    {
        "kind": "science", "year": 2013,
        "title": "Differences and discriminatory power of water polo game-related statistics in men in international championships",
        "source": "PubMed / Journal of Strength & Conditioning Research", "url": "https://pubmed.ncbi.nlm.nih.gov/22692107/",
        "implication": "Contextualize performance by competition phase; the variables that separate winners and losers change as opposition becomes more balanced."
    },
    {
        "kind": "science", "year": 2010,
        "title": "Notational analysis of American women's collegiate water polo matches",
        "source": "PubMed", "url": "https://pubmed.ncbi.nlm.nih.gov/20647945/",
        "implication": "Measure action duration, passes, exclusions/penalties, shot origin and outcomes separately for even, counterattack and power-play situations."
    },
    {
        "kind": "science", "year": 2018,
        "title": "Physiological and Tactical On-court Demands of Water Polo",
        "source": "PubMed", "url": "https://pubmed.ncbi.nlm.nih.gov/29912072/",
        "implication": "Combine tactical phase with physical load; fatigue can alter playing intensity and technical/tactical efficacy."
    },
    {
        "kind": "science", "year": 2018,
        "title": "Effects of Rule Changes on Game-Related Statistics in Men's Water Polo Matches",
        "source": "PubMed", "url": "https://pubmed.ncbi.nlm.nih.gov/29910444/",
        "implication": "Benchmarks must be rule-version aware; longitudinal comparisons can be misleading across major rule changes."
    },
    {
        "kind": "industry-analysis", "year": 2022,
        "title": "Advanced data analytics on the 2022 Men's World Championship final",
        "source": "Total Waterpolo / teamio.ai collaboration", "url": "https://total-waterpolo.com/5-conclusions-of-advanced-data-analytics-on-the-2022-mens-world-championship-final/",
        "implication": "Explore expected/true-shooting style metrics, defence-type outcomes and power-play structures, but validate methods independently before using them for ratings."
    },
    {
        "kind": "industry-analysis", "year": 2023,
        "title": "Total Waterpolo Water Polo Efficiency Rating (WER)",
        "source": "Total Waterpolo", "url": "https://total-waterpolo.com/what-is-total-waterpolos-wer/",
        "implication": "External rating systems can inspire feature design, but AquaMetric should keep its own formula transparent, role-aware and evidence-linked rather than copy an opaque metric."
    },
    {
        "kind": "coaching", "year": 2020,
        "title": "David Martín on tactical variability and multi-position players",
        "source": "Total Waterpolo interview", "url": "https://total-waterpolo.com/david-martin-future-is-for-players-who-can-master-all-the-positions/",
        "implication": "Treat player role as dynamic by phase and match context instead of forcing one permanent position label."
    },
]

TACTICAL_LIBRARY = {
    "even_attack": {
        "principles": ["width and depth", "centre-entry threat", "weak-side movement", "shoot/pass double threat", "turnover protection"],
        "patterns": ["3-3/umbrella-like perimeter", "drives", "picks/screens", "post-up/centre entry", "overload vs zone"],
        "requires_tracking_for": ["formation label", "spacing", "driving lane quality", "centre fronting relation"],
    },
    "even_defence": {
        "principles": ["protect central high-value space", "ball pressure", "passing-lane denial", "help/recover", "counterattack readiness"],
        "patterns": ["press/man-to-man", "2-4 drop", "M-zone/drop", "hybrid/help defence"],
        "requires_tracking_for": ["press/drop classification", "help distance", "goal-side position", "rotation quality"],
    },
    "power_play": {
        "principles": ["arrive/set quickly", "move defence with ball and players", "create cross-cage/inside threat", "avoid static circulation", "shot quality before exclusion ends"],
        "patterns": ["4-2", "3-3", "post rotations", "cross-pass/catch-and-shoot", "low-post action"],
        "requires_tracking_for": ["4-2 vs 3-3", "post occupancy", "defensive shift", "goalkeeper displacement", "lane openness"],
    },
    "penalty_kill": {
        "principles": ["protect high-value lanes", "coordinated rotation", "block lanes without screening goalkeeper", "track re-entry", "force lower-quality shots"],
        "patterns": ["compact rotating 5", "goal-line/three-goalie variant", "match-up rotations"],
        "requires_tracking_for": ["rotation speed", "block geometry", "goalkeeper sightline", "re-entry responsibility"],
    },
    "counterattack": {
        "principles": ["first reaction after possession change", "lane occupation", "head-up ball advancement", "numerical advantage recognition", "early high-quality shot vs forced shot"],
        "patterns": ["wing release", "centre lane", "trailer", "goalkeeper outlet"],
        "requires_tracking_for": ["lane assignment", "swim speed", "numerical advantage", "pass choice quality"],
    },
    "defensive_recovery": {
        "principles": ["immediate transition", "protect centre first", "identify most dangerous attacker", "communicate matchups", "avoid ball-watching"],
        "patterns": ["sprint-back", "funnel/recovery", "mid-pool pickup"],
        "requires_tracking_for": ["recovery time", "goal-side recovery", "danger-space protection", "matchup restoration"],
    },
}
