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
- Les Occurrences en cours ne sont admises que sous `ACTIVITY_OPERATIONS_VIEW` **et** si `Operations.resolve_occurrence_live` établit une `next_action` non nulle/non `none`. Le déroulement seul ne crée plus de situation Now.
- Les demandes `JourneyRequest.PENDING` non expirées et liées à une Journey encore approuvable sont retenues sous `ACTIVITY_REQUESTS_VIEW` ; `ACTIVITY_REQUESTS_DECIDE` conditionne la décision, sinon l'attente est légitime et le viewer peut lire sans décider.
- Les dossiers Services ne sont admis que lorsqu'un selector propriétaire `facilitator_attention_journeys` ou `manager_attention_journeys` atteste l'attention ; l'intersection avec la portée `VIEW_ALL` ou Assignment actif et l'exclusion du viewer bénéficiaire évitent de transformer son dossier personnel en fait collectif.
- Les conséquences non fournies par l'owner restent explicitement `unknown`. Les actions proposées sont des **handoffs owner** vers Jour J ou Métier, jamais un POST fictif.
- Aucune photo ni pièce privée n'est ajoutée par inférence. `media_bindings=[]` est légitime tant qu'aucun usage média owner autorisé n'est établi.
- La sélection globale reste `partial / owner_coverage_incomplete`, même avec zéro item. **Aucun faux « Tout est en ordre »**.
- `freshness.state=unknown` distingue l'instant d'observation de la fraîcheur effective des faits owners.
- Aucune table, aucun nouveau modèle métier et aucune migration. Une profondeur API ciblée `SpaceJourneyRequestAPIView` revalide scope/Permission avant d'appeler exclusivement les services transactionnels `approve_request` / `reject_request` déjà propriétaires de la mutation. Conflit/révocation = refus, jamais succès optimiste.

## Web et Flutter

- Web : lecture N1, développement N2 avec `details`, conséquences connues/inconnues distinctes, handoffs Web, états partiel/vide/erreur cohérents ; la console Requests n'affiche ses boutons de mutation que si la permission effective et l'échéance propriétaire l'autorisent.
- Flutter : réutilisation directe de `NowSelector` et `NowView` personnels (N1/N2 et navigation propriétaire), sans nouveau système de cartes ; route `/space/requests/:id` vers une profondeur de demande native sécurisée, décision explicite confirmée par l'owner, reprise/actualisation au retour. Dossiers Services via la profondeur propriétaire Space Work.
- Les snapshots Space continuent de passer par `WorkspaceContextRepository`, sources scoped par Space et perspective, invalidation/révocation existantes et freshness locale existante.
- L'état partiel vide a un message dédié, distinct d'une erreur de transport, avec actualisation explicite.
- Une sélection partielle non vide conserve un indicateur discret sur sa couverture.

### Propriétaire de décision JourneyRequest (Web + mobile)

- `organizations/api/space_request_views.py` et `organizations/api/urls.py` : `GET/POST /api/v1/organizations/workspaces/<slug>/requests/<request_id>/`. Réponse restreinte au Space courant, au viewer et à sa perspective actuelle ; seul un `JourneyRequest` effectivement visible est retourné, sans identifiants privés du demandeur. `POST` appelle uniquement `journeys.services.approve_request/reject_request`, toujours avec revalidation propriétaire et transaction.
- `mobile/lib/features/space/space_request_screen.dart` : profondeur native en ligne, informations communiquées par le propriétaire, confirmation explicite, vérification du résultat réel, message de refus ou conflit, effacement sur changement de contexte.
- `mobile/lib/navigation/deep_link_resolver.dart` et `mobile/lib/app/router.dart` : chemins propriétaires Space enregistrés. La profondeur Services ne permet pas de lien externe arbitraire.
- `organizations/console_views.py` et `templates/organizations/console/requests.html` : boutons de décision Web masqués dès qu'ils ne sont plus autorisés, expirés ou hors contexte ; la validation backend ne change pas.
- Les retours de profondeur native relancent la projection Now, sans succès optimiste ni transfert d'autorité.

## Extension des owners confirmés — 31 octobre 2026

L'extension `organizations/api/space_now_domain_signals.py` complète la sélection existante **sans nouvel état persistant ni écriture métier**. Elle ne sélectionne aucun objet simplement parce qu'il existe.

