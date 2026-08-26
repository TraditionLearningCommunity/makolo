# Commerce et Capacity — cœur transversal Makolo

Cette note décrit l’implémentation du cœur Commerce/Capacity et ses évolutions T25. Elle complète le blueprint canonique sans remplacer le vocabulaire métier des verticales.

## Principes

- **Journey** reste propriétaire du processus : inscription, réservation, approbation, paiement attendu, confirmation, fulfillment.
- **Capacity** répond à « combien de places/quota reste-t-il ? » et ne dépend ni de Commerce ni de Payment.
- **Commerce** répond à « qu’est-ce qui est proposé, à quel prix, dans quelle devise et selon quelles règles de paiement ? ».
- **Payment** reste propriétaire de ce qui s’est réellement passé financièrement chez un provider ou lors d’un encaissement manuel réellement enregistré.
- **Access** reste propriétaire du droit individuel accordé à un titulaire Profile ou externe.

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

## Séparation des rôles humains et financiers

T25 rend explicites les rôles suivants, qui ne doivent pas être confondus :

- `initiated_by` : Profil qui lance la Démarche ;
- `buyer` : acheteur de la CommerceOrder ;
- `payer` / `Payment.initiated_by` : acteur de la tentative ou de l’enregistrement financier ;
- `beneficiary` / `external_beneficiary` : titulaire du droit ;
- `payee_space` ou `payee_profile` : bénéficiaire financier logique de la commande ;
- `Activity.space` ou `Activity.owner_profile` : opérateur logique de l’Activity.

Une même personne peut remplir plusieurs de ces rôles, mais le modèle ne les fusionne pas. En particulier, acheter pour quelqu’un ne donne aucun accès général à son Profil et posséder personnellement une Activity ne constitue pas automatiquement une destination de settlement chez un provider.

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

La libération d’une réservation `committed` doit être explicitement autorisée par la politique métier. Un remboursement, un no-show ou une absence de paiement sur place ne libère donc pas universellement une place.

### Quantité et droits

La quantité réservée doit rester cohérente avec le nombre de droits délivrés par le métier. Un flux multi-bénéficiaires futur qui réserve trois places doit produire trois Access individuels avec credentials distincts. Transport T25 conserve volontairement `min_quantity=max_quantity=1` : plusieurs voyageurs sont plusieurs intentions/réservations explicites tant qu’un checkout multi-voyageurs transactionnel n’est pas livré.

## Commerce

### Offer

`Offer` est un nom backend. Les surfaces Events continuent à parler de **Type de billet / Tarif**. D’autres verticales peuvent employer Classe, Catégorie, Formule ou Option.

Une Offer référence explicitement :

- Activity ;
- Occurrence nullable ;
- CapacityPool nullable.

Elle conserve Decimal `unit_price`, devise sur trois lettres normalisée en majuscules, fenêtre de disponibilité, min/max quantity, statut et un `payment_mode` historique/default.

T25 ajoute `OfferPaymentOption`, relation explicite et requêtable qui représente les modes **autorisés** par la politique commerciale. `Offer.payment_mode` reste le mode par défaut et la compatibilité des anciennes Offers ; il doit faire partie des modes autorisés.

Exemple :

```text
Offer 20 USD
payment_mode = upfront            # défaut
payment_options = [upfront, on_site]
```

L’utilisateur peut alors choisir « payer maintenant » ou « réserver et payer sur place ». La CommerceOrder créée snapshotte le choix réel, elle ne reçoit jamais un état ambigu `mixed`.

Une Offer gratuite est normalisée en `unit_price=0`, `payment_mode=none` et n’accepte que `none`. Une Offer payante ne peut pas ajouter `none` à ses modes autorisés.

### PaymentMode

Les modes contrôlés sont :

- `none` : aucun paiement attendu, donc montant nul ;
- `upfront` : paiement requis avant confirmation ;
- `after_approval` : la Journey est d’abord approuvée, puis passe en attente de paiement ;
- `on_site` : montant dû, mais aucun Payment n’est fabriqué pour confirmer la réservation selon le métier ;
- `later` : paiement différé, sans obligation provider immédiate.

`PaymentMode` n’est jamais un `PaymentStatus`. Une commande `on_site` de 20 USD peut être confirmée et engager sa capacité tout en ayant `Payment count = 0`. Elle doit être présentée comme « 20 USD à payer sur place », jamais comme « payée ».

### CommerceOrder et CommerceOrderItem

Une Journey peut posséder plusieurs CommerceOrders. Une commande conserve des snapshots auditables : devise, PaymentMode réellement choisi, subtotal, discount_total, total et timestamps. Chaque ligne conserve le libellé utile, la quantité, le prix unitaire et la remise de ligne au moment de la commande.

