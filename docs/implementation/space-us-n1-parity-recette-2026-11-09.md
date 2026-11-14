# Recette Nous N1 — Parité de présentation avec Moi

**Date :** 2026-11-09  
**Cible :** PR #522, branche de travail existante  
**Portée :** présentation Flutter et Web de Nous, sans intervention dans Objectives, Project, Dossier ou Journey.

## Constats sur les captures de recette

- Le mode Grille de Moi dispose de deux colonnes sur l'émulateur, mais Nous n'en affiche qu'une : Nous imposait 24 px de marges et un minimum de 320 px **après marges** pour les deux colonnes.
- La carte d'identité de Nous prend une hauteur importante avec une longue description.
- Les actions d'administration au bas de Nous ressemblent à des liens isolés plutôt qu'aux cartes du reste de la surface.

## Correction appliquée

1. **Densité Flutter** : Nous utilise les marges compactes partagées de 16 px ; un index de largeur intérieure à partir de 260 px se compose sur deux colonnes (espacement 10 px). À plus faible largeur, une seule colonne reste lisible. Les cartes restent les composants `MakoloTerritoryGridCard` et `MakoloTerritoryListCard` issus du lot 2.
2. **Identité** : la présentation institutionnelle utilise le même `MakoloIdentityPortrait`, mais une variante de résumé limité à deux lignes visuelles. Le texte intégral reste dans la projection owner et n'est pas remplacé par un extrait artificiel ; le nom et la localisation restent présents. Les dimensions du logo et les espacements sont rapprochés de Moi. Le champ `subtitleMaxLines` est opt-in ; Moi conserve le comportement antérieur.
3. **Gestion** : les liens serveur existants (abonnement, connexions, réglages, pilotage) sont affichés avec le composant de carte partagée, avec icône et sous-titre, et sans route ou permission supplémentaire. Leur groupe est visuellement secondaire sous les territoires.
4. **Grammaire** : le compteur de la grille respecte le singulier/pluriel (`1 élément visible` / `N éléments visibles`).
5. **Web** : le CSS de Nous maintient deux colonnes sur les écrans compacts dès 280 px de viewport, limite visuellement la description sans retirer le contenu DOM et permet aux libellés longs de revenir à la ligne. L'affichage reste mono-colonne sous 280 px.

## Contrats conservés

- Aucun changement des modèles, API, permissions, migrations, routes ou handoffs.
- L'équipe, les relations et les autres données institutionnelles restent conditionnées aux mêmes projections autorisées et vérifications de slug.
- La grille/liste reste une préférence locale par Space ; la bascule ne change ni les droits cumulés ni les propriétaires métier.
- **Non compris dans ce correctif** : `Nos démarches`, Projets et Dossiers (traités dans d'autres conversations).

## Recette et tests

- `mobile/test/space_us_surface_test.dart` : position de deux cartes sur la même rangée aux largeurs 320/360/393, navigation vers l'owner Équipe, identité compacte sous longue description, entrée Paramètres et absence d'exception widget.
- `mobile/test/identity_surface_test.dart` : variante de description Space sans changement de la présentation Moi.
- Contrôler également la liste, le retour N2, le basculement d'acteur et les permissions de la PR #522 sur un émulateur réel.
- Les suites Flutter/Django et les captures Android doivent encore être exécutées sur un environnement Flutter configuré ; aucune CI verte ou QA Android n'est présumée.
