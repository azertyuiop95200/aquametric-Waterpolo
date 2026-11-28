# AquaMetric — tableau de suivi du rapport final
Mise à jour initiale : 28 novembre 2026. Ce tableau est un état vérifié à date, pas une télémétrie en direct. Le responsable intégration & événements le met à jour à chaque cycle à partir des preuves des spécialistes. [Mandat commun](DELIVERY_REPORT_FIRST.md) · [Convergence](CONVERGENCE.md) · [Feuille de route](ROADMAP.md).

## Livraison
- [Site Ultimate](https://aquametric-ultimate-guest.onrender.com) : lot 8, SHA `c6ee727786928332176a0e6d75a7e09a7932248a`, Render live (27/11, 23:09:46 heure de Paris).
- [CI lot 8](https://github.com/azertyuiop95200/aquametric-Waterpolo/actions/runs/46074577789) : 146 tests précédemment vérifiés, dont 2 parcours HTTP sur fixture synthétique. Pas une validation sportive réelle.
- Objectif restant : rapport réel Q1 complet autant que les observations le permettent, puis match entier. Couverture sportive globale : non établie.

## Chantiers par agent
| Agent | Priorité courante | Preuve / branche | Blocage ou prochaine action |
|---|---|---|---|
| Intégration & événements | P0 : réunir producteurs V3 et lot 8, possessions et actions | [PR47](https://github.com/azertyuiop95200/aquametric-Waterpolo/pull/47), convergence V3 `b0e7f09`, possessions `aec4ef8` | V3 diverge (+129/-46 commits par rapport à la production) ; possessions +138/-100 ; intégrer petits lots compatibles, ne pas fusionner en bloc |
| Vision & calibration | P0 : suivi ballon/joueuses, repères, identité et horloge | [Branche vision](https://github.com/azertyuiop95200/aquametric-Waterpolo/tree/feature/continuous-match-2026), `8689b7d` | Mesures métriques sur Q1 non validées ; bench local de 50 points en pixels ; branche +20/-110 |
| Statistiques & restitution | P0 : connecter données disponibles à tous les indicateurs | [Journaux](https://github.com/azertyuiop95200/aquametric-Waterpolo/tree/stats-advanced/research/advanced_stats/journal), `96ddd84` | Vérifier alimentation automatique et matrice producteur/snapshot/rendu/export ; branche +88/-315 |
| Parcours & UX | P0 : import, progression, arrêt et rapport, stockage, revue minimale | [Roadmap](ROADMAP.md), [PR45](https://github.com/azertyuiop95200/aquametric-Waterpolo/pull/45) | Vérifier parcours réel et persistance ; ne pas présenter une simple sauvegarde d'URL comme analyse |
| Validation indépendante | P0 : contrôles SHA, CI, rapports non vides et référence réelle | [Actions GitHub](https://github.com/azertyuiop95200/aquametric-Waterpolo/actions) | Vérifier précisément le prochain lot intégré ; distinguer fixture et vidéo réelle |
Les écarts de commits ne sont pas un pourcentage d'avancement et ne justifient pas une fusion globale.

## Matrice de couverture initiale du rapport
| Famille | Calcul/rendu disponible dans Ultimate | Résultat sur match réel complet |
|---|---|---|
| Événements et score | Oui, données confirmées requises | À valider |
| Possessions, passes et phases | Partiel | À valider |
| Identités et temps de jeu | Partiel | Non établi |
| Déplacements, vitesses, cartes | Oui, calibration et identités revues | Non établi en mètres |
| Pression, soutien, pointe, gardienne | Oui, fenêtres revues | À valider |
| Repli défensif | Oui, transitions revues | À valider |
| Tirs et arrêts contextualisés | Oui, associations revues | À valider |
| 3D et alternatives | Oui, simulations conditionnelles | Pas une reconstruction réelle |
| Web / HTML / JSON / ZIP | Disponibles selon données | Concordance sur Q1 réel à vérifier |
| CSV exhaustifs | Partiel | À compléter |
Ne jamais remplir une cellule sportive sans preuve. Ne pas assimiler absence de données à zéro.

## Journal de mise à jour
À chaque cycle, l'intégrateur ajoute une entrée datée avec : agent, lot réellement terminé, SHA/PR, lien CI et résultat exécuté, source et couverture (sans données privées), rapport réellement produit ou blocage, prochain responsable. Mettre à jour la matrice seulement sur preuve nouvelle. Conserver historiques, distinguer statut technique, résultat sportif et mise en ligne. Les cinq automatisations sont programmées chaque heure ; leurs résultats et leur historique se consultent dans ChatGPT. Aucun identifiant de conversation privée ni vidéo privée dans ce dépôt public.
