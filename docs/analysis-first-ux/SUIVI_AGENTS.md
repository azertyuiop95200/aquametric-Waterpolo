# AquaMetric — tableau de suivi du rapport final
Mise à jour initiale : 28 novembre 2026. Ce tableau est un état vérifié à date, pas une télémétrie en direct. Le responsable intégration & événements le met à jour à chaque cycle à partir des preuves des spécialistes. [Mandat commun](DELIVERY_REPORT_FIRST.md) · [Convergence](CONVERGENCE.md) · [Feuille de route](ROADMAP.md).

## Avancement vers 100 % — référentiel v1
[Consulter les 50 critères détaillés et les preuves](OBJECTIFS_100.md). Chaque jalon vaut 10 points pour son agent, seulement après validation intégrale. Pondérations égales par agent ; avancement global = jalons vérifiés / 50. Ce score mesure les livrables, pas la précision sportive, le temps restant ni le taux de statistiques renseignées.

| Agent | Jalon validé | Progression | Prochain jalon prioritaire |
|---|---|---:|---|
| Intégration & événements | I01, I02 | 20 % | I03 — convergence des producteurs V3 et lot 8 |
| Vision & calibration | V01, V02 | 20 % | V03/V04 — PTS Q1, benchmark indépendant |
| Statistiques & restitution | S01 à S04 | 40 % | S05 — inventaire complet producteur/rendu/export |
| Parcours & UX | U01, U02 | 20 % | U03 — import vidéo réel et plusieurs segments |
| Validation indépendante | Q01, Q02 | 20 % | Q03 — smoke HTTP sur lot8 exact |
| **Global** | **12/50** | **24 %** | **38 jalons restent à valider** |

État initial établi le 28/11/2026 sur les preuves liées dans OBJECTIFS_100.md. U01 est validé sur branche uniquement. U02 utilise une fixture URL, pas un vrai traitement vidéo. Les 146 tests et le pilote de tracking ne certifient pas un rapport sportif complet. L'intégrateur met à jour les IDs, scores, preuves et blocages à chaque cycle ; une régression peut réduire le score. Les spécialistes transmettent leurs résultats dans leurs propres journaux. Conserver les critères et poids fixes.

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

### 28/11/2026 — R7, convergence du suivi et du rapport
- [PR59](https://github.com/azertyuiop95200/aquametric-Waterpolo/pull/59), branche integration/r7-vision-evidence, base lot8 c6ee727, head a58849d, 20 fichiers : six modules génériques de l'archive R7 identiques par empreinte Git, réutilisation du scan borné et de la table de preuve V3, déclenchement d'une première fenêtre locale, routes propriétaire pour scan et revue, annexe HTML/snapshot/JSON/ZIP. Aucun poids, image, annotation ou contenu privé publié.
- 10 tests R7 d'origine réexécutés localement : succès. Essai local sur pixels Q1 : 13 images échantillonnées sur 25 frames, 99 pistes anonymes dont 35 à ≥3 points et 16 points de flux seuls, 3 propositions de revue. Pas de mesure de précision sportive ni d'identité confirmée. [CI PR59](https://github.com/azertyuiop95200/aquametric-Waterpolo/actions/runs/46126693885) en cours à ce relevé ; quatre tests HTTP nouveaux sur vidéo synthétique à vérifier, pas de fusion ni déploiement. Poids privés absents du serveur ; revue HOG conditionnelle, API propriétaire uniquement.
- Prochain responsable : intégration & événements — vérifier CI, compatibilité du modèle/migration et stockage, passage vers données calibrées avec source/période/identité et couverture. Vision — élargir benchmark indépendant et fournir modèle privé vérifié sans publication ; statistiques — adapter pistes revues, ne pas promouvoir les candidats ; UX — interface de revue et progression du traitement complet ; QA — vérifier parcours réel, provenance, contrôles d'accès, exports et régressions. Aucun nouveau jalon de 10 points n'est crédité avant validation de ses critères entiers (I03/I07, V04/V05/V10, S08/S09, U03/U08, Q03/Q07).
