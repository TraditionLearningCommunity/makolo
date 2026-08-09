# Growth Analytics — cohortes, rétention et contribution

## Objectif

Le Lot 6 transforme les signaux déjà produits par Events, Tickets, CRM, Partners, Promotions, Loyalty et Payments en métriques de croissance organisationnelles. Il n'ajoute pas de tracking invisible et ne remplace aucune source de vérité métier.

Les écrans principaux sont :

- `/analytics/growth/` pour le portefeuille d'organisations accessible au membre ;
- `/analytics/growth/o/<organization-slug>/` pour le dashboard Growth d'une organisation ;
- `/analytics/growth/o/<organization-slug>/spend/new/` pour enregistrer un coût observable lorsque le rôle financier l'autorise.

L'API correspondante est sous `/api/v1/analytics/growth/`.

## Identité analytique sans exposition de PII

Pour calculer répétition et cohortes, Makolo regroupe une commande confirmée par `buyer_id` lorsqu'un compte existe, sinon par e-mail normalisé. Cette identité n'est jamais renvoyée par le dashboard ou l'API Growth. Les sorties sont des agrégats : nombres de clients, taux, cohortes, revenus groupés par devise et performances de sources.

Aucun nom, e-mail, téléphone, QR ou référence de paiement n'est inclus dans les payloads Growth.

## Repeat buyers

Un repeat buyer est un acheteur identifié possédant au moins deux commandes `confirmed` dans la même organisation. Le taux de repeat buyers est :

`repeat buyers / acheteurs identifiés`.

Une commande annulée ou expirée ne compte pas comme achat confirmé de rétention.

## Cohortes

Le mois de la première commande confirmée définit la cohorte du client. `M0` représente ce mois. `M1`, `M2`, etc. mesurent la part de la cohorte ayant au moins une nouvelle commande confirmée pendant le mois relatif correspondant.

Les cohortes ne prétendent pas mesurer une causalité marketing ; elles décrivent le comportement observé.

## Conversion follower → acheteur

Un follower est considéré converti uniquement s'il possède une commande confirmée **postérieure ou égale à sa date de follow**. Un ancien acheteur qui suit ensuite l'organisateur ne devient donc pas artificiellement une conversion follower.

`OrganizationFollow` reste une relation sociale et ne vaut jamais consentement marketing.

## LTV

La LTV financière est réservée aux rôles Finance/Owner/Admin et au staff. Elle est calculée depuis Payments : paiements réussis moins remboursements réussis, par client identifié et **par devise**.

Makolo ne convertit jamais USD, CDF ou une autre monnaie pour fabriquer une LTV globale multi-devise. Chaque devise possède sa propre ligne `gross`, `refunds`, `net` et `average_net_ltv`.

## Canaux Growth

### CRM

Makolo expose : destinataires envoyés, clics enregistrés par le mécanisme CRM existant, conversions confirmées et revenus explicitement attribués par `CampaignAttribution`.

### Partners

Makolo expose : visites anonymes, conversions confirmées, revenus des commandes attribuées et commissions `earned`/`paid` comme coût intrinsèque observable.

### Promotions

Makolo expose : redemptions confirmées, revenu final après remise et montant de remise comme coût économique observable du canal.

### Loyalty

Makolo expose : comptes fidélité, memberships actifs, récompenses utilisées, dette de points et écart de repeat rate entre clients Loyalty et non-Loyalty. Cet écart est présenté comme **corrélation**, jamais comme preuve causale du programme.

Lorsqu'une récompense Loyalty génère un `PromotionCode` privé et que ce code est réellement utilisé, la commande correspondante peut être comptée comme `reward_driven_order`. Makolo n'attribue pas toutes les commandes d'un membre au programme fidélité.

## GrowthSpend

Les coûts externes non déjà connus de Makolo peuvent être enregistrés dans `GrowthSpend` : création de contenu, achat média, frais d'agence, activation partenaire ou autre coût observable.

Une dépense appartient à une organisation, une devise et un canal. Elle peut être rattachée à une seule source précise : campagne CRM, campagne partenaire, promotion ou programme Loyalty. Elle peut aussi rester au niveau du canal global.

Les validations interdisent une source ou un événement appartenant à une autre organisation.

## ROI de contribution

Makolo n'affiche pas un « ROI magique » basé sur des hypothèses invisibles. Le ratio disponible est un **ROI de contribution sur revenus attribués et coûts observables** :

`(revenu attribué - coûts observables) / coûts observables × 100`.

Les coûts observables peuvent inclure :

- dépenses `GrowthSpend` ;
- commissions partenaires acquises/payées ;
- remises Promotion confirmées.

Un ratio n'est calculé que lorsqu'un coût supérieur à zéro existe **dans la même devise** que la ligne. Makolo ne mélange jamais des revenus USD avec des coûts CDF.

Ce ratio n'est ni une marge comptable complète, ni une preuve d'incrémentalité, ni une estimation de causalité. Il manque notamment les coûts de production, taxes, frais PSP et coûts fixes tant qu'ils ne sont pas explicitement modélisés.

## Autorisations

Les métriques opérationnelles Growth sont accessibles aux rôles Owner/Admin/Event Manager/Finance/Marketing. Scanner Manager n'obtient aucun accès Growth implicite.

Les métriques monétaires — LTV, revenus attribués, coûts, dépenses et ROI — restent limitées à Owner/Admin/Finance et staff. Marketing peut piloter audience, CRM, promotions et fidélité sans obtenir les montants financiers du dashboard Growth. Event Manager peut consulter la rétention opérationnelle sans voir LTV ou ROI.

La création/suppression de `GrowthSpend` suit la même frontière financière.

## Interprétation des insights

Les insights Growth sont déterministes et explicables : répétition faible, follower conversion faible, conversion CRM faible, trafic partenaire peu converti, écart Loyalty, contribution négative lorsque les données financières sont autorisées.

Ils ne prennent aucune décision automatique sur un client, ne changent aucun prix et ne déclenchent aucune campagne. Ils servent de signaux de pilotage à l'équipe autorisée.