| Domaine propriétaire | Admission fondée sur un fait | Non-admission | Autorité / profondeur |
| --- | --- | --- | --- |
| Operations | Incident HIGH/CRITICAL encore OPEN/INVESTIGATING, rattaché à l'Activity autorisée | incident clos, mineur, sans Activity admissible | `ACTIVITY_OPERATIONS_VIEW`; Jour J ou Activity natifs et Operations Web |
| Access | Refus `EXPIRED` ou `REVOKED` constaté par `AccessUse` sur la même Occurrence active dans les six dernières heures, et sans passage ultérieur accepté | AccessCredential, mauvaise Occurrence/scanner sans portée établie, passage accepté ensuite, ancien refus, hors portée | `ACTIVITY_ACCESS_VIEW` **et** `ACTIVITY_OPERATIONS_VIEW`; Jour J / console Access |
| Capacity | `held + committed > total` établi par `capacity_availability_many`, pool actif et quantité bornée | sold-out normal, nombre inféré, Placement | `ACTIVITY_CAPACITY_VIEW`; Activity/Jour J et console propriétaire |
| Commerce | Commande payante (`total > 0`) du Space réellement PENDING avec `expires_at` dans les 24 heures | commande gratuite, commande ordinaire sans horizon, statut terminal, simple vente sans fenêtre | `ORDERS_VIEW` Space + perspective Activity; profondeur native Commerce Order autorisée |
| Payments | Dernière tentative `FAILED` dans les trois jours, Commerce Order encore PENDING, sans tentative ultérieure ni réussite | historique de paiement, Payment du buyer personnel, faux échec encore pertinent | `ORDERS_VIEW` **et** `FINANCE_VIEW` Space; détail native Commerce + finance Web |
| Automation | `AutomationExecution.FAILED` récent sur la règle d'une Activity gérable | règle sans exécution échouée, échec passé, règle d'autre Activity | `ACTIVITY_MANAGE`, Activity native / console Automation |
| PaymentObligation (débiteur Space) | Obligation explicitement à la charge de cet Espace (`payer_space`) avec une Journey de l'Espace, échéance dépassée et statut PENDING/PROCESSING | obligation future, déjà satisfaite, commande Commerce, simple dette d'un Profile ou autre Espace | `FINANCE_VIEW` direct Space + perspective Activity ; lecture Web et Flutter propriétaire, **aucun règlement implicite** |

- Les scans sources sont techniquement bornés et `has_more` reste honnête si une source dépasse son budget. Les Situations réellement admises **ne sont plus coupées à un Top 24 artificiel**.

- La lecture d'une obligation financière dont **le Space est débiteur** utilise `payments.space_obligation_views.space_payer_obligation`, le garde FINANCE_VIEW et la perspective validée ; les routes sont `/api/v1/organizations/workspaces/<slug>/payment-obligations/<uuid>/` et `/spaces/<slug>/payment-obligations/<uuid>/` (route canonique `organizations:space-payment-obligation`). Son owner est toujours Payments. Le client Flutter ouvre une profondeur native `space_payment_obligation` via une route propriétaire relative et revalide le scope. Aucun nouveau paiement, mandat, preuve, Access ou statut n'est créé par Now.

- Les labels descriptifs ne contiennent ni identité du bénéficiaire, ni credential, ni secret, ni PII financière. La provenance demeure un identifiant propriétaire, les conséquences non établies restent `unknown`.
- Le Web conserve les profondeurs owner, Flutter résout uniquement des chemins relatifs de formes autorisées pour `space_work_activity`, `space_work_journey` et `space_commerce_order` ; les écrans réévaluent l'autorité à l'ouverture.
- La proximité d'un paiement ou d'une commande sans action connue n'est jamais convertie en mutation ou en autorité. Les anomalies et les échéances ont des réponses d'Action, de compréhension ou d'attente distinctes.
- Ni une source absente, ni un tableau vide ne suffisent à établir le calme global. Les autres propriétaires et les signaux Space sans contrat restent **hors couverture**.

**Tests ajoutés :** `organizations/test_space_now_domain_signals.py` vérifie portée Activity, incidents fermés/mineurs, refus Access et passage accepté ultérieur, sold-out sans alerte, surallocation réelle, horizon d'une commande payante et exclusion de la commande gratuite, paiement supersédé, obligation institutionnelle échue et payeur inter-Space refusé, échec Automation et sortie après résolution. `mobile/test/space_now_composition_test.dart` vérifie en plus les profondeurs natives autorisées et le rejet des URLs externes.

### Retour de validation locale — permissions et révocation (31 octobre 2026)

Le premier lancement de `organizations.test_zs6_space_projection_reconciliation`, `organizations.test_ws2_space_now_discover_web` et `organizations.test_space_now_domain_signals` a découvert 31 tests, avec 4 échecs et 1 erreur. Les 5 défauts provenaient des scénarios de test, pas d'une raison démontrée d'élargir les droits en production :

