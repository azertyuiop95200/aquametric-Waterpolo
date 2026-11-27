# AquaMetric — fusion d'identité 0.2.0 — 2026-11-27

## Portée
Module expérimental hors production. Il ne confirme jamais une joueuse : il produit uniquement des review_candidate, puis applique une contrainte d'unicité sur les pistes simultanées. Les branches distantes contrôlées avant modification restent feature/continuous-match-2026@8689b7d et feature/elite-performance-2026@0372b6e.

## Correction 0.2.0
Une même identité sportive (équipe, numéro) ne peut plus rester attribuée à deux pistes qui se chevauchent temporellement. Pour chaque paire en conflit, l'identité est conservée seulement si une piste possède une supériorité explicite : marge de support >= 2 images sans baisse de share, ou marge de share >= 0,10 sans baisse de support. Sinon le conflit reste non résolu.

Ces marges sont des seuils expérimentaux internes et non des résultats de validation ni des règles fédérales.

## Dictionnaire statistique partiel v0.2.0
- frames — images distinctes avec au moins une lecture admissible. Unité: image. Source: OCR/lecture par image. Dénominateur de share.
- support — images non contradictoires votant pour le candidat dominant. Unité: image.
- share — support / frames; null si frames=0. Unité: ratio.
- conflicting_frames — images contenant plusieurs identités admissibles. Unité: image.
- identity_conflict_count — nombre de pistes simultanées portant le même candidat (équipe, numéro). Unité: conflit de piste.
- conflict_pairs — paires uniques de pistes en collision d'identité après filtre temporel. Unité: paire.
- rejected_tracks — pistes dont le candidat est supprimé par l'arbitre d'unicité. Unité: piste.
- remaining_candidates — candidats encore présents après arbitrage. Unité: piste. Ce n'est pas un nombre d'identités confirmées.

Déduplication: ensemble (équipe, numéro) par image avant vote; paires de pistes uniques pour l'unicité. Confiance: consensus expérimental non calibré. Couverture sportive: non mesurée faute d'annotations indépendantes et de vidéo accessible.

## Contrôle Q1 exporté
Le JSON existant contient 53 fragments, 14 avec une identité forte ou probable et 39 sans identité. Les intervalles accepted_edges permettent un audit de collision des 14 identités existantes : 0 paire simultanée avec le même (équipe, numéro) a été trouvée. Ce contrôle ne valide pas les identités elles-mêmes et ne permet pas de rejouer le nouvel arbitre, car les scores OCR/support/share par piste ne sont pas présents.

## Tests et limites
Reproduction locale: python -m unittest -v test_cap_fusion.py. Le module teste consensus, doublons intra-image, contradictions, équipe+numéro, faible confiance, effectif, absence de lecture, puis collisions inter-pistes, égalités, marges de preuve, réutilisation non simultanée et numéros identiques entre équipes.

Limites: aucune lecture OCR réelle, aucune annotation indépendante, pas de calibration des scores, pas de vidéo Q1_APERCU_720p.mp4 dans l'environnement. Aucun recalcul de tirs/passes/distances/temps de jeu n'est donc revendiqué.

Prochain chantier prioritaire: connecter reading_frames horodatés au tracker, conserver provenance/crop/score, puis produire un jeu d'annotations indépendant pour mesurer précision/rappel/F1 d'identité et la couverture par famille avant toute propagation vers les statistiques individuelles.
