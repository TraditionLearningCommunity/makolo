# Audit final anti-duplication — Interaction Grammar (PR #522)

**Date :** 9 novembre 2026  
**Portée :** écrans Web migrés Groupes 1–3 ; contrôles Dossier/Projet dynamiques ; feuilles de styles des surfaces principales/secondaires/de profondeur.  
**Type de changement :** présentation, sans modification des contrats de domaine ni des transports propriétaires.

## Sources comparées

- Fondation : `static/css/makolo-interactions.css`, `static/js/makolo-interactions.js`, `static/js/makolo-interactions-f2.js`, `mobile/lib/design/action_controls.dart`.
- CSS de composition inspectés : `mature-experience.css`, `me-n1.css`, `dossier-workspace.css`, `project-workspace.css`, `space-us-n1.css`, `space-documents.css`, `notifications-inbox.css`, `objective-organizer.css`, `account-switcher-layout.css`, `personal-connections-layout.css` et `space-ws4.css`.
- Vues et scripts : Dossier/Projet, Notifications, En cours, Maintenant, Nous, Relations, Ressources, Space Work, Scanner et consoles déjà adoptées lors des migrations successives.

## Doublons avérés corrigés

1. **Vues Dossier et Projet :** les onglets `data-dossier-view` / `data-project-view` utilisent désormais `mk-interaction-tabs`. Les règles locales qui redessinaient leurs boutons, l’état `aria-pressed`, le fond, le focus et les couleurs sélectionnées sont retirées. Les grilles, espaces, libellés, `role=group` et gestionnaires de navigation restent propres aux vues.
2. **Dossier, commandes créées en JS :** `static/js/dossier-workspace.js` créait encore les boutons `mk-dossier__small-button` et `mk-dossier__submit` avec des skins distincts. La factory produit désormais `mk-action-button` avec la variante cohérente, notamment `danger` pour les retraits/révocations. Les vérifications `capabilities`, dialogues de confirmation, raisons obligatoires et POST/CSRF ne changent pas. Les styles locaux de boutons devenus sans utilisateur sont retirés, mais les marges des actions dans le graphe restent.
3. **Projet, commandes créées en JS :** `static/js/project-workspace.js` créait des boutons de déplacement/détachement, des confirmations et des contrôles de continuation/calendrier avec des skins locaux. Ils adoptent `mk-action-button` (including `data-size=icon` pour les actions icône seule et `danger` pour détacher). Les labels accessibles, la sélection de cible et les routes owner existantes restent. Le CSS local conserve la grille de cartes, le calendrier, la disposition des dialogues et le menu, sans recréer une bibliothèque d’actions.
4. **Notifications :** retrait d’une règle locale imposant couleur et graisse aux liens/boutons des barres d’action. Les variantes globales restent propriétaires de leur apparence ; les compteurs, la présentation des états de notification et les espacements de la liste restent spécifiques à la surface.

## Frontières et exemptions intentionnelles

- **Composition, pas duplication :** `mk-ws4-action` est une carte de navigation avec texte et détail, pas un bouton générique ; elle garde sa grille et ses interactions. Les cellules de calendrier, panneaux de graphiques, éléments de scan/QR, états métier, portraits et cartes ne sont pas recastés en boutons.
- **En cours :** la barre d’actions est une grille contextuelle dont les tailles et l'ordre dépendent du nombre de commandes rendues. Son menu de partage comprend QR, champs et détails natifs ; ce panneau spécifique n’est pas interchangeable avec un menu générique sans vérification comportementale. Les commandes déjà marquées `mk-action-button` conservent leur variante commune ; ces règles de composition sont maintenues.
- **Documents Space :** les contrôles spécialisés de la bibliothèque demandent une vérification de leur source de rendu et de leurs scripts avant suppression des classes `mk-docs-*` : ne pas effacer des styles actifs sans preuve de remplacement. Cet audit ne déclare pas la totalité du dépôt exempte de CSS hérité.
- **Flutter :** les écrans déjà migrés réutilisent les boutons canoniques ; les contrôles intrinsèques de widgets spécialisés (cartes, dates, champs, chartes d’édition) restent dans leur widget. Aucun moteur générique de permissions, mutation ou undo n’est ajouté.

## Protection contre la réapparition

`scripts/check_group3_interactions.py` vérifie en plus l’adoption des tabs partagés par Dossier/Projet, l’absence de skins de boutons historiques sur ces deux feuilles, la présence des variantes communes sur les commandes JavaScript générées et la non-réintroduction du skin local Notifications.

## Vérification et état

- Les modifications ont été relues par comparaison des sources GitHub sur la branche de la PR #522. Les sélecteurs/attributs d’identification métiers et les commandes de navigation restent inchangés.
- Les contrôles structurels et les correspondances de sélecteurs ont été vérifiés pendant la préparation ; **aucune exécution locale de Django, Playwright, Node ni Flutter et aucun rendu visuel ne sont revendiqués**, faute d’environnement de projet disponible dans cette session.
- **Non effectué :** merge, modification directe de `main`, modification d’API, migration de données, modification de droits.

La finalisation visuelle et les tests d’intégration doivent être réalisés séparément ; elle ne justifie pas la réintroduction de doublons de présentation.
