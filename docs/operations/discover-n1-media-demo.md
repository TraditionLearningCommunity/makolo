# Discover N1 — médias reproductibles

Exécuter uniquement sur une copie de la base de démonstration. Le dossier media/
local et la base db2.sqlite3 ne sont pas nécessairement synchronisés.
La commande réutilise les services autoritatifs Presentation et Preparation.

Commandes PowerShell (depuis la racine du dépôt, environnement Python actif) :

    Copy-Item .\db2.sqlite3 .\db-discover-media-demo.sqlite3
    $env:DJANGO_DB_PATH = (Resolve-Path .\db-discover-media-demo.sqlite3).Path
    python manage.py seed_discover_media_demo --operator USERNAME --activity-id ACTIVITY_UUID --dry-run
    python manage.py seed_discover_media_demo --operator USERNAME --activity-id ACTIVITY_UUID

Option vidéo courte réelle si ffmpeg est disponible :

    python manage.py seed_discover_media_demo --operator USERNAME --activity-id ACTIVITY_UUID --with-video

Effets bornés : deux PNG originaux associés à PresentationMediaUse/RECOGNIZE,
un PDF réel, un CSV réel, une image documentaire, un lien externe d’exemple.org, un texte public et un texte PARTICIPANT non public.
La vidéo optionnelle est une Resource documentaire : elle ne devient pas couverture.
Les assets Presentation sont stockés dans le stockage privé existant et délivrés
par leur usage publié contrôlé côté serveur. Aucune base ni média existant
n'est supprimé. Le script est réexécutable sans dupliquer les ressources nommées.

Vérifier dans la projection Discovery les deux media_bindings, l'image principale
et les resources accessibles. L'URL de la ressource PARTICIPANT doit retourner 404
en visiteur. Vérifier sur Web et Flutter l'ouverture des documents et la galerie.
Le contrôle réel sur Android et les fichiers locaux antérieurs restent à exécuter
sur la machine possédant MEDIA_ROOT et le SDK Flutter.
