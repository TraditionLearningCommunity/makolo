# Recette — trois vues distinctes de Mes / Nos démarches

**PR #522 · 12 novembre 2026.** Présentation Flutter uniquement. Les domaines Project, Dossier et Journey, leurs propriétaires API, leurs permissions et leurs relations ne changent pas.

## Constat sur les captures Android

- **Cartes** : carte riche avec type, statut et date, adaptée au balayage visuel.
- **Liste** : petite carte horizontale avec titre et sous-ligne, adaptée à un inventaire rapide.
- **Explorateur** : arborescence existante mais avec 28 px de gouttière vide devant toute démarche indépendante et un léger décalage superflu. Lorsqu'une fenêtre locale ne contient que des démarches racines, cette vue ressemblait trop à Liste.

## Ajustement

Conserver les trois modes plutôt que supprimer Liste. Dans l'Explorateur :
- Retirer la réserve de 28 px devant les éléments sans enfants.
- Rapprocher la marge extérieure de 4 à 8 px *mais* ramener le contenu réel des lignes racines de 28 px vers le bord; l'alignement est désormais indépendant de la présence d'un bouton d'extension.
- Rendre visibles la hiérarchie réelle avec des retraits progressifs de 16 px et un filet vertical sur les niveaux enfants.
- Ajouter une séparation discrète entre lignes, conserver le titre cliquable, la flèche d'accès et les boutons d'extension de 44 px distincts.
- Réserver le dépliage aux Projets/Dossiers ayant effectivement des enfants visibles; il ne crée aucun lien artificiel.
- Ajouter le repère « Par organisation » au-dessus de l'arborescence.

**Pas de duplication :** l'explorateur utilise toujours `OrganizerHierarchy`. Une Journey associée à plusieurs Dossiers reste représentée une seule fois sous son parent primaire acquis; les autres liens restent signalés. Les parents partiellement chargés ne sont pas réinventés.

## Recette sur émulateur

1. Ouvrir **Mes démarches**, puis comparer Cartes, Liste et Explorateur.
2. En Explorateur, vérifier qu'une démarche autonome commence près du bord gauche, sans colonne vide.
3. Avec Projet → Dossier → Démarche acquis, déplier successivement Projet puis Dossier. Confirmer la progression visuelle et l'ouverture des profondeurs existantes.
4. Vérifier les filtres, les passages entre les trois modes et le retour arrière.
5. Refaire sur le contexte Space via **Nos démarches**, sans mélange de projections ni autorisation supposée.

**Tests** : `mobile/test/objective_organizer_view_modes_test.dart` couvre les trois modes, les racines sans espace réservé, les retraits des enfants et la navigation.

Tests Flutter et formatage canonique non exécutés ici (SDK Flutter/Dart absent). Exécuter le formatter propriétaire et la CI mobile avant toute intégration. Aucun merge.
