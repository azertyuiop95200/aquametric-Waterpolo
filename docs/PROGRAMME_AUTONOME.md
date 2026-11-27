# Programme autonome AquaMetric Ultimate — journal de reprise
Ce document suit le développement, pas les données privées de match. Ne pas y copier les vidéos, annotations ou identités. Les données restent dans les archives privées.

## Point de reprise
- Étape 1 : référentiel temporel initial établi; décodage intégral et comparaison à l'original à vérifier.
- Étape 2 : annotation en cours, sous-étape 2.3 possessions. Les buts et tirs ont une référence partielle, pas de validation indépendante. Dernière archive locale : AquaMetric_Q1_etape2_3_v5.zip (si accessible); entrée Q1_import_reference_v5.json. Reprendre le registre existant, ne pas refaire les mêmes fenêtres.
- Étapes 3–12 : non validées. Le code préexistant ne vaut pas validation vidéo.

## Journal 2026-11-27 (première exécution autonome)
- Revue de nouvelles fenêtres du Q1; annotations révisées localement, pas d'injection dans les statistiques du site. Poursuivre la revue des gestes arbitraux, contrôles et erreurs techniques, puis les passes et exclusions. Le registre conserve les ambiguïtés.
- PR #43 : formulaire et moteur de possession, import de référence isolé, borne minimale disjointe hors tirs liés, distinction geste arbitral / décision confirmée, hypothèses séparées, remplacement explicite avec archive de l'ancienne référence, ZIP avec historique. La validation initiale à 69edfdc a 43 tests réussis; contrôler la dernière exécution CI après les modifications.
- PR #42 : audit statistique, mouvement et séquences, dernière CI réussie à bbd7a5d. PR #41 : simulateur 3D, dernière CI et mobile réussies à 80dba6e. Branches non fusionnées; #41 cible main et doit être adaptée à la branche elite, non fusionnée automatiquement.
- Production : branch feature/elite-performance-2026; Render gratuit et stockage temporaire. Pas de redémarrage avant sauvegarde vérifiée; pas de dépenses ou changement d'accès. L'import privé Q1 n'a pas encore été exécuté en production.
- Prochaines actions : 1 vérifier CI de #43 et corriger toute erreur; 2 tester import de deux révisions réelles localement si fichiers disponibles; 3 poursuivre revue possession/cause et lancer annotation des passes sur séquences déjà suffisamment visibles; 4 préparer consolidation non destructive des branches, contrôler les conflits et le risque de régression; 5 sécuriser sauvegarde/restauration.

## Critères des 12 étapes
1. PTS, empreintes, continuité et décodage.
2. Annotations, preuves, exhaustive revue et second observateur.
3. Détection avec précision/rappel sur données réservées.
4. Suivi : couverture, identités et pertes de piste.
5. Calibration : erreurs sur repères indépendants et horloges.
6. Reconnaissance : erreur temporelle et métriques par famille.
7. Registre des 112 indicateurs et autres pertinents : sources, dénominateurs, états et tests.
8. Cartographie cohérente avec trajectoires calibrées.
9. Scénarios 3D et probabilités avec validation indépendante.
10. Rapports HTML/PDF/export concordants, données manquantes explicites.
11. Site : import, analyse, rapport, sauvegarde/restauration et test complet.
12. Validation multi-match indépendante.
À chaque exécution, mettre à jour ce journal avec commits, résultats CI réellement observés et prochaines actions. Ne jamais présenter un test synthétique comme une mesure de match.

## Révision 6 — contrôle approfondi des transmissions et preuves
- Nouveau point de reprise : sous-étape 2.3 non close, premières annotations 2.4 en parallèle. Archive locale AquaMetric_Q1_etape2_3_v6.zip, fichier Q1_import_reference_v6.json. La référence précédente reste conservée. Ne pas répéter les cinq fenêtres déjà revues.
- Code : services/pass_review.py et services/evidence_manifest.py. Validation des bornes de libération, contact apparent/observé, maîtrise distincte, issue inconnue, déviation conservée, interception directe, sortie; liens aux événements/possessions, refus des chevauchements. Aucun taux global ou crédit individuel induit. Manifeste de preuves avec SHA déclarées, contrôle des chemins et des contradictions; aucune lecture des chemins importés sur le serveur.
- Import, rapport partagé et export JSON/ZIP reliés au module. CI 45912014167 au commit a62d397c24e45c68b645068493054b9bf5496570 : 28 + 19 + 34 = 81 tests réussis, compilation et rendu Jinja réussis. 25 tests locaux sur le dossier réel, empreintes vidéo et preuves. Les deux blobs locaux sont identiques à GitHub. Le serveur réel n'a pas reçu le fichier privé; pas de test navigateur ni de déploiement.
- Prochain cycle : poursuivre les observations des changements de contrôle et des transmissions (notamment issues inconnues et fautes), faire une validation intégrée de l'import réel hors production, compléter les critères de continuité pour les possessions. Préparer consolidation prudente #42/#43 sur une branche de test et adapter #41 séparément; vérifier sauvegarde/restauration avant redéploiement. Maintenir les données privées hors dépôt.

