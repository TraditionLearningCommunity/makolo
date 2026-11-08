# F2 — Fondation transversale d'interactions (Web + Flutter)

**Statut : primitives communes implémentées sur la branche de la PR #522 ; écran par écran NON migré.**  
**Date : 8 novembre 2026.**  
**Source du contrat :** 00-audit.md, 01-interaction-contract.md, 02-primitives-catalog.md, 03-validation-matrix.md, 04-foundation-implementation.md.

## 1. Règle d'architecture

Le même composant et la même sémantique **ont vocation à servir** dans Maintenant, Découvrir, En cours, Moi, Space métier et les profondeurs N1/N2/N3. Une page peut avoir sa mise en page propre, jamais sa propre définition de bouton, menu, état, poignée ou commande commune.

**Le Web et Flutter restent deux implémentations appropriées :** les contrats d'intention, de feedback, de permissions et d'accessibilité sont partagés ; les gestes et les surfaces adaptent leur rendu. La fondation ne possède **aucune** règle d'Activity, Journey, Project, Dossier, Payment, Access, Capacity, Mandate ou Readiness.

**Ne pas confondre F2 avec la migration des écrans.** F2 fournit les primitives prêtes à consommer. Les CSS/JS locaux existants ne sont pas supprimés tant que chaque groupe de pages n'a pas été migré et testé.

## 2. Fichiers d'implémentation

| Plateforme | Emplacement | But |
| --- | --- | --- |
| Web | static/css/makolo-interactions.css | Styles/tokens applicatifs partagés, y compris F2 |
| Web | static/js/makolo-interactions.js | Menus ⋯, focus, clavier, fermeture externe (F1) |
| Web | static/js/makolo-interactions-f2.js | Sélection, tri/filtre local, preview, édition, reorder/move owner-bound, context restore, clic droit |
| Web | templates/base/app.html | Scripts/styles communs chargés dans la shell, avant extra_css |
| Web | window.MakoloInteractionIcons (makolo-interactions-f2.js) | Registre sémantique ; les glyphes Lucide seront inclus lors de l'adoption réelle par les templates |
| Flutter | mobile/lib/design/interaction_primitives.dart | Intentions, icônes, menu, barre de sélection (F1) |
| Flutter | mobile/lib/design/interaction_f2.dart | Sélection, recherche/tri/filtre, preview, edit, reorder, move, Undo et long press |
| Tests Web | e2e/specs/interaction-foundation.spec.mjs ; interaction-f2.spec.mjs | Menus et scénarios F2 y compris refus de confirmation |
| Tests Flutter | mobile/test/interaction_primitives_test.dart ; interaction_f2_test.dart | États, commandes owner simulées et alternatives de gestes |

Les nouvelles classes/contrôleurs sont **opt-in** ; les pages actuelles restent fonctionnelles sans ces attributs/widgets. Pas de framework JS, routeur, nouvelle outbox ni modèle canonique. Le builder Lucide existant recense les icônes réellement présentes dans les templates HTML : la mise en production d'un nouveau glyphe se fera avec le premier template consommateur et la synchronisation du bundle généré, pas par ajout anticipé qui rendrait les artefacts incohérents.

## 3. Primitives et statut réel

| Primitive C | Web F2 | Flutter F2 | Invariant |
| --- | --- | --- | --- |
| P01 ActionMenu | F1, clic droit F2 seulement si data-mk-context-shortcut | MakoloActionMenu, MakoloContextActionRow (appui long + menu visible) | Pas de geste secret obligatoire |
| P02 ActionFeedback | mk-interaction-feedback + états typés, status live près de reorder/move | Compositions des SuccessFeedback/MakoloNotice existants ; erreurs locales F2 | Jamais confirmer une commande sans owner |
| P03 ContextPreview | Native dialog, Escape/close, focus restauré | MakoloContextPreviewButton sur showMakoloBottomSheet | Preview respecte visibilité source |
| P04 Selection | data-mk-selection-* ; events + selectedIds/clearSelection | MakoloSelectionController + MakoloSelectionBar F1 | Sélection locale, batch non inventé |
| P05 SortFilter | data-mk-query-* ; tri local opt-in, liste déjà acquise | makoloFilterLocal et MakoloSortFilterBar | Ne fait pas recherche Discovery globale ni ranking |
| P06 Reorder | data-mk-reorder-* ; boutons up/down, poignée drag facultative, registerReorder | MakoloOwnerReorderList avec poignée + boutons | callback canonique obligatoire ; aucune mutation optimiste |
| P07 Move | data-mk-move-* ; drag/drop facultatif, registerMove avec formulaire POST réel protégé CSRF | MakoloMoveDestinationButton avec liste owner-filtered | MOVE ≠ LINK ; réponse owner obligatoire |
| P08 InlineEditor | data-mk-inline-edit, form propriétaire, Escape/Annuler | MakoloInlineEditor / MakoloInlineSaveResult | Pas de sauvegarde fantôme |
| P09 UndoAction | Présentation via vrai formulaire/commande inverse du propriétaire, pas de faux bouton générique | MakoloOwnerUndoButton disponible uniquement sur commande inverse réelle | Aucune réversibilité présumée |
| P10 ActionCapabilityAdapter | Menu reçoit HTML autorisé du serveur, callback owner explicitement inscrit | MakoloInteractionAction fourni après résolution owner | Pas de resolver global de permissions dans Presentation |
| P11 InteractionIconRegistry | window.MakoloInteractionIcons traduit les 15 intentions en noms Lucide ; l'inclusion des glyphes dans le bundle attend les premiers templates consommateurs | MakoloInteractionIcons | Signification stable et labels accessibles |
| P12 ContextRestore | captureContext et restoreContext (mémoire caller seulement, clé de contexte opaque) | Sélection contrôlée + ResumableInteractionStore existant ; état tri/filtre caller-controlled | Ne traverse jamais le scope acteur sans vérification |

