(() => {
  'use strict';

  const CURRENT = '2026-2027';
  const PREVIOUS = '2025-2026';
  const ROLE_GROUPS = [
    ['Coaching', ['Head coach', 'Associate / first assistant', 'Assistant coach', 'Assistant coach #2', 'Goalkeeper coach']],
    ['Performance & analyse', ['Strength & conditioning', 'Performance coach', 'Video / tactical analyst', 'Data analyst / scout']],
    ['Médical & management', ['Team manager', 'Technical / sporting director', 'Physiotherapist', 'Doctor / medical staff', 'Psychology / nutrition']],
  ];

  const FEDERATIONS = {
    France: ['🇫🇷', 'Fédération Française de Natation', 'FFN', 'Europe'],
    Spain: ['🇪🇸', 'Real Federación Española de Natación', 'RFEN', 'Europe'],
    Italy: ['🇮🇹', 'Federazione Italiana Nuoto', 'FIN', 'Europe'],
    Hungary: ['🇭🇺', 'Hungarian Water Polo Federation', 'MVLSZ', 'Europe'],
    Greece: ['🇬🇷', 'Hellenic Swimming Federation', 'KOE', 'Europe'],
    Croatia: ['🇭🇷', 'Croatian Water Polo Federation', 'HVS', 'Europe'],
    Serbia: ['🇷🇸', 'Water Polo Federation of Serbia', 'VSS', 'Europe'],
    Montenegro: ['🇲🇪', 'Water Polo and Swimming Federation of Montenegro', 'VPSCG', 'Europe'],
    Germany: ['🇩🇪', 'Deutscher Schwimm-Verband', 'DSV', 'Europe'],
    Netherlands: ['🇳🇱', 'Koninklijke Nederlandse Zwembond', 'KNZB', 'Europe'],
    Romania: ['🇷🇴', 'Romanian Water Polo Federation', 'FRP', 'Europe'],
    Turkey: ['🇹🇷', 'Turkish Swimming Federation', 'TYF', 'Europe'],
    Portugal: ['🇵🇹', 'Federação Portuguesa de Natação', 'FPN', 'Europe'],
    'United Kingdom': ['🇬🇧', 'Aquatics GB / Home Nations', 'GB', 'Europe'],
    'United States': ['🇺🇸', 'USA Water Polo', 'USAWP', 'Americas'],
    Canada: ['🇨🇦', 'Water Polo Canada', 'WPC', 'Americas'],
    Brazil: ['🇧🇷', 'Confederação Brasileira de Desportos Aquáticos', 'CBDA', 'Americas'],
    Argentina: ['🇦🇷', 'Confederación Argentina de Deportes Acuáticos', 'CADDA', 'Americas'],
    Australia: ['🇦🇺', 'Water Polo Australia', 'WPA', 'Oceania'],
    'New Zealand': ['🇳🇿', 'New Zealand Water Polo', 'NZWP', 'Oceania'],
    Japan: ['🇯🇵', 'Japan Swimming Federation', 'JSF', 'Asia'],
    China: ['🇨🇳', 'Chinese Swimming Association', 'CSA', 'Asia'],
    Kazakhstan: ['🇰🇿', 'Aquatics Federation of Kazakhstan', 'AFK', 'Asia'],
    'South Africa': ['🇿🇦', 'Swimming South Africa', 'SSA', 'Africa'],
    Egypt: ['🇪🇬', 'Egyptian Swimming Federation', 'ESF', 'Africa'],
  };

  const LEAGUES = [
    // France — 2026-27 Elite lists are from the published FFN calendar. N1 remains season-sensitive.
    {country:'France', gender:'Women', level:1, name:'Élite Féminine', source:'https://www.extranat.fr/waterpolo/', currentStatus:'official', currentTeams:['Granville Water Polo','Lille UC Métropole Water-Polo','Union St-Bruno Bordeaux','Olympic Nice Natation','Taverny Sports Nautiques 95','Toulon Waterpolo','Sporting Club des Nageurs de Choisy le Roi','Paris Water-Polo','Cercle des Nageurs de Marseille','Grand Nancy Aquatique Club'], previousTeams:['Lille UC Métropole Water-Polo','Union St-Bruno Bordeaux','Olympic Nice Natation','Taverny Sports Nautiques 95','Toulon Waterpolo','Sporting Club des Nageurs de Choisy le Roi','Libellule Paris / Paris Water-Polo','Cercle des Nageurs de Marseille','Grand Nancy Aquatique Club','Mulhouse Water Polo']},
    {country:'France', gender:'Men', level:1, name:'Élite Masculine', source:'https://www.extranat.fr/waterpolo/', currentStatus:'official', currentTeams:['Cercle des Nageurs de Marseille','Montpellier Water-Polo','Taverny Sports Nautiques 95','Union St-Bruno Bordeaux','Douaisis Agglo Waterpolo','Team Strasbourg SNS-ASPTT-PCS','Olympic Nice Natation','Pays d’Aix Natation','AS Monaco Natation','Sète Natation'], previousTeams:['Cercle des Nageurs de Marseille','Montpellier Water-Polo','Taverny Sports Nautiques 95','Union St-Bruno Bordeaux','Douaisis Agglo Waterpolo','Team Strasbourg SNS-ASPTT-PCS','Olympic Nice Natation','Pays d’Aix Natation','Sète Natation','Tourcoing Lille Métropole']},
    {country:'France', gender:'Women', level:2, name:'Nationale 1 Féminine', source:'https://www.extranat.fr/waterpolo/', currentStatus:'provisional', currentTeams:['NC Saint-Jean-d’Angély','RC Arras Water-Polo','AS Montgeron Water-Polo','ASPTT Limoges','Laval Water-Polo','EN Tourcoing','CN Le Havre','SC Thionville'], previousTeams:['NC Saint-Jean-d’Angély','Granville Water Polo','Libellule Paris','Laval Water-Polo','RC Arras Water-Polo','AS Montgeron Water-Polo','ASPTT Limoges','Grand Nancy Aquatique Club']},
    {country:'France', gender:'Men', level:2, name:'Nationale 1 Masculine', source:'https://www.extranat.fr/waterpolo/', currentStatus:'provisional', currentTeams:['Cercle des Nageurs de Marseille B','Canards Rochelais A','Granville Water Polo','Paris Water-Polo','Union St-Bruno Bordeaux B','Olympic Nice Natation B','Grand Nancy Aquatique Club','Lille UC Métropole Water-Polo'], previousTeams:['AS Monaco Natation','Sauveteurs Givors','Nautic Club Moulins','NC Saint-Jean-d’Angély','SN Harnes','Canards Rochelais A','CNR INSEP','SCN Choisy-le-Roi','Mulhouse Water-Polo','Cercle des Nageurs de Marseille B','Racing Club de France','Paris Water-Polo']},

    // Spain — complete 2025-26 RFEN league participants. 2026-27 stays explicitly provisional until RFEN season publication.
    {country:'Spain', gender:'Men', level:1, name:'División de Honor Masculina', source:'https://rfen.es/especialidades/waterpolo/competicion/1510/equipos/', currentStatus:'provisional', previousTeams:['Zodiac CN Atlètic-Barceloneta','CN Sabadell','CN Barcelona','CN Terrassa','Solartradex CN Mataró','CN Sant Andreu','Santa Cruz Tenerife Echeyde','CN Rubí','CN Caballa - Ciudad de Ceuta','CE Mediterrani','EPlus CN Catalunya','C. Encinas de Boadilla']},
    {country:'Spain', gender:'Women', level:1, name:'División de Honor Femenina', source:'https://rfen.es/especialidades/waterpolo/competicion/1511/equipos/', currentStatus:'provisional', previousTeams:['CN Sant Andreu','Assolim CN Mataró','Astralpool CN Sabadell','CN Terrassa','CN Atlètic-Barceloneta','EPlus CN Catalunya','CE Mediterrani','CN Sant Feliu','Santa Cruz Tenerife Echeyde','Geodesic Real Canoe NC','UE Horta','CD Waterpolo Iruña 98 02']},
    {country:'Spain', gender:'Men', level:2, name:'Primera División Masculina', source:'https://rfen.es/especialidades/waterpolo/competicion/1512/equipos/', currentStatus:'provisional', previousTeams:['Geodesic Real Canoe NC','CN Sant Feliu','CN Premià','UE Horta-Haxelia','C Waterpolo Sevilla','CDW Turia','CN Montjuïc','CN Granollers','CN Las Palmas','CN Helios','CN Molins de Rei','C Askartza','CN Ciutat de Palma','CN Poble Nou']},
    {country:'Spain', gender:'Women', level:2, name:'Primera División Femenina', source:'https://rfen.es/especialidades/waterpolo/competicion/1513/equipos/', currentStatus:'provisional', previousTeams:['AR Concepción Ciudad Lineal','AESE - L’Hospitalet','C Waterpolo Turia','CD Natación Boadilla','CD Waterpolo Málaga','CN Barcelona','CN Ciudad de Alcorcón','CN Cuatro Caminos','CN Molins de Rei','CN Montjuïc','CN Rubí','CN Vallirana','CW Dos Hermanas','Club Esportiu Illes Balears-Gobycar','Club Waterpolo Elx Manolet','CW Pontevedra','Leioa WP','Waterpolo Ciudad de Rivas']},

    // Italy — complete 2025-26 A1; A2 grouped North/South as the national second tier.
    {country:'Italy', gender:'Men', level:1, name:'Serie A1 Maschile', source:'https://www.federnuoto.it/home/pallanuoto/campionato-a1-maschile/2025-2026.html', currentStatus:'provisional', previousTeams:['Pro Recco Waterpolo','AN Brescia','Banco BPM RN Savona','CC Ortigia 1928','Pallanuoto Trieste','Roma Vis Nova PN','Ranieri Impiantistica CN Posillipo','De Akker Team','Telimar Palermo','Iren Genova Quinto','RN Florentia','RN Nuoto Salerno','Training Academy Olympic Roma','AC Group CC Napoli']},
    {country:'Italy', gender:'Women', level:1, name:'Serie A1 Femminile', source:'https://www.federnuoto.it/home/pallanuoto/campionato-a1-femminile/2025-2026.html', currentStatus:'provisional', previousTeams:['SIS Roma','L’Ekipe Orizzonte','Rapallo Pallanuoto','Pallanuoto Trieste','Smile Cosenza Pallanuoto','Plebiscito Padova','AGN Energia Bogliasco 1951','Brizz Nuoto','Nautilus Civitavecchia','Iren Tauride L. Locatelli Genova']},
    {country:'Italy', gender:'Men', level:2, name:'Serie A2 Maschile — Girone Nord', source:'https://www.federnuoto.it/home/pallanuoto/campionato-a2-maschile/2025-2026.html', currentStatus:'provisional', previousTeams:['Chiavari Nuoto','Futurenergy RN Sori','Reale Mutua Torino 81 Iren','AGN Energia Bogliasco 1951','Vela Nuoto Ancona','Piacenza Pallanuoto 2018','Mobilpesca Lavagna','RN Arenzano','Waterpolo Milano Metanopoli','Dream Sport','Pallanuoto Bergamo','Spazio RN Camogli']},
    {country:'Italy', gender:'Men', level:2, name:'Serie A2 Maschile — Girone Sud', source:'https://www.federnuoto.it/home/pallanuoto/campionato-a2-maschile/2025-2026.html', currentStatus:'provisional', previousTeams:['SS Lazio Nuoto','Ischia Marine Club','Lemon Sistemi Waterpolo Palermo','Nuoto Catania','Onda Forte','Anzio Waterpolis','GLS Napoli Lions','Giorgini Ottica Muri Antichi','Ortigia Academy','Roma 2020','Pallanuoto Anzio 1954','Acquachiara ATI 2000']},
    {country:'Italy', gender:'Women', level:2, name:'Serie A2 Femminile — Girone Nord', source:'https://www.federnuoto.it/home/pallanuoto/campionato-a2-femminile/2025-2026.html', currentStatus:'provisional', previousTeams:['Sori Pool Beach','Como Nuoto Recoaro','RN Bologna','Spazio RN Camogli','RN Florentia','Waterpolo Milano Metanopoli','Isocell Orobica','Project Sport']},
    {country:'Italy', gender:'Women', level:2, name:'Serie A2 Femminile — Girone Sud', source:'https://www.federnuoto.it/home/pallanuoto/campionato-a2-femminile/2025-2026.html', currentStatus:'provisional', previousTeams:['Vela Nuoto Ancona','SS Lazio Nuoto','Castelli Romani','BCC Villani','Acquachiara','Volturno','Roma Vis Nova','Cosenza PN']},

    // International top divisions: one senior top tier per gender, as requested. These are maintained as federation coverage indexes.
    {country:'Hungary', gender:'Men', level:1, name:'OB I', currentStatus:'reference', previousTeams:['FTC-Telekom','VasasPlaket','BVSC-Zugló','A-Híd OSC Újbuda','Szolnoki Dózsa','Honvéd','Eger','Szeged','Miskolc','UVSE']},
    {country:'Hungary', gender:'Women', level:1, name:'OB I Women', currentStatus:'reference', previousTeams:['UVSE','Dunaújváros','FTC-Telekom','BVSC-Zugló','Eger','Szentes','III. Kerületi TVE','Szeged']},
    {country:'Greece', gender:'Men', level:1, name:'A1 Ethniki', currentStatus:'reference', previousTeams:['Olympiacos','NC Vouliagmeni','Panionios','Apollon Smyrnis','PAOK','Peristeri','ANO Glyfada','Ethnikos Piraeus','Palaio Faliro','Chios']},
    {country:'Greece', gender:'Women', level:1, name:'A1 Ethniki Women', currentStatus:'reference', previousTeams:['Olympiacos','NC Vouliagmeni','Alimos NAC','Ethnikos Piraeus','ANO Glyfada','Panionios','PAOK','Rethymno']},
    {country:'Croatia', gender:'Men', level:1, name:'Prvenstvo Hrvatske', currentStatus:'reference', previousTeams:['Jadran Split','Jug Adriatic osiguranje','Mladost Zagreb','Solaris Šibenik','Primorje EB Rijeka','Mornar Split','Medveščak Zagreb','KPK Korčula']},
    {country:'Serbia', gender:'Men', level:1, name:'Superliga Srbije', currentStatus:'reference', previousTeams:['Novi Beograd','Radnički Kragujevac','Crvena zvezda','Partizan','Šabac','Valis','Vojvodina','Nais']},
    {country:'Montenegro', gender:'Men', level:1, name:'Prva Liga', currentStatus:'reference', previousTeams:['Jadran Herceg Novi','Primorac Kotor','Budva','Cattaro']},
    {country:'Germany', gender:'Men', level:1, name:'Wasserball-Bundesliga', currentStatus:'reference', previousTeams:['Waspo 98 Hannover','Spandau 04','ASC Duisburg','Duisburger SV 98','OSC Potsdam','SG Neukölln','SV Ludwigsburg','SV Krefeld 72']},
    {country:'Germany', gender:'Women', level:1, name:'Wasserball-Bundesliga Women', currentStatus:'reference', previousTeams:['Spandau 04','SV Bayer Uerdingen 08','Waspo 98 Hannover','SV Blau-Weiß Bochum','Eimsbütteler TV','SC Chemnitz']},
    {country:'Netherlands', gender:'Men', level:1, name:'Eredivisie', currentStatus:'reference', previousTeams:['GZC Donk','ZV De Zaan','Polar Bears','UZSC','ZVL-1886','Het Ravijn','AZC Alphen','ZPB H&L Productions']},
    {country:'Netherlands', gender:'Women', level:1, name:'Eredivisie Women', currentStatus:'reference', previousTeams:['ZV De Zaan','GZC Donk','Polar Bears','ZVL-1886','UZSC','Het Ravijn','ZPB H&L Productions','De Ham']},
    {country:'Romania', gender:'Men', level:1, name:'Superliga Națională', currentStatus:'reference', previousTeams:['Steaua București','CSM Oradea','Dinamo București','Rapid București','Sportul Studențesc','Politehnica Cluj']},
    {country:'Turkey', gender:'Men', level:1, name:'Sutopu Süper Lig', currentStatus:'reference', previousTeams:['Galatasaray','ENKA','İstanbul Yüzme İhtisas','Heybeliada','Kınalıada','Adalar Su Sporları']},
    {country:'Portugal', gender:'Men', level:1, name:'Campeonato Portugal A1', currentStatus:'reference', previousTeams:['Vitória SC','Fluvial Portuense','Paredes','Sporting CP','Portinado','CNPO']},
    {country:'Australia', gender:'Men', level:1, name:'Australian Water Polo League', currentStatus:'reference', previousTeams:['Sydney Uni Lions','UNSW Wests Magpies','Drummoyne Devils','UTS Balmain Tigers','Queensland Thunder','Fremantle Mariners','Melbourne Collegians','Hunter Hurricanes']},
    {country:'Australia', gender:'Women', level:1, name:'Australian Water Polo League Women', currentStatus:'reference', previousTeams:['Sydney Uni Lions','UNSW Wests Killer Whales','Drummoyne Devils','UTS Balmain Tigers','Queensland Thunder','Fremantle Marlins','Melbourne Collegians','Hunter Hurricanes']},
  ];

  // For leagues not yet published for 2026-27, display the complete N-1 list as a clearly labelled reference.
  LEAGUES.forEach(l => { if (!l.currentTeams) l.currentTeams = l.previousTeams || []; });

  const NATIONAL_CATEGORIES = ['Senior','U20 / Junior','U18','U16'];

  const app = document.getElementById('coachDirectoryApp');
  if (!app) return;
  const directory = document.getElementById('coachDirectory');
  const kpis = document.getElementById('coachKpis');
  const note = document.getElementById('coachCurrentNote');
  const countrySelect = document.getElementById('coachCountry');
  const genderSelect = document.getElementById('coachGender');
  const searchInput = document.getElementById('coachSearch');
  let records = [];
  try { records = JSON.parse(document.getElementById('aquametricCoachRecords').textContent || '[]'); } catch (_) { records = []; }

  const state = {season: CURRENT, view:'clubs', country:'all', gender:'all', search:''};
  const norm = v => (v || '').toString().normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
  const aliases = {
    'granville waterpolo':'granville water polo',
    'granville water polo':'granville water polo',
    'union saint bruno bordeaux':'union st bruno bordeaux',
    'usb bordeaux':'union st bruno bordeaux',
    'taverny sn 95':'taverny sports nautiques 95',
    'cn marseille':'cercle des nageurs de marseille',
    'lille uc metropole water polo':'lille uc metropole water polo',
  };
  const keyTeam = name => aliases[norm(name)] || norm(name);
  const recordSeason = season => {
    const s = norm(season);
    if (s === '2026' || s.includes('2026 2027')) return CURRENT;
    if (s.includes('2025 2026')) return PREVIOUS;
    return season || '';
  };
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const nationalCountry = record => (String(record?.team || '').split(/\s+[—–-]\s+/)[0] || '').trim();
  const nationalGender = record => {
    const text = `${record?.category || ''} ${record?.team || ''}`;
    if (/\bWomen\b/i.test(text)) return 'Women';
    if (/\bMen\b/i.test(text)) return 'Men';
    return '';
  };

  function leagueTeams(league) { return state.season === CURRENT ? league.currentTeams : league.previousTeams; }

  function availableCountries() {
    if (state.view === 'national') {
      return [...new Set(records
        .filter(r => r.team_type === 'national_team' && recordSeason(r.season) === state.season)
        .filter(r => state.gender === 'all' || nationalGender(r) === state.gender)
        .map(nationalCountry)
        .filter(Boolean))]
        .sort((a,b)=>a.localeCompare(b));
    }
    return [...new Set(LEAGUES
      .filter(l => (state.gender === 'all' || l.gender === state.gender) && leagueTeams(l)?.length)
      .map(l => l.country))]
      .sort((a,b)=>a.localeCompare(b));
  }

  function countryOptions() {
    const countries = availableCountries();
    if (state.country !== 'all' && !countries.includes(state.country)) state.country = 'all';
    countrySelect.innerHTML = '<option value="all">Tous les pays couverts</option>' + countries.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join('');
    countrySelect.value = state.country;
  }

  function linkedRecords(team, season, teamType='club') {
    const tk = keyTeam(team);
    return records.filter(r => r.team_type === teamType && keyTeam(r.team) === tk && recordSeason(r.season) === season);
  }

  function roleGroupsHtml() {
    return `<div class="coach-role-groups">${ROLE_GROUPS.map(([group, roles]) => `<div class="coach-role-group"><b>${esc(group)}</b>${roles.map(r => `<span class="coach-missing">${esc(r)} — à identifier / vérifier</span>`).join('')}</div>`).join('')}</div>`;
  }

  function personHtml(r) {
    const pct = Math.round((Number(r.confidence)||0)*100);
    const source = r.source_url ? `<a class="coach-source-link" href="${esc(r.source_url)}" target="_blank" rel="noopener">source</a>` : 'source non jointe';
    return `<div class="coach-person-card"><div class="coach-person-head"><div><a href="/coach-intelligence/${encodeURIComponent(r.id)}">${esc(r.name)}</a><div class="coach-role">${esc(r.role)}</div></div><div class="coach-confidence">${pct}%</div></div><div class="coach-source-line">${esc((r.status||'').replaceAll('_',' '))} · ${esc(r.source_tier||'')} · ${source}</div></div>`;
  }

  function statusBadge(status, season) {
    if (season === PREVIOUS) return '<span class="coach-status-badge official">N-1 officiel / historique</span>';
    if (status === 'official') return '<span class="coach-status-badge official">2026-27 publié</span>';
    if (status === 'reference') return '<span class="coach-status-badge reference">D1 internationale · N-1 référence</span>';
    return '<span class="coach-status-badge provisional">2026-27 à confirmer</span>';
  }

  function matchSearch(parts) {
    if (!state.search) return true;
    return norm(parts.join(' ')).includes(norm(state.search));
  }

  function filteredLeagues() {
    return LEAGUES.filter(l => {
      if (state.country !== 'all' && l.country !== state.country) return false;
      if (state.gender !== 'all' && l.gender !== state.gender) return false;
      if (!leagueTeams(l)?.length) return false;
      if (!state.search) return true;
      const teamHit = leagueTeams(l).some(t => matchSearch([t]));
      const coachHit = records.some(r => matchSearch([r.name,r.team,r.role]) && leagueTeams(l).some(t => keyTeam(t) === keyTeam(r.team)));
      return matchSearch([l.country,l.name,(FEDERATIONS[l.country]||[]).join(' ')]) || teamHit || coachHit;
    });
  }

  function renderClubs() {
    const leagues = filteredLeagues();
    const byCountry = new Map();
    leagues.forEach(l => { if (!byCountry.has(l.country)) byCountry.set(l.country, []); byCountry.get(l.country).push(l); });
    let clubCount = 0, linkedCount = 0, officialLeagueCount = 0;
    leagues.forEach(l => { clubCount += leagueTeams(l).length; if (state.season===PREVIOUS || l.currentStatus==='official') officialLeagueCount += 1; leagueTeams(l).forEach(t => { if (linkedRecords(t,state.season).length) linkedCount += 1; }); });
    kpis.innerHTML = `<div class="coach-kpi"><strong>${byCountry.size}</strong><span>Fédérations</span></div><div class="coach-kpi"><strong>${leagues.length}</strong><span>Championnats</span></div><div class="coach-kpi"><strong>${clubCount}</strong><span>Clubs indexés</span></div><div class="coach-kpi"><strong>${linkedCount}</strong><span>Clubs avec staff sourcé</span></div>`;
    note.innerHTML = state.season === CURRENT
      ? `<b>2026-27 :</b> ${officialLeagueCount}/${leagues.length || 0} championnats affichés ont déjà une liste de participants explicitement publiée dans cette base. Les autres utilisent le dernier championnat complet N-1 comme référence et restent marqués « à confirmer » — aucune continuité de coach n'est supposée.`
      : `<b>2025-26 :</b> vue N-1. Les listes France/Espagne/Italie proviennent des championnats nationaux officiels intégrés ; les autres D1 servent d'index international de couverture.`;

    if (!byCountry.size) { directory.innerHTML = '<div class="coach-empty">Aucun championnat ne correspond aux filtres.</div>'; return; }
    directory.innerHTML = [...byCountry.entries()].sort((a,b)=>a[0].localeCompare(b[0])).map(([country, ls]) => {
      const fed = FEDERATIONS[country] || ['🌐',country,country,'International'];
      const teamsTotal = ls.reduce((n,l)=>n+leagueTeams(l).length,0);
      const leaguesHtml = ls.sort((a,b)=>a.level-b.level || a.gender.localeCompare(b.gender) || a.name.localeCompare(b.name)).map(l => {
        const teams = leagueTeams(l).filter(t => !state.search || matchSearch([t,l.name,country]) || linkedRecords(t,state.season).some(r=>matchSearch([r.name,r.role,r.team])));
        if (!teams.length && state.search) return '';
        const teamHtml = teams.map(team => {
          const staff = linkedRecords(team,state.season);
          const staffHtml = staff.length ? staff.map(personHtml).join('') : '<div class="coach-person-card"><div class="coach-role">Staff public vérifié non encore rattaché pour cette saison.</div><div class="coach-source-line">AquaMetric laisse les noms vides plutôt que de reconduire un staff N-1 sans preuve.</div></div>';
          return `<details class="coach-team"><summary><span class="coach-team-name">${esc(team)}</span><span class="coach-team-meta">${staff.length ? `${staff.length} sourcé${staff.length>1?'s':''}` : 'staff à vérifier'} · ouvrir</span></summary><div class="coach-team-body">${staffHtml}${roleGroupsHtml()}</div></details>`;
        }).join('');
        return `<section class="coach-league"><div class="coach-league-head"><div class="coach-league-title"><h3>${esc(l.name)} · ${l.gender==='Women'?'Femmes':'Hommes'} · D${l.level}</h3><small>${teams.length} club${teams.length>1?'s':''} · ${state.season}${l.source ? ` · <a class="coach-source-link" href="${esc(l.source)}" target="_blank" rel="noopener">source fédérale</a>`:''}</small></div>${statusBadge(l.currentStatus,state.season)}</div><div class="coach-teams">${teamHtml}</div></section>`;
      }).join('');
      return `<article class="coach-federation"><header class="coach-federation-head"><div class="coach-fed-title"><span class="coach-flag">${fed[0]}</span><div><h2>${esc(fed[1])}</h2><small>${esc(country)} · ${esc(fed[2])} · ${esc(fed[3])}</small></div></div><div class="coach-fed-meta">${ls.length} championnat${ls.length>1?'s':''}<br>${teamsTotal} clubs</div></header><div class="coach-leagues">${leaguesHtml}</div></article>`;
    }).join('');
  }

  function coveredNationalGenders(country) {
    return [...new Set(records
      .filter(r => r.team_type === 'national_team' && recordSeason(r.season) === state.season && nationalCountry(r) === country)
      .map(nationalGender)
      .filter(Boolean))];
  }

  function renderNational() {
    const countries = availableCountries().filter(c => (state.country==='all'||c===state.country) && (!state.search || matchSearch([c,(FEDERATIONS[c]||[]).join(' ')])));
    const totalTeams = countries.reduce((sum, country) => {
      const genders = state.gender === 'all' ? coveredNationalGenders(country) : [state.gender];
      return sum + genders.length * NATIONAL_CATEGORIES.length;
    }, 0);
    const displayedGenders = new Set(countries.flatMap(country => state.gender === 'all' ? coveredNationalGenders(country) : [state.gender]));
    const sourced = records.filter(r =>
      r.team_type === 'national_team' &&
      recordSeason(r.season) === state.season &&
      (state.country === 'all' || nationalCountry(r) === state.country) &&
      (state.gender === 'all' || nationalGender(r) === state.gender)
    ).length;
    kpis.innerHTML = `<div class="coach-kpi"><strong>${countries.length}</strong><span>Fédérations nationales</span></div><div class="coach-kpi"><strong>${displayedGenders.size}</strong><span>Genres couverts</span></div><div class="coach-kpi"><strong>${totalTeams}</strong><span>Sélections / catégories</span></div><div class="coach-kpi"><strong>${sourced}</strong><span>Staffs sourcés en base</span></div>`;
    note.innerHTML = `<b>Équipes nationales :</b> seuls les pays et genres disposant d'au moins un staff sourcé pour la saison sélectionnée sont proposés. Aucun pays théorique ou non couvert n'est ajouté au déroulant.`;
    if (!countries.length) { directory.innerHTML='<div class="coach-empty">Aucune fédération nationale couverte ne correspond aux filtres.</div>'; return; }
    directory.innerHTML = countries.map(country => {
      const fed=FEDERATIONS[country]||['🌐',country,country,'International'];
      const genders = state.gender === 'all' ? coveredNationalGenders(country) : [state.gender];
      const cards = genders.map(g => {
        const teamLabel = `${country} — ${g==='Women'?'Women':'Men'} Senior`;
        const staff = linkedRecords(teamLabel,state.season,'national_team');
        const staffHtml = staff.length ? staff.map(personHtml).join('') : '<div class="coach-source-line">Head coach et staff : validation saison/compétition en attente dans la base.</div>';
        return `<div class="coach-national-card"><h3>${g==='Women'?'Femmes':'Hommes'}</h3><small>${esc(state.season)} · senior + jeunes</small>${staffHtml}<div class="coach-national-categories">${NATIONAL_CATEGORIES.map(c=>`<span>${esc(c)}</span>`).join('')}</div></div>`;
      }).join('');
      return `<article class="coach-federation"><header class="coach-federation-head"><div class="coach-fed-title"><span class="coach-flag">${fed[0]}</span><div><h2>${esc(country)}</h2><small>${esc(fed[1])} · ${esc(fed[2])}</small></div></div><div class="coach-fed-meta">National teams<br>${esc(fed[3])}</div></header><div class="coach-league"><div class="coach-national-grid">${cards}</div></div></article>`;
    }).join('');
  }

  function render() { state.view === 'national' ? renderNational() : renderClubs(); }

  app.querySelectorAll('[data-season]').forEach(btn => btn.addEventListener('click', () => {
    state.season = btn.dataset.season;
    app.querySelectorAll('[data-season]').forEach(x=>x.classList.toggle('is-active',x===btn));
    countryOptions();
    render();
  }));
  app.querySelectorAll('[data-view]').forEach(btn => btn.addEventListener('click', () => {
    state.view = btn.dataset.view;
    app.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('is-active',x===btn));
    countryOptions();
    render();
  }));
  countrySelect.addEventListener('change',()=>{state.country=countrySelect.value;render();});
  genderSelect.addEventListener('change',()=>{state.gender=genderSelect.value;countryOptions();render();});
  searchInput.addEventListener('input',()=>{state.search=searchInput.value;render();});

  countryOptions();
  render();
})();
