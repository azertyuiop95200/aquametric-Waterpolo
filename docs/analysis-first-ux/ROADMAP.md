# AquaMetric — feuille de route analyse-first
Date initiale : 2026-11-27. Branche : feature/analysis-first-ux.
But : un outil d'analyse water-polo simple à utiliser, sans classement ni scoring composite dans le parcours principal. Conserver les scores réels, la compatibilité des données, l'isolation des utilisateurs et les travaux des agents.

## Programme et critères de sortie
| Étape | Livraison | Validation |
|---|---|---|
| 1 | Menu réduit, accueil analyse, accès par match | 6 destinations, aucun lien classement/recrutement/simulation dans le menu et l'accueil ; routes réelles ; état actif non ambigu ; mobile et 5 langues |
| 2 | Import unique URL/vidéo locale | fichier autorisé et URL valide, taille et erreur explicites, reprise, absence de perte silencieuse |
| 3 | Pilotage analyse | démarrer, progression réelle, arrêt, finalisation partielle, reprise, rapport accessible, test des échecs |
| 4 | Statistiques | événements, joueuses, équipes, gardiennes, possessions, unités et provenance ; zéro distinct de non mesuré |
| 5 | Cartométrie et temps | suivi, calibration, temps de jeu, distances, zones, incertitude et contrôle sur annotations |
| 6 | Tactique | phases, espaces, transitions, 6v5/5v6, pression et jeu sans ballon ; preuves vidéo |
| 7 | Géométrie 3D | angles, alternatives de passes/tirs, hypothèses de reconstruction et incertitude ; simulation explicitement signalée |
| 8 | Rapport | résumé, sections détaillées, filtres, preuves, exports cohérents, valeurs absentes signalées |
| 9 | Optimisation | profilage, latence, mémoire, traitement asynchrone, stockage durable et récupération ; avant/après mesuré |
| 10 | Validation intégrée | tests Python, sécurité, Docker, mobile, CI, aperçu déployé ; aucune régression critique |
| 11 | Matchs réels | annotations humaines et comparaison des mesures sur matchs distincts, couverture et erreurs documentées |
| 12 | Maintenance | régression, suivi des PR, optimisation mesurable et journal de reprise |

## Boucle horaire
Lire ce document, le dernier commit et les PR concurrentes ; identifier le plus petit lot à fort impact ; développer et tester ; documenter les preuves et limites ; corriger ; pousser sur branche dédiée et mettre à jour la PR/journal. Si un blocage empêche le lot, traiter une tâche indépendante. Ne pas écraser les autres branches ni fusionner ou déployer sans validation. Ne jamais fabriquer de résultats.
Agents partenaires : statistiques avancées (stats-advanced), Ultimate, amélioration continue (feature/continuous-match-2026, feature/elite-performance-2026), validation Render. Vérifier leurs changements et éviter les conflits.

## Journal — étape 1
- Audit de main : FastAPI + Jinja, 22 liens de navigation, accueil avec raccourcis classement/scouting/simulation ; routes individuelles statistiques/tactique/rapport existantes ou utilisées par les pages existantes.
- Modifications : base.html (6 liens, aria-current, icônes décoratives), dashboard.html (flux analyse, suppression des raccourcis hors sujet, accès aux équipes conservé), matches.html (liens directs par rencontre), i18n.js (5 locales).
- Tactique dans la navigation mène provisoirement à la base de connaissances ; l'analyse tactique propre au match est accessible dans la liste des matchs. Les rapports restent accessibles depuis l'historique et la liste.
- Les routes historiques restent intactes. Pas de suppression de données, pas de modification des autorisations, pas de déploiement.
- À vérifier : tests de rendu Jinja, menu mobile, traductions, CI existante et éventuels scripts d'intégration qui réécrivent les templates ; ouverture réelle des routes avec match propriétaire. Ne pas déclarer l'étape terminée avant ces validations.
- Étape suivante après validation : audit du formulaire /matches/new, parcours URL/local et erreurs bucket/worker.
