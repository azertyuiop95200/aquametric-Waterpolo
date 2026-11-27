# AquaMetric · vidéos de 1 à 5 Go : stockage direct R2/S3

## Pourquoi l'ancien téléversement de 50 Mo ne convient pas

Le formulaire historique passe par une seule requête `multipart/form-data` sur Render.
Un replay de water-polo de 1 h 22 min en HD peut atteindre plusieurs Go.
Augmenter `MAX_UPLOAD_MB` ne règle pas les limites de durée de requête, de disque
temporaire ni la perte des fichiers sur Render Free lors d'un redémarrage.

L'import volumineux utilise maintenant **S3 Multipart Upload signé** :
- le navigateur découpe un fichier MP4/MOV/MKV/WebM/M4V en morceaux de 16 MiB ;
- AquaMetric reçoit les métadonnées et signe les morceaux (il ne reçoit pas les octets vidéo) ;
- le navigateur envoie au maximum trois morceaux en parallèle au bucket privé ;
- les morceaux reçus sont retrouvés par `ListParts` : interrompre et reprendre ne réenvoie pas ceux qui existent ;
- le serveur valide l'ordre, le nombre, la taille de chaque morceau et la taille de l'objet final ;
- un match n'est créé qu'après cette vérification ; son état initial est `cloud_video_received` ;
- la lecture du fichier est autorisée au propriétaire au moyen d'une URL de lecture temporaire.

**Un téléversement terminé ne signifie pas analyse terminée.** Les OCR et métriques
sportives automatiques des objets cloud nécessitent un traitement vidéo distant
adapté ; le lecteur HTML5 intégré au rapport permet déjà le codage manuel horodaté.

## Configuration requise par l'administrateur

1. Créer un bucket **privé** dans [Cloudflare R2](https://dash.cloudflare.com/)
   ou un stockage compatible AWS S3. Ne pas rendre le bucket public.
2. Créer des identifiants d'API limités à ce bucket, avec droits multipart :
   `CreateMultipartUpload`, `UploadPart`, `ListParts`,
   `CompleteMultipartUpload`, `AbortMultipartUpload`, `HeadObject`,
   `GetObject` et `PutObject` selon le fournisseur.
3. Sur Render, ouvrir le service → **Environment**, puis renseigner (jamais dans
   GitHub ou dans la conversation) :
   - `AQUAMETRIC_OBJECT_BUCKET` : nom du bucket privé.
   - `AQUAMETRIC_OBJECT_ENDPOINT` : endpoint S3 compatible, pour R2
     `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`.
   - `AQUAMETRIC_OBJECT_ACCESS_KEY` : identifiant de clé R2/S3.
   - `AQUAMETRIC_OBJECT_SECRET_KEY` : clé secrète R2/S3.
   - `AQUAMETRIC_OBJECT_REGION` : `auto` pour R2 (ou la région S3).
   - `AQUAMETRIC_MAX_CLOUD_VIDEO_GB` : `5` par défaut.
   - `AQUAMETRIC_MAX_USER_CLOUD_GB` : `10` par défaut.
4. **Important :** configurer aussi une base de données **PostgreSQL persistante**
   pour `DATABASE_URL`. Un SQLite dans le conteneur Render Free disparaît
   au redéploiement ou à la mise en sommeil et les matchs perdraient le lien vers
   le fichier cloud. Si et seulement si SQLite est sur un disque persistant,
   l'administrateur peut définir `AQUAMETRIC_PERSISTENT_UPLOAD_METADATA=1`.
   Un disque persistant Render n'est pas disponible sur le plan Free.
5. Configurer la politique CORS du bucket pour autoriser les requêtes PUT
   envoyées depuis le navigateur de l'utilisateur, en limitant les origines
   aux domaines AquaMetric réellement utilisés. Exemple R2 :
   ```json
   [
     {
       "AllowedOrigins": [
         "https://aquametric-youtube-validation.onrender.com",
         "https://aquametric-polo-coach.onrender.com"
       ],
       "AllowedMethods": ["PUT", "GET", "HEAD"],
       "AllowedHeaders": ["*"],
       "ExposeHeaders": ["ETag"],
       "MaxAgeSeconds": 3600
     }
   ]
   ```
6. Configurer sur le bucket une règle de cycle de vie **AbortIncompleteMultipartUpload**
   après 1 à 7 jours pour éviter les coûts de morceaux abandonnés.
7. Relancer le service, visiter `/api/large-upload/capabilities`, vérifier
   `"enabled":true`. Dans « Nouvelle analyse », utiliser « Importer un match
   volumineux ». Si le navigateur est interrompu, sélectionner exactement le même
   fichier et cliquer sur « Reprendre ».
8. Essayer avec un MP4 de quelques dizaines de Mo, puis 1–3 Go avant de
   l'utiliser pour un match officiel. Surveiller les limites de stockage et
   le quota de transfert du fournisseur choisi.

## Contrôles et limites

- Taille : jusqu'à 5 GiB par fichier par défaut ; 10 GiB réservés par utilisateur.
- Types : MP4, MOV, M4V, WebM, MKV ; seules les extensions reconnues sont signées.
- Les URL d'envoi expirent en 15 minutes ; de nouvelles signatures sont obtenues
  lors d'une reprise.
- Deux sessions multipart simultanées maximum par utilisateur.
- Les sessions appartiennent au compte authentifié et ne sont pas accessibles à
  d'autres comptes ; les comptes de démonstration sont exclus.
- Le serveur ne fait **jamais confiance aux déclarations de progression du navigateur**
  pour décider qu'une vidéo est reçue.
- Les transferts interrompus doivent être annulés ou nettoyés via le cycle de vie
  du bucket ; sauvegarder la DB et les règles de conservation du stockage.
- Un fichier cloud peut être lu et annoté, **mais** le traitement automatique
  complet d'une vidéo de 3 Go doit être implémenté via un worker et un stockage
  de travail capables de décoder cette taille. Aucun événement sportif n'est
  inféré à partir du seul upload.

Tests : `pytest source/tests/test_large_video_cloud_upload_2026.py` depuis
l'environnement Python de `source/`. Les tests simulent un transfert de 3 GiB
sans allouer les 3 GiB en local.
