# Makolo — Security Threat Model (Pré-M7)

## Portée

Ce document fixe le socle de sécurité avant M7. Il ne remplace ni M9, ni la production readiness M10, ni un pentest externe, ni les contrôles d’un PSP/provider réel.

Principe de confiance : **client non fiable → sécurité HTTP Django → authentication → Authorization Makolo → services métier → invariants → transactions/contraintes DB → audit/observabilité**. Aucune couche n’est suffisante seule.

## Actifs critiques

- **Money** : Offer, quote, CommerceOrder, PaymentObligation, Payment, Refund et allocations/ledger.
- **Authorization** : Role, Permission, Scope et Mandate.
- **Access** : droits d’accès, credentials et observations d’usage.
- **Capacity** : pools configurables et réservations transactionnelles.
- **Données privées / PII** : Profile privé, Veilles, Passeport, dossiers, commandes et données financières.
- **Secrets providers** : clés, signatures, tokens et credentials externes.
- **Autorité administrative** : staff technique, Mandates plateforme/Space/Activity et superuser.

## Frontières de confiance

1. Navigateur/client ↔ backend Makolo.
2. Backend ↔ PostgreSQL.
3. Staff/admin ↔ services métier.
4. Backend ↔ provider externe.
5. Source webhook ↔ endpoint callback.
6. Futures extensions M7 ↔ contrats Makolo.

Un identifiant, un bouton visible, un `is_staff`, une Membership ou une valeur envoyée par le client ne constituent jamais une autorité métier.

## Menaces et défenses propriétaires

| Menace | Frontière / défense | Propriétaire |
|---|---|---|
| Price / currency tampering | Les montants et devises Payment proviennent des snapshots Commerce/obligations; validations modèle + contraintes | Commerce, Payments |
| Discount tampering | Promotion calculée serveur; snapshots financiers historiques immuables | Promotions, Commerce |
| IDOR commande/paiement | Querysets/permissions contextualisés et contrôle propriétaire/Mandate | Payments, Authorization |
| Privilege escalation | `Profile + Role + Permission + Scope = Mandate`; staff simple n’accorde pas de pouvoir métier | Authorization |
| Forged payment success/refund | Transitions via services, autorité finance, état canonique et transaction | Payments |
| Forged Access status / credential | Transitions exclusivement via services Access; admin transactionnel read-only | Access |
| Forged CapacityReservation | Réservation/commit/release via services Capacity; admin réservation read-only | Capacity |
| Double spend / double confirmation | `transaction.atomic`, `select_for_update`, unicité d’un succès par source | Payments, PostgreSQL |
| Capacity race | Réservation/commit via Capacity et locks/contraintes canoniques | Capacity, PostgreSQL |
| Webhook forgé/rejoué | HMAC sur body brut, comparaison constante, `(provider,event_id)` unique, hash de payload et idempotence | Payments |
| Même event id, payload différent | Hash différent = anomalie/refus | Payments |
| Data leakage cross-Space | Selectors + permissions contextualisés; divulgation minimale | Domaines propriétaires + Authorization |
| Compte staff compromis | Django staff reste une capacité technique; mutations métier exigent Mandate/service | Django Admin, Authorization, domaines |
| Superuser compromis | Compromission administrative critique; le pouvoir technique du superuser n’est pas prétendu supprimable | Django / opérations |
| Secret leakage | Configuration production obligatoire, secrets hors code, redaction des logs sensibles | settings, middleware, logging |
| Provider compromis/malveillant | Callback non autoritatif : signature → anti-replay → validation → résolution canonique → service | Provider adapter + domaine propriétaire |

## Garanties pré-M7 confirmées

- `DEBUG=False`, secret key, hosts et URL HTTPS sont exigés par la configuration production; cookies Secure, HSTS, redirection SSL et CSRF trusted origins sont configurés côté production.
- JWT : access court, refresh borné, rotation, blacklist/révocation configurées; password reset borné.
- Login, inscription et password reset ont des throttles; Payments possède des throttles d’initiation, transition et webhook.
- Payment amount/currency sont dérivés de la source canonique et revalidés par les modèles.
- Un seul Payment réussi est autorisé par Order / CommerceOrder / PaymentObligation; provider reference et clés d’idempotence sont contraintes.
- Refund actuel est intégral : montant/devise proviennent du Payment canonique.
- Webhook sandbox : signature HMAC avec `compare_digest`, event id unique, payload hash anti-confusion, payload persisté limité et aucune mutation métier ORM brute.
- Payment / Refund / PaymentObligation / PaymentEvidence sont read-only dans Django Admin; CommerceOrder et CommerceOrderItem sont explicitement non ajoutables/modifiables/supprimables via admin.
- Access / AccessCredential / AccessUse sont explicitement non ajoutables/modifiables/supprimables via Django Admin : émission, révocation, expiration et usage restent des transitions de services Access.
- CapacityReservation est explicitement non ajoutable/modifiable/supprimable via Django Admin; CapacityPool reste un objet de configuration légitime.
- Les écritures Offer via Django Admin exigent une autorité plateforme explicite en plus des permissions admin Django; le journal `LogEntry` natif de Django fournit la trace minimale de ces changements.
- Waitlist/transferts privés et surfaces Scanner/Access ne confèrent aucun accès global au simple staff; l’accès reste propriétaire ou contextuel.
- Les logs appliquent une redaction best-effort des mots de passe, tokens, secrets, signatures, cookies, bearer tokens et URLs de reset.

## Corrections pré-M7

Le baseline retire les héritages historiques où `is_staff` ou une Membership pouvaient être utilisés comme autorité financière. Les paiements, remboursements, encaissements manuels et transitions d’obligation utilisent désormais les permissions/Mandates canoniques ou une autorité plateforme explicite. L’application d’une Promotion à une commande pending est liée au buyer de la commande. Les lectures privées waitlist/transfert et les vues de gestion Scanner/Access ne disposent plus d’un bypass staff. Les commandes transactionnelles, les droits/credentials/uses Access et les CapacityReservation sont immuables dans Django Admin, et les écritures Offer y sont réservées à l’autorité plateforme explicite.

## Risques acceptés / différés

- **M7** : contrats de signature/authentication/idempotence spécifiques à chaque futur provider/extension, isolation des credentials et lifecycle des connections.
- **M9** : hardening systématique du repository, dependency scanning élargi, fuzzing, observabilité sécurité et revue exhaustive des uploads/endpoints non critiques. Les GitHub Actions actuellement référencées par tags majeurs plutôt que par SHA immuable relèvent aussi de ce hardening supply-chain.
- **M10 / infra production** : WAF/CDN éventuel, politiques réseau, rotation/stockage opérationnel des secrets, sauvegarde/restauration, alerting et incident response.
- **PSP réel** : contrôles propres au protocole, signature, retries, disputes, reconciliation, conformité et responsabilités PCI. Makolo ne stocke pas PAN/CVV dans ce baseline.
- **Pentest externe** : validation indépendante avant exposition production appropriée.

## Menace interne

Un compte utilisateur, organisateur, finance ou staff compromis reste borné par ses Mandates et scopes métier. Finance n’implique ni Marketing ni Access/Scanner. Un admin Space n’est pas un admin plateforme. **Un superuser compromis représente une compromission administrative critique.** Les procédures de détection, réponse et récupération sont différées à M9/M10.
