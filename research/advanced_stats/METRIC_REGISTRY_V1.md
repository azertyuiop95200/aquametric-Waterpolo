# Registre atomique — v1 — 2026-11-27
Statut T = testé sur simulations uniquement, S = spécifié, non implémenté dans cette branche. Aucune validation vidéo réelle des métriques tactiques. Seuils expérimentaux, non normatifs.
Pour tout indicateur : null en absence du dénominateur/entrées fiables, unité explicite, source, fenêtre (match/période/possession), identifiants, couverture et statut. Ne pas additionner des fenêtres superposées.

| ID stable | Unité | Calcul / entrées / attribution | Statut |
|---|---|---|---|
| spatial.window_s | s | dernier - premier timestamp de fenêtre vidéo monotone; paire | T |
| spatial.observed_s | s | somme dt avec positions valides aux deux extrémités, dt <= max_gap; paire | T |
| spatial.coverage | fraction | observed_s/window_s; paire, null si fenêtre nulle | T |
| spatial.proximity_s | s | somme dt x fraction du segment relatif dans disque de rayon r; paire, pas preuve de pression | T |
| spatial.mean_distance_m | m | intégrale approchée distance relative / observed_s; paire, quadrature milieu 32 | T |
| spatial.proximity_fraction | fraction | proximity_s/observed_s; paire | T |
| spatial.proximity_lower_s | s | rayon r-2e, borne déterministe si erreur par joueuse <= e | T |
| spatial.proximity_upper_s | s | rayon r+2e, borne déterministe si erreur par joueuse <= e | T |
| quality.calibration_residual | m | erreur sur points de contrôle indépendants; plan, segment caméra | S |
| quality.identity_coverage | fraction | durée identité confirmée / durée d'observation cible; joueuse | S |
| time.playing_s | s | somme des intervalles en eau ET horloge de jeu active; joueuse; rotations vérifiées | S |
| move.distance_m | m | somme déplacement métrique valide; joueuse, couverture | S |
| move.speed_mps | m/s | distance / dt valide; joueuse | S |
| move.acceleration_mps2 | m/s² | variation vitesse / dt, filtrage validé; joueuse | S |
| move.sprint_count | n | épisodes au-dessus seuil vitesse/durée validés; joueuse | S |
| offball.separation_delta_m | m | variation distance défenseure la plus proche pendant possession sans ballon; joueuse | S |
| offball.available_pass_s | s | durée avec ligne de passe géométriquement ouverte; joueuse, ballon | S |
| defense.closing_speed_mps | m/s | opposé de variation distance / dt; paire | S |
| defense.team_proximity_s | s | union temporelle des intervalles de proximité; porteuse, sans doubles comptes | S |
| defense.pass_lane_block_s | s | durée intersection obstacle/couloir de passe; paire, ballon | S |
| duel.duration_s | s | durée événement duel annoté; paire | S |
| duel.win_count | n | issue observable et définie par phase; joueuse | S |
| transition.recovery_s | s | temps perte -> repli selon critère spatial préétabli; équipe | S |
| transition.progress_m | m | progression ballon projetée vers but attaqué; possession | S |
| center.receptions | n | réception vérifiée en zone pointe définie; joueuse | S |
| center.exclusions_drawn | n | exclusion et attribution vérifiées; joueuse | S |
| goalkeeper.save_pct | fraction | arrêts / tirs cadrés subis selon convention documentée; gardienne | S |
| goalkeeper.angle_2d_rad | rad | angle apparent des poteaux depuis point de tir plan; tir | S |
| goalkeeper.reaction_s | s | début mouvement observable - libération ballon; tir; résolution et ambiguïté | S |
| special.powerplay_conversion | fraction | buts / possessions en supériorité vérifiées; équipe | S |
| special.pass_rate | passes/s | passes complétées / temps actif de phase; équipe | S |
| attack.shots | n | tirs distincts confirmés; joueuse | S |
| attack.goals | n | buts confirmés; joueuse | S |
| attack.completed_passes | n | passes reçues confirmées; joueuse | S |
| attack.turnovers | n | pertes attribuables confirmées; joueuse | S |
| attack.xg | probabilité | modèle entraîné et calibré hors match; tir; pas de probabilité heuristique | S |
| attack.xa | probabilité | xG des tirs attribués à une passe décisive potentielle; passe; convention explicite | S |
| tactic.width_m | m | étendue transversale des joueuses de champ visibles; équipe | S |
| tactic.pass_network_edge | n | passes confirmées i -> j; paire orientée | S |
| spatial3d.goal_open_solid_angle | sr | angle solide des surfaces libres du but; positions 3D calibrées, tir | S |
| discipline.exclusions | n | événements réglementaires confirmés; joueuse | S |
| efficiency.goals_per_min | buts/min | 60 x buts / playing_s; joueuse | S |
| export.metric_status | texte | provenance et état par métrique exportée; rapport | S |

## Conventions de v1
Entrée spatiale : temps vidéo en secondes, positions 2D en mètres, identités distinctes; fenêtre homogène sans coupure caméra ou changement de possession. Rayon 1,5 m et max_gap 0,25 s configurables et NON validés scientifiquement. Erreur de position 0 par défaut = hypothèse mathématique, jamais preuve d'exactitude; ne pas afficher des bornes sans erreur estimée. Ne pas confondre observed_s avec temps de jeu. Modèle linéaire entre observations; pas de reconstruction du mouvement réel sous l'eau.
Sources d'orientation (consultées 27/11/2026): https://www.worldaquatics.com/rules/competition-regulations (version novembre 2026 affichée, vérifier compétition/date), https://doi.org/10.1080/24748668.2017.1308112 (contexte opposition/score/lieu), https://doi.org/10.1080/24748668.2017.1339258 (phases et tirs), https://www.worldaquatics.com/news/4441220/inside-the-action-water-polo-performance-analysis-at-singapore-2025 (benchmark institutionnel). Aucun seuil spatial dérivé de ces sources.