- `ACTIVITY_LOCAL_MANAGER` ne possède pas `ACTIVITY_OPERATIONS_VIEW`. Les scénarios d'Occurrence, d'Incident et d'AccessUse exigent désormais une délégation explicite `ACTIVITY_OPERATIONS_MANAGER` sur la même Activity. Aucun transfert implicite de permission depuis Membership ou Activity Manage.
- `revoke_mandate` interdit la suppression du dernier `SPACE_OWNER`. Le test crée un second propriétaire légitime, retire ensuite le Mandate initial et exige toujours un refus `404` pour toute décision prise par l'ancien propriétaire, sans mutation de la demande.
- Les assertions d'admission, de confidentialité et de sécurité sont conservées. Aucun test n'a été supprimé, relâché ou contourné.

**À relancer localement :** `python manage.py test organizations.test_zs6_space_projection_reconciliation organizations.test_ws2_space_now_discover_web organizations.test_space_now_domain_signals`. Les tests ne sont **pas attestés verts** tant qu'une nouvelle exécution locale ne l'a pas confirmé.

## Vérifications intégrées au code

- `organizations/test_zs6_space_projection_reconciliation.py` : sélection partielle, perspective Activity limitée, Occurrence sans action non admise, signal Operations confirmé, demande owner et permission de décision, IDOR inter-Space, demande expirée, double commande refusée, révocation de Mandate, Services assigné uniquement.
- `organizations/test_ws2_space_now_discover_web.py` : état partiel honnête, rendu Web d'un signal Operations et masquage des contrôles de décision sans autorité.
- `e2e/specs/ws2-space-now-discover.spec.mjs` : régime responsive et navigation vérifient désormais Now partiel sans faux calme ; Découvrir demeure indisponible.
- `mobile/test/space_foundation_stabilization_test.dart` : fixture N1 valide et non-réutilisation d'une situation d'un autre Space au changement d'acteur.\n- `mobile/test/space_now_composition_test.dart` : `partial + []` ne devient pas un calme établi, la décision est une profondeur propriétaire, les liens Services doivent rester relatifs et sûrs.

**Ces tests ont été modifiés, pas exécutés.** Le conteneur ne possède ni clone du dépôt ni toolchain Dart/Flutter ; l'accès au dépôt s'est fait directement par le connecteur GitHub.

## Commandes locales à exécuter sur Windows

Depuis la branche de #522, après avoir sauvegardé tout travail non commité :

```powershell
git fetch origin
git switch fix/discover-a-continuation-context-20261014
git pull --ff-only origin fix/discover-a-continuation-context-20261014
python manage.py test organizations.test_zs6_space_projection_reconciliation organizations.test_ws2_space_now_discover_web organizations.test_space_now_domain_signals
python manage.py check
cd mobile
bash tool/dart_format.sh write
bash tool/dart_format.sh check
flutter analyze
flutter test test/space_foundation_stabilization_test.dart test/space_now_composition_test.dart
flutter run
```

Contrôler physiquement : passage Moi ↔ Space, acteur et perspective, Occurrence en cours, demande en attente, refus d'une source non autorisée, navigation vers Jour J/Métier et retour, perte réseau, cold start, révocation, absence de fuite entre Espaces, et absence de promotion d'un dossier personnel de prestation vers une attention collective.

## Limites et critères de fermeture restant ouverts

Cette verticale couvre les interventions Operations effectivement signalées, les `JourneyRequest` réellement en attente et les dossiers Services signalés aux opérateurs ; elle prend aussi en charge les faits explicites d'Access, Capacity, Commerce, Payments et Automation décrits ci-dessus. Elle **ne prétend toujours pas couvrir toutes les nuances et propriétaires** de ces domaines. Les domaines qui ne disposent pas encore d'un signal owner sûre (autres opérations, Access, Capacity, Commerce, Payment, ressources, dépendances externes...) ne sont pas intégrés automatiquement. Les médias privés et mutations génériques ne sont pas exposés sans contrat propriétaire. La décision native de demande utilise uniquement le service JourneyRequest transactionnel existant. La conclusion `calm` reste interdite tant que la couverture transversale ne peut l'établir.

L'expérience peut être testée dès ce checkpoint, mais la **fermeture Mature complète** nécessite encore la couverture owner pertinente, les validations visuelles Android/Web, les tests locaux ciblés, le formatage Flutter canonique et les gates pertinentes avant tout merge.

## Règle d'intégration

Uniquement PR #522 ; ne pas merger automatiquement. Aucun CI affirmé vert. Des commits concurrents de #522 ont été observés sur `mobile/test/me_secondary_offline_test.dart` et `organizations/space_product.py` sans toucher aux fichiers directs de cette verticale ; recontrôler le HEAD avant intégration finale.
