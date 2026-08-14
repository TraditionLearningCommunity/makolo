# CRM, Audiences et Promotions — Tâche 8B

Cette étape généralise les capacités CRM et Promotions sur le cœur Makolo stabilisé par Journey/Access/Commerce et les Domain Events 8A.

```text
Domain Events
    ↓
CRM contact / interactions
    ↓
Audience matérialisée
    ↓
Promotion eligibility
    ↓
Offer / CommerceOrder snapshots
```

## Identité CRM

`accounts.User/Profile` reste l’identité canonique. `CRMContact` représente la relation entre un Espace (`Organization`) et un Profil lorsqu’un compte Makolo existe. La contrainte canonique est unique par `organization + user` ; la contrainte historique par e-mail reste utile pour les contacts guest/pending sans Profil.

Les contacts historiques sans Profil ne provoquent jamais la création artificielle d’un User. Lorsqu’un Domain Event concerne un Profil dont un contact historique du même Espace porte déjà l’e-mail fiable, ce contact peut être relié au Profil plutôt que dupliqué.

`CRMInteraction` enregistre uniquement un fait CRM dérivé utile : Journey soumise/confirmée/réalisée, Access émis/utilisé, CommerceOrder confirmée ou Payment réussi. Le payload complet du Domain Event n’est pas copié. La relation `contact + domain_event + interaction_type` rend une relivraison idempotente, en plus de `DomainEventConsumption`.

Le consumer `crm.system` est enregistré localement par l’app CRM. Les faits commerciaux utilisent `CommerceOrder.payee_space`; les autres faits utilisent l’Espace métier du Domain Event. Aucun `created_by.organization` arbitraire n’est utilisé.

## Audiences

`Audience` appartient à un Espace et matérialise un ensemble de Profils via `AudienceMember`.

Sources supportées :

- sélection statique de Profils déjà connus du CRM de l’Espace ;
- membres **actuels** d’un Group de l’Espace, copiés au moment de la création ;
- population exacte d’un `GroupSnapshot`.

Un `Group` personnel ou appartenant à un autre Espace est refusé. Une Audience créée depuis un Group n’est pas dynamique : les changements ultérieurs du Group ne modifient pas ses membres.

**Group ≠ Audience.** Le Group porte une appartenance métier ; l’Audience porte une population ciblée pour une opération.

**Audience ≠ consentement.** Ajouter un Profil à une Audience ne modifie jamais `CRMContact.marketing_consent`, les préférences e-mail ou les consentements existants. Les notifications transactionnelles 8A restent indépendantes des Audiences et des Promotions.

## Promotions canoniques

Le modèle historique `Promotion` reste conservé, mais sa cible commerciale canonique passe par des relations explicites :

- `PromotionTargeting` : Activity et Audience optionnelles ;
- `PromotionOffer` : une ou plusieurs `commerce.Offer` ;
- `CommercePromotionRedemption` : snapshot d’une utilisation sur `CommerceOrder`.

Aucune GenericForeignKey, expression SQL libre, Python arbitraire ou `eval` n’est introduit.

Les `TicketType` restent la projection Events. Leur relation historique `Promotion.eligible_ticket_types` est bridgée vers `ticket_type.offer` avec des `PromotionOffer` marquées `source=ticket_type`. Les cibles Offer configurées directement ne sont pas supprimées par le bridge.

## Calcul et éligibilité

Le checkout canonique reste `commerce.create_order`. Le frontend ne fournit jamais le montant final de remise comme vérité lorsqu’un code Promotion est utilisé.

Le serveur calcule :

```text
Offer.unit_price × quantité = subtotal
subtotal éligible - remise fixed/percent = total
```

Les montants utilisent `Decimal`. Les fenêtres, devise, minimum de commande, quota global, quota du code et limite par Profil sont contrôlés serveur sous verrou transactionnel. Les quotas comptent à la fois les redemptions Event historiques et les redemptions Commerce canoniques afin d’éviter deux compteurs concurrents.

Une Promotion peut être publique ou réservée à une `Audience`. La possession du code ne contourne jamais cette restriction : le Profil doit appartenir à l’Audience matérialisée au checkout.

Une seule Promotion par code/commande reste la règle de cette étape ; aucun stacking avancé n’est ajouté.

## Snapshots Commerce

`CommerceOrder` et `CommerceOrderItem` restent les sources historiques du prix effectivement vendu : subtotal, remise et total sont snapshotés lors de la création. Modifier ensuite le prix de l’Offer, la valeur de la Promotion, sa fenêtre ou son statut ne réécrit jamais la commande existante.

`Payment` reçoit uniquement le `CommerceOrder.total` final et n’est jamais modifié directement par Promotions.

## Permissions et confidentialité

Les permissions existantes sont réutilisées : `crm.view`, `crm.manage`, `crm.financials.view` et les permissions Promotions. Le rôle Marketing peut gérer CRM/Audiences/Promotions selon la matrice actuelle mais n’obtient pas implicitement Finance, Access, provider Payment, QR credentials, Scanner, KYC ou notes internes d’autres domaines.

Les nouveaux selectors Audience n’exposent que le Profil nécessaire. Les agrégats financiers canoniques sont fournis séparément et ne doivent être appelés que derrière la permission financière existante.

## Compatibilité

Restent volontairement en place pendant la transition :

- `AudienceSegment` et campagnes CRM historiques Event/Ticket ;
- `CRMWorkflow*` legacy, sans nouvelles responsabilités transversales ;
- `Promotion.event`, `eligible_ticket_types` et `PromotionRedemption` TicketOrder ;
- le vocabulaire Event « Type de billet / Code promo / Promotion » dans l’interface.

Aucun historique complet de Domain Events n’est recréé. Le seed couvre les nouveaux modèles avec quelques objets déterministes, sans prétendre reconstruire tout le passé.

## Hors scope

8C garde Scanner/Operations et Analytics. Restent également hors scope : GroupEligibility de participation, campagnes SMS/providers externes, segmentation SQL arbitraire, lead scoring complexe, promotion stacking, dynamic pricing, transport et marketplace payouts.
