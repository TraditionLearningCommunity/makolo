# Module Payments

## Responsabilité

`payments` orchestre le règlement des commandes payantes de `tickets`. Il ne crée jamais directement de billets : une transaction réussie confirme la `TicketOrder`, puis le service de billetterie transforme le stock réservé en billets émis.

Le module est volontairement séparé des fournisseurs externes. Le noyau livré ici contient un fournisseur `sandbox` pour le développement et un mode `manual` pour les encaissements contrôlés par un organisateur/staff. Aucun PSP réel, numéro de carte, secret bancaire ou donnée PCI n’est stocké dans Makolo.

## Modèles

### Payment

Une tentative de paiement contient notamment :

- la commande ;
- le fournisseur et la méthode ;
- le montant et la devise figés depuis la commande ;
- le statut ;
- une référence Makolo et une référence fournisseur ;
- une clé d’idempotence facultative ;
- les informations minimales du payeur ;
- les horodatages de succès, échec ou annulation.

États :

```text
pending -> processing -> succeeded -> refunded
   |          |
   +----------+-> failed
   +------------> cancelled
```

Une contrainte de base de données interdit plusieurs paiements `succeeded` pour une même commande.

### Refund

Le socle actuel implémente le remboursement **complet**. Un remboursement réussi annule la commande et tous ses billets encore valides. Un billet déjà utilisé bloque l’opération afin de préserver la cohérence comptable et le contrôle d’accès.

### PaymentEvent

Journal des événements fournisseur/webhook. Le payload persistant est volontairement limité à une liste blanche de champs opérationnels. Le corps brut et les secrets ne sont pas stockés.

## Cohérence transactionnelle

Les transitions critiques utilisent `transaction.atomic()` et `select_for_update()`.

Pour un succès :

```text
Payment.pending
  -> verrou Payment
  -> verrou TicketOrder
  -> vérification expiration / montant / paiement déjà réussi
  -> verrou stock TicketType
  -> émission des billets
  -> TicketOrder.confirmed
  -> Payment.succeeded
  -> commit
```

Ainsi deux paiements concurrents ne peuvent pas émettre deux fois les billets d’une même commande.

## Idempotence

`Payment.idempotency_key` empêche une double création lors d’un retry HTTP. Le webhook utilise `(provider, event_id)` comme clé d’unicité. Le scanner possède sa propre stratégie d’idempotence indépendante.

## Sandbox

En développement, `PAYMENTS_SANDBOX_ENABLED` est activé par défaut lorsque `DEBUG=True`. En production il reste désactivé sauf configuration explicite.

Le sandbox permet de tester tout le cycle sans argent réel :

```text
commande payante pending
-> création Payment sandbox
-> succès simulé
-> commande confirmed
-> billets émis
-> QR disponibles
-> scanner utilisable
```

## Paiement manuel

Le fournisseur `manual` est réservé à l’organisateur propriétaire de l’événement ou au staff. Il sert aux cas comme espèces, virement vérifié hors plateforme ou tests opérationnels. Le participant ne peut pas auto-confirmer un paiement manuel.

## Webhook sandbox signé

Endpoint :

```text
POST /api/v1/payments/webhooks/sandbox/
```

Le corps JSON est signé par HMAC-SHA256 avec `PAYMENTS_WEBHOOK_SECRET` et la signature hexadécimale est envoyée dans :

```text
X-Makolo-Signature
```

Événements pris en charge :

```text
payment.succeeded
payment.failed
```

Ce mécanisme est un banc de test de l’architecture webhook. Chaque PSP réel devra avoir son propre adaptateur et sa propre vérification cryptographique conforme à sa documentation officielle.

## API v1

```text
GET              /api/v1/payments/configuration/
GET/POST         /api/v1/payments/payments/
GET              /api/v1/payments/payments/<id>/
POST             /api/v1/payments/payments/<id>/sandbox-complete/
POST             /api/v1/payments/payments/<id>/manual-complete/
POST             /api/v1/payments/payments/<id>/cancel/
POST             /api/v1/payments/payments/<id>/refund/
GET              /api/v1/payments/events/
POST             /api/v1/payments/webhooks/sandbox/
```

L’ancien endpoint direct `tickets/orders/<id>/confirm/` est retiré de l’API. Une commande payante doit passer par le domaine `payments`.

## Interface web

```text
/payments/
/payments/order/<order-id>/new/
/payments/<payment-id>/
```

La page d’une commande payante propose désormais `Payer maintenant` et affiche l’historique de ses tentatives.

## Sécurité

- aucun stockage de PAN/CVV ou secret bancaire ;
- montant et devise dérivés côté serveur depuis `TicketOrder` ;
- confirmation utilisateur limitée au sandbox de développement ;
- paiement manuel réservé organisateur/staff ;
- remboursement réservé organisateur/staff ;
- remboursement interdit après utilisation d’un billet ;
- références fournisseur uniques ;
- une seule transaction réussie par commande ;
- webhooks signés et limités en débit ;
- accès aux paiements filtré par acheteur, organisateur ou staff.

## Fournisseurs réels

Le prochain ajout PSP devra être un adaptateur dédié, par exemple Mobile Money ou carte, sans déplacer la logique métier hors de `payments.services`. Avant activation en production il faudra vérifier la documentation officielle du fournisseur, la signature webhook, les politiques de retry, les devises, les remboursements et les exigences réglementaires locales.
