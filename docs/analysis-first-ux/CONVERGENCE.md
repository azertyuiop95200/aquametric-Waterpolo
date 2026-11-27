# Programme de convergence AquaMetric — 27 novembre 2026
Objectif : une seule application analyse-first, rapport sportif complet et traçable à partir de vidéo réelle. La V2 locale est une référence de présentation, pas une preuve d'exhaustivité.
## Responsabilités et interfaces
| Agent | Producteur responsable | Livrable consommable |
|---|---|---|
| Ultimate | Référence annotée, événements, possessions, arbitrage, phases | registre Q1 versionné avec temps vidéo, période, couleurs, identifiants, preuves et couverture ; PR43 |
| Amélioration continue | vision, horloge, suivi ballon/joueuses, calibration | pistes et événements candidats horodatés, identité et état de mesure, erreurs contre référence ; feature/continuous-match-2026, feature/elite-performance-2026 |
| PoloIQ statistiques avancées | définitions et calculs | catalogue atomique avec unité, formule, dénominateur, n, preuve, statut et tests ; stats-advanced ; contrats PR42 |
| Intégration UX | consolidation, contrats et restitution | snapshot commun, interface, HTML/PDF/JSON/CSV cohérents ; PR44, correctif PR45 |
| Prêt à analyser | validation indépendante et livraison | CI même SHA, parcours mobile et desktop, import, reprise, stockage et preuve de version Render ; PR40 |
Ne pas modifier les tâches des autres agents sans mandat distinct. Lire leurs journaux, prendre des lots disjoints, identifier le propriétaire d'un fichier partagé, ne pas écraser les branches. Aucune vidéo privée ni secret dans le dépôt.
## Baseline vérifiée
PR40 223acdac : CI 45671881354 succès, mobile 45671881269 échec. PR41 80dba6e9 : CI et mobile succès. PR42 bbd7a5de : audit 45896726241 succès. PR43 1b6f8769 : possessions 46001444514 succès. PR44 322183bb : CI 46003529429 et mobile 46003529306 en cours. PR45 1c75e879 : 438 tests Python réussis, deux avertissements, mobile échec (run 45987992349, job 140468387004). Toutes les PR signalées fusionnables séparément, aucune intégrée ; ce n'est pas une validation commune.
Rapport Q1 : deux segments privés accessibles via Drive GWP-CNM, durée source déclarée 791,72 s, 793 images échantillonnées ; tableau physique 0–7 observé, attribution aux clubs non confirmée. V2 locale 5 pages, onze lignes sportives comparatives non mesurées. Ne pas traiter les indices visuels comme du temps de jeu. Source et chronologie : vérifier PTS/offset sur jointure, aucune double comptabilisation.
## Jalons ordonnés (travaux indépendants en parallèle)
1. P0 accès et pipeline : terminer PR45, valider PR40 sur même SHA, import local/URL autorisée, deux parties, progression, arrêt et rapport partiel, reprise, erreurs lisibles. Test navigateur inchangé ; stockage persistant vérifié en environnement isolé, sans frais ni production.
2. P0 référentiel Q1 : fixer hash/segments/PTS, mapping couleurs par preuve, horloge de jeu distincte de vidéo, registre événements/possessions/phases avec couverture par intervalle, relecture indépendante. Livrable privé portable conforme au contrat review_reference_import; ne pas promouvoir automatiquement une référence partielle en événement confirmé.
3. P0 consolidation : créer branche d'intégration depuis base commune après vérification des dépendances ; PR42 et 43 ciblent elite-performance, PR41 et 44 main. Comparer source/main.py, services/analysis_product.py, templates/analysis_all_measurements.html, templates/analysis_result_clean_v2.html et scripts d'intégration ; résoudre les conflits par conservation des contrats, pas par remplacement intégral. Ajouter test de snapshot commun avec tous les producteurs ; préserver JSON/ZIP, contrôles d'accès, données, migrations réversibles. Aucun merge non validé.
4. P1 vision : détection dynamique du tableau, stabilisation caméra, suivi ballon et joueuses, identité équipe+bonnet, continuité et calibration. Comparer précision/rappel/F1 pour actions annotées, erreurs horloge/distance, taux d'identification, couverture par famille, latence. Mesurer séparément la qualité de référence et celle du modèle. Choisir seuils avant évaluation ; pas de score global arbitraire.
5. P1 statistiques : réconcilier score et événements, tirs distincts des contres, passes uniques, possessions appariées, arrêts, exclusions, transitions, phases numériques, jeu sans ballon et physique. Toute statistique dérivée a unité, dénominateur, n, provenance, scope et état. Zéro échantillonné distinct de non mesuré, estimation, simulation ; ne pas convertir une référence externe en preuve vidéo.
6. P1 rapport : synthèse sportive, chronologie, comparaison, possessions, tirs, passes, gardiennes, défense, discipline, transitions, 6v5/5v6, rotations, cartométrie, jeu sans ballon, tactique, individuel, 3D conditionnelle, recommandations sourcées, annexe. Un snapshot canonique alimente interface et exports. Cartes calibrées uniquement, pas de notes composites ni classement. Test identité des valeurs exportées, navigation accessible, impressions et mobile.
7. P2 validation Q1 : produire rapport avec vrai moteur intégré ; comparer indépendamment chaque famille, audit visuel et scientifique, corriger, rejouer la même référence et documenter différences. Rapport partiel disponible dès le premier lot de données validé, sans attendre toutes les fonctions.
8. P2 validation match entier : quatre périodes, contrôle de couverture, plusieurs matchs distincts, performance et persistance ; sauvegarde/restauration vérifiée puis déploiement de validation autorisé. Version et SHA vérifiés avant livraison ; aucun engagement de frais.
## Contrat commun minimal
Pour chaque observation : match_id, period, segment_id, temps_video_s et/ou intervalle, horloge_jeu_s nullable, side/color et player_id nullable, action_id stable, source, état (candidat/confirmé/référence), preuve, version de calibration. Pour chaque métrique : key, value nullable, unit, denominator nullable, sample_n, scope, state, evidence_ids, limitation. Conserver les données historiques ; adaptateurs versionnés plutôt qu'une migration destructive.
## Registre de blocages
| ID | Symptôme/preuve | Responsable | Solution/prochain test | État |
|---|---|---|---|---|
| B01 | PR45 job 140468387004 : Wrong YouTube button remains visible, analysis_buttons_browser.cjs:27 ; JS hidden=true mais .btn display:inline-flex | UX | d774958 : #analysisForm [hidden] display:none!important ; rejouer Chromium sans supprimer assertions | corrigé dans code, CI à valider |
| B02 | PR42/43 et PR44 modifient contrats partagés | UX + producteurs | consolidation testée, snapshot commun et exports | ouvert |
| B03 | Q1 V2 données sportives insuffisantes | Ultimate + vision | référence privée, annotation par famille et comparaison | ouvert |
| B04 | pixels/caméra confondus avec activité sportive | amélioration continue | stabilisation et horloge réelle, test contre annotation | ouvert |
| B05 | stockage/worker/Render non vérifiés | prêt à analyser + UX | workspace confirmé, sauvegarde, test persistance isolé | ouvert |
## Boucle horaire
Chaque agent lit le plan et ses journaux ; choisit un lot avec critères de sortie ; mesure baseline, code, teste, produit un rapport ou export partiel si applicable, audite, corrige, reteste, consigne SHA/commandes/logs/artefact, dépendances et prochaine action. Aucun résultat de test anticipé. L'intégrateur consolide les handoffs, ne répète pas les mêmes tâches en échec sans alternative.

