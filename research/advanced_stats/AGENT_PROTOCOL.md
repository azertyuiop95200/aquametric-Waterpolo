# AquaMetric — protocole autonome statistiques avancées v1
Responsable : agent statistiques. Branche d'intégration isolée : stats-advanced.
Ne jamais écraser main, forcer un push, modifier le travail concurrent sans comparaison ni déployer sans validation. Les autres agents gardent leur périmètre. Lire main et les branches pertinentes à chaque cycle. Préparer une PR ciblée lorsque les tests et contrats sont validés ; ne pas fusionner automatiquement en cas de conflit.

## Boucle horaire (reprendre depuis le journal)
1. Lire HEAD, journal, différences depuis dernier cycle, architecture réelle, contrats, tests et rapports existants. Inventorier les métriques par identifiant stable, repérer doublons et lacunes.
2. Choisir un lot limité : priorité aux dépendances bloquantes, puis impact coaching, risque d'erreur, couverture, faisabilité. Justifier le choix. Ne pas refaire un lot déjà validé sans régression.
3. Rechercher les règlements World Aquatics applicables à la compétition/date, littérature scientifique, fournisseurs de stats et benchmarks. Consigner URL, version/date, limites, licence. Distinguer normes, hypothèses et mesures.
4. Spécifier par métrique : identifiant, définition, unité, entrées, formule, fenêtres, attribution, dénominateur, événements exclus, seuils configurables, qualité/calibration, minimum d'observation, incertitude, statut, exemples, visualisation.
5. Implémenter code réel compatible avec le pipeline, tests unitaires, cas limites, fixtures synthétiques étiquetées. Ne pas inventer données ni confondre null et zéro. Valider dimensions, temps, possession, identité, occultations, doublons, changement de période et de côté.
6. Exécuter tests et analyser échecs. Corriger, rejouer ; vérifier non-régression et comparer aux annotations humaines si accessibles (précision/rappel/F1 pour événements, MAE et biais pour mesures, calibration des probabilités, couverture, erreurs par contexte). Ne pas prétendre avoir exécuté des tests non exécutés. Quantifier incertitude et expliciter échantillon.
7. Raccorder calcul -> schéma/API -> export -> interface -> rapport par joueuse/équipe/période/phase. Tester parcours import vidéo et URL si environnement le permet, sans inventer résultats. Montrer valeurs manquantes et sources. Séparer observation de prédiction.
8. Auto-audit contradictoire : rechercher faux positifs, biais de caméra et d'identité, doubles comptes, métriques redondantes, fuites de données, dénominateurs erronés, surinterprétation. Corriger ou rétrograder le statut.
9. Enregistrer modifications et résultats sur branche dédiée (commits ciblés), préparer PR lorsque prêt. Rédiger journal durable par cycle : date, SHA de base et résultat, fichiers, métriques et statut, commandes et résultats réels, blocages, prochain lot et critères. Si accès manquant, signaler et produire un livrable portable. Si cycle précédent actif, éviter écritures concurrentes ; utiliser branche de travail isolée.
10. Reprendre au prochain cycle depuis ce journal ; recalculer la priorité et enrichir le registre à chaque découverte. Pas de pourcentage d'avancement inventé.

## Registre initial de domaines (à décomposer en identifiants atomiques)
| Domaine | Familles à recenser et implémenter | Prérequis |
|---|---|---|
| P0 données | calibration métrique, horodatage, tracking, identité, confiance, occlusions, temps de jeu, rotations, possession, phase, côté, score, force numérique | vidéo, règles, événements |
| P1 événements | tirs (zone, type, issue), buts, passes, pertes, récupérations, contres, interceptions, exclusions, penalties, fautes, arrêts, remises, engagements | événements attribués |
| P1 mouvement | distance, vitesse, accélération/décélération, sprints, changements de direction, temps actif observé, densité, trajectoires, cartes de chaleur, occupation, dispersion | calibration et suivi |
| P1 sans ballon | appels, démarquages, permutations, séparation, soutien, espaces créés, courses utiles, disponibilité de passe | suivi et possession |
| P1 défense | proximité, rapprochement, temps sous pression, lignes obstruées, aide, compacité, couverture, récupérations sous pression | suivi et ballon |
| P1 duels/pointe | durée, distance, issue, réception, conservation, position, exclusions et fautes provoquées, assistance | suivi + événements |
| P1 transitions | délai projection/repli, distance, vitesse, surnombre, temps de stabilisation, efficacité | possession, phases |
| P1 gardiennes | placement, angles 2D et 3D si calibrés, distance, réaction estimée, arrêts, rebonds, relances, performance selon qualité du tir | but, ballon, tirs, suivi |
| P1 situations spéciales | supériorité/infériorité, égalité, penalties, passes, vitesse circulation, décalages, conversion, efficacité défensive | règles et effectifs |
| P2 création | xG/xA calibrés sur données annotées, passes dangereuses, progression, qualité des occasions, contribution à la possession | jeu de données et validation hors match |
| P2 tactique | réseaux de passes, occupation des couloirs, largeur/profondeur, options réalisables, synchronisation, soutien, anticipation observable | suivi multi-joueurs |
| P2 3D | angles, obstacles, trajectoires et options contrefactuelles avec intervalles, distinction plan de surface / hauteur | calibration 3D ou hypothèses explicites |
| P2 discipline | localisation, type, conséquence, répétition, coût tactique et exclusions | événements et règles |
| P2 rendement | par minute réellement jouée, poste, phase, force numérique, adversaire et contexte, normalisation et taille échantillon | temps de jeu fiable |
| P3 rapport | synthèse coach, chronologie synchronisée, carte/graphique/table, filtres, fiches individuelles, comparaisons, export, qualité des données | contrats validés |

## Statuts et barrières
Inventorié -> spécifié -> codé -> tests synthétiques exécutés -> validé sur annotations réelles -> intégré et testé bout en bout -> prêt pour revue. Les étapes ne sont jamais implicites. Un proxy de proximité n'est pas une preuve d'intention ou d'efficacité. Pas de mesure physiologique (fatigue, charge interne) par pixels seuls. Pas de reconstruction 3D exacte depuis une caméra monoculaire sans hypothèses et validation. Un modèle xG non entraîné/calibré reste un score heuristique et ne doit pas être présenté comme probabilité validée.

## Point de départ
Le prototype spatial_metrics.py est enregistré au commit 57b416fde584f6144df6b099856594c573764b22 ; ses six assertions sont écrites mais leur exécution n'a pas été confirmée. Premier lot : exécuter les tests, ajouter cas limites, inspecter l'architecture applicative réelle, recenser le registre atomique et établir le contrat de données ; rechercher les références avant de valider des seuils. Aucun déploiement public confirmé.
