# Customer 360, timeline et segmentation comportementale

Le Lot 3 transforme le CRM Makolo en vue relationnelle unifiée sans créer une seconde base de vérité. `CRMContact` reste l'identité organisationnelle du contact ; les commandes, billets, paiements, waitlists, transferts, campagnes, promotions et attributions restent dans leurs domaines d'origine.

## Customer 360

`crm.customer360.customer_360()` calcule à la demande une synthèse pour un contact et une organisation. L'identité est rapprochée par compte Makolo lorsqu'il existe, avec l'e-mail normalisé comme repli pour les commandes/billets historiques.

La synthèse couvre notamment :

- commandes totales, confirmées, pending, annulées/expirées et nombre d'événements distincts ;
- billets valides/utilisés/annulés, événements fréquentés et no-shows déjà terminés ;
- waitlist active et conversions ;
- transferts envoyés/reçus/acceptés ;
- follow de l'organisateur ;
- campagnes reçues, cliquées et conversions CRM ;
- promotions réellement converties ;
- commandes réellement attribuées à un partenaire ;
- première/dernière commande confirmée et récence.

Aucun QR, secret PSP, payload webhook ou donnée d'un autre organisateur n'est agrégé dans cette vue.

## Frontière financière individuelle

Owner, Admin et staff peuvent voir la dépense confirmée par devise et la composante monétaire du RFM. Marketing et Event manager peuvent lire la relation CRM, la récence, la fréquence, la présence, les campagnes, waitlists et autres signaux d'engagement, mais les montants individuels et références financières sont masqués.

Le rôle Finance n'obtient pas pour autant le CRM : il conserve son domaine financier sans accès implicite aux fiches relationnelles et notes CRM.

## RFM explicable

Makolo ne présente pas le RFM comme une prédiction IA. Les règles sont déterministes et explicables :

- **R — Recency** : score 1–5 selon l'ancienneté de la dernière commande confirmée ;
- **F — Frequency** : score 1–5 selon le nombre de commandes confirmées ;
- **M — Monetary** : pour chaque devise séparément, quintile de dépense confirmée parmi les identités d'achat de la même organisation dans cette devise.

Les devises ne sont jamais additionnées entre elles. Un contact ayant des achats USD et CDF possède deux valeurs monétaires distinctes. Le libellé `Champion`, `Fidèle`, `Prometteur`, `À risque`, etc. est une lecture de ces scores et non une décision automatique.

## Timeline participant

`customer_timeline()` reconstruit un journal chronologique à partir des sources de vérité :

- follow organisateur ;
- création/confirmation de commande ;
- paiement réussi/remboursé pour les rôles financiers autorisés ;
- check-in ;
- entrée/offre/conversion waitlist ;
- transferts de billets ;
- campagnes reçues et clics ;
- attribution de conversion CRM ;
- promotion convertie ;
- acquisition partenaire confirmée.

Les montants ne sont ajoutés aux métadonnées de timeline que lorsque la permission financière Customer 360 est vraie.

## Segments comportementaux

Le modèle `AudienceSegment` possédait déjà un `custom_filters` JSON extensible. Le Lot 3 utilise un espace réservé `$behavior` qui ne peut pas entrer en collision avec une clé `SlugField` de champ personnalisé. Cela évite une migration et garde les segments existants compatibles.

Critères supportés :

- `min_confirmed_orders` ;
- `max_days_since_last_order` ;
- `min_days_since_last_order` ;
- `min_attended_events` ;
- `min_promotion_redemptions` ;
- `min_partner_referred_orders` ;
- `min_spend_amount` + `spend_currency`.

Tous les critères renseignés sont combinés en **ET** avec l'audience métier, les tags, ville/pays, consentement et champs personnalisés existants. Les agrégats sont calculés par sous-requêtes SQL depuis les domaines métier ; aucun compteur client mutable n'est stocké dans `CRMContact`.

Exemples :

```text
Clients récurrents actifs
min_confirmed_orders = 2
max_days_since_last_order = 90
```

```text
Clients à réactiver
min_confirmed_orders = 1
min_days_since_last_order = 180
```

```text
VIP présents
min_attended_events = 2
min_spend_amount = 250.00
spend_currency = USD
```

## Web

```text
/crm/contacts/<contact-id>/
/crm/org/<organization-slug>/segments/new/
/crm/segments/<segment-id>/
/crm/segments/<segment-id>/edit/
```

La fiche contact devient le workspace Customer 360 ; le formulaire de segment expose les filtres comportementaux sans demander aux équipes d'écrire le namespace `$behavior` manuellement.

## API

```text
GET  /api/v1/crm/contacts/<contact-id>/360/
GET  /api/v1/crm/segments/behavioral/
POST /api/v1/crm/segments/behavioral/
```

L'endpoint Customer 360 renvoie `financials_visible` afin que les clients web/mobile sachent si les composantes monétaires sont intentionnellement absentes. L'API de segments comportementaux valide les mêmes règles que le formulaire web et passe ensuite par `create_segment()` et les permissions CRM existantes.

## Invariants

1. Une organisation ne peut jamais voir le Customer 360 d'un contact d'une autre organisation.
2. Les montants individuels ne sont pas exposés à Marketing/Event manager.
3. Finance n'obtient pas le CRM par transitivité.
4. Les devises ne sont jamais fusionnées dans un total global.
5. Les segments sont recalculés depuis les données métier et ne dépendent pas d'un score persistant devenu obsolète.
6. Le Customer 360 n'accorde jamais de consentement marketing et ne modifie pas les préférences du participant.
7. Les règles RFM sont déterministes, inspectables et présentées comme aide au pilotage, pas comme décision automatisée.
