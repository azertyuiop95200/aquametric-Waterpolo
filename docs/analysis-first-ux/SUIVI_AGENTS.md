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
| Validation indépendante | Q01 à Q03 | 30 % | Q04 — référence Q1 indépendante |
| **Global** | **13/50** | **26 %** | **37 jalons restent à valider** |

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

- **CI R7 terminée : 160/160 tests** sur a58849d, run 46126693885 (154 unitaires + 6 HTTP dont 4 nouveaux R7). Les trois jobs verify, calibrated-http et live-release-eight sont verts. Tests vidéo synthétique : décodeur réel, persistance/dédoublonnage, revue HOG avec poids synthétiques, refus source modifiée et tiers, HTML/ZIP. Aucun nouveau jalon entier validé. Render : service gratuit, pas de disque persistant déclaré, aucun Postgres Render recensé dans workspace ; base externe non vérifiée. AutoDeploy actif, **ne pas fusionner PR59 avant preuve de sauvegarde/persistance et compatibilité migration**, QA indépendant. Poids privés à configurer via canal autorisé, pas dans GitHub. Site lot8 maintenu. Prochain : intégration contrôlée des pistes revues vers calibration/identités, couverture Q1 réelle et rapport sportif. Ne pas traiter les 99 pistes comme 99 joueuses.

### 28/11/2026 — R7, fenêtres métriques et contrôle réel
- [PR59](https://github.com/azertyuiop95200/aquametric-Waterpolo/pull/59), head d3acdccf2ab3d65d5fff5e8b8440968452176c18, 32 commits / 22 fichiers par rapport au lot8. Pistes explicitement revues, SHA256 vidéo contrôlé au calcul, indices de source, identité/feuille/période, repères et alignement caméra ; réutilisation calibrate/CameraAligner/measure, motion, occupancy. Formulaire expert JSON et accès propriétaire aux preuves. Distance, durée observée, vitesse et carte par fenêtre dans rapport web/HTML/JSON/ZIP et CSV dédié. Temps vidéo nominal (PTS non validé), estimations de tête projetée, non additionnées aux totaux ; pas d'usage 3D automatique, pas de validation métrique réelle. Pas de modification des mesures canoniques existantes.
- [CI finale 46127778673](https://github.com/azertyuiop95200/aquametric-Waterpolo/actions/runs/46127778673) : 165/165 (154 unitaires et 11 HTTP, 5 nouveaux tests métriques sur vidéo synthétique et pistes de référence), trois jobs verts. Q03 validé : job 140926093928, SHA lot8 c6ee727 exact, accès invité, rapport et export HTTP, rejet source non calibrée et isolation, marqueur LIVE_GUEST_MOTION_REPORT_OK. Q passe 20 à 30 %, global 24 à 26 % (13/50). Ce test sur production est un dossier URL sans traitement vidéo, pas validation sportive Q1.
- Comparaison locale réelle sur les deux fenêtres Q1 déjà annotées (52 images échantillonnées, 50 centres partiels, un annotateur) : classique vs R7 head_flow, 10 px 37/50 vs 38/50 ; 22 px 45/50 vs 47/50. Même ID aux deux bornes : 1/10 pour chaque mode, bornes toutes deux retrouvées 7/10 vs 8/10 à 22 px. Pas de précision globale ou identité certifiée. Données détaillées CSV conservées localement, pas publiées. Continuité et calibration réelle restent les blocages prioritaires (V04/V05/V08 non validés). 
- PR59 fusionnable mais non fusionnée : autoDeploy actif ; persistance et sauvegarde des dossiers existants non démontrées (disque Render non déclaré, aucun Postgres Render, éventuelle base externe inconnue). Aucun nouveau coût ni déploiement. Intégrateur et QA : vérifier sauvegarde/restauration et migration ; vision : repères indépendants et continuité ; statistiques : rapprocher fenêtres validées du snapshot canonique sans doublons ; UX : remplacer revue JSON par éditeur visuel. Les scores ne doivent augmenter qu'avec les jalons entiers du référentiel v1.

### 28/11/2026 — R7, raccordement conservateur des fragments
- PR59, head e1bb680947986856ca5bbde5791259812b77791c, 40 commits / 24 fichiers sur base lot8 c6ee727. Nouveau r7_link_review.py : rapprochements rétrospectifs entre fragments disjoints, maximum deux échantillons manquants et 0,24 s, rejet des coupures et compétitions locales, aller-retour du flux et contrôle du résidu de retour depuis la nouvelle observation. Aucune fusion automatique, aucune interpolation de positions, aucun changement des six modules R7 originaux ou du calcul métrique. Mode optionnel head_flow_links, cache images BGR limité à 128 Mio, preuves et détails dans rapport web/HTML, snapshot et ZIP. Pas activé automatiquement.
- Essai exploratoire sur mêmes deux fenêtres Q1, 26 images échantillonnées par fenêtre, 50 centres partiellement annotés. 74 propositions (30 + 44). À 22 px : 13/36 paires de points de contrôle successifs avec même ID original contre 18/36 après chaînage hypothétique, soit 36,1 % contre 50,0 %. À 10 px : 13/24 contre 15/24. Aucune contradiction aux contrôles dans les deux modes ; ne démontre ni l'absence de faux liens hors contrôles ni l'identité. Aux deux bornes de chaque extrait, seulement 1/10 références conserve même ID dans les deux modes (8/10 deux bornes retrouvées à 22 px). Pas de progrès certifié sur match complet ni calibration métrique. CSV privé local conservé.
- [CI du nouveau lot](https://github.com/azertyuiop95200/aquametric-Waterpolo/actions/runs/46129514450) lancée sur e1bb680 ; neuf tests ajoutés (8 logique, 1 HTTP/exports), résultat à confirmer. Site lot8 maintenu ; code db.py confirme possibilité SQLite locale par défaut ou DB externe, /health ne révèle pas le backend et les outils Render disponibles ne permettent pas de lire la configuration de connexion. Sauvegarde/restauration durable toujours non démontrée ; pas de fusion ou déploiement. Aucun nouveau jalon entier ; 26 % (13/50). Prochain : audit indépendant des liens et revue de chaînes sans inventer les trous, calibration indépendante Q1, contrôle stockage avant merge.
