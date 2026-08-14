# Commerce et Capacity — cœur transversal Makolo

Cette note décrit l’implémentation de la Tâche 7. Elle complète le blueprint canonique sans remplacer le vocabulaire métier des verticales.

## Principes

- **Journey** reste propriétaire du processus : inscription, réservation, approbation, paiement attendu, confirmation, fulfillment.
- **Capacity** répond à « combien de places/quota reste-t-il ? » et ne dépend ni de Commerce ni de Payment.
- **Commerce** répond à « qu’est-ce qui est proposé, à quel prix, dans quelle devise et selon quel mode de paiement attendu ? ».
- **Payment** reste propriétaire de ce qui s’est réellement passé chez un provider ou dans le flux financier Makolo.
- **Access** reste propriétaire du droit accordé à un bénéficiaire.

Une représentation simplifiée est :

```text
Activity / Occurrence
        │
        ├──────► Offer
        │          │
        │          └────► CapacityPool (optionnel)
        │                    │
Journey ─────────────────► CapacityReservation
   │                         │
   ├────► CommerceOrder ─────┤  (optionnel)
   │          │              │
   │          └────► Payment (optionnel)
   │
   └──────────────────────► Access
```

Le schéma réel n’est pas une chaîne stricte : CapacityReservation est liée directement à Journey ; CommerceOrder et Capacity peuvent vivre en parallèle. Une inscription gratuite peut donc réserver puis engager une place et émettre un Access sans CommerceOrder et sans Payment.

## Capacity

### CapacityPool

Un pool référence explicitement une `Activity` et éventuellement une `Occurrence`. Si l’Occurrence est renseignée, elle doit appartenir à l’Activity. `total_quantity=NULL` représente une capacité illimitée ; aucune valeur magique n’est utilisée.

La source auditable n’est pas un ensemble de compteurs mutables. La consommation est dérivée des `CapacityReservation` actives :

- `held` non expirées ;
- `committed`.

Les états `released` et `expired` ne consomment plus de capacité. Les selectors exposent total, held, committed, disponible, unlimited et sold-out.

### Réservation et concurrence

`reserve_capacity()` ouvre une transaction, verrouille **uniquement** le `CapacityPool` avec `select_for_update(of=("self",)).order_by()`, recalcule la consommation, puis crée le hold. Il n’utilise pas de `select_related()` sur le verrou.

Cette séquence empêche deux transactions PostgreSQL concurrentes de dépasser la capacité. Les transitions hold/commit/release/expire sont centralisées dans les services et sont idempotentes lorsque la répétition ne doit pas modifier le résultat.

`expire_stale_capacity_reservations()` et la commande `expire_capacity_holds` rendent les holds abandonnés récupérables sans introduire de nouveau scheduler.

La libération d’une réservation `committed` doit être explicitement autorisée par la politique métier. Un remboursement ou une révocation d’Access ne libère donc pas universellement une place.

## Commerce

### Offer

`Offer` est un nom backend. Les surfaces Events continuent à parler de **Type de billet / Tarif**. D’autres verticales pourront employer Classe, Catégorie, Formule ou Option.

Une Offer référence explicitement :

- Activity ;
- Occurrence nullable ;
- CapacityPool nullable.

Elle conserve Decimal `unit_price`, devise sur trois lettres normalisée en majuscules, fenêtre de disponibilité, min/max quantity, statut et `PaymentMode`.

Une Offer peut être gratuite (`unit_price=0`) et peut ne pas avoir de pool lorsqu’aucune logique de capacité n’existe.

### PaymentMode

Les modes contrôlés sont :

- `none` : aucun paiement attendu, donc montant nul ;
- `upfront` : paiement requis avant confirmation ;
- `after_approval` : la Journey est d’abord approuvée, puis passe en attente de paiement ;
- `on_site` : montant dû, mais aucun Payment provider Makolo n’est requis pour confirmer la réservation selon le métier ;
- `later` : paiement différé, sans obligation provider immédiate.

`PaymentMode` n’est jamais un `PaymentStatus`. Une commande `on_site` de 20 USD peut être confirmée sans être « payée » et sans créer un faux Payment réussi.

### CommerceOrder et CommerceOrderItem

Une Journey peut posséder plusieurs CommerceOrders. Une commande conserve des snapshots auditables : devise, PaymentMode, subtotal, discount_total, total et timestamps. Chaque ligne conserve le libellé utile, la quantité, le prix unitaire et la remise de ligne au moment de la commande.

`payee_space` est explicite et distinct du buyer, du créateur et de `Activity.space`. Le bridge Event choisit `activity.space` dans le cas simple ; le modèle générique ne suppose pas qu’ils seront toujours identiques. Une commande n’a qu’un payee principal dans cette version ; split payouts et marketplace settlement restent hors scope.

