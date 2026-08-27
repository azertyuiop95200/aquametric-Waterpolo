(()=>{
const P={
'Dashboard':{fr:'Tableau de bord',it:'Dashboard',es:'Panel principal',ru:'Панель'},
'Analyze match':{fr:'Analyser un match',it:'Analizza partita',es:'Analizar partido',ru:'Анализировать матч'},
'Add player':{fr:'Ajouter une joueuse',it:'Aggiungi giocatrice',es:'Añadir jugadora',ru:'Добавить игрока'},
'Players':{fr:'Joueuses',it:'Giocatrici',es:'Jugadoras',ru:'Игроки'},
'Player profiles':{fr:'Fiches joueuses',it:'Profili giocatrici',es:'Perfiles de jugadoras',ru:'Профили игроков'},
'Saved matches':{fr:'Matchs enregistrés',it:'Partite salvate',es:'Partidos guardados',ru:'Сохранённые матчи'},
'Add match':{fr:'Ajouter un match',it:'Aggiungi partita',es:'Añadir partido',ru:'Добавить матч'},
'Imported fixtures & results':{fr:'Calendrier et résultats importés',it:'Calendario e risultati importati',es:'Calendario y resultados importados',ru:'Импортированные матчи и результаты'},
'Standings':{fr:'Classements',it:'Classifiche',es:'Clasificaciones',ru:'Таблицы'},
'Official source health':{fr:'État des sources officielles',it:'Stato delle fonti ufficiali',es:'Estado de las fuentes oficiales',ru:'Состояние официальных источников'},
'Training':{fr:'Entraînement',it:'Allenamento',es:'Entrenamiento',ru:'Тренировки'},
'2026–27 Calendar':{fr:'Calendrier 2026–27',it:'Calendario 2026–27',es:'Calendario 2026–27',ru:'Календарь 2026–27'},
'Next opponents':{fr:'Prochains adversaires',it:'Prossime avversarie',es:'Próximos rivales',ru:'Следующие соперники'},
'Granville roster':{fr:'Effectif Granville',it:'Rosa Granville',es:'Plantilla Granville',ru:'Состав Granville'},
'Elite women weekly plan':{fr:'Planning hebdomadaire Élite féminine',it:'Piano settimanale Élite femminile',es:'Plan semanal Élite femenino',ru:'Недельный план женской Elite'},
'Open full scouting':{fr:'Ouvrir le scouting complet',it:'Apri scouting completo',es:'Abrir scouting completo',ru:'Открыть полный скаутинг'},
'View scouting →':{fr:'Voir le scouting →',it:'Vedi scouting →',es:'Ver scouting →',ru:'Открыть скаутинг →'},
'Granville players observed in 2025–26':{fr:'Joueuses de Granville observées en 2025–26',it:'Giocatrici Granville osservate nel 2025–26',es:'Jugadoras de Granville observadas en 2025–26',ru:'Игроки Granville, наблюдавшиеся в 2025–26'},
'Final position':{fr:'Classement final',it:'Posizione finale',es:'Posición final',ru:'Итоговое место'},
'Vice-champion':{fr:'Vice-champion',it:'Vicecampione',es:'Subcampeón',ru:'Вице-чемпион'},
'Match workspace':{fr:'Espace du match',it:'Area partita',es:'Espacio del partido',ru:'Рабочая зона матча'},
'Tactical report':{fr:'Rapport tactique',it:'Rapporto tattico',es:'Informe táctico',ru:'Тактический отчёт'},
'What the verified evidence supports':{fr:'Ce que les preuves vérifiées permettent d’affirmer',it:'Cosa supportano le evidenze verificate',es:'Lo que respaldan las evidencias verificadas',ru:'Что подтверждают проверенные данные'},
'Highest evidence-supported player evaluations':{fr:'Meilleures évaluations joueuses fondées sur les preuves',it:'Migliori valutazioni supportate dalle evidenze',es:'Mejores evaluaciones respaldadas por evidencias',ru:'Лучшие оценки игроков по подтверждённым данным'},
'Detailed match evaluation':{fr:'Évaluation détaillée du match',it:'Valutazione dettagliata della partita',es:'Evaluación detallada del partido',ru:'Подробная оценка матча'},
'Zone+, Zone−, transition and structure':{fr:'Zone+, Zone−, transition et structure',it:'Zona+, Zona−, transizione e struttura',es:'Zona+, Zona−, transición y estructura',ru:'Зона+, Зона−, переходы и структура'},
'Open Tactical Chess →':{fr:'Ouvrir Tactique →',it:'Apri Tattica →',es:'Abrir Táctica →',ru:'Открыть тактику →'},
'Evidence-supported tactical remarks':{fr:'Observations tactiques appuyées par les preuves',it:'Osservazioni tattiche supportate dalle evidenze',es:'Observaciones tácticas respaldadas por evidencias',ru:'Тактические выводы по подтверждённым данным'},
'Replay the tactical moments':{fr:'Revoir les séquences tactiques',it:'Rivedi i momenti tattici',es:'Revisar los momentos tácticos',ru:'Пересмотреть тактические эпизоды'},
'Open moment':{fr:'Ouvrir la séquence',it:'Apri momento',es:'Abrir momento',ru:'Открыть эпизод'},
'No clip yet':{fr:'Pas encore d’extrait',it:'Nessun clip disponibile',es:'Aún no hay clip',ru:'Клип пока отсутствует'},
'What AquaMetric is not claiming':{fr:'Ce qu’AquaMetric ne prétend pas',it:'Cosa AquaMetric non afferma',es:'Lo que AquaMetric no afirma',ru:'Чего AquaMetric не утверждает'},
'Project the match — respect the level gap':{fr:'Projeter le match — respecter l’écart de niveau',it:'Proietta la partita — rispetta il divario di livello',es:'Proyectar el partido — respetar la diferencia de nivel',ru:'Прогноз матча с учётом разницы уровней'},
'Team A':{fr:'Équipe A',it:'Squadra A',es:'Equipo A',ru:'Команда A'},'Team B':{fr:'Équipe B',it:'Squadra B',es:'Equipo B',ru:'Команда B'},
'Plan A':{fr:'Plan A',it:'Piano A',es:'Plan A',ru:'План A'},'Plan B':{fr:'Plan B',it:'Piano B',es:'Plan B',ru:'План B'},
'Availability A':{fr:'Disponibilité A',it:'Disponibilità A',es:'Disponibilidad A',ru:'Доступность A'},'Availability B':{fr:'Disponibilité B',it:'Disponibilità B',es:'Disponibilidad B',ru:'Доступность B'},
'Form A':{fr:'Forme A',it:'Forma A',es:'Forma A',ru:'Форма A'},'Form B':{fr:'Forme B',it:'Forma B',es:'Forma B',ru:'Форма B'},
'Rest A':{fr:'Repos A',it:'Riposo A',es:'Descanso A',ru:'Отдых A'},'Rest B':{fr:'Repos B',it:'Riposo B',es:'Descanso B',ru:'Отдых B'},
'Venue':{fr:'Lieu',it:'Campo',es:'Sede',ru:'Место'},'Neutral':{fr:'Neutre',it:'Neutro',es:'Neutral',ru:'Нейтральное'},'Team A home':{fr:'Équipe A à domicile',it:'Squadra A in casa',es:'Equipo A local',ru:'Команда A дома'},'Team B home':{fr:'Équipe B à domicile',it:'Squadra B in casa',es:'Equipo B local',ru:'Команда B дома'},
'Factor breakdown':{fr:'Détail des facteurs',it:'Dettaglio dei fattori',es:'Desglose de factores',ru:'Разбор факторов'},
'Reality check':{fr:'Contrôle de réalisme',it:'Controllo di realismo',es:'Control de realismo',ru:'Проверка реалистичности'},
'What this forecast means':{fr:'Comment interpréter cette projection',it:'Come interpretare questa previsione',es:'Cómo interpretar esta proyección',ru:'Как понимать этот прогноз'},
'Current evidence':{fr:'Preuves actuelles',it:'Evidenze attuali',es:'Evidencias actuales',ru:'Текущие данные'},
'Affiliations':{fr:'Affiliations',it:'Affiliazioni',es:'Afiliaciones',ru:'Принадлежность'},
'Statistics by match':{fr:'Statistiques par match',it:'Statistiche per partita',es:'Estadísticas por partido',ru:'Статистика по матчам'},
'Aggregate evidence':{fr:'Données agrégées',it:'Evidenze aggregate',es:'Evidencias agregadas',ru:'Сводные данные'},
'Creation, centre play, duels and shot maps':{fr:'Création, jeu au centre, duels et cartes de tirs',it:'Creazione, gioco al centro, duelli e mappe di tiro',es:'Creación, juego de boya, duelos y mapas de tiro',ru:'Создание моментов, игра на центре, дуэли и карты бросков'},
'Pool shot origin':{fr:'Origine des tirs dans le bassin',it:'Origine dei tiri in vasca',es:'Origen de los lanzamientos en piscina',ru:'Зоны бросков в бассейне'},
'Goal target map':{fr:'Carte des zones visées dans le but',it:'Mappa delle zone bersaglio',es:'Mapa de zonas objetivo de la portería',ru:'Карта зон ворот'},
'Movement history':{fr:'Historique des mouvements',it:'Cronologia dei trasferimenti',es:'Historial de movimientos',ru:'История переходов'},
'What AquaMetric should find next':{fr:'Prochaines données à rechercher',it:'Dati da cercare successivamente',es:'Próximos datos a buscar',ru:'Какие данные искать дальше'},
'Evidence-based dimensions':{fr:'Dimensions fondées sur les preuves',it:'Dimensioni basate sulle evidenze',es:'Dimensiones basadas en evidencias',ru:'Показатели на основе данных'},
'Verified tagged actions':{fr:'Actions vérifiées et taguées',it:'Azioni verificate e taggate',es:'Acciones verificadas y etiquetadas',ru:'Проверенные размеченные действия'},
'Strengths supported by this sample':{fr:'Points forts soutenus par cet échantillon',it:'Punti di forza supportati dal campione',es:'Fortalezas respaldadas por la muestra',ru:'Сильные стороны по выборке'},
'Development review':{fr:'Axes de progression',it:'Aree di miglioramento',es:'Áreas de mejora',ru:'Зоны развития'},
'Recent attributed events':{fr:'Actions attribuées récentes',it:'Eventi attribuiti recenti',es:'Eventos atribuidos recientes',ru:'Последние привязанные события'},
'Coaching intelligence':{fr:'Intelligence entraîneur',it:'Analisi allenatori',es:'Inteligencia de entrenadores',ru:'Аналитика тренеров'},
'All coaches →':{fr:'Tous les entraîneurs →',it:'Tutti gli allenatori →',es:'Todos los entrenadores →',ru:'Все тренеры →'},
'Coach not confirmed':{fr:'Entraîneur non confirmé',it:'Allenatore non confermato',es:'Entrenador no confirmado',ru:'Тренер не подтверждён'},
'Loading verified coach records…':{fr:'Chargement des entraîneurs vérifiés…',it:'Caricamento allenatori verificati…',es:'Cargando entrenadores verificados…',ru:'Загрузка подтверждённых тренеров…'},
'Coach data unavailable':{fr:'Données entraîneur indisponibles',it:'Dati allenatore non disponibili',es:'Datos del entrenador no disponibles',ru:'Данные тренера недоступны'},
'Roster refresh required':{fr:'Mise à jour de l’effectif nécessaire',it:'Aggiornamento rosa necessario',es:'Actualización de plantilla necesaria',ru:'Требуется обновление состава'},
'Roster confirmation pending':{fr:'Confirmation de l’effectif en attente',it:'Conferma rosa in attesa',es:'Confirmación de plantilla pendiente',ru:'Подтверждение состава ожидается'},
'Players in the scouting file':{fr:'Joueuses du dossier de scouting',it:'Giocatrici nel dossier scouting',es:'Jugadoras del informe de scouting',ru:'Игроки в скаутинговом досье'}
};
const original=new WeakMap();
function lang(){return (window.AquaMetricI18n?.current?.()||document.documentElement.lang||'en').toLowerCase();}
function translateNode(node,l){
 if(!node.parentElement||node.parentElement.closest('script,style,code,pre,textarea,select,[data-i18n]'))return;
 if(!original.has(node))original.set(node,node.nodeValue);
 const src=original.get(node);const trimmed=src.trim();if(!trimmed)return;
 const tr=l==='en'?trimmed:P[trimmed]?.[l];if(!tr)return;
 const lead=src.match(/^\s*/)?.[0]||'',trail=src.match(/\s*$/)?.[0]||'';node.nodeValue=lead+tr+trail;
}
function apply(){const l=lang();const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n;while((n=walker.nextNode()))translateNode(n,l);}
window.addEventListener('aquametric:language',apply);new MutationObserver(()=>apply()).observe(document.body,{subtree:true,childList:true});apply();
})();
