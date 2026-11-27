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

## Journal — audit inter-agents et correction CI (27/11/2026)
- PR #44 est signalée fusionnable à la relecture (brouillon, non fusionnée). CI sur a029552 : 381 tests réussis, 4 échecs, 1 avertissement ; mobile bloqué à la suite Python avant navigateur. Sources : actions/runs/45955693120 et 45955693102.
- Corrections ciblées : 8c9fd8f (séances vidéo et traçabilité en pied de menu, hors six entrées principales), 1aa967c (référentiel tactique dans accueil), 428d047 (en-tête historique traduit), f259429 (ancien test exigeant simulation remplacé par contrat analyse-first + test explicite absence simulation/classement/scouting). Ne pas déclarer ces corrections validées avant nouvelle CI.
- PR #40 : CI Python réussie ; mobile échoue sur navigation **/my-team** après connexion (run 45671881269, job 139409051630). Reproduire redirection réelle puis corriger test/comportement sans masquer problème. Adapter également les assertions de défilement et clés i18n au menu réduit : vérifier absence de débordement inaccessible, et ne pas imposer un débordement sur un menu court. Conserver tests mobiles de navigation, langues, routes historiques utiles et fermeture du menu.
- PR #41 : CI et mobile réussies sur 80dba6e ; pas de validation sur vidéo réelle attestée. PR #42 et #43 : leurs workflows spécifiques réussis sur bbd7a5d et 1d8afef ; ne pas assimiler à validation intégrée ou sportive réelle. Toutes PR ouvertes. Pas de fusion/déploiement.
- Blocages transversaux : PR #40 mentionne stockage Render temporaire et moteur IA missing_key (log historique 31/10). Vérifier état actuel et sauvegarde ; ne pas exposer secrets. Priorité après CI : formulaire import, tests parcours complet, rapport réel ou fixture clairement étiquetée.
- Protocole commun par cycle : reproduire → développer → tester → générer rapport via moteur réel → auditer les familles, dénominateurs, attribution, temps, confiance, cartes et export → corriger cause racine → retester/régénérer → consigner métriques et preuves. Si vidéo inaccessible, fixture synthétique séparée et mention explicite. Pour chaque agent, noter défaut, preuve, correctif/PR, dépendance et prochaine action. Aucun rapport sportif généré pendant cet audit technique ; ne pas inventer de résultats.
