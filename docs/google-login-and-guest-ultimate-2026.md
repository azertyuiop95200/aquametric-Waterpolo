# AquaMetric — Se connecter avec Google et tester Ultimate sans mot de passe

## Lien de validation

- Connexion : https://aquametric-youtube-validation.onrender.com/login
- Invité Ultimate : https://aquametric-youtube-validation.onrender.com/guest/ultimate
- Nouveau match après connexion : https://aquametric-youtube-validation.onrender.com/matches/new

**Le mode invité** donne accès à la vraie page Ultimate et aux rapports
associés à un identifiant utilisateur temporaire distinct. Trois matchs
par session, quatre parties par match, fichiers de 30 Mo maximum ; pas de
Gemini payant, pas de gros stockage R2/S3, pas de garantie de conservation
en l'absence de PostgreSQL persistant. Aucun événement sportif n'est inventé.

## Activer « Continuer avec Google »

AquaMetric prend en charge le parcours OpenID Connect OAuth 2.0 **code
autorisation côté serveur**. Authlib vérifie `state`, `nonce` et le
`id_token` signé par Google selon sa configuration OIDC officielle. Le site
utilise l'identifiant stable `sub`, pas simplement une adresse email.

1. Dans **Google Cloud Console** :
   <https://console.cloud.google.com/apis/credentials>, créer un projet
   ou sélectionner celui de l'application, configurer « Google Auth Platform »
   (écran de consentement / Branding / Audience), puis créer un client
   **OAuth 2.0 > Application Web**.
2. Autoriser comme URI de redirection :
   `https://aquametric-youtube-validation.onrender.com/auth/google/callback`
   (URI exact, HTTPS). Si l'application est en mode Testing, ajouter
   explicitement l'adresse Gmail de l'utilisateur aux « utilisateurs de test ».
   Ces réglages sont modifiés par l'administrateur du projet Google, jamais
   par l'assistant à la place de l'utilisateur.
3. Dans **Render > service aquametric-youtube-validation > Environment**
   ajouter les trois variables (ne jamais coller la clé dans un chat) :
   - `GOOGLE_OAUTH_CLIENT_ID` = ID du client Web Google
   - `GOOGLE_OAUTH_CLIENT_SECRET` = secret du client Web Google
   - `GOOGLE_OAUTH_REDIRECT_URI` =
     `https://aquametric-youtube-validation.onrender.com/auth/google/callback`
4. Déployer le service et ouvrir `/login` : le bouton
   « Continuer avec Google » sera affiché automatiquement lorsque les trois
   variables sont présentes. Valider la sélection du compte sur le site
   `accounts.google.com` et revenir dans AquaMetric.
5. Pour les comptes locaux **@gmail.com / @googlemail.com** dont l'adresse
   correspond à l'adresse Google vérifiée, l'ancien `User.id`, ses matchs
   et ses rapports sont conservés dans la même base. Pour les adresses
   Google tierces, il faut confirmer **une seule fois le mot de passe
   AquaMetric existant** avant la liaison ; aucune correspondance
   automatique par email non fiable.

**Important** : le nouveau fournisseur d'identité Google NE recrée PAS les
dossiers perdus si l'ancien serveur Render utilisait SQLite éphémère
(redéploiements sans disque persistant). Pour préserver les comptes/matchs,
configurer une base PostgreSQL persistante et migrer l'ancienne base si elle
existe. Ne pas créer un nouvel espace déconnecté et prétendre qu'il contient
les anciens matchs.

Le site principal n'est pas modifié par la validation. Une véritable
connexion Google en production nécessite l'autorisation effective du compte
Google et un client OAuth configuré. Les tests automatiques simulent les
réponses Google signées et ne remplacent pas cette étape réelle.
