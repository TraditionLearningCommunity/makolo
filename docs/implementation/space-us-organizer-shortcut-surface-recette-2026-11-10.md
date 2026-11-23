# Recette Nous — raccourci Démarches et allégement du contenu (2026-11-10)

**PR #522** · correction de la surface mobile Nous, sans modèle parallèle.

## Changements

- Le titre de page « Nous » n'est plus répété dans le contenu : l'en-tête de l'application porte déjà ce repère.
- Suppression sur **Nous uniquement** du bandeau de fraîcheur « Actualisation disponible », déjà couvert par l'état technique du shell. Si la projection de Nous existe, une expiration de fraîcheur ne la remplace plus par une page d'erreur. L'invalidation d'autorisation continue de bloquer l'accès et une projection inexistante continue d'afficher son état vide.
- La carte « Notre Passeport » est suivie d'un raccourci **« Nos démarches »** utilisant le même `MakoloPrimaryShortcut` que « Mes démarches ». Sa destination est la route existante `/space/:slug/objectives`, qui crée le même `ObjectiveOrganizerScreen` avec `spaceSlug`, contrôle l'Actor Space actif et isole les lectures Objectives par contexte. Aucun nouvel écran.
- Allègement des espaces entre l'identité, le Passeport, le raccourci et les territoires : 12 px entre les premières cartes et 14 px avant « Notre espace », comme la composition Moi.
- « Informations et gestion » garde les destinations institutionnelles autorisées Réglages et Pilotage, sans sous-titre d'explication. Les cartes Abonnement et Connexions sont retirées **de Nous** seulement, sans révoquer leur accès par leurs routes légitimes.
- Les Zones à accès limité gardent leur présentation de permissions et ne reçoivent pas une destination collective non garantie.

## Recette Android

1. Dans Nous, vérifier que l'en-tête contient le seul titre « Nous », puis l'identité de l'Espace.
2. Vérifier l'ordre : identité → Notre Passeport → Nos démarches → Notre espace (liste/grille).
3. Ouvrir Nos démarches : même organisateur que Moi, avec le contexte du Space courant; revenir sans changer de Space.
4. Quand la connexion échoue mais que les informations existent, vérifier l'absence de bandeau de fraîcheur et le maintien de la vue; vérifier séparément qu'une révocation de droits n'affiche pas les données.
5. Sur une autre largeur Android, vérifier l'espacement et l'accessibilité des deux raccourcis.
6. Au bas de Nous, vérifier l'absence d'Abonnement et Connexions mais la présence de Modifier les informations collectives et Comprendre notre activité si autorisées.

Pas de migration ni changement de modèle/API. Tests Flutter/Django à exécuter dans l'environnement de développement.