Le payee logique est représenté par deux FK explicites :

```text
payee_space   -> Space | null
payee_profile -> Profile | null
```

Pour une nouvelle commande, les deux ne peuvent pas être renseignés simultanément. Les lignes historiques sans payee restent valides : une migration ne les attribue pas arbitrairement à `created_by`.

Un flow collectif peut fournir `payee_space`; un flow personnel peut fournir explicitement `payee_profile`. **Commerce ne déduit pas automatiquement `payee_profile` de `Activity.owner_profile`**, car opérateur de l’Activity et bénéficiaire financier/provider settlement sont deux responsabilités différentes. Le sandbox et le manuel peuvent valider le domaine sans prétendre qu’un payout production existe.

Promotions reste actuellement Space-scoped. Une commande qui applique une Promotion canonique exige donc encore un `payee_space`; T25 ne crée aucun faux Space pour étendre Promotions aux Activities personnelles.

`CommerceOrderItem` peut viser un Profile bénéficiaire ou un `ExternalBeneficiary`. Les nouvelles écritures évitent l’ambiguïté et gardent le titulaire cohérent avec la Journey.

`create_order()` recalcule toujours les montants côté serveur depuis les Offers, Promotions et quantités. Un prix, total, devise ou remise soumis par le frontend n’est jamais la source d’autorité. Le mode de paiement demandé est également revalidé contre `OfferPaymentOption`.

Les lignes peuvent référencer une `CapacityReservation`; Capacity n’importe jamais Commerce.

### Idempotence

`CommerceOrder.idempotency_key`, `source_key`, `CapacityReservation.source_key`, `Payment.idempotency_key` et `Access.source_key` identifient des intentions/résultats stables à leur niveau.

Un retry HTTP ou réseau avec la même clé doit retrouver la même commande et ne pas créer une nouvelle Journey/CapacityReservation/Payment/Access. À l’inverse, une action volontaire « Acheter un autre billet » génère une nouvelle intention et peut produire une nouvelle Journey, CommerceOrder et Access.

Transport résout désormais la clé d’idempotence **avant** de créer une nouvelle Journey. Event conserve ses bridges d’idempotence existants.

## Journey, confirmation et Access

Pour une Offer `upfront`, Commerce place la Journey d’achat en `pending_payment`. Pour `after_approval`, une Journey approuvée passe en `pending_payment`. Les modes `none`, `on_site` et `later` ne fabriquent pas de Payment provider.

Lorsqu’une confirmation commerciale donne réellement droit à la place, les réservations associées passent explicitement à `committed`. Pour les Events bridgés, l’émission d’un Ticket/Access capacitaire s’appuie sur une CapacityReservation committed avant l’émission du droit individuel.

La quantité reste portée par la réservation et la ligne. `Access` demeure individuel : aucune `Access.quantity` n’est introduite.

## Paiement réel, retry et encaissement sur place

`Payment` décrit un fait financier réel ou une tentative réelle. Un paiement `upfront` réussi confirme la CommerceOrder via le bridge Payment/Commerce. Une commande ne peut pas posséder deux Payments `SUCCEEDED` pour la même source commerciale ; la contrainte et les services préservent cette garantie malgré callback/retry concurrent.

Un Payment échoué ou annulé peut être suivi d’une nouvelle tentative tant que la CommerceOrder reste valide ; cela ne crée pas une nouvelle Journey ni une nouvelle réservation de capacité.

Pour `on_site`, T25 ajoute un service d’enregistrement manuel destiné à **l’encaissement réellement effectué**. Il crée alors un vrai Payment `MANUAL`/`CASH` `SUCCEEDED` avec le montant et la devise exacts de la CommerceOrder. Cette opération :

- n’est jamais déclenchée automatiquement par la réservation ;
- exige une autorité financière serveur ;
- conserve l’acteur et une référence/idempotency key utile ;
- refuse montant/devise forgés puisque ces valeurs viennent de la commande ;
- ne reconfirme pas artificiellement une commande déjà confirmée on-site.

Les Activities personnelles utilisent une permission Activity-scoped financière dédiée (`activity.finance.*`) matérialisable par un Mandat `activity-finance`. Un simple `activity-manager`, l’owner personnel ou `is_staff` ne reçoit pas un bypass financier universel. Pour les Activities de Space, les permissions financières Space/Activity existantes restent la source d’autorité.

## Billets achetés pour autrui

Le buyer peut retrouver les Access produits par ses propres commandes, y compris lorsque leur titulaire est une autre personne. Cette visibilité est limitée à la transaction et ne change pas le bénéficiaire de l’Access.

Les projections participant distinguent donc :