**Attention :** un composant ou callback disponible n'implique pas que l'endpoint métier ou le tri manuel existe. Les cas de MOVE/REORDER/UNDO ne sont exposés sur un écran que lorsque le propriétaire possède vraiment les commandes correspondantes. F2 ne fabrique **aucun** endpoint de mutation.

## 4. Contrat DOM pour les futures pages Web

### 4.1 Sélection

- Racine : data-mk-selection-scope.
- Contrôles : input type=checkbox data-mk-select-item value=<identité stable>.
- Compteur optionnel : data-mk-selection-count ; barre optionnelle : data-mk-selection-bar hidden.
- Sortie : button type=button data-mk-selection-clear.
- Événement : makolo:selection-change, détail {ids: [...]}; aucun bulk POST déclenché implicitement.

### 4.2 Tri, recherche et filtre local

- Racine : data-mk-query-scope, **data-mk-query-local="true"**.
- Collection : data-mk-query-items contenant les enfants directs data-mk-query-item.
- Commandes : data-mk-query-search, data-mk-query-sort, data-mk-query-filter ; attribut data-mk-sort-<clé approuvée> sur chaque item.
- Liste des clés tri autorisées : data-mk-sort-keys="name,date"; sens descendant facultatif data-mk-sort-descending="true".
- Filtre : data-mk-filter-value sur les items ; recherche textuelle locale via data-mk-search-text ou texte rendu.
- Indicateurs : data-mk-query-count, data-mk-query-empty hidden.
- **Aucun chargement distant ni mélange entre corpus complets/partiels**. Le propriétaire de la collection décide s'il est légitime d'activer ce tri.

### 4.3 Aperçu

Button data-mk-preview-target="<id-du-dialog>" ; dialog id correspondant avec **data-mk-preview** et aria-labelledby ; bouton de fermeture data-mk-preview-close. L'API native HTMLDialogElement gère l'overlay et Escape. Le focus revient au bouton d'ouverture. Pour un aperçu partiel, ne jamais surpromettre l'exhaustivité.

### 4.4 Édition

Racine data-mk-inline-edit ; vue data-mk-edit-view avec button data-mk-edit-open ; **form method=post action=... data-mk-edit-form hidden** avec CSRF Django, champ(s) valides, bouton submit natif, button type=button data-mk-edit-cancel.

La fondation ouvre/ferme l'éditeur et abandonne le brouillon sur annulation, **mais ne bloque pas le submit natif**. Le propriétaire valide et confirme toute mutation. Le champ ne doit être proposé qu'après vérification de l'autorité.

### 4.5 Réorganisation

Racine data-mk-reorder-scope ; conteneur data-mk-reorder-items ; enfants directs data-mk-reorder-item data-mk-reorder-id unique ; boutons natifs data-mk-reorder-up et data-mk-reorder-down avec noms accessibles ; poignée facultative draggable=true data-mk-reorder-handle.

**L'écran doit enregistrer son transport propriétaire** via :

```js
const scope = document.querySelector('[data-mk-reorder-scope]');
window.MakoloInteractions.registerReorder(scope, async (order, movedId) => {
  // Retourner true uniquement après confirmation et réconciliation owner.
  return await ownerConfirmedReorder(order, movedId);
});
```

Sans adaptateur, les boutons/drag ne modifient pas la collection. Confirmation : makolo:reorder-confirmed ; refus : makolo:reorder-failed ; aria-busy durant attente ; option data-mk-reorder-status role=status.

### 4.6 Déplacement

Racine data-mk-move-scope, source data-mk-move-source data-mk-move-id, poignée draggable=true data-mk-move-handle, cible data-mk-move-destination data-mk-destination-id, option data-mk-move-status role=status.

