# Module Tickets

## Responsabilité

`tickets` gère les produits de billetterie, le stock, les réservations, les commandes, l’émission des billets et les jetons QR. Il dépend de `events` et prépare les interfaces nécessaires à `payments` et `scanner`.

## Modèles

### TicketType

Un type de billet appartient à un événement et définit :

- nom et description ;
- prix et devise ISO à 3 lettres ;
- stock optionnel ;
- quantités réservées et émises ;
- fenêtre de vente ;
- quantité minimale et maximale par commande ;
- état actif/inactif.

Le stock disponible est calculé comme `quantity_total - reserved_quantity - issued_quantity`. Si `quantity_total` est vide, le type de billet est illimité, mais la capacité globale de l’événement reste appliquée.

### TicketOrder

Une commande appartient à un événement et éventuellement à un utilisateur connecté. États :

```text
pending -> confirmed
   |          |
   v          v
expired    cancelled
   |
cancelled
```

Les commandes gratuites sont confirmées immédiatement. Les commandes payantes restent `pending` et réservent le stock pendant 20 minutes par défaut. Le futur module `payments` appellera le service `confirm_order` après confirmation du paiement.

### TicketOrderItem

Ligne de commande contenant le type de billet, la quantité et le prix unitaire figé au moment de la réservation.

### Ticket

Billet individuel émis uniquement lors de la confirmation d’une commande. États :

- `valid` ;
- `used` ;
- `cancelled` ;
- `refunded`.

Chaque billet possède un UUID public `code`. Le QR n’encode pas directement des permissions métier : il contient un jeton signé par Django dérivé de ce code.

## Concurrence et capacité

Les services d’écriture utilisent `transaction.atomic()` et `select_for_update()` sur l’événement et tous ses types de billets avant de modifier les compteurs de stock. Cette stratégie évite le dépassement simultané du stock d’un type et de la capacité globale de l’événement sur une base transactionnelle compatible.

PostgreSQL reste recommandé pour la production et la forte concurrence. SQLite est conservé pour le développement local.

## Cycle d’une commande

### Gratuit

```text
create_order
  -> réserve le stock
  -> confirme immédiatement
  -> transforme reserved en issued
  -> crée N Ticket
```

### Payant

```text
create_order
  -> réserve le stock
  -> pending
  -> paiement externe
  -> confirm_order
  -> transforme reserved en issued
  -> crée N Ticket
```

Une commande expirée doit libérer son stock. Le service `expire_order` est disponible et la commande :

```text
python manage.py expire_ticket_orders
```

traite les réservations arrivées à expiration. En production cette commande devra être planifiée périodiquement.

## QR et scanner

`validate_qr_token()` vérifie la signature, retrouve le billet et contrôle sa validité de base. Il ne marque pas le billet comme utilisé. Cette mutation sera volontairement implémentée dans `scanner` afin que l’enregistrement du scan et la prévention du double scan restent transactionnels et auditables.

## API v1

```text
GET/POST        /api/v1/tickets/types/
GET/PATCH/DEL   /api/v1/tickets/types/<id>/
GET/POST        /api/v1/tickets/orders/
GET             /api/v1/tickets/orders/<id>/
POST            /api/v1/tickets/orders/<id>/confirm/
POST            /api/v1/tickets/orders/<id>/cancel/
GET             /api/v1/tickets/tickets/
GET             /api/v1/tickets/tickets/<id>/
```

La confirmation d’une commande payante n’est pas autorisée au participant : elle est réservée à l’organisateur/staff en attendant l’intégration du fournisseur de paiement.

## Interface web

```text
/tickets/
/tickets/<id>/
/tickets/<id>/qr.png
/tickets/manage/types/
/tickets/manage/types/new/
/tickets/manage/types/<id>/edit/
/tickets/buy/<event-slug>/
/tickets/orders/<id>/
```

## Sécurité

- les billets d’un utilisateur ne sont pas visibles par un autre participant ;
- l’organisateur peut voir les billets et commandes de ses événements ;
- le staff dispose du périmètre global ;
- un organisateur ne peut pas gérer les types de billets d’un autre organisateur ;
- le QR est signé et une modification du jeton invalide la vérification ;
- les commandes confirmées contenant un billet déjà utilisé ne peuvent pas être annulées.

## Prochaines intégrations

- `payments` : confirmation et remboursement des commandes payantes ;
- `scanner` : validation d’accès atomique, anti-double-scan et journal de contrôle ;
- `notifications` : envoi du billet et rappels ;
- `analytics_app` : ventes, taux de conversion, présence et revenus.
