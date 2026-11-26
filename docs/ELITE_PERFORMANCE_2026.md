# Ultimate performance 2026

Evidence-only extension based on the user-supplied Water Polo Stats match and player report structure (no private match data copied). Goals count as shots, accuracy and conversion differ, possession ends are explicit, numerical advantage and penalty denominators are separate. Physical metrics are recorded samples, not video estimates. Senior defaults 28/18 seconds, four 8 minute quarters, exclusion 18 seconds; other formats require configuration. See https://www.worldaquatics.com/rules/competition-regulations and https://www.ffnatation.fr/reglements-du-water-polo.

## Account persistence
The existing application supports DATABASE_URL (PostgreSQL) and otherwise uses SQLite. Render free local storage is not persistent. Preserve/backup any existing account and match data before migrating; an erased password hash cannot be reconstructed. Provision a durable database and configure DATABASE_URL in the service. Google requires GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, and GOOGLE_OAUTH_REDIRECT_URI, with matching authorized redirect https://aquametric-youtube-validation.onrender.com/auth/google/callback. Do not commit secrets, auto-authorize an email, or disable identity verification. Existing verified Gmail identities are linked by the existing OIDC implementation. No password reset mechanism without a verified delivery channel.

## Next steps
Continuous tracking with identity re-identification, camera calibration, clock OCR, substitution and foul review; separate candidate predictions from confirmed actions; xG calibration on labeled shots; plus/minus with complete lineups; user-editable rules profiles; automatic possession segmentation and validated tests on held-out real matches. These are not provided by the annotation reducer.
