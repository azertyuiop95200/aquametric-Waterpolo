# Conservation des dossiers AquaMetric sur Render

Les adresses `aquametric-polo-coach.onrender.com` et
`aquametric-web-demo.onrender.com` sont deux installations distinctes.
Les identifiants `/matches/1` ne désignent pas nécessairement le même match.

## État vérifié le 14 septembre 2026

Les deux services gratuits utilisent SQLite et des médias sous `/tmp`.
Ces fichiers disparaissent au redémarrage, au redéploiement ou à la mise en
veille de Render. Une correction de l'OCR ne résout pas cette perte de stockage.
Le code invalide désormais les anciennes sessions si la base est remplacée,
pour empêcher qu'un numéro de compte réutilisé donne accès à un autre utilisateur.

Une base `aquametric-db`, en région Frankfurt, existe déjà dans l'espace Render.
Sa formule gratuite expire le **6 octobre 2026**. Le raccordement n'a pas été
effectué : les outils disponibles ne fournissent pas sa chaîne de connexion,
et l'inspection SQL du connecteur échoue à établir la connexion TLS.

## Raccordement sans publier de secret

1. Dans Render, ouvrir `aquametric-db` → **Connect** → **Internal Database URL**.
2. Dans le service choisi, **Environment**, remplacer `DATABASE_URL` par cette
   URL interne. SQLAlchemy utilise déjà le pilote psycopg 3. Ne pas enregistrer
   cette valeur dans Git ou dans une conversation.
3. Sauvegarder les dossiers de l'installation actuelle avant de basculer de
   base. Une URL de connexion ne migre pas les anciennes données SQLite.
4. Redéployer, créer un dossier de contrôle, redéployer une seconde fois et
   vérifier que le compte et le dossier existent encore.

La base contient comptes, matchs, statistiques, observations, annotations et
références aux médias. Elle ne contient pas les fichiers vidéo.
Connecter les deux sites à la même base partage leurs données de comptes ;
ne pas fusionner automatiquement deux bases SQLite dont les identifiants se
chevauchent.

## Conservation des vidéos et des extraits

Render ne permet pas de disque persistant sur un service gratuit. Après choix
explicite d'une instance payante et ajout d'un disque monté sous `/var/data`,
configurer :

```
UPLOAD_DIR=/var/data/uploads
EVIDENCE_DIR=/var/data/evidence
```

Si une seule installation conserve SQLite sur ce disque, utiliser
`DATABASE_URL=sqlite:////var/data/aquametric.db` à la place de Postgres.
Sauvegarder et restaurer les anciennes données avant bascule ; le disque neuf
ne contient pas les dossiers perdus. Aucun achat ni changement d'offre n'a été
effectué par le correctif.

## Analyse sur petite instance

```
CAPTURE_LIVE_OCR=0
AQUAMETRIC_OCR_BACKEND=rapidocr
```

Les images de capture sont conservées et l'OCR s'exécute après réception,
hors de la requête HTTP d'envoi. Les calculs natifs et encodages vidéo sont
bornés et sérialisés. Le rapport suit la progression, puis donne accès aux
vrais MP4 ; le ZIP inclut ces fichiers et un rapport HTML avec liens relatifs.
Le code ne transforme pas les lectures du score ou pics de mouvement en
statistiques sportives exhaustives ou en identités de joueuses.

Sources : https://render.com/docs/free et https://render.com/docs/disks