- **Mes accès** : droits dont le Profile connecté est titulaire ;
- **Billets achetés pour d’autres personnes** : droits issus des CommerceOrders de cet acheteur pour un autre titulaire.

Un tiers ne peut pas ouvrir ces billets par UUID arbitraire. Les coordonnées éventuelles d’un `ExternalBeneficiary` ne deviennent pas publiques et ne sont pas envoyées inutilement dans les Domain Events.

## Bridges Events

### TicketType

`TicketType.offer` et `TicketType.capacity_pool` sont des OneToOne nullable de transition. Toute nouvelle écriture TicketType maintient :

- Offer : nom, description, prix, devise, fenêtre de vente, min/max et état ;
- CapacityPool : quantité totale, y compris `NULL` pour illimité.

Le calcul de disponibilité TicketType privilégie Capacity lorsque le bridge existe. Les anciens compteurs `reserved_quantity` / `issued_quantity` restent pour la compatibilité Event, mais ne sont plus la source transversale canonique.

### TicketOrder / TicketOrderItem

`TicketOrder.commerce_order` et `TicketOrderItem.commerce_item` sont des OneToOne nullable de transition. Les nouveaux parcours Event produisent, lorsque la Journey est déterminable :

```text
Journey
  └─ CommerceOrder
       └─ CommerceOrderItem
            └─ CapacityReservation
```

TicketOrder, TicketOrderItem et TicketType restent les représentations Events utilisées par l’UX existante. Ticket n’est pas remis au centre : la vérité du droit reste Access.

Les commandes historiques invitées qui ne peuvent pas être attribuées de façon déterministe restent temporairement sur le chemin legacy plutôt que de créer une identité fictive ou d’effectuer un claim automatique par email.

### Payment

`Payment.commerce_order` est une FK nullable explicite. Le lien legacy `Payment.order -> TicketOrder` est conservé. Les Payments historiques sont reliés à la CommerceOrder de leur TicketOrder sans dupliquer les transactions.

Un nouveau Payment Event connaît la CommerceOrder canonique. La réussite du Payment synchronise Commerce/Journey/Capacity, mais toutes les données provider (référence provider, webhook, statut financier, refund) restent dans le bounded context Payment.

### Promotions et Waitlist

Promotions n’est pas refondu. Les Promotions canoniques restent liées à un Espace/payee_space ; aucune Organization fictive n’est créée pour les Activities personnelles. Waitlist reste verticale Events ; sa disponibilité bénéficie du `TicketType.available_quantity` basé sur Capacity quand le bridge existe.

## Backfill et migrations T25

Les migrations restent additives et utilisent des relations explicites, sans `GenericForeignKey`, `ContentType` ou JSON payee.

T25 :

- ajoute `ExternalBeneficiary` ;
- ajoute les relations nullable alternatives sur Journey, Access et CommerceOrderItem tout en préservant les FK Profile historiques ;
- ajoute `CommerceOrder.payee_profile` sans modifier les payees historiques indéterminables ;
- crée `OfferPaymentOption` et backfill chaque Offer existante avec son `payment_mode` historique comme unique option autorisée ;
- ajoute les permissions financières Activity nécessaires sans étendre implicitement les rôles existants.

Le backfill des options de paiement est déterministe et portable SQLite/PostgreSQL. Les anciens Access/Journey Profile ne sont pas convertis en texte et les anciennes CommerceOrders sans payee restent compatibles.

Les migrations historiques Commerce/Capacity conservent par ailleurs leurs snapshots : TicketOrderItem.unit_price, quantité, total historique et statut de capacité. Elles ne recalculent jamais rétroactivement une ancienne commande depuis le prix courant d’une Offer.

## Compatibilités conservées

Après T25 :

- Journey reste canonique pour le processus ;
- Access reste canonique pour le droit et son titulaire individuel ;
- Offer/OfferPaymentOption, CapacityPool/Reservation et CommerceOrder/Item sont canoniques pour le commerce transversal ;
- Payment reste canonique pour la transaction financière réelle ;
- TicketType, TicketOrder, TicketOrderItem et Ticket restent la verticale Events ;
- Promotions et Waitlist restent Event/Space-oriented là où leur généralisation personnelle n’est pas encore sûre ;
- le FK Payment → TicketOrder reste pendant la transition ;
- une Activity personnelle n’exige aucun faux Space pour utiliser Commerce.

## Hors scope

T25 n’introduit ni vrai provider de paiement production absent du dépôt, split payouts, marketplace settlement, escrow, FX, taxes internationales, wallet financier Makolo, claim automatique d’un bénéficiaire externe, transfert complet d’Access entre identités, GroupEligibility, recherche T26, favoris, carte/feed social, ni refonte Promotions.
