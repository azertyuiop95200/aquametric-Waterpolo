# Cycle — trajectoires fragmentées et cinématique directionnelle (2026-11-27)
Avant lot : stats-advanced +22/-0, ultimate-statistical-audit +251/-0, spatial-decision-3d +42/-0; base main bb1b3ce52b5517342bc8a7dce0e2789968f6424c. Protocole, journal de rapport unifié, advanced_tracking et match_tactical_report relus. Réutilisation des identités et segments métriques du système existant; aucune modification de la branche 3D.
## Production
- 2b28bf832c3d91421ba274ea1bc1dddf9a2971e2 : tracklet_union.py, union temporelle des segments d'une identité déjà revue. Priorité au segment le plus court, exclusion des désaccords aux deux extrémités, pas de réidentification ni comblement de lacune.
- c98a7fa6374df4e212daae8649e31f84d5383cff : directional_effort.py, accélération vectorielle, virages, épisodes de sprint et intervalles observés.
- f394dba686fb459fad572ecb38b48ad195b35a25 : adaptateur reviewed_motion mis à jour.
- 98ba3e0d2c706f53da368d923a39108d99865569 et 3336344580659f27fd2d1c21748ab4f527440a2d : cartes et fenêtres chronologiques alimentées par les mêmes segments fusionnés.
- f039e084bf34d2f3083788a5cb677397b19e5276 : 8 nouveaux tests.
- 79cc627c7e2ab131f2122df432a2b244bc1e1fb1 : rendu HTML des trajets, virages et épisodes de sprint, qualité du suivi.
## Tests effectivement exécutés
Dans /mnt/data/aqua_union_cycle : python -m unittest -v test_tracklet_union.UnionTests test_advanced_tracking.Tests test_match_tactical_report.Tests test_match_report_sequence.SequenceTests test_tactical_trajectories.TacticalTests : 37 tests OK (8 nouveaux + 29 régressions). Rendu Jinja StrictUndefined sur données synthétiques : OK. Empreintes locales et distantes concordantes pour les 7 fichiers. Le premier passage d'audit a révélé un risque de joindre deux sprints de part et d'autre d'une lacune dans un même segment; correction appliquée avant publication et test dédié.
## Extension du registre atomique
Tous statuts: tests synthétiques uniquement, pas de validation sur match. Fenêtre: une source, une période, un repère métrique stable, identité confirmée en amont. Durées en secondes vidéo, jamais temps de jeu. Seuils expérimentaux non normatifs: écart maximal .26 s, vitesse maximale 3.5 m/s, désaccord .75 m; virage 60°, vitesse minimale .5 m/s, intervalle entre sprints rapprochés <=5 s. Seuils de sprint et durée minimale fournis au moteur. Aucun lien physiologique déduit.
| ID | Unité | Définition et dénominateur |
|---|---|---|
| quality.track_overlap_s | s | union temporelle avec plusieurs segments observés pour une identité |
| quality.track_conflict_s | s | partie du chevauchement exclue si désaccord spatial > seuil à l'une des extrémités |
| quality.track_rejected_edges | n | intervalles invalides, trop longs ou trop rapides |
| move.vector_acceleration_peak | m/s² | maximum de la norme de la différence de vitesses vectorielles divisée par différence des temps centraux, uniquement intervalles contigus du même fragment; null si aucun couple |
| move.turn_count | n | nombre de changements de direction >= seuil entre vecteurs consécutifs de vitesse suffisante; null sans paire éligible |
| move.turn_eligible_pairs | n | nombre de paires contiguës avec vitesse suffisante, dénominateur du comptage |
| move.sprint_episodes | liste | intervalles contigus au-dessus du seuil et de durée minimale; interrompus aux lacunes |
| move.repeated_sprint_pairs | n | paires d'épisodes successifs séparés par un intervalle observé <= seuil, au sein du même segment continu |
| move.inter_sprint_gap_s | s | durée vidéo entre épisodes rapprochés observés, pas récupération physiologique |
Limites: même identité revue, pas de fusion entre sources ni de calibration nouvelle. Les dérivées et le nombre de virages dépendent du bruit et de la fréquence; sélection d'un intervalle plutôt que moyenne des pistes; qualité de mesure non calibrée. Les routes de production ne sont pas encore raccordées et aucune vidéo réelle n'a été validée pendant ce cycle.
## Reprise
Prochain lot: couloirs de passe et réseaux temporels à partir des événements existants et des positions pré-action, réutiliser le moteur 3D pour les dégagements; intégrer l'exposition collective par possession et mesurer le repli sans inférer une intention. Raccorder le rapport dans une branche d'intégration après validation des entrées/ownership, tester le navigateur et les exports; ne pas modifier main ou déployer sans validation.
