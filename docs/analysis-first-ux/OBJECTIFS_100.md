# Objectifs 100 % — AquaMetric, référentiel v1
Date de référence : 28/11/2026. Mandat : [DELIVERY_REPORT_FIRST.md](DELIVERY_REPORT_FIRST.md). Suivi périodique : [SUIVI_AGENTS.md](SUIVI_AGENTS.md).

## Règles de mesure
Chaque agent a 10 jalons d'acceptation de 10 points chacun. 100 points = 100 % de ses livrables convenus, pas 100 % de précision du modèle ni 100 % des événements observables. Les jalons intermédiaires techniques comptent comme tels, jamais comme validation sportive. Les pondérations sont une convention de pilotage choisie pour être simple, non une estimation du temps restant. Le total global = nombre de jalons validés / 50 × 100 ; agents à poids égal. Un jalon n'est crédité que si **toutes** ses conditions sont satisfaites et une preuve traçable existe ; sinon 0 point, avec état en cours/bloqué/non vérifié. Pas de pourcentage subjectif. Ne pas augmenter le score sur un commit, une promesse, un candidat ou un test non exécuté. Une régression invalide le jalon et peut réduire le score ; journaliser la raison. Chaque preuve précise date, branche/SHA, scope (branche, production, fixture, vidéo réelle), test ou rapport et limites. Pas de double comptage à l'intérieur d'un rôle. Les preuves peuvent être communes entre métiers (livraison vs vérification indépendante). Les agents ne modifient pas les poids ou critères sans décision explicite de l'utilisateur et nouvelle version du référentiel.
Pour la précision sportive, publier séparément couverture vidéo et par famille, précision/rappel/F1, taux d'identités correctes, erreur temporelle et métrique, n, dénominateurs et incertitude sur référence indépendante. Avant évaluation, définir et justifier des seuils d'acceptation par famille et compétition, avec jeu de contrôle réservé ; ne jamais déduire ces seuils des résultats de test. Les zones hors champ ou données intrinsèquement impossibles restent explicites et ne sont pas assimilées à zéro. 100 % de livraison ne peut être déclaré avant validation du rapport complet sur match réel et vérification des autres jalons.

