# Promotions, codes et offres avancées

## Objectif

Le domaine `promotions` ajoute une couche de pricing commercial contrôlée au-dessus de la billetterie Makolo sans déplacer la source de vérité des commandes, paiements ou billets. Le navigateur ou le client API transmet un code ; le serveur recalcule toujours la remise à partir des prix et règles persistés.

Le flux est :

```text
sélection de billets
      ↓
code promotionnel facultatif
      ↓
validation serveur des règles + quotas
      ↓
réservation de stock
      ↓
PromotionRedemption reserved
      ↓
paiement / confirmation réelle
      ↓
PromotionRedemption confirmed
```

Une annulation ou expiration passe la redemption à `reversed`, ce qui libère le quota promotionnel.

## Modèle

### Promotion

Une offre appartient à une organisation et peut être liée à un événement précis ou rester organisationnelle. Elle définit :

- remise en pourcentage ou montant fixe ;
- plafond facultatif pour une remise en pourcentage ;
- minimum de commande ;
- devise lorsque la règle monétaire l'exige ;
- liste facultative de types de billets éligibles ;
- période d'activité ;
- quota global ;
- nombre maximum d'utilisations par client ;
- état actif/inactif.

Une liste de billets éligibles vide signifie que tous les billets compatibles de l'événement peuvent contribuer au montant éligible.

### PromotionCode

Un code est globalement unique après normalisation en majuscules. Il peut ajouter ses propres dates, quota et état. `is_private=True` signifie que le code reste utilisable lorsqu'il est connu mais n'est jamais proposé publiquement dans le checkout.

Un code peut référencer une `CommunicationCampaign`. Cette relation mesure explicitement « campagne → code → commande » ; elle ne crée pas artificiellement un clic ni une `CampaignAttribution` signée.

### PromotionRedemption

Chaque commande possède au plus une redemption. La ligne conserve un snapshot immuable de la décision commerciale prise au checkout :

```text
subtotal_amount
eligible_amount
discount_amount
final_amount
currency
```

Les changements futurs apportés à l'offre ou au code ne réécrivent donc pas l'historique d'une commande existante.

## Validation transactionnelle

`create_order_with_promotion()` enveloppe la réservation de stock et la validation du code dans la même transaction. Si le code est invalide, expiré, hors quota ou incompatible, la commande et sa réservation de stock sont annulées avec la transaction.

Le service verrouille l'offre et le code via `select_for_update()` avant de vérifier les quotas. PostgreSQL reste la cible production pour que ces verrous offrent la sémantique de concurrence attendue ; SQLite est conservé pendant la construction fonctionnelle.

Les règles vérifiées côté serveur comprennent :

- organisation ;
- événement ;
- période de l'offre et du code ;
- état actif ;
- devise ;
- minimum de commande ;
- billets éligibles ;
- quota global ;
- quota du code ;
- limite par client.

Une remise ne peut jamais rendre le total négatif. Si elle ramène une commande payante exactement à zéro, Makolo confirme immédiatement la commande et émet ses billets dans la transaction.

## Waitlist et paiement

Les commandes créées par la waitlist peuvent recevoir un code tant qu'elles sont encore `pending`, non expirées et qu'aucun paiement n'a été initialisé. Le code est donc appliqué avant la création d'une transaction Payments, ce qui garantit que le fournisseur reçoit le vrai `TicketOrder.total_amount` après remise.

Les paiements, commissions partenaires et attributions CRM continuent d'utiliser `TicketOrder.total_amount`. Ils voient donc le prix effectivement payé, tandis que `PromotionRedemption.subtotal_amount` permet de conserver la valeur catalogue avant remise.

## Attribution et coexistence

Une même commande peut contenir simultanément :

```text
ReferralAttribution        → qui a apporté le client
CampaignAttribution        → quel clic CRM signé a déclenché la vente
PromotionRedemption        → quelle offre a réduit le prix
```

Ces trois mécanismes ne s'écrasent pas.

Lorsqu'un code est lié directement à une campagne CRM, les métriques de campagne exposent séparément les conversions par code, les remises et le CA final par devise. Ces valeurs restent distinctes des conversions par clic afin d'éviter de présenter une attribution inexistante.

## Permissions

- Owner/Admin : gestion complète et métriques financières ;
- Marketing : création/modification/pause des offres et codes, compteurs d'utilisation, pas de liste financière détaillée des redemptions ;
- Finance : lecture des offres et redemptions financières, sans droit de modifier la stratégie promotionnelle ;
- Event Manager : lecture des offres et compteurs, sans lignes financières ;
- Scanner Manager : aucun accès implicite ;
- Participant : utilisation d'un code sur ses propres commandes uniquement.

`is_staff` conserve le droit de supervision plateforme.

## Web et API

Interface organisateur :

```text
/promotions/
/promotions/org/<organization-slug>/
/promotions/<promotion-id>/
```

Le checkout participant accepte un code directement pendant la création de commande ou sur une commande `pending` avant paiement.

API de gestion :

```text
GET/POST /api/v1/promotions/promotions/
GET      /api/v1/promotions/promotions/<id>/
POST     /api/v1/promotions/promotions/<id>/toggle/
GET      /api/v1/promotions/promotions/<id>/metrics/
GET/POST /api/v1/promotions/codes/
POST     /api/v1/promotions/codes/<id>/toggle/
GET      /api/v1/promotions/redemptions/
```

L'API billetterie accepte également :

```json
{
  "promotion_code": "SUMMER20"
}
```

Les réponses de commande exposent `subtotal_amount`, `discount_amount`, `promotion_code` et `total_amount` afin qu'un client mobile puisse afficher exactement la décision serveur.

## Principes de sécurité

- aucun montant de remise fourni par le client n'est accepté ;
- un code privé n'est jamais listé publiquement ;
- les quotas incluent les réservations `pending` pour éviter leur contournement par réservation massive ;
- les redemptions inversées ne consomment plus les quotas ;
- les montants restent séparés par devise ;
- Marketing ne reçoit pas l'API brute des redemptions financières ;
- les règles historiques ne sont jamais recalculées rétroactivement.
