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

## Rééquilibrage après le seed homogène (base synthétique uniquement)

La commande de seed existante a volontairement attribué deux images et six Resources
à chaque Activity. Ce n'est **pas** une règle du produit. Pour rendre les galeries
de démo moins uniformes, prévisualiser puis retirer seulement les usages
Presentation correspondant exactement aux deux PNG synthétiques générés :

    python manage.py rebalance_discover_demo_images
    python manage.py rebalance_discover_demo_images --limit 5
    python manage.py rebalance_discover_demo_images --apply

Le rééquilibrage est déterministe par UUID ; il conserve 0, 1 ou 2 images de seed
sur chaque Activity. Il vérifie le checksum exact, le texte alternatif et la
permission de l'opérateur avant tout retrait. Il n'efface **aucun** fichier ou
PresentationAsset, ne retire aucune image réelle et ne touche ni aux Resources,
ni aux droits, ni aux médias des Occurrences. Le retrait passe par le service
canonique et reste auditable. Dry-run par défaut.

**Important** : ne pas relancer le seed homogène sur les mêmes Activities après
ce rééquilibrage : la version actuelle du seed peut réassocier les images
retirées. Les Resources générées restent présentes ; leur éventuelle
diversification requiert une opération métier de retrait/versionnement explicite,
sans suppression ORM directe. Aucune règle « toute Activity doit avoir un média »
ne doit être introduite en production.

## Diversification des Resources synthétiques

Après les 157 Activities ensemencées, prévisualiser :

    python manage.py rebalance_discover_demo_resources
    python manage.py rebalance_discover_demo_resources --limit 5

Puis, uniquement sur la base de démonstration sauvegardée :

    python manage.py rebalance_discover_demo_resources --apply

Les Resource gardées varient selon une empreinte stable de l'UUID. Le service
`retire_resource` impose l'autorité Activity, ne retire que l'état published,
préserve les versions/fichiers, et publie l'événement resource.retired. La commande
ne touche qu'aux clés de seed dont titre, type, visibilité et contenu ou empreinte
correspondent strictement au générateur. Elle ne fait aucune suppression physique.
Les fixtures modifiées ou sans opérateur autorisé sont ignorées. Ne pas relancer
l'ancien seed homogène ensuite ; il n'est pas adapté à ce rééquilibrage.
Cette diversification ne crée ni MP4 ni WAV : l'import documenté du ZIP doit
être développé séparément avec un lien sémantique explicite vers l'Activity.

## Audit lecture seule : fichiers réellement présents

Ne pas lancer un nouveau seed avant d'avoir mesuré les octets effectivement
disponibles dans les stockages existants :

    python manage.py audit_discover_demo_storage
    python manage.py audit_discover_demo_storage --examples 20

La commande audite par défaut toutes les Resources `demo-*`, y compris
`retired`, et les PresentationMediaUse publiés. L'option
`--all-resources` inclut les ressources non synthétiques. Elle vérifie
`storage.exists` sans ouvrir les octets ni publier d'URL et ne touche
ni à la BDD ni aux fichiers. Les états `missing-bytes`,
`missing-reference` et `storage-error` sont des anomalies à examiner.
L'existence physique ne prouve pas l'autorisation HTTP : compléter
par des essais visiteur, participant, gestionnaire et le rendu Web/Flutter.