`create_order()` recalcule toujours les montants côté serveur depuis les Offers et les quantités. Un prix soumis par le frontend n’est jamais la source d’autorité. La première version refuse les mélanges de devises ou de PaymentModes dans une même commande.

Les lignes peuvent référencer une `CapacityReservation`; Capacity n’importe jamais Commerce.

## Journey, confirmation et Access

Pour une Offer `upfront`, Commerce place la Journey d’achat en `pending_payment`. Pour `after_approval`, une Journey approuvée passe en `pending_payment`. Les modes `none`, `on_site` et `later` ne fabriquent pas de Payment provider.

Lorsqu’une confirmation commerciale donne réellement droit à la place, les réservations associées passent explicitement à `committed`. Pour les Events bridgés, l’émission d’un Ticket/Access capacitaire s’appuie sur une CapacityReservation committed avant l’émission du droit individuel.

La quantité reste portée par la réservation et la ligne. `Access` demeure individuel : aucune `Access.quantity` n’est introduite.

## Bridges Events

### TicketType

`TicketType.offer` et `TicketType.capacity_pool` sont des OneToOne nullable de transition. Toute nouvelle écriture TicketType maintient :

- Offer : nom, description, prix, devise, fenêtre de vente, min/max et état ;
- CapacityPool : quantité totale, y compris `NULL` pour illimité.

Le calcul de disponibilité TicketType privilégie Capacity lorsque le bridge existe. Les anciens compteurs `reserved_quantity` / `issued_quantity` restent pour la compatibilité Event, mais ne sont plus la source transversale canonique.

### TicketOrder / TicketOrderItem

`TicketOrder.commerce_order` et `TicketOrderItem.commerce_item` sont des OneToOne nullable de transition. Les nouveaux parcours Event produisent désormais, lorsque la Journey est déterminable :

```text
Journey
  └─ CommerceOrder
       └─ CommerceOrderItem
            └─ CapacityReservation
```

TicketOrder, TicketOrderItem et TicketType restent les représentations Events utilisées par l’UX existante.

Les commandes historiques invitées qui ne peuvent pas être attribuées de façon déterministe à un Profil/Journey restent temporairement sur le chemin legacy plutôt que de créer une identité fictive.

### Payment

`Payment.commerce_order` est une FK nullable explicite. Le lien legacy `Payment.order -> TicketOrder` est conservé. Les Payments historiques sont reliés à la CommerceOrder de leur TicketOrder sans dupliquer les transactions.

Un nouveau Payment Event connaît la CommerceOrder canonique. La réussite du Payment synchronise Commerce/Journey/Capacity, mais toutes les données provider (référence provider, webhook, statut financier, refund) restent dans le bounded context Payment.

### Promotions et Waitlist

Promotions n’est pas refondu. Lorsqu’une remise Event a déjà produit un total, Commerce enregistre ce résultat comme snapshot. Waitlist reste verticale Events ; sa disponibilité bénéficie progressivement du `TicketType.available_quantity` basé sur Capacity quand le bridge existe.

## Backfill

Les migrations utilisent `apps.get_model`, sans imports runtime ni API externe. Elles créent de façon déterministe :

- une Offer et un CapacityPool par TicketType historique ;
- une CommerceOrder par TicketOrder possédant une Journey déterministe ;
- une CommerceOrderItem et une CapacityReservation par ligne historique bridgée ;
- le lien Payment → CommerceOrder lorsque le Payment historique pointe vers un TicketOrder bridgé.

Les snapshots utilisent le `TicketOrderItem.unit_price`, la quantité et le `TicketOrder.total_amount` historiques. Ils ne recalculent pas rétroactivement une ancienne commande depuis le prix courant du TicketType.

Pour la capacité historique, une commande `confirmed` devient committed, une commande `pending` devient held, une commande `cancelled` released et une commande `expired` expired. Le backfill ne copie pas naïvement les compteurs TicketType comme vérité canonique.

## Compatibilités conservées

Après cette tâche :

- Journey reste canonique pour le processus ;
- Access reste canonique pour le droit ;
- Offer, CapacityPool/Reservation et CommerceOrder/Item deviennent canoniques pour le commerce transversal ;
- Payment reste canonique pour la transaction financière réelle ;
- TicketType, TicketOrder, TicketOrderItem et Ticket restent la verticale Events ;
- Promotions et Waitlist restent Event-oriented ;
- le FK Payment → TicketOrder reste pendant la transition.

## Hors scope

Cette implémentation n’introduit ni Seat/SeatMap, Transport/Vehicle/Route, PostGIS/MapLibre, moteur FX, taxes internationales, split payouts, escrow, commissions marketplace, refonte Promotions, GroupEligibility complet, CRM audiences, grande Console Espace, grande UX Participant, ni suppression des modèles Tickets historiques.
