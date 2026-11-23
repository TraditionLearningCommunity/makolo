# C — Catalogue des primitives transversales et plan d'adoption

**Statut : spécification de composants, aucun composant créé.**  
**Source et limites :** 00-audit.md et 01-interaction-contract.md. Les noms ci-dessous préfixés « proposé » ne sont pas des classes ou widgets existants.

## 1. Politique de réutilisation

**Ne pas lancer un nouveau design system.** La source Web reste le système .mk-* et ses tokens CSS, avec HTML sémantique et des contrôleurs JavaScript compatibles HTMX. La source Flutter reste mobile/lib/design et MakoloLayout, sans second router/state engine. Product Language demeure responsable des noms visibles ; services owners responsables des mutations.

Une primitive ne doit être partagée que si sa **sémantique, ses états et son contrat d'accessibilité** sont identiques sur plusieurs contextes. La composition visuelle d'une surface métier reste locale.

Les classes Web et widgets Flutter proposés décrivent **deux implémentations homologues du même contrat**, pas un partage de code exécutable. Leur API définit les entrées d'interaction et les callbacks ; jamais l'autorisation métier elle-même.

## 2. Inventaire de réemploi préalable

| Besoin | Web existant à examiner / réutiliser | Flutter existant à réutiliser | Décision |
| --- | --- | --- | --- |
| Couleur, forme, motion | static/css/makolo-ui.css, makolo-brand.css, mature-experience.css, makolo-a11y.css | makolo_theme.dart | Unifier les rôles, vérifier la cascade |
| Cartes, sections, métadonnées | .mk-panel, .mk-btn, .mk-badge, .mk-workspace | MakoloCard, MakoloSection, MakoloMetadata, MakoloStatus | Ne pas recréer de carte universelle |
| État et notification | messages/template, .mk-toast, outils de formulaires existants | SuccessFeedback, MakoloNotice, PendingIndicator, showMakoloToast | Réutiliser les états sans inventer de succès |
| Confirmation et Undo | Formulaires POST et messages existants ; mécanisme inverse owner à vérifier | showMakoloConfirmationDialog, showMakoloUndoToast | Undo widget ≠ Undo métier |
| Preview et profondeur | workspace Inspect/Explore, workspace-runtime.js | MakoloDetailHeader, showMakoloBottomSheet, layouts adaptatifs | Choisir selon viewport |
| Palette Web | static/js/desktop-power.js | Aucun clone demandé | Garder Ctrl/Cmd+K comme accélérateur |
| Continuité | URL/HTMX/history + runtime scope | ResumableInteractionStore, système sync existant | Pas de deuxième moteur |

## 3. Catalogue normatif de primitives candidates

| ID | Primitive / nom de travail | Contrat et états | Condition d'utilisation | Priorité |
| --- | --- | --- | --- | --- |
| P01 | **ActionMenu** | Ouvre/ferme actions contextuelles ; focus, ancrage, Escape, permission, disabled avec raison utile | Actions secondaires réellement offertes | Première vague |
| P02 | **ActionFeedback** | Préparé, en cours, attente, confirmé, refus, conflit, hors ligne ; message concis | Toutes commandes significatives | Première vague, surtout composition de l'existant |
| P03 | **ContextPreview** | Ouvre détail secondaire, restaure focus, conserve scroll ; sensitive content scoping | Une preview apporte un gain réel | Première vague |
| P04 | **SelectionController / SelectionBar** | Identités stables, entrer/sortir sélection, compteur, actions compatibles, changement de contexte | Opération groupée réelle ou inspection utile | Deuxième vague |
| P05 | **SortFilterControls** | Tri par critère, portée de recherche, état restaurable, commande de réinitialisation | Collections qui exposent ces critères | Première vague |
| P06 | **ReorderHandle** | Saisie via poignée, cible valide, retour accessible Monter/Descendre, confirmation owner | Ordre manuel propriétaire ; interdit sur ranking serveur | Deuxième vague conditionnelle |
| P07 | **MoveIntent / DropTarget** | Source/cible, survol admissible, refus explicite, alternative « Déplacer vers… », réconciliation | Commande owner, cible visible, transport Web/mobile pris en charge | Première vague pilote uniquement, puis généralisation |
| P08 | **InlineEditor** | Focus, validation, annuler brouillon, erreur locale, conflit concurrent | Champ éditable avec mutation existante et politique de concurrence | Deuxième vague |
| P09 | **UndoAction** | Inverse disponible / indisponible, délai si owner défini, action revalidée | Owner expose une vraie compensation | Conditionnelle |
| P10 | **ActionCapabilityAdapter** | Traduit capacités/états métier vers actions présentables, sans accorder de droits | Toute interaction sensible | Socle conceptuel, aucun endpoint générique |
| P11 | **InteractionIconRegistry** | Clé sémantique, glyph cohérent, libellé accessible, état | Toute action iconifiée | Première vague |
| P12 | **ContextRestore** | Retour, scroll, tri, filtres, sélection, overlay, draft autorisé, actor scope | Profondeurs et collections | Composition de l'existant |

