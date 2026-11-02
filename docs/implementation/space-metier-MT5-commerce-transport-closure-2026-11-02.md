# MT5 — Commerce et Transport : fermeture N1 → N2 → N3

**Date : 2 novembre 2026.** Dépôt : `TraditionLearningCommunity/makolo`. Branche de travail et PR : `fix/discover-a-continuation-context-20261014` / **#522**. Aucune intervention sur `main`.

**Statut honnête : code MT5 Web, API et Flutter implémenté sur la PR.** Les tests sont écrits mais **non exécutés** avec Django/PostgreSQL/Flutter dans cette session. Ce checkpoint ne constitue ni une certification E2E, ni un résultat CI, ni une autorisation de merge sans vérification.

## 1. Problème produit résolu

MT1 avait établi les propriétaires mais prouvé des profondeurs Métier inégales : Offer ouvrait une console d'offres, Vehicle une console de flotte ; Order ne montrait qu'un résumé ; Departure/Route/Service n'avaient pas une continuité spécialisée dans les deux clients.

La correction MT5 s'appuie sur le même sélecteur owner-backed de Work et sur les services propriétaires. Elle **n'ajoute aucun modèle métier ou état persisté**.

| Métier | Vérité propriétaire | N2 / N3 désormais assemblés |
| --- | --- | --- |
| Offre | `Offer` attachée à `Activity` | Identité, prix, devise, modes acceptés, min/max, fenêtre, statut, disponibilité et pool Capacity lorsqu'il existe ; édition par `commerce.services` sous `ACTIVITY_COMMERCE_MANAGE` |
| Commande | `CommerceOrder` et `CommerceOrderItem` | Référence, lignes de commande **snapshots historiques**, quantités, prix historiques, totaux et paiement attendu ; liens de lecture/Console existants sous `ORDERS_VIEW` |
| Paiement / remise / Obtention | Payment, Commerce, Journey, Access et Obtention selon owner réel | **Aucun succès de paiement, réservation ou fulfillment inféré** depuis `Order.confirmed` ou `Offer.active` ; pas de mutation universelle fabriquée |
| Route | `TransportRoute` + `TransportRouteStop` + `Place` | Arrêts ordonnés, embarquement/descente, services reliés et départs ; pas de ligne cartographique si géométrie insuffisante |
| Service de transport | `TransportService` + `Activity` | Route, mode, départs reliés ; l'activité reste le propriétaire durable |
| Véhicule | `Vehicle` | Type, immatriculation **sous droit**, capacité physique, affectations de départs ; aucune équivalence avec Capacity ou Placement |
| Départ | `TransportDeparture` + `Occurrence` + `CapacityPool` | Date/heure, route, véhicule affecté si autorisé, disponibilité du pool, consignes opérationnelles, Jour J conditionnel ; N3 d'exploitation |
| Opérations départ | `transport.services.assign_vehicle`, `reschedule_transport_departure`, `cancel_transport_departure` | Affecter véhicule, reprogrammer ou annuler seulement sous `ACTIVITY_OPERATIONS_MANAGE` et conditions métier ; ni paiement ni billet ni présence inventés |

## 2. N1 → N2 : sélection owner, responsabilités, retour

- Dans `organizations/space_work_web.py`, les entrées Commerce/Transport renvoient à `organizations:space-work-depth-g3` lorsque l'owner est sélectionnable avec `view`. La destination conserve `responsibility` et `from`.
- `organizations/space_work_g3_web.py` et `templates/organizations/space/work_g3_depth.html` rendent le N2 avec la grammaire Commerce ou Transport et le contexte de retour à Métier. Aucun formulaire de paiement ou tâche générique n'est greffé.
- `organizations/api/space_work_g3.py` n'étend `selection.owner_depth` **qu'après** la sélection autorisée par `build_space_work_projection`. Sous-collections paginées de 12 et responsables distincts ; statuts `partial/established` suivant l'étendue réellement lue.
- Le mobile `SpaceRetrievalOwnerScreen` relit le propriétaire dans le Space et la perspective actifs, puis présente `SpaceWorkG3Depth` avec sous-collections et pages successives. Une Occurrence datée ancienne encore `scheduled` n'ouvre pas un N2 inaccessible.
- Sources contextuelles privées, manifestes, données acheteur, QR, preuve ou encaissement non autorisé restent hors de cette projection.

## 3. N3 Commerce : Offer, Order, Payment et résultat

- Web : `space_work_g3_offer_web.py` et `work_g3_offer_form.html` appellent `space_work_g3_offer_owner.py`, qui impose le vrai owner Activity + permission + sélection Work, puis `commerce.services.create_offer/update_offer`.
- API Flutter : `workspace-work-g3-offer-create` et `workspace-work-g3-offer-edit` réutilisent **la même validation** `SpaceOfferOwnerForm`, le même owner et ses services ; payloads client ne choisissent ni Space, ni Activity lors de l'édition.
- Flutter : `SpaceWorkOfferEditorScreen` relit les options réelles (modes de paiement, statuts), valide l'identité de réponse et ne réémet pas automatiquement un POST ambigu. Un rejet de validation explicite peut être corrigé.
- Les modes complémentaires déjà configurés ne sont pas effacés silencieusement lorsqu'on réenregistre le mode par défaut. `Offer.is_currently_available` reste le fait propriétaire (dates + pool + statut).
- Order : les lignes de `CommerceOrderItem` affichent `label_snapshot`, `unit_price`, `line_total` ; **jamais** le prix actuellement modifié d'une Offer. Le paiement attendu n'est pas un état `Payment.succeeded`, et `confirmed` ne veut pas dire remis.
- Aucun nouvel owner `Fulfillment` ou dette de `OrderReadiness` n'a été créé. Obtention se compose uniquement lorsqu'un lien propriétaire existant est attesté.

