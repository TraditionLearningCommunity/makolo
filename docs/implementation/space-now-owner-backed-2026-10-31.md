# Makolo — Space Maintenant : fermeture verticale owner-backed (#522)

**Date :** 31 octobre 2026  
**Branche unique :** `fix/discover-a-continuation-context-20261014`  
**Base main vérifiée :** `d0f0ec421c94c255fa4c0acd3509938a70c6322f`  
**Statut :** implémentation incrémentale poussée ; validation Django/Flutter/Android locale non exécutée ici ; **couverture métier encore partielle**.

## Problème résolu

Auparavant, `build_space_now_projection` renvoyait toujours `no_safe_selection_contract`. Le Web n'affichait aucune situation et Flutter ne savait afficher qu'un compteur. Maintenant, une sélection serveur strictement scoped admet des faits propriétaires déjà établis, et les clients les composent avec la grammaire commune de Now de Moi.

## Contrat serveur et autorité

- Nouvelle sélection de lecture `organizations/api/space_now_selection.py`, raccordée à la projection/API existante.
- L'entrée Space continue d'exiger une session humaine, un Space accessible et une perspective de responsabilité validée serveur.
- Les Activities admissibles sont l'intersection des Activities effectivement visibles, de la perspective choisie et des permissions owners pour le fait considéré.
- Les Occurrences **actuellement en cours** sont retenues uniquement sous `ACTIVITY_OPERATIONS_VIEW`, en s'appuyant sur `Occurrence.is_ongoing`.
- Les inscriptions `SUBMITTED/PENDING_APPROVAL` sont retenues sous `ACTIVITY_REQUESTS_VIEW` ; `ACTIVITY_REQUESTS_DECIDE` distingue un passage vers décision du simple examen.
- Les cas de prestation soumis/en attente sont retenus uniquement via `service_journeys_visible_to` et les permissions Activity de lecture appropriées ; lorsque la permission est limitée aux cas assignés, seuls les Assignments actifs du viewer sont admis. Un Journey personnel du viewer ne devient pas automatiquement une situation collective.
- Les conséquences non fournies par l'owner restent explicitement `unknown`. Les actions proposées sont des **handoffs owner** vers Jour J ou Métier, jamais un POST fictif.
- Aucune photo ni pièce privée n'est ajoutée par inférence. `media_bindings=[]` est légitime tant qu'aucun usage média owner autorisé n'est établi.
- La sélection globale reste `partial / owner_coverage_incomplete`, même avec zéro item. **Aucun faux « Tout est en ordre »**.
- `freshness.state=unknown` distingue l'instant d'observation de la fraîcheur effective des faits owners.
- Aucune table, aucun nouveau modèle métier, aucune migration, aucun nouveau service de mutation.

## Web et Flutter

- Web : lecture N1, développement N2 avec `details`, conséquences connues/inconnues distinctes, handoffs Web, états partiel/vide/erreur cohérents ; présentation spécifique au contexte Space.
- Flutter : réutilisation directe de `NowSelector` et `NowView` personnels (N1/N2 et navigation propriétaire), sans nouveau système de cartes.
- Les snapshots Space continuent de passer par `WorkspaceContextRepository`, sources scoped par Space et perspective, invalidation/révocation existantes et freshness locale existante.
- L'état partiel vide a un message dédié, distinct d'une erreur de transport, avec actualisation explicite.
- Une sélection partielle non vide conserve un indicateur discret sur sa couverture.

## Vérifications intégrées au code

- `organizations/test_zs6_space_projection_reconciliation.py` : initialisation partielle honnête, autorité Activity-limited, Occurrence en cours, non-divulgation d'une autre Activity, annulation exclue, demande owner sans mutation directe, refus Membership, changements de Mandate.
- `organizations/test_ws2_space_now_discover_web.py` : état partiel honnête et rendu Web d'une situation owner.
- `e2e/specs/ws2-space-now-discover.spec.mjs` : régime responsive et navigation vérifient désormais Now partiel sans faux calme ; Découvrir demeure indisponible.
- `mobile/test/space_foundation_stabilization_test.dart` : fixture N1 valide et non-réutilisation d'une situation d'un autre Space au changement d'acteur.

**Ces tests ont été modifiés, pas exécutés.** Le conteneur ne possède ni clone du dépôt ni toolchain Dart/Flutter ; l'accès au dépôt s'est fait directement par le connecteur GitHub.

## Commandes locales à exécuter sur Windows

Depuis la branche de #522, après avoir sauvegardé tout travail non commité :

```powershell
git fetch origin
git switch fix/discover-a-continuation-context-20261014
git pull --ff-only origin fix/discover-a-continuation-context-20261014
python manage.py test organizations.test_zs6_space_projection_reconciliation organizations.test_ws2_space_now_discover_web
python manage.py check
cd mobile
bash tool/dart_format.sh write
bash tool/dart_format.sh check
flutter analyze
flutter test test/space_foundation_stabilization_test.dart
flutter run
```

Contrôler physiquement : passage Moi ↔ Space, acteur et perspective, Occurrence en cours, demande en attente, refus d'une source non autorisée, navigation vers Jour J/Métier et retour, perte réseau, cold start, révocation, absence de fuite entre Espaces, et absence de promotion d'un dossier personnel de prestation vers une attention collective.

## Limites et critères de fermeture restant ouverts

Cette verticale ne couvre actuellement **que** les Occurrences en cours et les \`JourneyRequest\` en attente et les dossiers de prestation soumis/en attente. Les domaines qui ne disposent pas encore d'un signal owner sûre (autres opérations, Access, Capacity, Commerce, Payment, ressources, dépendances externes...) ne sont pas intégrés automatiquement. Les médias privés et mutations directes ne sont pas exposés sans contrat propriétaire. La conclusion `calm` reste interdite tant que la couverture transversale ne peut l'établir.

L'expérience peut être testée dès ce checkpoint, mais la **fermeture Mature complète** nécessite encore la couverture owner pertinente, les validations visuelles Android/Web, les tests locaux ciblés, le formatage Flutter canonique et les gates pertinentes avant tout merge.

## Règle d'intégration

Uniquement PR #522 ; ne pas merger automatiquement. Aucun CI affirmé vert. Des commits concurrents de #522 ont été observés sur `mobile/test/me_secondary_offline_test.dart` et `organizations/space_product.py` sans toucher aux fichiers directs de cette verticale ; recontrôler le HEAD avant intégration finale.