**Interdit :** UniversalMakoloCard, GenericActionEndpoint, GenericDossierStatus, nouveau router, nouvelle outbox ou store global d'interactions. Une primitive de présentation ne possède aucun état Readiness, Access, Payment, Capacity, Mandate ou permission.

## 4. Nomenclature Web proposée (sans création de CSS)

Les noms suivants **sont des propositions à réserver**, afin que les futurs écrans ne créent pas leurs propres variantes :

| Classe / attribut proposé | Rôle | Règle d'usage |
| --- | --- | --- |
| .mk-action-trigger | Accès ⋯ aux actions | bouton HTML, nom accessible, aria-expanded, aria-controls |
| .mk-action-menu | Menu local d'actions | role/menu uniquement si pattern ARIA complet ; sinon liste de boutons |
| .mk-interaction-row | Ligne avec zone principale et actions séparées | ne pas rendre un article entier ambigu pour clavier |
| .mk-selectable | Surface en mode sélection | état sélectionné dans attribut/contrôle réel, pas couleur seule |
| .mk-selection-bar | Actions portant sur la sélection | expliciter nombre + sortie de sélection |
| .mk-reorder-handle | Poignée d'ordre manuel | cachée si ordre owner non modifiable |
| .mk-drop-target | Cible de déplacement | aria-label/action alternative, états visuels accept/reject |
| .mk-context-preview | Aperçu sans changement de page | focus/retour et responsive explicites |
| .mk-inline-editor | Éditeur de champ | brouillon, validation, erreurs à proximité |
| [data-mk-interaction] | Point de liaison déclaratif | contenu strictement borné, pas d'autorité en data-attribute |

Noms sous réserve de collision avec les classes existantes au moment de coder. **Aucun CSS n'est ajouté aujourd'hui.**

Les scripts futurs doivent rester compatibles CSP, chargement fragment HTMX, focus après swap, event delegation, URL directes et runtime de projections. Pas de dépendance JS product-wide, de poll massif ou de préchargement de toutes les données.

## 5. Nomenclature Flutter proposée (sans création de Dart)

- MakoloActionMenu : consomme une liste d'actions présentables dérivée du serveur et du contexte.
- MakoloSelectableCollection : gère sélection UI et sortie de mode, sans mutation.
- MakoloReorderHandle : affordance d'ordre manuel et alternative non gestuelle.
- MakoloMoveDestinationSheet : choix autorisé de destination sans convertir le geste en autorité.
- MakoloContextPreview : compose DetailHeader, BottomSheet ou route existante.
- MakoloInlineEditField : composition de TextField/validation/annuler.
- MakoloInteractionFeedback : compose MakoloNotice, SuccessFeedback et états existants.

**Avant tout nouveau widget, vérifier si l'actuel MakoloCard / MakoloNotice / MakoloSurfacePresentation / MakoloLayout couvre déjà le besoin.** Les noms ne sont pas une commande de création automatique.

## 6. Contrat d'entrée des primitives

Toute primitive d'action attend **des données de présentation** décidées en amont :

- identité stable de l'objet, contexte acteur ;
- clé sémantique OPEN/MOVE/LINK/etc ;
- libellé résolu par Product Language ;
- état de disponibilité et éventuelle raison compréhensible ;
- destination/effet explicitement représentable ;
- callback vers commande existante du client concerné ;
- état de progression et résultat autoritatif ;
- éventuel mécanisme de réconciliation et de retour de focus.