## Révisions 7–8 — continuité et attribution prudente (27 novembre 2026)
- R7 : commits b82d66e et 2d2a1d8 : contrôle des départs successifs et unicité du lien direct au tir. CI précédente 45916914090 signalée réussie ; recompter les tests depuis les logs.
- R8 : commits 5c2f1b6, f81fa0e, 6ca5e4f : export explicite shot_link_status=temporal_only, key_pass_verified=false et assist_verified=false ; avertissement HTML et test de non-attribution. Ne pas confondre association temporelle et continuité prouvée. CI à vérifier avant validation.
- Prochaine action : vérifier CI R8, tester import réel hors production, définir preuve positive de continuité et contradictions inter-registres. Aucun nouveau relevé vidéo ni déploiement dans ce cycle.

## Révision 9 — contradictions passe-tir (27 novembre 2026)
- Code c5640d36758095f7c5f228b0e481d456e2c4a472 : contrôle adverse observé dans l'intervalle maîtrise–tir, identifiants des fenêtres exportés. CI 45945180270 terminée avec succès, avant ajout des tests ciblés.
- Ajout de cinq tests synthétiques : contrôle observé, apparent, hors intervalle, borne du tir, rendu HTML. Le rapport affiche désormais la contradiction et les identifiants associés. Nouvelle CI à vérifier; aucune attribution positive ni validation vidéo supplémentaire.
- Reprise : vérifier CI des cinq tests, puis audit des reprises attribuées et de la continuité. Ne pas fusionner ni redéployer avant validation et sauvegarde. Aucun fichier privé publié.

## Révision 10 — bornes contradictoires
- CI R9.1 45951242113 réussie. R10 : contrôles observés opposés au même instant dans la référence importée, conservation des annotations mais exclusion des fenêtres concernées de la borne minimale. Trois tests synthétiques ajoutés; rapport explicite. Comparaison exacte des secondes, sans tolérance arbitraire. CI R10 à vérifier. Aucun nouveau relevé vidéo, aucune fusion ni déploiement. Prochaine action : vérifier CI, étendre au registre manuel et examiner les reprises attribuées.

## R11 — qualité des passes
- Commit 380cdd6a : dimensions indépendantes accuracy, defensive_intervention, reception_quality; anciennes annotations inconnues par défaut. Échecs confirmés et taux sur issues résolues uniquement; déviations conservées non classées en réussite/échec sans preuve de réception cible. CI et tests ciblés à vérifier.
- Exigence utilisateur : relever toutes les passes, y compris circulation sans tir, gardiennes, transitions et reprises; distinguer précision, blocage, réception, responsabilité et finalité décisive. Couverture exhaustive à démontrer par fenêtres revues sans lacunes, pas par extrapolation. Aucun nouveau relevé vidéo dans ce cycle.
- Reprise : tests des nouvelles dimensions, interface HTML, preuve positive passe-tir, couverture Q1 puis match entier. Ne pas déployer.

## R12 — arrivées de ballon sans départ observé (27 novembre 2026)
- Reprise réelle du Q1 après R6 : 4 fenêtres de repérage (69–77, 181–189, 318–326, 532–539 s), 159 images à 200 ms; 213 vues de détail (40, 80 ou 120 ms) avec chevauchements. Registre privé R12 : neuf annotations de transmission, dont quatre passes observées, deux issues directes réussies, deux issues inconnues, deux arrivées seules, un candidat et deux contre-exemples. Aucun total exhaustif ni nouvelle possession déduit. Référence R6 préservée; 26 événements et 13 fenêtres de possession inchangés.
- Code pass_review.py : état arrival_only séparé des tentatives, origine inconnue, arrivée/contact/maîtrise et ordre vérifiés, pas de durée de vol ni de réussite attribuée. Affichage HTML. CI 45959511778 au commit d1f7efc77808d1511113d86e950767ee3e4e042e : 28 + 22 + 56 = 106 tests réussis, compilation et rendu Jinja réussis. Blob local du moteur identique c2a975c3380df38fe6bc3f9fd8d1bee4e51f89ed. Calcul local et validation du manifeste sur référence réelle : 106 liens, 105 fichiers distincts, empreintes des fichiers et des deux vidéos conformes. Pas de test HTTP du véritable import sur serveur ni de déploiement.
- Archive privée : AquaMetric_Q1_etape2_3_v12.zip; Q1_import_reference_v12.json, passes_Q1_v12.csv, audit_passes_v12.json. Prochain cycle : reprendre les arrivées en cherchant leur départ avant 319,84 et 538,20 s; examiner 327,32–327,40 s et la suite de l'action, puis poursuivre la revue systématique de la circulation sans tir. Ne pas traiter des vues échantillonnées comme couverture exhaustive. Tester l'import intégré des versions réelles hors production; préparer consolidation #42/#43; pas de redéploiement sans sauvegarde vérifiée.
