# Finance F1 — Pricing, Quote et Financial Snapshot

## Responsabilité

F1 reste dans `commerce` : Commerce explique ce qui est vendu et calcule le résultat économique attendu avant toute tentative de paiement. `payments` continue à représenter l'obligation et les transactions provider ; F1 n'ajoute ni provider réel, ni ledger, allocation, settlement ou payout.

Le propriétaire unique du calcul est `commerce.services.quote_financials()`, qui délègue au moteur pur `commerce.pricing.calculate_quote()`. Les views, serializers, templates et `model.save()` ne recalculent pas les frais.

## Politiques tarifaires

Deux politiques sont canoniques :

- `seller_net_guaranteed` : `subtotal - discount` est le net économique garanti au bénéficiaire. Les charges d'incidence `payer` s'ajoutent au-dessus. Une charge `payee` est rejetée car elle contredirait cette garantie.
- `customer_total_fixed` : `subtotal - discount` est l'enveloppe finale payée par le client. Les charges d'incidence `payee` sont déduites à l'intérieur de cette enveloppe. Une charge `payer` additionnelle est rejetée car elle contredirait le total client fixé.

L'incidence (`payer`, `payee`, `platform`) est indépendante de la formule de calcul. Une `ChargeRule` peut combiner montant fixe et pourcentage. F1 expose les scopes `order`, `line` et `unit`, mais calcule uniquement `order`; les autres scopes sont réservés à une extension explicite plutôt que simulés.

## Composantes financières

Les lignes de Quote distinguent : `base_price`, `discount`, `makolo_fee`, `processing_fee`, `tax` et `other_fee`. Une taxe est une composante générique : son libellé, sa base de calcul, son taux/montant, son montant calculé, son incidence et le caractère `included` sont conservés. Aucun taux fiscal réel ni vocabulaire TVA obligatoire n'est codé dans le domaine.

Tous les calculs utilisent `Decimal`, un quantum monétaire de `0.01` et `ROUND_HALF_UP`. Les `float` sont rejetés.

## Quote vs Snapshot

`FinancialQuote` est une représentation avant confirmation. Il expose notamment : devise, sous-total, remises, lignes de charges/taxes, total payeur, montant bénéficiaire attendu et montant Makolo lorsque calculable.

Lors de `create_order`, le Quote est figé dans `CommerceOrder.financial_snapshot` avec :

- politique appliquée ;
- sous-total et remise ;
- base nette ;
- règles/taux/montants de chaque composante ;
- total payeur ;
- net bénéficiaire attendu ;
- montant Makolo ;
- convention d'arrondi.

`CommerceOrder.total` reste le montant de référence transmis à Payments et représente désormais le **payer total**. Les champs legacy `subtotal`, `discount_total`, `total` sont conservés ; sans charge, leur comportement reste identique. Les snapshots historiques sont immuables via le service/model contract et les commandes existantes sont backfillées comme quotes legacy sans charge.

## Compatibilité future

Le moteur reçoit déjà une politique et une liste de règles sans imposer leur provenance. Une future résolution `Makolo defaults -> Space -> Activity -> Offer` peut donc fournir ces termes sans déplacer le calcul dans Activity ou Events.

## Hors F1

F1 ne définit pas M-Pesa/carte/PSP réel, billing Subscription, allocation définitive des fonds, ledger, balance, settlement, payout, split provider, direct-to-payee, fiscalité pays réelle, KYC/KYB, facturation légale, disputes ou chargebacks complets.
