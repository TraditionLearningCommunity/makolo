# Finance F2 — Payment Obligations & Subscription Billing Foundation

## Frontière canonique

F2 conserve trois responsabilités séparées :

- `commerce` explique la vente et son résultat économique ;
- `subscriptions` explique le produit Makolo souscrit et ses termes commerciaux versionnés ;
- `payments` possède l'obligation financière et le paiement.

`PaymentObligation` répond à : qui doit payer, qui doit recevoir, pourquoi, combien, dans quelle devise, selon quelle provenance et à quelle échéance. F2 n'introduit ni allocation financière, ni ledger, settlement, payout ou provider production.

## PaymentObligation sans Journey universelle

`PaymentObligation.journey` est désormais optionnelle. Une Journey reste un contexte canonique lorsqu'elle existe réellement, notamment pour Commerce et les processus Services.

Les invariants Journey ne sont pas affaiblis :

- une obligation avec `commerce_order` conserve la Journey de cette commande ;
- une obligation avec `step` conserve la Journey de cette étape ;
- `PaymentEvidence` reste volontairement Journey/Artifact-oriented et refuse explicitement une obligation sans Journey.

Aucune Activity ou Journey artificielle n'est créée pour Subscription.

## Parties financières

`created_by`, `initiated_by` et le payer sont distincts.

Une obligation peut exprimer un débiteur canonique via exactement au plus un `payer_profile` ou `payer_space`; une nouvelle obligation Subscription exige exactement l'un des deux.

Le bénéficiaire économique reste exactement un parmi :

- Space ;
- Profile ;
- plateforme Makolo (`payee_platform`) ;
- bénéficiaire externe nommé.

Makolo n'est donc pas représenté par un faux Profile, un faux Space ou `external_payee_name="Makolo"`.

## Commerce F1 préservé

Une obligation Commerce continue d'utiliser :

`PaymentObligation.amount = CommerceOrder.total`

`CommerceOrder.total` est le **payer total** de F1. `expected_payee_amount` et le snapshot financier Commerce restent inchangés et ne sont pas projetés comme montant de l'obligation. La répartition économique appartient à F3.

## Provenance et idempotence

`source_key` reste unique. Son rejeu renvoie la même obligation uniquement si le contrat financier et la provenance sont cohérents. Une réutilisation avec Journey, source métier, parties, montant, devise, motif ou mode incompatibles est rejetée.

Les nouvelles sources utilisent des namespaces explicites, notamment `commerce:` et `subscription:`.

## Billing Terms Subscription

`PlanVersionBillingTerms` appartient à `subscriptions` et est attaché à une `PlanVersion` exacte. Il porte le minimum commercial :

- montant et devise ;
- unité et nombre de périodes de billing ;
- délai minimal d'échéance ;
- période de grâce minimale.

Un montant nul représente un plan gratuit et ne crée aucune `PaymentObligation` positive artificielle.

Après publication/retrait de la PlanVersion, ses Billing Terms sont historiques et ne peuvent pas être modifiés ou supprimés silencieusement. Un changement commercial doit passer par de nouveaux termes/version.

## Subscription vers Payments

`SubscriptionBillingObligation` est le bridge explicite détenu par `subscriptions` entre Subscription/Transition, Billing Terms pinnés et `payments.PaymentObligation`.

Pour une Subscription payante :

- `reason = subscription` ;
- payer = Profile ou Space sujet de la Subscription ;
- payee = plateforme Makolo ;
- `journey = null` ;
- `commerce_order = null` ;
- `step = null` ;
- amount/currency viennent des Billing Terms pinnés.

Le bridge S4 `SubscriptionTransitionPaymentObligation` reste distinct et continue de représenter un `PlanRequirement` explicitement de type payment. Le prix normal d'un abonnement n'est pas transformé en faux Requirement.

Une Transition avec billing commercial obligatoire reste en cours tant que son obligation est ouverte ; `satisfied` ou `waived` peut débloquer la readiness. Aucun `SubscriptionPayment` ou `Subscription.is_paid` n'est ajouté : `PaymentObligation + Payment` restent la vérité financière.

## Domain Events et lifecycle

Les événements PaymentObligation peuvent être émis sans Journey. Le contexte Activity/Journey est nul lorsque non pertinent ; un Space peut rester disponible pour une Subscription Space. Le payload conserve au minimum l'identifiant, le motif, le statut et la provenance.

Le lifecycle `pending -> processing -> satisfied` fonctionne sans Journey, ainsi que les transitions terminales existantes selon leurs contrats.

## Différé F3/F4

F3 définira l'allocation économique et le ledger : quelle part du montant encaissé appartient à l'organisateur, Makolo, taxes ou PSP.

F4 définira les flux physiques de fonds, settlement, payout, split/direct-to-payee, remboursements avancés et hardening provider.
