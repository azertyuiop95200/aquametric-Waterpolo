# AquaMetric — Statistiques sportives automatiques : YouTube, MP4 et gros fichiers

Mise à jour : 25 novembre 2026 — code en branche de validation, PAS dans le site principal.

## Trois parcours de lecture, un même registre d'actions

1. **Lien YouTube public** : l'API Gemini Interactions peut lire un YouTube
   public directement (`{"type":"video","uri":"https://www.youtube.com/watch?v=..."}`).
   Le serveur n'a pas besoin de télécharger le replay ni de capturer l'écran ;
   il demande des intervalles `start_offset/end_offset` successifs de 60 s.
   Il faut renseigner la durée réelle de la vidéo dans le nouveau formulaire,
   car aucune durée ne doit être inventée à partir d'un titre. Sur téléphone,
   le même parcours direct est possible. L'API fournisseur ne peut pas
   nécessairement ouvrir les vidéos non répertoriées, privées, supprimées ou
   à accès restreint. La capture d'onglet reste le secours.
2. **MP4/MOV local (taille de l'import HTTP)** : après création du match, le
   moteur d'actions démarre avant le traitement OCR/extraits, y compris dans
   le routeur historique `premium_ingest_routes`. Il encode des clips de 60 s
   indépendants, interroge le fournisseur IA et enregistre chaque progrès.
   Ajouter une vidéo Q2/Q3/Q4 lance également la détection de cette partie.
3. **Fichier 1 à 5 Go dans R2/S3 privé** : le navigateur utilise l'upload
   multipart direct ; dès que chaque morceau et la taille finale sont
   vérifiés, un worker FFprobe/FFmpeg lit uniquement les plages temporelles
   requises par une URL GET temporaire du bucket (requêtes HTTP Range),
   génère un petit MP4 local jetable puis effectue la reconnaissance IA.
   Le fichier de plusieurs Go n'est jamais importé en entier sur le disque
   temporaire de Render. Le stockage doit supporter les lectures seekables,
   le fichier doit être décodable et le serveur doit disposer de `ffprobe`
   et `ffmpeg`.

Les trois parcours enregistrent des `VideoActionAnalysis` séparés par
source/intervalle. Le tableau de bord `/matches/{id}/analysis/actions/live`
charge l'état à quelques secondes d'intervalle, **sans interrompre la vidéo**.
Un but compte comme un seul tir. Les doublons de la même vidéo YouTube
analysée directement et par capture ne sont pas additionnés.

**Les résultats IA sont des hypothèses sportives, jamais des faits confirmés.**
Le moteur ne remplit pas la carte avec des coordonnées inventées ; la shot map
exacte ne contient que les actions avec une position observée/validée.
Les compteurs sont exclusivement ceux des segments effectivement traités.
La précision doit être évaluée sur des matchs annotés pour pouvoir parler de
rapport complet.

## Configuration Render (administrateur, secrets privés)

Dans **Render > Service de validation > Environment** :

- `AQUAMETRIC_VIDEO_ACTIONS=1`
- `GEMINI_API_KEY=...` (clé Google AI Studio, ne JAMAIS la mettre en GitHub)
- `AQUAMETRIC_VIDEO_MODEL=gemini-3.8-flash` (modèle reconnu par l'API Gemini
  Interactions en novembre 2026 ; vérifier l'accès et les quotas du projet)
- Pour les très gros fichiers : `AQUAMETRIC_OBJECT_BUCKET`,
  `AQUAMETRIC_OBJECT_ENDPOINT`, `AQUAMETRIC_OBJECT_ACCESS_KEY`,
  `AQUAMETRIC_OBJECT_SECRET_KEY`, une base PostgreSQL persistante, et un
  bucket R2/S3 privé autorisant les GET/Range signés. Voir
  `docs/large-video-uploads.md`.

Le `Dockerfile` du dépôt installe déjà `ffmpeg` (dont `ffprobe`). Ne
renseigner aucune clé ni token dans le chat, le dépôt ou un ticket.

L'API de Google peut facturer chaque minute demandée et appliquer des quotas.
Une exécution de 80 min peut nécessiter plusieurs sessions : chaque exécution
est plafonnée en temps sur le serveur et **la reprise conserve les intervalles
déjà terminés**. Le bouton « Analyser ou reprendre les intervalles manquants »
du rapport reprend le travail. Éviter les retries sans borne ou les rappels
automatiques qui pourraient multiplier la consommation API.

## Essai conseillé

1. Mettre la version de validation à jour, avec `GEMINI_API_KEY` et le
   commutateur d'actions activés.
2. Ouvrir `/matches/new`, saisir équipes, catégorie et URL YouTube **publique**,
   puis la durée exacte visible dans YouTube. « Analyser » crée le dossier et
   déclenche les tranches de 60 s. Sur téléphone, le même formulaire fonctionne.
3. Le dossier affiche « Statistiques détectées pendant le traitement ». La
   progression 0/N -> 1/N -> 2/N augmente pendant l'analyse. Le rapport reste
   lisible même pendant les appels au fournisseur.
4. Contrôler la liste des actions, le camp, la preuve horodatée et les résultats
   non déterminés. N'utiliser le score ou les métriques automatiques pour
   préparer une séance qu'avec leur statut **provisoire** clairement identifié.
5. Importer séparément Q1…Q4 ou un MP4 complet ; vérifier que les vidéos sont
   traitées sans fusion des horodatages locaux de périodes différentes.
6. Pour un fichier cloud de plusieurs Go, tester d'abord un MP4 court dans le
   bucket configuré, puis augmenter progressivement les tailles. Un hébergement
   Render gratuit avec SQLite non persistant ne suffit pas.

## Diagnostics et points de blocage

- `GET /health/video-actions` : moteur activé, clé présente, modèle sélectionné
  (jamais la valeur de la clé).
- `GET /api/large-upload/capabilities` : bucket privé et base persistante prêts.
- `GET /matches/{id}/analysis/actions/live` : lecture authentifiée, statut
  running/partial/ready et nombre de séquences réellement terminées.
- `GET /matches/{id}/analysis/actions/status` : progression du dernier run.
- Si YouTube renvoie non disponible, l'URL peut être privée, non répertoriée,
  géobloquée, limitée par le fournisseur, ou le quota IA peut être dépassé.
  Aucun contournement d'authentification n'est tenté.
- Si les 5 Go sont stockés mais les statistiques vides, vérifier la présence
  de `ffprobe` et les requêtes HTTP Range sur l'endpoint R2/S3, ainsi que
  `AQUAMETRIC_VIDEO_ACTIONS` et les quotas.
- Si le navigateur affiche des clips mais aucune action, les clips sont peut-être
  des écrans YouTube statiques : le filtre de qualité bloque alors leur
  promotion en véritables statistiques.

## Référence fournisseur

- <https://ai.google.dev/gemini-api/docs/video-understanding> —
  « Pass YouTube URLs » et « Set clipping intervals » ; fonctionnalité URL
  YouTube en preview, réservée aux vidéos publiques.
- <https://ai.google.dev/api/interactions-api> — API Interactions, input video,
  processing static et réponse structurée.

Tests : `source/tests/test_youtube_direct_video_actions_2026.py`,
`source/tests/test_cloud_s3_action_streaming_2026.py`,
`source/tests/test_live_automatic_stats_2026_11.py` et suite globale.
Les tests simulent les réponses du fournisseur ; ils ne prouvent pas encore la
précision du modèle sur un vrai match, laquelle exige une validation en production.