## Ordre prioritaire confirmé par l'utilisateur — V3.1 (27/11/2026)
1. Résoudre les conflits V3 et conserver les travaux récents : PR47 synchronisée avec 24ce9aa ; merge 9af6790 sur branche V3 seulement ; 17 commits manquants ramenés à 0. Valider le nouveau SHA, pas uniquement l'ancien résultat 259 tests.
2. Récupérer les annotations et résultats privés des agents via dossier Drive de passation autorisé ; vérifier relecture, SHA256 et provenance ; aucun fichier privé dans GitHub public.
3. Réunir les modules statistiques et les moteurs vidéo dans un snapshot commun ; tester les routes HTTP propriétaire/tiers, exports et erreurs.
4. Améliorer la reconnaissance du ballon et des joueuses sur référence indépendante ; mesurer précision, rappel, continuité et erreurs d'identité.
5. Valider la calibration dynamique et ses repères indépendants, avec incertitude et contrôle des changements de caméra.
6. Calculer déplacements, vitesses, rotations et temps de jeu uniquement dans leur domaine validé ; distinguer temps vidéo observé et temps réglementaire.
7. Intégrer cartographies, tirs, réseaux de passes et géométrie 3D conditionnelle ; conserver les limites et preuves.
8. Produire V3.1 avec le moteur réellement intégré sur GWP-CNM Q1, même partiel ; aucune statistique inventée.
9. Auditer lisibilité, exhaustivité, attribution, unités, dénominateurs et cohérence des exports ; corriger et rejouer.
10. Valider puis déployer progressivement, avec sauvegarde, contrôle du SHA live et parcours réel autorisé ; ne pas fusionner une PR non validée. Les agents poursuivent les tâches indépendantes en parallèle, sans franchir un jalon dépendant non validé.
Suivi : chaque cycle relire ce registre et le ROADMAP ; mettre à jour preuves, état, propriétaire, blocage et prochaine action. Aucun cycle ne remplace le rapport sportif par le seul nombre de tests.
