# Reconnaissance des actions vidéo

Le moteur local historique lit le score et l’activité. Il ne dispose pas d’un modèle
de reconnaissance des passes, tirs et acteurs. Le traitement ajouté appelle un modèle
vidéo Gemini sur les pixels d’un fichier importé ou d’une capture déjà envoyée.
Il ne télécharge pas une URL tierce et ne contourne pas un refus de lecture.

## Activation sur le service Render

Dans **Environment**, configurer par le gestionnaire de secrets Render :

```
AQUAMETRIC_VIDEO_ACTIONS=1
GEMINI_API_KEY=<clé du projet Gemini autorisé>
AQUAMETRIC_VIDEO_MODEL=gemini-3.8-flash
AQUAMETRIC_VIDEO_BUDGET_SECONDS=420
```

Ne pas coller de clé dans le dépôt, une conversation, un rapport ou une capture d’écran.
L’activation doit être faite par l’administrateur du service avec un projet autorisé
à traiter ces vidéos. Les appels consomment son quota et peuvent être facturés par
le fournisseur ; aucune souscription, clé ou activation payante n’est créée par ce code.
Le fournisseur reçoit uniquement les séquences vidéo et les noms des deux équipes,
sans adresses des comptes. `store=false` désactive le stockage de l’interaction ;
les conditions de traitement du fournisseur restent applicables.

Sans activation et clé, le rapport indique **reconnaissance des actions non activée**.
Les lectures OCR et les extraits locaux continuent à fonctionner. Un moteur non
connecté ne doit jamais être présenté comme ayant analysé les actions.

## Traitement

- Déclenchement automatique après l’OCR, sur import comme sur capture navigateur.
- Import : retour immédiat au rapport ; travail dans une tâche de fond.
- Séquences continues de 60 s, avec contexte de 2 s de chaque côté. Aucun choix
  de « meilleurs moments » n’écarte à l’avance une partie du fichier reçu.
- Une capture à 2 ou 4 panneaux est recadrée et remise à vitesse normale ; les
  horodatages reviennent à la chronologie source. Une capture tronquée diminue
  la durée traitée, sans déclarer les minutes manquantes analysées.
- Encodage local sérialisé, 960 pixels maximum, 8 images/s ; le fournisseur
  échantillonne à 4 images/s. Les actions rapides et masquées peuvent être manquées.
- Deux appels simultanés au maximum ; délais et durée de lot bornés. La limite de
  lot n’est pas une garantie de rapport exhaustif en dix minutes.
- Une ligne `VideoActionAnalysis` conserve les séquences réussies. Une relance de
  la même source et du même modèle reprend seulement les séquences manquantes.
  Un quota atteint ou une clé refusée arrête le lancement de nouvelles séquences.
- La disparition du processus laisse un état « interrompu » après expiration du
  battement de progression. Une relance est possible si source et base existent.

Le stockage dépend toujours de la configuration Render : une base ou vidéo placée
dans `/tmp` peut disparaître. Voir [RENDER_STORAGE.md](RENDER_STORAGE.md). Les tâches
de fond FastAPI ne sont pas une file de travaux durable indépendante du serveur.

## Rapport et statistiques

Le contrat typé couvre 34 types d’actions : buts, tirs, passes réussies/ratées,
passes décisives/clés, touches/centre, pertes, interceptions, récupérations,
duels, contres, arrêts/relances, fautes, exclusions, penalties, transitions,
supériorités/infériorités, rotations et bornes de possessions.
Il demande aussi zones bassin/cage, main, type de tir/passe, phase, période,
cause, pression et décision lorsqu’un indice visible les étaye.

Les chiffres sont des **détections automatiques**, distinctes des `Event` confirmés.
Le seuil interne de 0,65 filtre des propositions peu certaines ; la confiance du
modèle n’est pas une probabilité calibrée. Les équipes indéterminées ont leur propre
colonne. Les bonnets sont des propositions visuelles, jamais des noms inventés.
Une fiche peut présenter les propositions correspondant à son bonnet dans son équipe,
avec une association explicitement provisoire et sans fusion des statistiques confirmées.

Le rapport web, HTML, JSON, CSV et ZIP contiennent les mêmes mesures automatiques,
les résultats par bonnet, l’état de chaque séquence et ses limites de visibilité.
Chaque action dispose d’un extrait privé à la demande. Les extraits déjà produits
sont réutilisés et inclus dans le ZIP avec des liens relatifs.

## Limites qui restent à résoudre

- Les distances, vitesses de nage/tir, sprints et temps de déclenchement nécessitent
  suivi calibré et cadence suffisante ; ce modèle ne les mesure pas.
- Le temps de jeu complet nécessite vérification continue des rotations et de
  l’identité. Présence à l’écran et temps dans le bassin ne sont pas équivalents.
- Les notes et la fatigue ne sont pas déduites arbitrairement des images.
- Un modèle vidéo généraliste peut manquer ou confondre des actions. Aucune
  précision/exhaustivité n’est certifiée sans corpus de matchs annotés et mesure
  indépendante des faux positifs, omissions et erreurs d’attribution.

## Validation

`source/tests/test_video_action_analysis.py` vérifie mapping des captures, exclusion
des replays/doublons, réponses malformées, isolement des comptes, checkpoints,
cohérence des agrégats/exports et décodage d’un vrai MP4 synthétique. Les réponses
du fournisseur utilisées dans les tests sont **simulées**. Elles ne valident pas
la qualité de reconnaissance sur Granville–Choisy ou un autre match réel.

Avant d’annoncer une analyse exhaustive, activer un fournisseur autorisé puis
comparer une vidéo de référence annotée à ses détections, y compris les actions
manquées et l’attribution des deux équipes. Sans cette mesure, publier « estimation ».

API utilisée : [compréhension vidéo](https://ai.google.dev/gemini-api/docs/video-understanding),
[sorties structurées](https://ai.google.dev/gemini-api/docs/structured-output),
[Interactions REST](https://ai.google.dev/api/interactions-api), consultées le 15 septembre 2026.