## 4. N3 Transport : création et exploitation réelles

- Le Web préserve la Console Transport existante pour sa profondeur administrative, et ajoute `SpaceWorkG3DepartureOperationsView` pour une action contextualisée sur un Départ.
- `organizations/api/space_work_g3_transport_create.py` : créer Route via lieux `SpacePlace` autorisés, Vehicle dans l'Espace autorisé, Departure via les services Transport/Activity/Occurrence/Capacity/Offer existants **dans une transaction atomique**. Les limites de quantité, lieu, mode de paiement, fuseau, dates et capacité viennent du propriétaire. Une Activity/Capacity/Offer intermédiaire n'est pas conservée si la création globale échoue.
- `mobile/lib/features/space/space_transport_create_screen.dart` : formulaire natif avec données et capabilities fraîches, sélecteurs paginés de Route/Véhicule/Lieu, confirmation serveur, sans second POST automatique en cas de réponse incertaine.
- `organizations/api/space_work_g3_transport_operations.py` : GET et POST owner-scoped par `TransportDeparture`, `Occurrence`, acteur Space et responsabilité sélectionnée ; verrou `select_for_update` pour les mutations ; `can_assign_vehicle` exige en plus l'autorité directe flotte du Space. Un Mandate Activity ne transfère **pas** le droit sur toute la flotte.
- **Correction de fermeture MT5 :** la projection `g3_owner_depth` sépare `operations_visible` (lire) et `can_manage_operations` (agir). Le Web n'expose `Exploiter ce départ` que pour la gestion réelle et ouvre la profondeur N3 contextualisée `space-work-g3-departure-operations`, pas une mutation implicite dans la Console.
- **Flutter N3 ajouté :** `SpaceTransportDepartureOperationsScreen` via `/space/:slug/work/g3/departures/:id/operate`. Lecture owner vérifiée, véhicules actifs paginés, affectation confirmée, reprogrammation et annulation avec dialogue, nouvelle lecture après succès, protection contre changement d'acteur et résultats réseau incertains, aucune mutation optimiste.
- L'API réévalue toujours `ACTIVITY_OPERATIONS_MANAGE` et l'owner. `Capacity` reste quantité vendable, `Vehicle.passenger_capacity` une capacité physique ; `Access` et `AccessUse` restent leurs propres propriétaires.

## 5. Fichiers de livraison principaux

Serveur/Web :
- `organizations/api/space_work_g3.py`
- `organizations/api/space_work_projection.py`
- `organizations/api/space_work_g3_offer_views.py`
- `organizations/api/space_work_g3_transport_create.py`
- `organizations/api/space_work_g3_transport_operations.py`
- `organizations/space_work_g3_offer_owner.py`
- `organizations/space_work_g3_offer_web.py`
- `organizations/space_work_g3_web.py`
- `organizations/space_work_g3_departure_web.py`
- `organizations/api/urls.py`, `organizations/urls.py`, `organizations/space_work_web.py`
- `templates/organizations/space/work_g3_depth.html`, `work_g3_offer_form.html`, `work_g3_departure_operations.html`

Flutter :
- `mobile/lib/features/space/space_work_g3_depth.dart`
- `mobile/lib/features/space/space_work_offer_editor_screen.dart`
- `mobile/lib/features/space/space_transport_create_screen.dart`
- `mobile/lib/features/space/space_transport_departure_operations_screen.dart` (dernière fermeture)
- `mobile/lib/features/continuity/space_retrieval_owner_screen.dart`
- `mobile/lib/features/space/space_work_surface.dart`, `mobile/lib/app/router.dart`

Tests écrits :
- `organizations/test_space_work_group3.py` (N1)
- `organizations/test_space_work_mt5.py` (N2 et écriture propriétaires)
- `organizations/test_space_work_mt5_operations.py` (nouvelle couverture N3 gestion et révocation)
- `mobile/test/space_work_g3_depth_test.dart` (y compris CTA N3 sous `can_manage_operations`).

## 6. Vérification ciblée à exécuter (non exécutée)

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test organizations.test_space_work_group3 organizations.test_space_work_mt5 organizations.test_space_work_mt5_operations
cd mobile
bash tool/dart_format.sh write
bash tool/dart_format.sh check
flutter test test/space_work_g3_depth_test.dart test/space_work_surface_test.dart
```

Le dépôt distant a été inspecté au moyen de GitHub ; aucun checkout Django/PostgreSQL/Flutter exécutable n'est accessible localement, et la tentative Git directe ne pouvait pas résoudre `github.com`. **Ne pas présenter les tests comme verts.** Aucun test préexistant supprimé ou affaibli.

À contrôler en MT8 : 8 grammaires, états permission/entitlement et acteur changé, commande avec Offer dont le prix a évolué, dates de départ décalées, véhicule actif/inactif, capacité physique différente de la vendable, réservation concurrente, assignment entre Spaces refusé, commandes incertaines, révocation après ouverture, capacité pool saturée et écran compact/medium/wide.

## 7. Gate de sortie

**MT5 — périmètre de code Web/API/Flutter implémenté.** Les N2 Commerce et Transport sont individualisés. Les N3 Offer, création Transport et exploitation du Départ utilisent les vrais services propriétaires. Aucune carte n'invente un lieu, un paiement, une remise, une présence, un engagement de Capacity, ni une autorité.

**Non acquis :** validation d'exécution et parité de tous les outils administratifs propriétaires hors du parcours MT5. Ces points restent respectivement MT8 et assemblage transverse MT7. MT6 pourra se concentrer sur Creative/Media sans reprendre G3.

Aucun merge, aucune modification directe de `main`.

> Makolo marche pour vous. Pas le plaisir de rester. Le plaisir d'avancer.
