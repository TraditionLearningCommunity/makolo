# Finance F3 — Financial Allocation & Ledger

## Frontière F1 → F4

- **F1 / Commerce** calcule le prix, le `FinancialQuote` et fige le `financial_snapshot` historique.
- **F2 / Payments + Subscriptions** matérialise l’obligation financière : qui paie, qui reçoit, combien et pourquoi.
- **F3 / Payments** explique l’appartenance économique du montant via une allocation puis enregistre les conséquences réalisées dans un ledger append-only.
- **F4** déplacera réellement les fonds : custody provider, Settlement, Payout, direct-to-payee et provider split.

F3 ne crée aucun wallet, Payout, Settlement ni compte provider.

## Allocation économique

`FinancialAllocation` est unique par `PaymentObligation`. Ses `FinancialAllocationLine` portent les rôles minimaux `PAYEE`, `PLATFORM`, `TAX`, `PROCESSING` et `OTHER`. Une allocation complète est valide uniquement si la somme de ses lignes est exactement égale au montant de l’obligation dans la même devise.

Pour Commerce, l’allocation est construite uniquement depuis `CommerceOrder.financial_snapshot`. `expected_payee_amount` devient la ligne PAYEE ; les composantes F1 financées dans l’enveloppe (`incidence=payer|payee`) deviennent des lignes PLATFORM/TAX/PROCESSING/OTHER. Une composante `incidence=platform`, qui n’entre pas dans le `payer_total` F1, n’est pas inventée comme destination de ce total. Les commandes legacy sans composante gardent donc naturellement `PAYEE = payer_total` sans commission rétroactive.

Pour Subscription, l’obligation F2 a Makolo comme payee canonique et produit une unique ligne PLATFORM. Aucune Journey, CommerceOrder ou ligne PAYEE organisateur n’est fabriquée.

## Ledger opérationnel et reconnaissance

Le `LedgerEntry` est un ledger économique/opérationnel, pas un grand livre légal IFRS/OHADA/GAAP. Les entrées sont append-only : une correction crée une `REVERSAL` ou un `ADJUSTMENT`; elle ne réécrit pas un fait historique.

Une allocation peut exister avant encaissement. Les écritures réalisées ne sont créées que pour :

- un `Payment.status=succeeded` ;
- une `PaymentEvidence.status=verified` ;
- un `Refund.status=succeeded` ;
- un ajustement explicite autorisé côté serveur.

Chaque source utilise une `source_key` unique. Les retries de Payment, PaymentEvidence et Refund retrouvent donc la même série logique sans double revenu ni double payable. Les hooks appellent les services F3 dans la transaction Django existante : si la reconnaissance échoue, la transition financière appelante est annulée avec elle.

`PAYMENT_RECOGNIZED` mesure le volume/GMV. Les écritures de lignes expriment les positions : payable bénéficiaire, montant Makolo, taxe séparée, composante processing et autre position. La composante F1 `processing_fee` reste une composante facturée : F3 ne la transforme pas en coût PSP réel certain. Aucun provider réel n’existe encore pour fournir ce coût.

## GMV, revenu, payable et custody

Les projections sont dérivées du ledger, sans `space.balance += ...` :

- `gmv` = transactions reconnues ;
- `platform_amount` = position économique Makolo, ajustements/reversals inclus ;
- `payee_payable` = position restant économiquement payable par Makolo lorsque la garde n’est pas explicitement externe ;
- `tax_liability` = position taxe séparée ;
- `refund_total` = remboursements reconnus.

Ainsi GMV n’est jamais assimilé au revenu Makolo, et un montant PAYEE n’est jamais assimilé à un payout déjà exécuté.

La garde physique des fonds reste volontairement indéterminée (`unknown`) pour les Payments F3. Une `PaymentEvidence` externe est marquée `external`: la vente peut être reconnue économiquement, mais F3 ne prétend pas que Makolo détient les fonds ni n’augmente automatiquement un payable Makolo au bénéficiaire.

## Refunds et corrections

Un full refund crée un marqueur REFUND et des contre-écritures par composante sans effacer l’allocation d’origine. Un partial refund exige une décomposition explicite `financial_breakdown` par ligne d’allocation : F3 ne choisit pas arbitrairement une politique proportionnelle ni une règle PSP. Le processing F1 remboursé reste une composante client ; aucun coût provider non remboursable n’est inventé.

Un ajustement manuel est un nouveau `LedgerEntry` et exige un acteur staff, une raison et une clé d’idempotence. Aucun endpoint libre de mutation du ledger n’est ajouté.

## Historique et backfill

F3 n’effectue pas de backfill massif. Les allocations sont matérialisées de façon déterministe/lazy depuis les snapshots F1 ou les obligations F2 au moment où elles sont nécessaires. Cette décision évite de recalculer les anciennes transactions avec des règles tarifaires actuelles et conserve les données existantes sans migration destructive.

## Limites F3

F3 ne traite pas : providers production, comptes connectés, KYC/KYB, custody définitive, Settlement, Payout, payout schedule/batch, bank/mobile-money transfer, FX, fiscalité pays réelle, invoice légale, politique provider complète, dispute/chargeback workflow ni recouvrement d’un payable négatif. Le ledger peut porter des ajustements négatifs ; F4 décidera ensuite comment ces positions deviennent des flux physiques.
