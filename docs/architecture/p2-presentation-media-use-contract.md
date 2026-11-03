# P2 — Association explicite des médias de présentation

Base initiale : `main` `d0f0ec421c94c255fa4c0acd3509938a70c6322f`.

## Problème

Un `PresentationAsset` possède les octets et la provenance ; `ActivityPresentation` configure un rendu MPS et non la simple représentation d'une possibilité. `Event.cover_image` reste une source spécialisée. `ActivityResource` reste une ressource de préparation. Un `editorial_data.hero_image` historique est une URL, pas une relation propriétaire. Aucun de ces modèles ne représente à lui seul le sujet, l'usage, l'ordre et la publication d'un fichier graphique.

## Décision

`PresentationMediaUse` est une relation additive du domaine `presentations` vers `PresentationAsset`, `Activity` et éventuellement `Occurrence`.

- Un media-use est créé en brouillon ; il ne devient public que via le service `publish_presentation_media`.
- `purpose` : `recognize`, `understand`, `establish`, `prepare`, `act` (sémantique différente des purposes MPS `public_page`, `invitation`…).
- Le propriétaire de l'asset doit être le propriétaire logique de l'Activity : Profil personnel ou Espace. Aucun accès implicite croisé.
- Un usage Occurrence reste limité à cette Occurrence. Une association Activity est commune à l'Activity.
- `position` assure un ordre déterministe. `alt_text` est obligatoire.
- L'usage retiré reste historique et permet un nouvel usage explicite du même asset. Aucun backfill.
- JPEG/PNG uniquement, conformément au service d'upload Presentation existant. Pas de média universel vidéo/audio.
- `Event.cover_image`, `ActivityResource`, `ActivityPresentation` et `hero_image` préexistants ne sont pas modifiés.

## Opérations et frontières

`associate_presentation_media`, `publish_presentation_media`, `retire_presentation_media`, `reorder_presentation_media`, `replace_presentation_media` vérifient `ACTIVITY_MANAGE` côté serveur. L’association et la publication revalident aussi le droit d’utiliser l’asset : auteur de l’upload, Profil propriétaire ou `SPACE_MANAGE` du bon Espace. Un mandataire Activity seul ne peut pas divulguer un asset Espace importé par un tiers. Le modèle revalide l'ownership et le lien Occurrence/Activity. La publication vérifie les octets au stockage à cet instant, mais ne crée aucun statut `available` en BDD.

`public_presentation_media_for_activities(activities, occurrences=(), purpose=...)` retourne les références de média publiées sous forme de DTOs, **sans URL de fichier**. Elle ne réexécute pas le moteur d'admission Discovery ni les règles Group/Privacy d'une possibilité ; l'appelant doit fournir des Activities déjà admissibles. Elle applique néanmoins un garde minimum : Activity `public` et `published`, usage `published`, occurrence explicitement fournie. Une seule requête groupée, `select_related("asset")`.

## Handoff P3

P3 devra :
1. invoquer ce selector seulement après l'admission canonique des possibilités ;
2. donner à chaque binding un `target` et une finalité, sans émettre une URL privée/brute issue du stockage ;
3. définir et sécuriser le mécanisme HTTP de consultation des assets publics (contrôle d'autorité, retrait, cache, traitement des erreurs et disponibilité du fichier) ;
4. faire dériver `representation.image_url` du même ensemble publié lorsque ce transport est sécurisé ;
5. préserver les sources existantes `Event.cover_image` et les Resources, sans promouvoir automatiquement les Resources en couvertures ;
6. préserver l'absence légitime de média.

## Limites connues

Le stockage `PresentationAsset.file` historique et `editorial_data.hero_image` sont déjà publics via leurs URL lorsque le déploiement dessert ce stockage : P2 n'introduit aucun nouveau endpoint et ne prétend pas garantir la confidentialité de ces anciennes URL. Leur remplacement exige une analyse de compatibilité et un contrat de transport séparé avant P3.

## Vérifications attendues

`python manage.py test presentations.test_media_use presentations.tests presentations.test_library_hardening`

`python manage.py check`

`python manage.py makemigrations --check --dry-run`

Migration additive `presentations.0005_presentationmediause` à valider sur PostgreSQL en CI. Aucune modification de données de démonstration, API Discovery ou Flutter.


## Ajout P2 : stockage protégé des nouveaux médias N1

La migration additive `presentations.0006_private_presentation_assets` conserve `PresentationAsset.file` pour les anciens rendus MPS et ajoute `PresentationAsset.private_file`, stocké hors du `MEDIA_ROOT` public via `PrivatePresentationStorage`. Le formulaire d'import N1 écrit seulement dans ce champ protégé. La publication et le téléchargement autorisé privilégient `private_file` et conservent une lecture de compatibilité des anciens assets `file`. Les anciens liens `editorial_data.hero_image` ne sont pas automatiquement migrés ; leur confidentialité reste à vérifier selon le routage serveur existant.