## I — Intégration et événements (20/100 au départ)
| ID | Critère d'acceptation (10 points) | État initial / preuve |
|---|---|---|
| I01 | Mandat commun, responsabilités exclusives et plan de convergence versionnés | VALIDÉ — [mandat](DELIVERY_REPORT_FIRST.md) |
| I02 | Lots 1–8 intégrés sans perte des rapports partagés ; CI positive et SHA de production confirmé | VALIDÉ — [PR58](https://github.com/azertyuiop95200/aquametric-Waterpolo/pull/58), [CI](https://github.com/azertyuiop95200/aquametric-Waterpolo/actions/runs/46074577789), Render c6ee727 |
| I03 | Producteurs V3/branches utiles réconciliés sur base actuelle par lots compatibles, CI commune et conflits résolus | À valider |
| I04 | Événements tirs, buts, arrêts, fautes, exclusions et attributions issus de Q1 persistés avec sources et états, comparés à référence | À valider |
| I05 | Possessions, changements de contrôle, passes, réceptions et transitions réconciliés sur Q1 sans doubles comptes | À valider |
| I06 | Périodes, horloge, rotations, phases numériques et temps de jeu validés sur Q1 | À valider |
| I07 | Analyse lancée par l'utilisateur exécute automatiquement les producteurs disponibles, persiste et remplit le snapshot sans saisie redondante ; test non vide sur vidéo | À valider |
| I08 | Rapport Q1 entier généré par le moteur commun, toutes familles renseignées quand mesurables, manques motivés, export contrôlé | À valider |
| I09 | Quatre périodes réconciliées sur match complet avec données et couverture par famille, validation indépendante | À valider |
| I10 | Version finale déployée après QA, sauvegarde/restauration si nécessaire, SHA exact, vrai parcours import -> rapport et exports vérifiés | À valider |

## V — Vision et calibration (20/100 au départ)
| ID | Critère d'acceptation (10 points) | État initial / preuve |
|---|---|---|
| V01 | Deux clips Q1 accessibles et décodés sur des extraits, caractéristiques techniques et jointure déclarées documentées (pas PTS intégral) | VALIDÉ — [journal lot7](https://github.com/azertyuiop95200/aquametric-Waterpolo/blob/stats-advanced/research/advanced_stats/journal/2026-11-27-release7-predecision-motion.md) |
| V02 | Pilote de tracking réel avec références visuelles, absences incluses, erreurs en pixels et limites | VALIDÉ — [pilote Q1](https://github.com/azertyuiop95200/aquametric-Waterpolo/blob/stats-advanced/research/advanced_stats/journal/2026-11-27-real-video-pilot.md), 50 contrôles, non indépendant |
| V03 | Décodage Q1 entier, PTS et offsets contrôlés, jointure sans doublon et inventaire des lacunes | À valider |
| V04 | Benchmark indépendant stratifié de détection des joueuses : seuils fixés avant essai, précision/rappel/F1 et faux positifs | À valider |
| V05 | Suivi continu et réidentification des pistes sur Q1, occultations/coupes, continuité et erreurs contrôlées | À valider |
| V06 | Détection et suivi du ballon sur Q1, occultations, erreurs temporelles et spatiales sur référence | À valider |
| V07 | Identités équipe+bonnet, gardiennes, changements de côté ; taux correct et non attribués sur référence | À valider |
| V08 | Calibration dynamique validée en mètres sur repères indépendants, dimensions établies, erreur et incertitude | À valider |
| V09 | Chronomètre, temps actif et coupures détectés et validés contre référence ; distinction temps vidéo/jeu | À valider |
| V10 | Pipeline vision intégré, observations horodatées persistées et consommables automatiquement pour match complet et contrôle de généralisation | À valider |

## S — Statistiques et restitution (40/100 au départ)
| ID | Critère d'acceptation (10 points) | État initial / preuve |
|---|---|---|
| S01 | Registre atomique initial versionné avec identifiants, unités, calculs et états (pas inventaire exhaustif) | VALIDÉ — [registre V1](https://github.com/azertyuiop95200/aquametric-Waterpolo/blob/stats-advanced/research/advanced_stats/METRIC_REGISTRY_V1.md) |
| S02 | Cinématique et occupation/cartes intégrées au rapport, cas non vides et absents testés sur fixtures | VALIDÉ — [PR49](https://github.com/azertyuiop95200/aquametric-Waterpolo/pull/49), CI lot8 |
| S03 | Collectif, pression, soutien, pointe, gardienne, repli et tirs/arrêts reliés au rapport, test HTTP calibré synthétique | VALIDÉ — [PR57](https://github.com/azertyuiop95200/aquametric-Waterpolo/pull/57), [CI](https://github.com/azertyuiop95200/aquametric-Waterpolo/actions/runs/46069045867) |
| S04 | Simulation 3D conditionnelle intégrée, hypothèses explicites, tests et rendu/export | VALIDÉ — [PR55](https://github.com/azertyuiop95200/aquametric-Waterpolo/pull/55), [CI](https://github.com/azertyuiop95200/aquametric-Waterpolo/actions/runs/46044377942), lot8 |
| S05 | Inventaire exhaustif de toutes les métriques existantes : producteur, clé, preuve, dénominateur, n, couverture, rendu et export | À valider |
| S06 | Statistiques de passes, possessions et phases numériques alimentées par événements réels Q1 validés, sans doublons | À valider |
| S07 | Temps de jeu, rotations, distances et vitesses par joueuse validés avec support et incertitude métrique sur Q1 | À valider |
| S08 | Calcul automatique de toutes les familles mesurables à partir des données persistées, sans ressaisie ; rapport réel non vide | À valider |
| S09 | Concordance de toutes les familles entre web, HTML, JSON, ZIP et CSV, cartes et graphiques inclus, valeurs nulles motivées | À valider |
| S10 | Rapport statistique complet de match réel validé indépendamment, seuils et erreurs par famille documentés | À valider |

## U — Parcours et UX (20/100 au départ)
| ID | Critère d'acceptation (10 points) | État initial / preuve |
|---|---|---|
| U01 | Navigation analyse-first réduite, sans classement/scouting, contrôlée sur branche UX mobile | VALIDÉ sur branche, pas déploiement — [CI44](https://github.com/azertyuiop95200/aquametric-Waterpolo/actions/runs/45959484994), [CI45](https://github.com/azertyuiop95200/aquametric-Waterpolo/actions/runs/46003924392) |
| U02 | Accès invité et ouverture rapport/export sur site, avec refus des accès non autorisés | VALIDÉ sur lot7, fixture URL sans analyse — [CI58](https://github.com/azertyuiop95200/aquametric-Waterpolo/actions/runs/46074577789) |
| U03 | Import local réel, fichier volumineux et plusieurs segments, sans perte silencieuse | À valider |
| U04 | Analyse d'une URL autorisée effectivement lue et traitée, sinon alternative claire sans contourner protections | À valider |
| U05 | Bouton démarrer, état et progression mesurés, erreurs explicites, statistiques incrémentales | À valider |
| U06 | Arrêt/finalisation partielle et reprise testés avec vidéo réelle et conservation des résultats | À valider |
| U07 | Stockage et traitement durables, récupération/sauvegarde/restauration testées sans risque ni frais non autorisés | À valider |
| U08 | Interface de revue minimale, manques motivés et réutilisation des données déjà extraites sans doublons | À valider |
| U09 | Parcours intégré sur SHA commun, mobile/tablette/desktop, accessibilité et navigation vérifiées | À valider |
| U10 | Entraîneur peut analyser un match réel et lire son rapport organisé, cartes et export, sans assistance technique | À valider |

## Q — Validation indépendante (20/100 au départ)
| ID | Critère d'acceptation (10 points) | État initial / preuve |
|---|---|---|
| Q01 | Suite de régression, compilation, rendus stricts et tests positifs/négatifs sur lot8 exact réussis | VALIDÉ — [CI58](https://github.com/azertyuiop95200/aquametric-Waterpolo/actions/runs/46074577789), 144 tests calcul |
| Q02 | Véritables handlers HTTP sur base isolée et données synthétiques calibrées : persistance/relecture, exports, accès tiers, calibration périmée | VALIDÉ — [CI58](https://github.com/azertyuiop95200/aquametric-Waterpolo/actions/runs/46074577789), 2 tests HTTP |
| Q03 | Vérifier le SHA courant en ligne ET le vrai parcours de rapport/export de cette version sur Ultimate | À valider (lot8 live, smoke du lot7 seul dans CI58) |
| Q04 | Référence Q1 indépendante, protocole d'annotation, relecture et accord inter-annotateurs, seuils préfixés | À valider |
| Q05 | Benchmark vidéo stratifié, erreurs vision/identité/calibration/temps et couverture complète Q1 documentées | À valider |
| Q06 | Audit statistique par famille Q1, valeurs/dénominateurs/attribution comparés à référence, régressions corrigées et retestées | À valider |
| Q07 | Parcours réel de l'import Q1 à rapport et exports, comparaison des valeurs, droits et reprise | À valider |
| Q08 | Match entier puis au moins un autre match distinct, validation indépendante des familles et limites | À valider |
| Q09 | Tests intégrés mobile/desktop, sécurité, données absentes, gros fichiers et stockage/récupération sur SHA final | À valider |
| Q10 | Verdict de livraison final traçable, critères satisfaits sur données réelles et site live, régressions critiques fermées | À valider |

## Score initial
I 20 %, V 20 %, S 40 %, U 20 %, Q 20 % : 12 jalons validés sur 50, soit 24 % de progression des livrables. Ce n'est pas le taux de statistiques renseignées ni un délai de livraison. Les 38 jalons restants sont à valider, et certains disposent déjà de travaux partiels. Réévaluer avec preuve, pas avec impression.
## Actualisation
Chaque spécialiste transmet son état par ID (validé/en cours/bloqué/non vérifié), preuve, scope, delta de points, prochain jalon et blocage. Journal individuel sur sa branche ; seul intégration & événements met à jour SUIVI_AGENTS.md et le journal consolidé à chaque cycle. Les critères de ce fichier restent fixes. Ne pas publier de références vidéo privées ni de liens temporaires. Si un jalon ne peut être contrôlé, ne pas le créditer. Chaque changement de score exige une preuve et le détail des IDs concernés.
