# Makolo Services — Plan d’implémentation consolidé

> **Référence architecturale :** ce plan dérive de [`makolo-domain-blueprint.md`](makolo-domain-blueprint.md), de [`services-opportunities.md`](services-opportunities.md) et, pour les primitives transversales de conditions/éligibilité, de [`subscriptions-entitlements-requirements.md`](subscriptions-entitlements-requirements.md). Le runtime, les migrations et les tests du `main` courant gagnent sur un ancien statut documentaire.

## 1. Principe de livraison

Makolo Services est une verticale composée sur le cœur canonique Makolo.

> **Event est une verticale. Activity est le noyau.**

`ServiceDetails` spécialise une `Activity`; `Journey` reste le parcours individuel canonique. Services réutilise Profile, Space, Activity/Occurrence, Journey, Role/Permission/Mandate, Requirements, Opportunity, Domain Events, Notifications/Automation et Payments sans recréer ces domaines.

Règles de livraison : branche dédiée, services transactionnels avant UI, permissions serveur avant données, migrations compatibles, tests ciblés puis régressions pertinentes, PostgreSQL pour les invariants de concurrence, beta seed déterministe, E2E utile, aucune CI affaiblie pour obtenir du vert et `main` revérifié après merge.

## 2. État réel du cycle T31–T36

| Tâche | État canonique | Résultat |
| --- | --- | --- |
| T31 — Services Core & Journey Orchestration | ✅ livrée | Journey Services longue durée, Steps, Blockers, Assignments, Artifacts/Reviews/Notes, templates et intake |
| T32 — Opportunities & Requirement Engine | ✅ livrée | Opportunity/revisions/sources, requirements, pinning historique, assessments/evidence |
| T33 — Payments, Submissions & External Outcomes | ✅ livrée | PaymentObligation/Evidence, provider sandbox, external evidence, submissions/outcomes |
| T34A — Horizontal Requirements Foundation | ✅ livrée | kernel horizontal `requirements`, états/évaluateurs explicites, frontières de dépendance |
| T34B — Services Authorization, Privacy, Events & Automation | ✅ livrée | `activity.services.*`, rôles, anti-IDOR, artifacts restricted, Domain Events, notifications/automation |
| T35 — Complete Services UX | ✅ livrée | participant/public, facilitator, reviewer, manager et Opportunity Curator ; PR #95 + #99, intégration corrigée par #100 |
| T36 — Analytics, Hardening & V1 Release Gate | candidat dans PR #103 | ne devient ✅ qu’après merge et gates post-merge de `main` verts |

Le cycle Services n’est pas prolongé automatiquement par une T37. Après T36, les évolutions viennent des retours bêta, bugs, nouvelles décisions produit, Subscription ou nouveaux providers.

## 3. T31 — Services Core & Journey Orchestration

T31 a livré le moteur opérationnel Services sans Opportunity : `WorkflowKind.SERVICE`, transitions Journey, Steps et dépendances, Blockers, Assignments, Artifacts privés/versionnés, Reviews, Notes avec séparation bénéficiaire/interne, `ServiceDetails`, templates versionnés, Intake et `ServiceJourneyContext`.

Le noyau `journeys` ne dépend pas de `services`. Une affectation n’accorde jamais une autorité : **Mandate = autorité ; JourneyAssignment = responsabilité opérationnelle.**

## 4. T32 — Opportunities & Requirement Engine

T32 a livré Opportunity et OpportunityRevision, la provenance/source verification, les requirements et assessments, les saves/soumissions utilisateur, déduplication/merge, et le pinning Journey ↔ OpportunityRevision.

Une Opportunity externe n’est pas transformée en Activity. Une Journey pinnée sur une revision N reste sur N jusqu’à adoption explicite, même après publication d’une revision N+1.

## 5. T33 — Payments, Submissions & External Outcomes

T33 a livré `PaymentObligation`, `PaymentEvidence`, le bridge vers `Payment`, `ServiceSubmission` multi-attempt et `ServiceOutcomeEvent` append-only.

Invariants :

