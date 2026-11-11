# Recette — Nous comme identité collective vivante

**11 novembre 2026 — PR #522 — branche existante.** Objectif : alléger la surface mobile Nous sans inventer un second profil ni une gestion d'équipe parallèle.

## Changements Flutter

- Le portrait de l'Espace présente son **nom d'abord**, puis l'**archétype canonique** sous le nom, puis la description et la localisation. Les huit valeurs existantes de `SpaceArchetype` fournissent le libellé. Le composant partagé `MakoloIdentityPortrait` est conservé ; l'ordre de l'eyebrow reste inchangé dans Moi.
- Les membres autorisés apparaissent sous l'identité comme une **rangée de quatre petits avatars au maximum**, avec initiales réelles fournies par le serveur et `+N` seulement si le décompte autoritatif le justifie.
- Le texte « N membre(s) » ouvre la route existante `/space/:slug/us/team`, uniquement lorsque le handoff owner est autorisé. Un avatar disposant d'un identifiant de Profile ouvre la route canonique `/people/:id` : l'écran existant de Profil public applique toujours sa propre visibilité.
- La carte « Notre équipe » disparaît de la grille et de la liste des territoires. Aucune fonction de gestion des membres n'est supprimée ; sa profondeur et ses mandats restent propriétaires.
- « Ma place », « Nos relations », « Nos ressources », « Notre gouvernance », « Notre confiance », Notre Passeport et Nos démarches restent en place.

## Contraintes et cas limites

- Aucun changement des modèles, API, migrations, autorisations, membres ni mandats.
- Le footer s'affiche **uniquement** si `team.visibility == visible` ET le handoff `team` correspond au Space courant. Une projection limitée ou révoquée ne révèle aucun nom ou nombre.
- En cas de pagination, `+N` s'appuie sur le total serveur; si le total est absent, aucun chiffre n'est fabriqué.
- Les noms sont affichés sous forme d'initiales quand aucune photo n'est présente dans la projection canonique. Le modèle Organization et la projection Nous ne possèdent pas aujourd'hui de champ photo/logo institutionnel. Ne pas inventer une URL ni réutiliser une image privée pour simuler un logo. Une prise en charge réelle de médias Space devra être fournie par un owner canonique avec visibilité contrôlée.
- Pas de défilement automatique d'avatars : la navigation par la liste des membres reste la profondeur pertinente, accessible au toucher et à l'accessibilité.

## Vérifications

`mobile/test/space_us_surface_test.dart` couvre la hiérarchie, la grille, les quatre avatars et `+N`, l'ouverture d'un Profile via `/people/:id`, le lien membres, les scopes restreints, la révocation et le changement de Space.

Exécuter les tests Flutter ciblés, le formatter officiel et la recette Android (largeurs 320/360/393, permissions et retour arrière). Non exécutés dans l'environnement sans SDK Flutter.

Aucun merge; pas d'intervention sur Projets, Dossiers ou l'audit Drift.