Ne jamais passer un objet Django complet, des credentials, une liste globale non filtrée, ni des permissions brutes en tant que sources d'autorité. Le menu n'infère pas les actions de la simple présence de données privées.

## 7. Politique de lifecycle des interactions

### Navigation et inspection (sans mutation)

L'ouverture de preview conserve la collection ; Escape/back ferme le panneau ; le retour restaure focus et scroll. Le cache de preview reste scope-acteur et périssable. Une entrée invalide ou devenue privée doit disparaître sans divulgation.

### Édition et manipulation (avec mutation)

Préparer → contrôler l'affordance locale → présenter l'effet → valider via owner → afficher en cours → recevoir confirmation/refus/conflit → invalider/rafraîchir la projection → restaurer contexte. Le geste et la commande bouton doivent emprunter **la même opération propriétaire**.

### Glisser-déposer

Le drag visuel ne déclenche aucun changement métier jusqu'au drop sur une cible compatible. Sur drop invalide : retour sans mutation ni fausse confirmation. Sur validation refusée : restitution lisible et réconciliation. Sur succès : nouvelle association/position seulement après confirmation du service. Prévoir clavier, toucher sans drag et lecteur d'écran.

### Actions groupées

Par défaut, **aucune mutation de masse** tant que l'owner n'a pas défini atomicité, droits par objet, traitement partiel, idempotence, concurrence et résultat exploitable. Sélection multiple pour inspection/organisation locale peut être dissociée d'un batch métier.

## 8. Première application contrôlée — Objectifs

**Cas pilote : Projet ↔ Dossier**, vérifié dans objectives/services.py (link_dossier_to_project, move_dossier_to_project, unlink_dossier_from_project), views.py, urls.py et tests Objectives.

- Aujourd'hui : Web avec formulaires, propriétaire serveur et tests de permissions existants.
- Futures entrées équivalentes : formulaire « Déplacer vers… » et drop d'un Dossier sur Projet visible, tous deux reliés au même service.
- Conditions avant livraison : vérifier la couverture de la destination, la possibilité de changement d'owner/scope, la présentation d'échec, le niveau de confirmation, les conflits et le transport mobile de mutation.
- **Ne pas présumer** qu'un endpoint write existe : objectives/api_urls.py n'expose dans l'audit que des endpoints de détail en lecture.
- Ne jamais convertir « déplacer une Démarche dans un Dossier » en transfert de propriété Journey ; les services de lien décrivent une relation, pas un move.

Le Projet reste horizon durable ; Dossier objectif composé ; ni l'un ni l'autre ne devient gestionnaire de tâches générique.

## 9. Adoption ordonnée et dépendances

| Phase future | Action | Dépendance indispensable | Livraison du présent dossier |
| --- | --- | --- | --- |
| 0 | Audit cascade, composants, états, opérabilité des owners | Sources runtime et revue | Inventoriée, non exécutée |
| 1 | Registre d'intentions/icônes, menus/feedback/preview et alternatives | Design review + tests clavier | Spécifiée |
| 2 | Déplacement Dossier→Projet sur Web et mobile si transport autorisé | Services et endpoint/transport propriétaire prouvé, autorité et tests | Scénarios définis |
| 3 | Sélection/groupes, tri enregistré, édition en place, ordre manuel | Besoin owner et stockage/contrat de rang | Gate défini |
| 4 | Chronologie, graphe, calendrier, tableaux d'états interactifs | Vérités dates/dépendances/statuts et commandes autorisées | Reporté délibérément |

Chaque phase ultérieure implique **sa propre branche/PR** et des tests ciblés. Ce catalogue ne commande pas leur implémentation maintenant.

## 10. Évolutivité sans duplication

Si une autre surface (En cours, Space Métier, Jour J) réclame un nouveau geste, elle décrit l'intention et le propriétaire. Si l'intention existe, elle adopte la primitive commune. Si elle n'existe pas, ajouter la sémantique au registre après revue du cas ; ne pas enrichir une primitive universelle avec des paramètres spécifiques à chaque verticale.