- `makolo_provider` utilise le pipeline Payment réel (sandbox/manual existants) ;
- `external` est prouvé par PaymentEvidence et ne fabrique pas un faux Payment ;
- les bridges legacy `TicketOrder`, `CommerceOrder`, `Payment.order` et `Payment.commerce_order` restent compatibles ;
- `Journey.fulfilled` et `ServiceJourneyContext.current_outcome` sont deux axes distincts ;
- `Journey.fulfilled + current_outcome=unsuccessful` est un état valide.

Aucun M-PESA réel, nouveau provider ou billing Subscription n’est introduit par Services V1.

## 6. T34A — Horizontal Requirements Foundation

T34A a extrait le kernel horizontal `requirements` sans créer un modèle DB universel ni GenericForeignKey métier. Les états canoniques restent `unassessed`, `pending`, `satisfied`, `unsatisfied`, `not_applicable` ; les conséquences UI comme action requise, revue ou paiement requis sont dérivées des propriétaires canoniques.

`OpportunityRequirement` reste dans `opportunities`; `ServiceRequirementAssessment` et ses bridges restent dans `services`. Subscription peut consommer le kernel sans importer Services.

## 7. T34B — Authorization, Privacy, Events & Automation

T34B est livrée. Elle définit les permissions finales `activity.services.*`, les rôles Service Manager/Facilitator/Reviewer, les permissions Opportunity, les selectors anti-IDOR et la frontière serveur des artifacts restricted.

Principes :

- participant : seulement ses Journeys et données autorisées ;
- Facilitator : permission Activity + assignment actif, sauf `view_all` explicite ;
- Reviewer : assignment/review approprié + permission ;
- Manager : `view_all` n’accorde ni restricted artifact ni finance automatiquement ;
- Opportunity Curator : permissions `opportunities.*` sans droit sur les dossiers Services individuels ;
- deep-link Notification n’accorde jamais une permission ;
- Autopilot reste le scheduler canonique des rappels/automations.

## 8. T35 — Complete Services UX

T35 est livrée par la PR #95, complétée par la PR #99, puis stabilisée sur `main` par la PR #100. Les anciennes mentions « T35 en cours » sont obsolètes.

Surfaces livrées :

- découverte Services/Opportunities et parcours participant ;
- intake et workspace de démarche ;
- Steps, Requirements, Blockers, Artifacts, Reviews, paiements/preuves, submissions/outcomes ;
- dashboard Facilitator ;
- file Reviewer ;
- console Service Manager ;
- console Opportunity Curator.

La console Services reste opérationnelle (« travail du jour »). Elle n’est pas dupliquée par Analytics.

## 9. T36 — Analytics, Hardening & V1 Release Gate

### État de candidat

PR canonique : **#103 — `Task 36: harden and release Makolo Services V1`**.

Le statut T36 ne doit être considéré ✅ que si la PR est mergée et que `main` post-merge est vert (CI complète, Beta seed et Subscriptions applicables). Avant cela, elle reste un candidat de release.

### Analytics Services livrées dans le candidat

Le read model est ajouté dans `analytics_app`, sans `services_analytics`, snapshot ou modèle analytique parallèle. Il calcule depuis les modèles canoniques :

- volume Journey Services ;
- start rate avec numérateur/dénominateur explicites ;
- Makolo fulfillment rate séparé du succès externe ;
- temps jusqu’au fulfillment et durée des Steps mesurables ;
- blockers par statut/catégorie/sévérité ;
- deadlines actuelles et historique de completion tardive ;
- funnel observable Opportunity → Journey et Journey → Submission ;
- submissions et outcomes courants/historiques ;
- workload via JourneyAssignment ;
- reviews ;
- PaymentObligation, Payment provider et PaymentEvidence externe ;
- montants uniquement avec permission financière et toujours séparés par devise.

`AnalyticsFact` n’est pas étendu automatiquement : aucune projection événementielle Services supplémentaire n’est nécessaire pour les métriques V1 déjà fiables depuis les modèles canoniques et `ServiceOutcomeEvent`.

### Hardening du candidat

- Activity Services identifiée exclusivement via `ServiceDetails` ;
- autorité Analytics réutilisée, y compris ownership personnel par `owner_profile` et compatibilité legacy limitée ;
- anti-IDOR de l’API Analytics Services ;
- frontière financière indépendante de la simple gestion d’un dossier ;
- read model DB-first et test de croissance des requêtes ;
- pas d’index, cache ou lock spéculatif ;
- audit ciblé des surfaces T35 : pagination/SQL-first, selectors de dossiers, artifacts restricted, notes internes, téléchargements privés et PaymentEvidence restent derrière les frontières serveur existantes ;
- aucune migration T36 ajoutée.

