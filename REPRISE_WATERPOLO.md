# Reprise AquaMetric — 8 septembre 2026

Base : dépôt existant, commit bfe953440c22477116ba1b3e35ca9c97cc434c87. Les archives V11.1 et V11.2 ont été retrouvées mais ne remplacent pas le code plus récent du dépôt.

## Changements livrés

- Accueil recentré sur les analyses récentes, la préparation de match et l’état des sources.
- Présentation commune simplifiée, français par défaut, navigation et lisibilité mobile améliorées.
- Chargement différé des scripts ; scripts spécialisés retirés des pages simples ; compression HTTP ; huit matchs maximum chargés sur l’accueil, compteurs calculés en base et chargement groupé des équipes associées.
- Menu fermé réellement inaccessible au clavier sur mobile ; menu toujours accessible sur ordinateur ; défilement de tableaux préservant les clics sur les liens et formulaires.
- Résultats actualisés sans rechargement complet ; conservation des dernières données en cas d’échec avec message visible.
- Impact des absences calculé côté serveur avec dédoublonnage des noms, indépendamment du pourcentage transmis par le navigateur.
- Plans de jeu optionnels pour les scénarios avancés, distincts du calcul automatique par défaut.
- Hypothèses des projections de saison affichées ; exclusion des projections pour une équipe absente des participants documentés.

## Couverture et limites à ne pas masquer

Les modules existants sont conservés : analyse pour les équipes du catalogue, scouting, profils joueuses et entraîneurs, transferts, résultats par période, tactique et vidéo, simulations de matchs et projections de saison.

Cette livraison ne certifie pas l’intégralité du cahier des charges historique :

- Les flux de données dépendent des adaptateurs et de la disponibilité des sources. Une collecte réussie passée ne garantit pas une couverture actuelle exhaustive.
- La reconnaissance vidéo fiable des joueuses, du ballon, de toutes les actions et des formations n’est pas une capacité complète et validée du moteur actuel.
- Le manager ne propose pas encore un éditeur complet de compositions, rotations, minutes et consignes poste par poste ; les nouveaux scénarios concernent les plans de jeu.
- Les projections de saison utilisent un barème et des seuils génériques explicités ; les formats propres à chaque compétition, séries et playoffs complets nécessitent encore une modélisation dédiée.
- Les ébauches d’effectifs et impacts sans données suffisantes restent des estimations. Les statistiques publiques manquantes ne sont pas inventées.
- Aucun test visuel dans un navigateur ni mesure de charge en production n’a été effectué dans cette reprise.
- La configuration Render du dépôt décrit une démonstration gratuite avec fichiers et base temporaires. Une exploitation durable nécessite un stockage persistant à configurer avant de la considérer comme production.

## Vérification

Suite existante : 305 tests réussis et 3 échecs de libellés devenus obsolètes, corrigés dans cette livraison. Revalidation ciblée des parcours modifiés et des trois cas, plus tests des absences, des scénarios et de l’accueil. Syntaxe JavaScript et compilation Python vérifiées.

La publication sur l’hébergement existant reste à effectuer après confirmation de l’espace Render par le propriétaire.
