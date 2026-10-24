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

## Fermeture N1 : références de fichiers de démonstration cassées

Le contrôle sur la copie locale a montré 132 images Presentation présentes
et 228 fichiers de Resource `demo-*` publiés absents (anciens imports).
Il ne faut ni les remplir avec des contenus inventés, ni les remplacer par
une URL prise au hasard sur Internet, ni tenter de récupérer des octets sans
provenance/droits vérifiés. Un lien public vérifié doit être une Resource URL,
via les services Preparation ; il ne rend pas un ancien fichier FILE valide.

Opération de réconciliation en deux étapes, **uniquement sur la BDD de démo**
après sauvegarde :

    python manage.py reconcile_discover_demo_files
    python manage.py reconcile_discover_demo_files --apply --confirm-demo
    python manage.py audit_discover_demo_storage

La première commande ne modifie rien. La seconde retraite seulement les
Resources `demo-*` de type FILE encore publiées dont le stockage ne contient
plus les octets. Elle emploie `retire_resource` avec une autorité réelle,
préserve les lignes, versions et fichiers, ne recrée aucune Activity, ne
construit aucune URL, et saute les erreurs de stockage et les cas non autorisés.
Relancer est idempotent. Elle ne restaure pas les fichiers perdus.

La BDD de production future est neuve et séparée de cette BDD synthétique ;
ne pas transférer ses fichiers, son stockage, ses utilisateurs de démo ou ses
références de fichiers cassées. Le ZIP exemple est un jeu de QA, pas une
source sémantique automatiquement pertinente pour les 157 Activities.
Les medias des Occurrences suivent leur propre contexte et accès.

Gates : `python manage.py test preparation.tests
presentations.test_reconcile_discover_demo_files`, puis test manuel
visiteur/participant/gestionnaire sur URL publique, privée, absente ;
vérifier le rendu Découvrir sur Web et Flutter et la navigation vers les
documents, vidéos et audios réellement disponibles. L'absence d'images est
un état valide.

## Lecture dans Makolo (N1, branche PR #522)

Les médias de représentation se consultent en restant dans la surface Discover :
images et galerie en lecteur intégré avec zoom et compteur. Les ressources
publiques PDF, CSV, texte, image, audio et vidéo ont une destination de
consultation et un export explicite. Pour le texte, la projection Discover
n'expose qu'un extrait borné : l'endpoint Preparation
`/preparation/resources/<uuid>/text/` sert le texte intégral après contrôle
`can_view_resource`. Les fichiers Preparation passent par leur route
autorisée, jamais une URL de stockage privé.

Sur Flutter, l'icône signet conserve volontairement **une copie locale des
seules ressources publiques** (20 Mo maximum par document) dans le stockage
interne de l'application. Cette copie peut être retirée depuis le lecteur ;
l'icône téléchargement/export propose la feuille de partage native.
Ne jamais réutiliser ce cache public comme stockage de documents privés
pour un Profil. Les documents privés nécessitent un espace chiffré ou isolé
par Profil, purge de session et revalidation d'autorité adaptée.
La lecture Web est dépliable et reste sur la page ; le téléchargement est
une action séparée. Les sites externes ne se prêtent pas toujours à une
intégration iframe, et le navigateur intégré mobile est utilisé lorsqu'il
est pris en charge par la plateforme.

Contrôles locaux (pas de validation SDK Flutter depuis GitHub) :

    python manage.py test preparation.tests discovery.api.test_resource_previews
    cd mobile
    bash tool/dart_format.sh write
    bash tool/dart_format.sh check
    flutter test test/discovery_reader_test.dart
    flutter test test/discovery_mature_screen_test.dart

Vérifier manuellement sur appareil : premier chargement en ligne, sauvegarde
hors ligne, coupure réseau, réouverture, retrait de la copie, export système,
retour de galerie, permissions 404 et lecture PDF/MP4/WAV.

## Import réel du ZIP de QA (sans nouveau dossier)

Pour un scénario explicitement compatible avec `Clinique entrepreneuriale
Yaounde`, repérer une Activity publique publiée et son gestionnaire dans
la BDD synthétique. Depuis la racine du projet :

    python manage.py import_discover_demo_zip --zip "C:\\Users\\somaf\\Downloads\\makolo_decouvrir_n1_medias_demo.zip" --activity-id UUID --operator USERNAME

La commande prévisualise sans écrire. Pour appliquer sur la seule BDD de démo :

    python manage.py import_discover_demo_zip --zip "C:\\Users\\somaf\\Downloads\\makolo_decouvrir_n1_medias_demo.zip" --activity-id UUID --operator USERNAME --apply --confirm-demo

Vérification des noms/manifeste, taille et scénario avant import ; lecture
directe depuis l'archive, aucune extraction ni nouveau dossier de stockage.
3 couvertures PNG via PresentationAsset/PresentationMediaUse ; PDF, CSV, PNG
documentaire, MP4 et WAV via ActivityResource FILE ; texte public et note
PARTICIPANT distincts. Le même fichier image ne crée pas trois usages
identiques si ses octets sont identiques. Les fichiers sont servis par les
contrôles d'accès métier. Rejouer est idempotent ; un usage retiré n'est
pas réactivé. Ne jamais importer le ZIP dans une Activity sans lien avec
son scénario. Les sites publics externes restent des Resources URL dont
la source doit être vérifiée manuellement, pas des fichiers fictifs.
