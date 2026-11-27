# Extension du registre v1 — trajectoires tactiques (27/11/2026)
Service source/services/tactical_trajectories.py, schéma 1.0. Tous les indicateurs ci-dessous sont des proxies expérimentaux testés sur synthétique, non validés sur un match.
Fenêtre homogène (composition, possession, caméra), temps vidéo monotone, positions métriques 2D et identités validées en amont. Pour la proximité collective, toutes les défenseures déclarées actives et l'attaquante doivent être observables aux deux extrémités de l'intervalle. dt <= max_gap_s (0,25 s expérimental). Rayon configurable (1,5 m expérimental, non réglementaire). Pas de lissage ni d'estimation d'incertitude à ce stade. Une couverture faible n'autorise pas une extrapolation au match entier.
| ID | Unité | Calcul / dénominateur |
|---|---|---|
| move.observed_s | s | somme des intervalles valides pour la joueuse |
| move.coverage | fraction | observed_s/window_s |
| move.distance_m | m | somme des longueurs de segments observés; sous-estimation possible entre échantillons |
| move.speed_mps | m/s | distance_m/observed_s |
| defense.full_defender_observed_s | s | somme des intervalles avec toutes les défenseures et l'attaquante valides |
| defense.team_proximity_s | s | union exacte des intervalles de proximité avec au moins une défenseure sous hypothèse linéaire |
| defense.double_proximity_s | s | durée des intervalles où au moins deux défenseures sont simultanément proches; sous-ensemble de team_proximity_s |
| defense.team_proximity_fraction | fraction | team_proximity_s/full_defender_observed_s |
| offball.separation_delta_m | m | somme des variations de la distance à la défenseure la plus proche aux extrémités de chaque intervalle valide; porteuse connue et différente de la joueuse |
| offball.positive_separation_m | m | somme des variations positives précédentes; dépend de l'échantillonnage, ne prouve pas une intention ni un appel réussi |
Aucune distance en mètres déduite des seules coordonnées normalisées de tirs. Proximité n'est pas efficacité défensive; distance observée n'est pas distance totale ni temps de jeu. L'absence de mesure produit null; zéro signifie mesure observable nulle. L'étiquette verified_tracks est une déclaration du fournisseur, pas une certification par ce service.
Tests: 8 tests unittest, dont 200 comparaisons de l'union et de la double proximité avec quadrature de référence sur 100 jeux d'intervalles. Empreintes du code et des tests locaux identiques aux blobs GitHub. Pas encore raccordé à une route ni au rapport web.
