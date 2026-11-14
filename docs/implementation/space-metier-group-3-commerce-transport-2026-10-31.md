# Makolo — Métier Space / Groupe 3 : Commerce et Transport

**Date :** 2026-10-31. **PR de travail unique :** #522, branche `fix/discover-a-continuation-context-20261014`.
**Base main observée :** `d0f0ec421c94c255fa4c0acd3509938a70c6322f`. La PR accueille aussi d'autres commits concurrents : refaire un collision audit avant toute nouvelle modification partagée.

## Portée et statut

Implémentation **composition Métier N1 serveur et Web** du groupe 3, complémentaire aux groupes 1 (generic, community) et 2 (education, service_provider). Aucun nouveau domaine, `WorkItem`, statut, migration, Permission, Mandate, mutation ou endpoint créé.

Le périmètre de clôture N2/N3 Web et Flutter/local-first reste la phase d'intégration commune prévue **après les groupes de composition**, non un faux livrable de ce groupe.

Sources : `docs/ux/Makolo_UX_Space_Metier_Commerce_Contrat_Consolide_2026-10-08.md`, `docs/ux/Makolo_UX_Space_Metier_Transport_Contrat_Consolide_2026-10-08.md`, blueprint et owners runtime.

## Commerce

Question : « Que rendons-nous disponible, quelles commandes traiter et quelles réalisations devons-nous réellement accomplir ? »

- `CommerceOrder` reste la commande ; `Offer` reste l'offre ; `Activity` reste l'objet durable ; `Occurrence` reste une réalisation. Aucun de ces owners ne devient un statut de tâche.
- Le `business_world` compose **Commandes et traitement**, **Ce que nous rendons disponible**, **Réalisations à venir**, les autres verticales réellement présentes et l'historique, uniquement selon les sections et pages d'owner déjà autorisées.
- Une commande `CONFIRMED` conserve son statut *confirmée* ; cela ne vaut **ni Payment confirmé ni remise ni livraison ni Outcome accompli**. Le détail API Commerce déjà existant continue à vérifier `ORDERS_VIEW`, Space, responsabilité et Activity.
- Une offre `ACTIVE/INACTIVE` conserve son état source et peut exposer un agrégat `CapacityAvailability` **uniquement si une CapacityPool réelle est reliée**. Aucune disponibilité n'est inventée sans pool. Une CapacityPool désactivée est signalée, pas présumée vendable.
- Le Web route l'Order vers `organizations:space-retrieval-order-detail` seulement en scope global compatible avec cette profondeur, et l'Offer vers `organizations:console-offers` si la capacité de lecture correspond. Ces vues revalident la permission à l'ouverture.
- L'état calme permet de consulter l'offre durable même sans commande. Pas de KPI/finance/statut de fulfillment fabriqué.

## Transport

Question : « Quels départs préparons-nous et opérons-nous, sur quelles routes et avec quels véhicules réellement affectés ? »

- `TransportRoute` et `Vehicle` restent structurels, même quand `active=True`. Ils ne deviennent jamais une occurrence `live`.
- `TransportService` reste une Activity spécialisée ; un **départ réel** provient exclusivement du `TransportDeparture` associé à son `Occurrence`.
- Le `business_world` compose **Départs et exploitation**, **Routes et véhicules**, **Services de transport**, autres réalités visibles et historique. Structure, continuité et états owner ne sont pas confondus.
- Une Occurrence transport consultable par l'opérateur porte une référence `transport.departure_id`, la route réellement liée, et son **véhicule affecté réel** ou `null`. Une absence de véhicule n'est pas présentée comme Blocker dérivé sans owner.
- La Capacity du départ provient de sa `passenger_capacity_pool` et du sélecteur canonique `capacity_availability_many` : total, disponibilité, unlimited/sold_out et statut actif du pool. La capacité vendable n'est pas l'occupation physique du véhicule, ni un AccessUse.
- La continuité **Aujourd'hui** référence au plus cinq départs réels déjà visibles sur la page. Elle ne duplique aucun item, ne fait pas de ranking et n'apparaît pas lorsqu'aucun départ du jour n'est constaté.
- Jour J est proposé uniquement par la phase canonique Operations et le droit Activity Operations déjà contrôlés. Pas de nouvelle machine Live.
- Le Web mène vers `organizations:console-transport-departure-detail` pour les départs opérables, `organizations:console-transport-route-detail` pour les routes, et vers la vue Transport existante pour les véhicules (pas de fausse fiche véhicule). Le lecteur Activity-limited ne reçoit pas les routes et véhicules Space-wide.

## Confidentialité et frontières

- `Actor = Space`, `Viewer = Profile`, aucune autorité implicite via `Membership`, archétype ou composition.
- `ORDERS_VIEW` et `ACTIVITY_COMMERCE_VIEW` ne sont pas échangés ; `SPACE_ACTIVITIES_VIEW` reste requis pour les profondeurs Console Transport globales.
- Jamais de buyer email, manifest, billet/AccessCredential, QR, identité de passager, relevé financier ou paiement dupliqué dans la projection.
- Le lien Web ou API est un handoff et non une garantie d'autorisation au clic ; la vue propriétaire vérifie de nouveau l'autorité.
- Les groupes 1/2 restent sur les mêmes sections historiques ; `creative` et `media` n'héritent d'aucun `business_world` groupe 3 avant le groupe 4.
- Aucune migration.

## Tests ciblés créés

`organizations.test_space_work_group3` :
1. commandes confirmées vs offres/capacité réelle, états distincts, confidentialité acheteur et refus étranger ;
2. offre durable inactive sans commande ni capacité fictive ;
3. départ réel, route, véhicule affecté, CapacityPool, Jour J et projection du jour ;
4. absence d'affectation véhicule sans faux blocker/readiness ;
5. Activity-only Mandate sans exposition de la flotte Space-wide ;
6. Web Commerce vers les profondeurs owner existantes ;
7. Web Transport vers les profondeurs départ/route et liste des véhicules ;
8. sélection IDOR d'une route d'un autre Space refusée ;
9. aucune composition groupe 3 transmise prématurément à `media`.

À exécuter localement :

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test organizations.test_space_work_group3 organizations.test_space_work_group2 organizations.test_zs3_space_work_api organizations.test_ws3_space_work_web
```

**Validation non attestée :** le code et les tests ont été poussés, mais Django, PostgreSQL, Flutter et CI ne sont pas exécutés dans cette session. Aucun merge sur `main`.

## Suite

Groupe 4 — **Créatif + Média** ; puis la fermeture commune Web N2/N3, Flutter natif, Behavior, local-first/révocation, parcours complets et vérifications de permissions/IDOR.
