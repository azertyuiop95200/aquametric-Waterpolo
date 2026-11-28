# Audit de convergence — 28 novembre 2026
Base figée de l'audit : production lot9 `96931706e4f5d4071e489c3ef8798a4efe7bddef`. Render live 09:43:54 UTC, preuve HTTP exacte [CI 46131686379](https://github.com/azertyuiop95200/aquametric-Waterpolo/actions/runs/46131686379), marqueur LIVE_R7_RELEASE9_REPORT_OK. 73 branches recensées et comparées à cette base (pagination terminée). Les écarts Git sont topologiques, pas des pourcentages ni des preuves d'absence : un cherry-pick peut avoir un blob identique. Ce relevé couvre toutes les branches existant au début de l'audit, pas chaque commit individuel daté du 27/11 ni chaque fonction de chaque branche. Comparaisons approfondies ciblées sur 53 modules issus des branches sportives actives, plus trois chemins additionnels absents. Aucune fusion globale des branches anciennes/scouting.
## Modules comparés aux fichiers exacts de production
| Groupe | Identiques | Différents | Absents | Conclusion |
|---|---:|---:|---:|---|
| stats-advanced (14) | 11 | 0 | 3 | Les modules motion, centre, repli, effort directionnel, gardienne, occupation, possession_geometry, dominance, soutien, trajectoires, union sont identiques. Absents : match_report_sequence, match_tactical_report, spatial_report_detail. |
| spatial-decision-3d (5) | 5 | 0 | 0 | spatial_goal_coverage, spatial_replay, spatial_sandbox, spatial_scenario_search, spatial_two_step identiques ; sandbox et recherche de scénarios présents mais pas intégralement raccordés à l'interface actuelle. |
| possession-evidence (17) | 5 | 1 | 11 | candidate_review, detection_evaluation, head_flow_tracking, learned_head, local_object_tracking identiques ; local_clip_scan adapté en R7 (hash source et liens). Absents : ball_motion_review, calibration_validation, evidence_manifest, offline_detection_benchmark, pass_review, possession_context, possession_evidence, retrospective_review, review_coverage, review_reference_import, review_reference_revision. |
| continuous-match (17) | 0 | 1 | 16 | tactical_timeline différent (prod 7088da0, branche d04f7da). Absents : ball_continuity, ball_control, continuous_match, control_mobility, decision_space, dynamic_calibration, execution_timing, head_benchmark, lineup_exposure, lineup_performance, metric_context, mobility, pass_ledger, possession_performance, spatial_attribution, track_continuity. |
| **Total échantillon** | **21** | **2** | **30** | **53 modules** ; présence exacte ne garantit pas exécution ou restitution. |
Trois autres chemins constatés absents en production : cap_identity_fusion, advanced_observed_metrics, tactical_sequence_metrics. Les deux branches natives 28/11 introduisent aussi local_scan_batch, ball_assisted_fusion, private_review_export et shot_reference_summary : comparer contrats avant intégration.
## Lot 10 — premier manque corrigé
[PR61](https://github.com/azertyuiop95200/aquametric-Waterpolo/pull/61), head ad31364b0b59973012ad7bd8b63fd9ceee529082, fusion 9426151fff816ecfad5e6e1e6e843cf7afabe2ad. Module possession_evidence.py repris à l'identique (blob 124cfedf0b699aa15bd81f8ae08ed729b5227911). Adaptateur séparé, formulaire propriétaire, fenêtres de contrôles vidéo revues, 52 causes, distinction cause et décision arbitrale, borne inférieure par source et période, rejet doublons et recouvrement, empreinte fichier au calcul, export web/HTML/JSON/CSV/ZIP, aucun événement officiel ajouté. Pas de temps de jeu, taux de pertes ou possession complète déduits. [CI 46132858803](https://github.com/azertyuiop95200/aquametric-Waterpolo/actions/runs/46132858803) 207 tests (190 calcul et 17 HTTP), 28 tests d'origine et 5 nouveaux tests HTTP synthétiques ; trois jobs verts. Pas de validation sportive réelle. Reste à vérifier le déploiement.
## Ordre de convergence
1. Intégrateur et vision : rapprocher continuous_match, track_continuity, cap_identity_fusion et dynamic_calibration des producteurs R7 sans écraser leurs preuves. Dépendances et qualité sur Q1.
2. Événements : pass_review et ses dépendances evidence_manifest/review_coverage/retrospective_review, import privé de références, ball_motion_review et ball_control. Ne pas injecter la référence Q1 dans d'autres matchs.
3. Temps de jeu et phases : lineup_exposure, lineup_performance, execution_timing, pass_ledger, possession_performance, avec chronomètre indépendant et identités revues.
4. Rapport multi-fenêtres : match_report_sequence, match_tactical_report, spatial_report_detail, tactical_sequence_metrics ; dédoublonner les observations et sources, inventaire exhaustif export.
5. 3D : sandbox et scenario_search, options conditionnelles et mouvement récepteurs, pas de probabilité de réussite certifiée. UX analyse-first : comparer base.html/menu et parcours, sans sections scouting/classement.
6. QA : vérification exact SHA en ligne, tests du rapport non vide, vidéo réelle et contrôle indépendant. Conserver ancienne version, pas de données privées dans GitHub. Les branches anciennes doivent faire l'objet d'un contrôle ciblé de leurs changements utiles avant toute réintégration.
## Inventaire complet des 73 branches comparées
Ahead = commits propres à la branche par rapport à lot9 ; behind = commits du lot9 non ancêtres de la branche ; fichiers = diff retourné par la comparaison triple-dot. Les valeurs sont figées au relevé, pas en temps réel.
| Branche | Ahead | Behind | Fichiers diff |
|---|---:|---:|---:|
| stats-advanced | 88 | 356 | 62 |
| feature/spatial-decision-3d | 74 | 356 | 25 |
| feature/possession-evidence-integration | 138 | 141 | 45 |
| feature/continuous-match-2026 | 20 | 151 | 66 |
| feature/convergence-report-v3 | 129 | 87 | 88 |
| feature/analysis-first-ux | 57 | 356 | 20 |
| feature/video-boundary-ambiguity-2026 | 6 | 356 | 3 |
| feature/video-observation-quality-2026 | 4 | 356 | 3 |
| feature/vision-benchmark-matched-scope | 141 | 87 | 89 |
| dev/cap-identity-uniqueness-20261127 | 7 | 151 | 5 |
| dev/native-local-evidence-20261128 | 142 | 87 | 92 |
| dev/native-reviewed-shots-20261128 | 143 | 87 | 98 |
| fix/youtube-report-intake-2026-11 | 0 | 168 | 0 |
| feature/url-analysis-parity | 16 | 728 | 7 |
| feature/ultimate-statistical-audit | 46 | 151 | 20 |
| codex/automatic-match-measurements | 2 | 364 | 29 |
| codex/bound-ocr-memory | 1 | 372 | 3 |
| codex/captured-video-clips | 2 | 365 | 30 |
| codex/fix-capture-chunk-retries | 1 | 379 | 4 |
| codex/mobile-link-analysis | 1 | 380 | 11 |
| codex/native-ocr-progress | 1 | 373 | 8 |
| codex/ocr-work-reuse | 1 | 378 | 3 |
| codex/prevent-archive-replacement | 1 | 375 | 285 |
| codex/refonte-waterpolo | 0 | 385 | 0 |
| codex/repair-empty-analysis | 2 | 377 | 44 |
| codex/video-sessions-library | 3 | 381 | 9 |
| feat/automatic-manager-simulation | 7 | 783 | 3 |
| feature/coach-film-room-match-library-v2 | 17 | 771 | 14 |
| feature/deep-scouting-review | 4 | 820 | 4 |
| feature/deep-video-scouting-evidence | 0 | 820 | 0 |
| feature/deep-video-scouting-evidence-final | 0 | 820 | 0 |
| feature/deep-video-scouting-evidence-v2 | 0 | 820 | 0 |
| feature/deep-video-scouting-evidence-v3 | 0 | 820 | 0 |
| feature/elite-analyst-lab-v1 | 13 | 740 | 9 |
| feature/elite-performance-2026 | 0 | 0 | 0 |
| feature/elite-video-library-v2 | 3 | 804 | 3 |
| feature/eu-youth-scouting-2026 | 5 | 899 | 5 |
| feature/game-reading-score | 5 | 818 | 5 |
| feature/la-pointe-france-women-rosters | 6 | 559 | 3 |
| feature/la-pointe-france-women-rosters-v2 | 3 | 536 | 3 |
| feature/prospect-rating-v4 | 9 | 821 | 9 |
| feature/real-analysis-results-zip | 0 | 678 | 0 |
| feature/results-section | 2 | 917 | 2 |
| feature/scouting-player-resource-depth | 9 | 804 | 6 |
| feature/tactics-knowledge-hub-v2 | 1 | 816 | 4 |
| feature/ultimate-analyst-engine-v2 | 5 | 730 | 5 |
| feature/video-session-elite | 5 | 817 | 3 |
| fix/deep-review-rating-band | 1 | 819 | 1 |
| fix/eu-youth-scouting-seed-flush | 3 | 895 | 3 |
| fix/http500-vision-progress-race | 3 | 388 | 3 |
| fix/mobile-analysis-entry | 8 | 168 | 5 |
| fix/mobile-scouting-dossier-link-check | 1 | 800 | 1 |
| fix/pr40-mobile-analysis-entry | 4 | 168 | 4 |
| fix/preseason-zero-standings | 1 | 824 | 1 |
| fix/tactics-knowledge-ci | 9 | 815 | 9 |
| fix/v14-nonblocking-conclusive-analysis | 10 | 387 | 8 |
| fix/v15-browser-capture-89-stall | 6 | 383 | 6 |
| fix/v16-report-first-capture | 17 | 382 | 9 |
| fix/v16-report-first-capture-check | 6 | 382 | 6 |
| fix/video-readability-ai-analysis-20260907 | 3 | 389 | 3 |
| integration/advanced-motion-release1 | 0 | 142 | 0 |
| integration/advanced-occupation-release2 | 0 | 135 | 0 |
| integration/calibrated-http-release8 | 0 | 52 | 0 |
| integration/causal-motion-release8 | 0 | 42 | 0 |
| integration/r7-vision-evidence | 0 | 1 | 0 |
| integration/recovery-release4 | 0 | 102 | 0 |
| integration/reviewed-collective-release3 | 0 | 115 | 0 |
| integration/shot-context-release5 | 0 | 88 | 0 |
| integration/spatial-3d-release6 | 0 | 63 | 0 |
| integration/spatial-motion-release7 | 0 | 55 | 0 |
| main | 7 | 356 | 3 |
| qa/r7-live-release9 | 1 | 0 | 1 |
| ui/homogenize-eu-scouting | 4 | 811 | 4 |
