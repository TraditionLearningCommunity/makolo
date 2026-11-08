# Fondation réutilisable d'interaction — lot F1 (implémenté sur la branche de #522)

**État :** première coupe fonctionnelle opt-in, Web + Flutter. **Ce document n'affirme pas que les pages ont été migrées.**  
**Chantier parent :** A/B/C/D, 00–03 de ce répertoire.

## Périmètre livré

- Web : `static/css/makolo-interactions.css`, chargé une fois dans `templates/base/app.html` ; classes partagées boutons, items, menu, row, sélection, feedback, aperçu.
- Web : `static/js/makolo-interactions.js`, chargé une fois dans la base ; contrôleur de menus délégué, y compris pour un fragment ajouté après chargement. Ouverture clic/Enter/Espace via bouton natif, ArrowUp/Down, Home/End, Escape + retour focus, Tab et fermeture au clic externe. L'exécution d'actions reste celle des vrais liens, boutons et formulaires.
- Flutter : `mobile/lib/design/interaction_primitives.dart` ; registre des 15 intentions, mappings d'icônes, `MakoloInteractionAction`, `MakoloActionMenu`, `MakoloSelectionBar`.
- Tests ajoutés (à exécuter dans le CI/runtime réel) : `e2e/specs/interaction-foundation.spec.mjs` et `mobile/test/interaction_primitives_test.dart`.

**Ce qui n'est pas livré :** mutation générique, tri universel, drag & drop, déplacement Dossier/Projet, inline editor, moteur de sélection groupée, rollback/Undo métier, migration des styles anciens. Ces fonctionnalités attendent des opérations owner réelles et le passage écran par écran.

## Exemple de markup Web (pattern uniquement)

```html
<div class="mk-interaction mk-action-menu" data-mk-action-menu>
  <button type="button" class="mk-action-button" data-variant="ghost"
          data-size="icon" data-mk-action-trigger
          aria-label="Actions sur ce Dossier"
          aria-expanded="false" aria-controls="dossier-actions-42">
    <i data-lucide="ellipsis" aria-hidden="true"></i>
  </button>
  <div class="mk-action-panel" data-mk-action-panel
       id="dossier-actions-42" hidden>
    <a class="mk-action-item" href="/.../">Ouvrir</a>
    <!-- Render only actions allowed by the server projection. -->
  </div>
</div>
```

**Règles :** `id` du panneau unique dans la page, attribut `aria-controls` cohérent ; lien/formulaire natif pour l'action ; permissions à revérifier par l'owner lors de la mutation. Le conteneur n'exige pas `role=menu` : les éléments HTML natifs restent accessibles par Tab. Pas de JavaScript inline, pas de `onclick` HTML. Laisser les attributs `hidden` avant l'initialisation.

Boutons : `mk-action-button` + `data-variant="primary|secondary|ghost|danger"` ; `data-size="icon"` si nécessaire. Les zones de composition restent des classes de l'écran (`mk-project__...`) seulement pour leur mise en page. Ne pas recréer des styles de bouton locaux.

Le menu est facultatif : si l'owner n'autorise aucune action secondaire, ne pas rendre le trigger. La fondation ne cherche jamais des droits par elle-même.

## Exemple Flutter (pattern uniquement)

```dart
MakoloActionMenu(
  actions: [
    const MakoloInteractionAction(
      id: 'open',
      label: 'Ouvrir',
      intent: MakoloActionIntent.open,
    ),
  ],
  onSelected: (action) {
    // Déléguer à la navigation ou au service propriétaire du contexte.
  },
)
```

Un écran mobile ne construit pas son propre PopupMenuButton stylisé ; il consomme ce composant. Le constructeur reçoit une liste déjà bornée par l'owner, non un jeu brut de permissions à interpréter.

## Politique de migration : groupes, pas styles par page

1. **Fondation F1** : vérification des API de style/comportement, tests unitaires et E2E, stabilité globale.
2. **Pages principales personnelles** : Maintenant, Découvrir, En cours, Moi, Makolo Mark — audit de chaque surface, remplacement des répétitions par primitives partagées et suppression du CSS local devenu redondant.
3. **Pages secondaires personnelles** : listes, détails, paramètres, recherches, dossiers, projets, ressources, conversations — même audit avec états et contextual actions.
4. **N1/N2/N3 et Space métier** : adaptations des profondeurs, consoles et usages à forte densité ; aucune duplication pour les composants déjà communs.
5. **Interactions avancées prouvées** : MOVE/LINK/REORDER, multi-sélection et édition, par propriétaire et avec tests de mutation serveur et alternatives accessibles.

Pour chaque groupe : capturer les composants existants, établir correspondance sémantique, migrer les usages compatibles, retirer les anciennes règles uniquement après inspection de leurs références, protéger light/dark/compact/adaptatif/expanded/Flutter, lancer tests ciblés puis CI. Ne pas confondre une couleur différente voulue (état d'alerte) avec duplication décorative.

## Validations requises avant diffusion

Le commit ajoute la surface réutilisable **sans migrer les écrans existants**. Les E2E et tests Flutter ont été écrits ; les validations instrumentées et visuelles sur appareils dépendent des runners du dépôt. Vérifier les statuts GitHub, et ne pas merger avec gates rouges. Ce lot n'apporte pas de nouvelle autorité de mutation.