### E2E du candidat

Le job E2E canonique reçoit une fixture Services compacte et des parcours consolidés :

- participant sur workspace Services ;
- manager + facilitator sur le dossier dans leur scope ;
- reviewer sur une review restricted assignée ;
- same-Space sans autorité → refus ;
- staff sur Analytics Services ;
- smoke mobile 390 px sans overflow horizontal critique.

Le beta seed existant reste la gate de données complète : il couvre déjà sandbox, PaymentEvidence externe, pinning Opportunity revision, rôles opérateurs, restricted artifact, note interne et `Journey.fulfilled + external unsuccessful`. T36 ne crée pas une seconde population de comptes bêta.

## 10. Parallélisation avec Subscription

Subscription est un chantier distinct. Le runtime courant S1–S4 (et toute évolution mergée pendant T36) doit rester vert, mais T36 n’implémente pas S5/S6, pricing, billing, entitlement paywall Services, UX Subscription, notifications ou automation Subscription.

T36 et Subscription partent de `main` et ne dépendent jamais de leurs branches respectives. Si `main` avance avant le candidat final, T36 doit intégrer le nouveau `main`, relire les contrats concernés et rejouer les gates affectés.

## 11. Scénarios de release Services V1

La release doit rester démontrable par les scénarios canoniques suivants :

1. Service sans Opportunity : CV/intake → Journey → Steps → Artifact → Review → fulfillment.
2. Opportunity emploi : Opportunity → Journey pinnée → Requirements → documents → Submission → outcome.
3. Bourse : même pipeline avec requirement documentaire et deadline, sans code spécifique scholarship.
4. Opportunity proposée par un utilisateur : submission → curation → promotion/publication.
5. Opportunity change : revision N pinnée → N+1 publiée → adoption explicite seulement.
6. Paiement provider : PaymentObligation → sandbox Payment succeeded → satisfied.
7. Paiement externe : PaymentObligation external → Artifact/Evidence → verified → satisfied, sans faux Payment.
8. Outcome négatif : Journey fulfilled + external unsuccessful représentés séparément.
9. Permissions : beneficiary, assigned facilitator, unassigned facilitator, reviewer, manager, same-Space no authority, curator et staff.
10. Restricted artifact : backend autorisé selon rôle/permission, jamais masqué uniquement en CSS.

## 12. Gates V1

Le candidat Ready doit passer :

```text
sync main
→ python manage.py check
→ makemigrations --check --dry-run
→ tests ciblés Analytics / security / performance
→ Django complet
→ PostgreSQL Core
→ PostgreSQL Ops
→ E2E
→ Beta seed SQLite/PostgreSQL/idempotence
→ Subscriptions si applicable
→ frontend/static/CSP/security checks
```

Puis, avant merge, `origin/main` est revérifié une dernière fois. Un gate pending, queued, in_progress, failure ou cancelled n’est pas considéré vert.

Après squash merge, T36 n’est close que lorsque le nouveau `main` obtient son cycle complet vert et `ci/aggregate=success`.

## 13. Déploiement et opérations

PythonAnywhere reste uniquement l’environnement temporaire de test/bêta. Il n’est pas l’hébergement de production final.

Le runbook existant reste canonique pour déploiement, backup, health/readiness, Autopilot et private artifacts. T36 n’introduit aucun scheduler ni procédure de déploiement parallèle et ne lance pas npm/Playwright/beta seed sur le serveur PythonAnywhere.

## 14. Différés explicites après Services V1

Ne font pas partie de la V1 Services :

- IA / matching IA / CV AI / ranking automatique ;
- M-PESA réel ou nouveaux providers réels non décidés ;
- hébergement de production final ;
- Subscription pricing/billing ;
- feature entitlement paywall Services spéculatif ;
- analytics prédictives avancées ;
- snapshots/cache Analytics sans preuve de besoin.

Ces éléments ne bloquent pas le release gate T36.
