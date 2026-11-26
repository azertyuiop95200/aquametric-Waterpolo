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