**Alternative obligatoire :** vrai form method=post action=... data-mk-move-form, input csrfmiddlewaretoken, select[name] ou input[name=destination_id] et submit explicite. Ne pas mettre un formulaire vide « pour satisfaire » la condition de rendu. La destination doit rester visible/autorisé ; le serveur revalide son droit au commit.

Enregistrer un adaptateur réel avec registerMove(scope, async ({sourceId,destinationId}) => boolean). L'API refuse l'enregistrement si le formulaire alternatif est absent. Aucune modification DOM avant confirmation ; events makolo:move-confirmed / makolo:move-failed.

### 4.7 Context restore

`captureContext(scope)` renvoie un snapshot éphémère de query, sort, filter, selectedIds, scrollTop et focusId. `restoreContext(scope, snapshot)` exige la même valeur opaque **data-mk-context-key** ; l'application doit inclure les frontières acteur/conteneur dans cette clé. **Aucun stockage global ou localStorage par cette primitive.**

Appeler avant/après un swap compatible avec le contrat HTMX, seulement lorsque la même personne et le même scope restent autorisés. Un changement d'acteur invalide le snapshot.

### 4.8 Menus contextual actions

Le menu visible ⋯ reste la voie principale. Ajouter data-mk-context-shortcut au conteneur compatible autorise le clic droit comme raccourci, sans intercepter le clic droit sur les inputs, liens ou texte éditable. L'appui long côté Web tactile dépend du navigateur ; il ne remplace donc jamais le bouton visible.

## 5. Contrat Flutter

Les écrans importent :

```dart
import 'package:makolo_mobile/design/interaction_primitives.dart';
import 'package:makolo_mobile/design/interaction_f2.dart';
```

- `MakoloSelectionController` : état d'identités UI, `retainVisible` pour nettoyer les éléments devenus invisibles, `clear` sur changement acteur.
- `MakoloSortFilterBar` : valeurs search/sort/filter externes ; seulement les critères autorisés fournis par caller. `makoloFilterLocal` n'est pas moteur de Discovery.
- `MakoloContextPreviewButton` : compose la feuille existante, aucun fetch caché.
- `MakoloInlineEditor` : Future<MakoloInlineSaveResult>, confirmed **avec valeur canonique**, rejected/conflict conservent le brouillon.
- `MakoloOwnerReorderList` : Future<bool> onRequestReorder(order), poignée native et commandes Monter/Descendre ; parent actualise la collection canonique après réponse.
- `MakoloMoveDestinationButton` : destinations visibles filtrées upstream ; Future<bool> onRequestMove(id), la sheet se ferme seulement sur true.
- `MakoloOwnerUndoButton` : visible seulement si owner offre une vraie commande inverse, disparition après confirmation.
- `MakoloContextActionRow` : appui long vers sheet + MakoloActionMenu permanent avec mêmes actions disponibles.
- Les états persistés/resumables et les fonds adaptatifs restent ceux du socle natif existant, pas un nouveau routeur ou second moteur sync.

## 6. Tests et limites de validation

Web E2E : clavier/focus F1 ; F2 sélection+effacement, local corpus/tri stable, preview, editor cancel, reorder refus/confirmation, move sans fallback/refus/confirmation, snapshot isolé entre acteurs et clic droit opt-in. Flutter : sélection, filtre local, preview, save pending/confirmed/conflict, reorder refus, move refus/confirmation, Undo réel et appui long.

**Validation statique déjà réalisée :** parsing JS des contrôleurs F1/F2 et des tests Web ; HEAD GitHub et absence de changement main. **Validation non affirmée :** `flutter analyze`, `dart format`, flutter test ciblés, E2E Playwright et captures visuelles sur appareils ; les jobs CI du grand chantier #522 peuvent être rouges pour des causes hors F2.

Le dépôt prescrit **`mobile/tool/dart_format.sh` avec Dart 3.13.3/Flutter 3.47.3 ou workflow GitHub "Mobile Format" sur la branche de travail** ; ne pas contourner le formatter en reformattant à la main ou en affaiblissant les tests. Les seuls outils GitHub de cette session ne disposent pas d'action workflow_dispatch, donc ne pas déclarer ce gate validé avant exécution effective.

## 7. Garde-fous pour le futur groupe de pages

1. Pour chaque écran, repérer sa CSS locale de boutons/cartes/menus/statuts.
2. Remplacer la **sémantique des composants** par la fondation ; conserver seulement le layout spécifique.
3. Vérifier capabilities et transport owner avant d'afficher MOVE, REORDER, EDIT, UNDO ou BULK.
4. Tester le parcours clavier, tactile simple, lecteur d'écran, light/dark, reduced motion, offline/conflit et identité de l'acteur.
5. Éliminer les règles locales devenues inutiles **après** contrôle des références.
6. Ne pas déclarer la migration d'une page faite tant qu'elle n'a pas réellement changé et passé sa validation.

**F2 s'arrête aux primitives.** Le groupe suivant commence seulement lorsque les gates ciblés de F2 sont satisfaits.
