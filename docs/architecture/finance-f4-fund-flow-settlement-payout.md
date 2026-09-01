# Finance F4 — Fund Flow, Settlement et Payout

F1 répond à **combien payer**. F2 répond à **quelle obligation doit être réglée**. F3 répond à **à qui l'argent appartient économiquement** via `FinancialAllocation` et le ledger append-only. F4 répond à **comment les fonds circulent réellement, ce qui est réglable et ce qui a effectivement été transféré**.

## Invariants

- `Payment succeeded` n'implique jamais `Payout succeeded`.
- `PAYEE_PAYABLE` est une dette économique ; `Settlement` est une décision de règlement ; `Payout` est une tentative de transfert réel.
- Un Settlement et ses Payouts restent mono-devise et mono-bénéficiaire.
- Une même position ledger ne peut être réservée par deux Settlements.
- Un Payout réussi est reconnu une seule fois et ses termes financiers ne sont pas réécrits.
- Un refund après payout ajoute une nouvelle position économique négative ; il ne modifie jamais l'ancien payout.
- Une position négative n'engendre jamais de payout négatif : elle est reportée et compense les prochains payables positifs.
- Les allocations et écritures F1-F3 restent immuables.

## FundFlowStrategy

`FundFlowStrategy` est indépendant de `PaymentMode`, du moyen de paiement, de la politique de pricing et de l'incidence des charges.

- `PLATFORM_COLLECT` : Makolo détient conceptuellement les fonds avant Settlement/Payout.
- `PROVIDER_SPLIT` : un provider pourra verser directement les parts payee et Makolo. Aucun faux Payout Makolo→payee n'est créé.
- `DIRECT_TO_PAYEE` : le payee reçoit via sa destination/son compte marchand ; Makolo custody est faux. Une part PLATFORM économiquement due peut être exposée comme `platform_receivable_amount` sans inventer son recouvrement.
- `EXTERNAL` : paiement hors rails Makolo ; aucune custody ni Payout plateforme n'est déduit de la seule satisfaction de l'obligation.

La résolution suit `Offer → Activity → Space → Makolo default`. Un override est distinct d'une absence de configuration et conserve `configured_by`, `configured_at`, le niveau source et l'objet source. Aucun nom de plan Subscription n'est hardcodé dans Payments.

Les anciennes transactions ne sont pas backfillées en Payout ou en custody : l'absence de données historiques ne permet pas d'inventer où l'argent a circulé.

## FinancialDestination

Une `FinancialDestination` appartient à exactement un `payee_profile` ou un `payee_space`. Les services vérifient l'ownership côté serveur avant création d'un payout.

Le modèle ne stocke que des références provider/non sensibles, libellés masqués, derniers chiffres optionnels, type, statut et métadonnées minimales. Les métadonnées rejettent explicitement des clés de type secret/password/PIN/private key/API key. Une destination sauvegardée n'est pas considérée comme KYC/PSP vérifiée.

Lifecycle minimal : `pending → active → disabled`.

## Settlement

Un `Settlement` agrège des écritures `PAYEE` F3 disponibles et non encore réservées pour un même bénéficiaire/devise. Le montant n'est jamais recalculé depuis les Payments : il est la somme explicite de `SettlementItem`, eux-mêmes liés aux `LedgerEntry` et `FinancialAllocationLine` sources.

Le service `build_settlement()` verrouille les positions éligibles, ne prend que les obligations `PLATFORM_COLLECT` avec custody Makolo, applique le netting des positions positives et négatives, puis crée le Settlement et ses items dans une transaction atomique.

Si le net est nul ou négatif, aucun Payout négatif n'est créé : la position reste recoverable et compensera des payables futurs.

Lifecycle : `draft`, `ready`, `processing`, `settled`, `cancelled`, `failed`.

## Payout

Un `Payout` représente une tentative de transfert d'un Settlement vers une FinancialDestination. Un Settlement peut avoir plusieurs tentatives ; un retry après échec crée une nouvelle tentative et conserve l'historique.

Providers F4 : `SANDBOX` et `MANUAL` uniquement. Aucun appel externe n'est implémenté.

Lifecycle : `pending → processing → succeeded|failed|cancelled`, avec `reversed` pour une reversal provider explicite après succès.

`mark_payout_succeeded()` verrouille Payout + Settlement, empêche un second succès pour le même Settlement et enregistre un `FundMovement(PAYOUT)` append-only. Un callback rejoué avec la même source key est idempotent ; un callback supplémentaire après succès ne crée pas de second mouvement de fonds.

`mark_payout_failed()` conserve la tentative et ne règle pas définitivement le Settlement. `retry_payout()` recrée une tentative sur le même Settlement. `reverse_payout()` conserve le succès historique et ajoute un mouvement compensatoire `PAYOUT_REVERSAL`.

## Refunds avant et après payout

Les remboursements client restent le domaine du `Refund` F3. F4 ne crée pas de `PayoutRefund`.

Avant payout, la contre-écriture PAYEE F3 réduit le net du prochain Settlement. Après payout, le payout historique reste intact et la contre-écriture devient une position négative/recoverable. Exemple : payout +10 puis refund PAYEE -4 ⇒ paid out historique 10, recoverable futur 4.

F4 ne suppose pas qu'une commission Makolo ou un frais provider est automatiquement remboursé : la décomposition F3 reste la vérité économique.

## Direct-to-payee, provider split et external

Ces stratégies ne produisent pas de faux Settlement/Payout Makolo. `FundFlowRecord.platform_custody` reste faux. Des `FundMovement` provider-agnostic peuvent enregistrer plus tard des faits directs/split/externes lorsque la source est fiable.

Pour un flux direct/externe comportant une allocation PLATFORM, `platform_receivable_amount` permet de représenter la créance Makolo sans créer de payout inverse ni prélèvement automatique.

## Permissions et audit

Les services réutilisent l'autorité canonique `Role / Permission / Mandate` : `FINANCE_MANAGE`, `ACTIVITY_FINANCE_MANAGE` et l'autorité plateforme. Les propriétaires Profile ne peuvent gérer que leurs propres destinations/positions, sauf autorité plateforme.

Les opérations sensibles conservent actor/timestamps/références source : configuration fund flow, destination, Settlement, Payout, retry/failure/success/reversal. Les écritures F3 et mouvements de fonds F4 sont append-only.

## Analytics / opérations

`payee_finance_projection()` distingue au minimum : payable économique, montant réservé/settled, paid out, recoverable négatif, settleable non réservé, payouts pending et failed. Les opérateurs peuvent remonter de chaque Settlement aux écritures et allocations sources et de chaque payout à sa destination/tentative/provider reference.

## Hors périmètre

F4 ne définit ni KYC/KYB réel, ni politique juridique/fiscale pays, ni délai légal, ni minimum payout commercial, ni scheduler financier complet, ni wallet, ni FX, ni chargeback/dispute provider complet, ni API M-Pesa/carte/banque/Stripe/PayPal.

## Ready for provider integration

Le noyau F1-F4 supporte désormais conceptuellement : card, mobile money, bank transfer, provider split, platform collection, direct merchant payment, external payment et payout provider. Un futur adapter peut créer/confirmer des paiements et payouts, rejouer des événements idempotents, reporter références/frais/dates provider et enregistrer les mouvements réels sans modifier les principes métier F1-F4.

Aucun provider production n'est activé sans intégration dédiée.
