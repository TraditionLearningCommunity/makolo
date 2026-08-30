# Makolo Services — Plan d’implémentation consolidé

> **Référence architecturale :** ce plan dérive de [`makolo-domain-blueprint.md`](makolo-domain-blueprint.md), de [`services-opportunities.md`](services-opportunities.md) et, pour les primitives transversales de conditions/éligibilité, de [`subscriptions-entitlements-requirements.md`](subscriptions-entitlements-requirements.md). Le document `services-opportunities.md` reste la spécification canonique détaillée des décisions Services/Opportunity. Ce document décrit uniquement le découpage d’exécution et les gates de livraison.

## 1. Principe de livraison

Makolo Services est une verticale composée sur le cœur canonique Makolo.

Le principe reste :

> **Event est une verticale. Activity est le noyau.**

Services suit la même règle : `ServiceDetails` spécialise une `Activity`, tandis que `Journey` reste le parcours individuel canonique. La verticale réutilise Profile, Space, Activity/Occurrence, Journey, Role/Permission/Mandate, Geography, Requirements, Domain Events, Notifications/Automation, Commerce et Payments lorsque leur responsabilité s’applique ; elle ne recrée pas ces domaines.

Règles de livraison :

- branche dédiée par tâche ;
- changements petits, traçables et réversibles autant que possible ;
- services métier transactionnels avant UI ;
- permissions serveur avant exposition de données ;
- migrations non destructrices sauf décision explicite justifiée par l’absence de données réelles à préserver ;
- Domain Events émis depuis les services propriétaires ;
- tests ciblés puis régressions pertinentes ;
- `python manage.py check` vert ;
- `python manage.py makemigrations --check --dry-run` vert ;
- migrations SQLite et PostgreSQL vertes ;
- build frontend/E2E lorsque la CI l’exige ;
- beta seed déterministe et vert ;
- aucun merge avec CI rouge ;
- `main` revérifié après chaque merge.

## 2. Découpage d’exécution T31–T36

Les anciens lots détaillés T31–T44 ont été consolidés afin d’éviter de traiter Makolo Services comme une succession de mini-apps. Ils restent utiles comme historique de conception, mais la séquence d’exécution officielle est désormais **T31–T36**, avec T34 séparée en T34A/T34B depuis la décision horizontale Requirements/Subscriptions.

### T31 — Services Core & Journey Orchestration

**Statut : livrée et mergée.**

**But :** construire le moteur opérationnel complet d’un dossier Services longue durée, sans Opportunity.

Périmètre :

- Journey longue durée : `WorkflowKind.SERVICE`, `JourneyStatus.IN_PROGRESS`, `started_at` et transitions contrôlées ;
- JourneyStep et transitions transactionnelles ;
- JourneyStepDependency et prévention des cycles ;
- JourneyBlocker ;
- JourneyAssignment et JourneyStepAssignment, sans création d’autorité ;
- JourneyArtifact privé, versionné et servi uniquement derrière une frontière serveur autorisée ;
- JourneyArtifactReview ;
- JourneyNote avec séparation stricte `beneficiary_visible` / `internal` ;
- Domain Events T31 via l’outbox existante ;
- `ServiceDetails` OneToOne Activity ;
- templates de plan versionnés et immuables après publication ;
- Intake typé et validé ;
- `ServiceJourneyContext` sans Opportunity ;
- matérialisation transactionnelle/idempotente du template vers JourneyStep ;
- completion policy Services ;
- scénario de référence « refaire mon CV » sans Opportunity, PaymentObligation ni soumission externe ;
- sécurité transitoire deny-by-default avec autorité Activity existante + Assignment lorsqu’une action porte sur un dossier individualisé.

**Direction de dépendance :**

```text
services → activities
services → journeys
```

Le noyau `journeys` ne dépend pas de la verticale `services`.

**Note d’implémentation T31 :** la PR T31 matérialise ces responsabilités avec deux migrations additives (`journeys` puis `services`), conserve les workflows Journey historiques, utilise le stockage Django configuré sans imposer de provider futur, et n’introduit aucun modèle Opportunity/PaymentObligation/ServiceSubmission placeholder. Les projections personnelles existantes continuent d’être la source d’attention/historique des Journeys ; aucun second inbox n’est créé.

### T32 — Opportunities & Requirement Engine

**Statut : livrée et mergée ; ses primitives génériques de state/evaluation sont désormais extraites par T34A.**

**But :** introduire le domaine canonique Opportunity et composer les requirements avec les dossiers Services.

Périmètre livré :

- Opportunity et OpportunityRevision ;
- provenance : OpportunitySource / SourceCheck ;
- requirements ;
- zones géographiques ;
- saves ;
- soumissions utilisateur d’Opportunities et déduplication/merge ;
- liaison Journey ↔ Opportunity avec revision pinnée ;
- assessments ;
- evidence ;
- adoption explicite d’une nouvelle revision sans mutation silencieuse des dossiers historiques.

T32 ne remplace jamais Activity par Opportunity : une Opportunity externe reste une opportunité, pas une activité opérée par Makolo.

**Décision post-T32 :** la sémantique `Requirement → Assessment → Evidence/Action` est validée, mais la mécanique commune ne doit pas rester enfermée dans la verticale Services si Subscriptions et d’autres domaines doivent l’utiliser. T34A extrait donc un kernel horizontal `requirements` sans déplacer les agrégats métiers : `OpportunityRequirement` reste dans `opportunities`, `ServiceRequirementAssessment` reste dans `services`, et leurs FKs explicites sont conservées. Aucun GenericForeignKey métier n’est introduit.

### T33 — Payments, Submissions & External Outcomes

**Statut : livrée et mergée dans `main` par la PR #84.**

**But :** couvrir les obligations financières et fermer le parcours jusqu’aux systèmes/tiers externes.

Périmètre livré :

- PaymentObligation ;
- PaymentEvidence ;
- généralisation progressive de Payments sans casser Commerce/TicketOrder ;
- sandbox Services ;
- paiements externes prouvés sans faux Payment ;
- ServiceSubmission multi-attempt ;
- receipt artifacts ;
- ServiceOutcomeEvent append-only ;
- distinction stricte entre fulfillment Makolo et résultat externe.

**Note d’implémentation T33 :** le runtime livré reste additif et expand-compatible. `payments` possède `PaymentObligation` et `PaymentEvidence`; `Payment` conserve ses relations legacy `order` et `commerce_order` tout en acceptant une `obligation`. Une obligation peut avoir plusieurs tentatives de Payment, avec une contrainte DB garantissant au plus un `succeeded` par obligation. Les nouveaux paiements Commerce créent/réutilisent une obligation canonique ; le backfill ne crée une obligation que lorsque Journey, montant, devise et payee sont objectivement déterminables. La relation `PaymentObligation.commerce_order` est nullable et `SET_NULL` afin de préserver l’historique financier lorsqu’une ancienne projection Commerce est reconstruite, sans supprimer l’obligation ni le Payment.

Les obligations `makolo_provider` passent par le pipeline Payment existant. Un contrat provider minimal centralise `initiate`, `confirm`, `cancel` et `refund`; les seuls adapters T33 sont les providers déjà réels dans le dépôt, `sandbox` et `manual`. Aucun M-PESA, Airtel Money, wallet, split payment, payout ou credential fictif n’est introduit. Une obligation `external` est satisfaite par `PaymentEvidence` reliée à un `JourneyArtifact`; aucune transaction `Payment(status=succeeded)` n’est fabriquée pour représenter un paiement effectué sur un portail tiers.

Le lien entre un Requirement financier individuel et une obligation reste propriétaire de la verticale Services via `ServiceRequirementPaymentObligation` (`ServiceRequirementAssessment ↔ PaymentObligation`). `payments` ne dépend donc pas d’`opportunities`. Une `JourneyStep(kind=payment)` est validée par le bridge Services avant completion : le noyau `journeys` ne connaît pas Payments. Un paiement intermédiaire ne modifie pas la Journey globale vers `pending_payment`.

`ServiceSubmission` conserve des tentatives numérotées par contexte avec unicité `(context, attempt)` et transitions contrôlées. La completion policy historique `required_steps` est conservée ; `required_steps_and_submission` est opt-in et exige une tentative réellement `submitted` ou `acknowledged`, jamais un résultat externe favorable. `ServiceOutcomeEvent` est append-only et `ServiceJourneyContext.current_outcome` est une projection transactionnelle déterminée par `occurred_at` avec un tie-breaker stable. `Journey.status` et `current_outcome` restent deux axes indépendants : `Journey.fulfilled + current_outcome.unsuccessful` est un état valide et couvert par les tests.

La sécurité T33 réutilise l’autorité existante : bénéficiaire pour les actions propres autorisées, ou autorité Activity + `JourneyAssignment` active pour les opérations de dossier. Les opérations financières sensibles et la vérification externe restent deny-by-default hors autorité explicite/staff jusqu’à la matrice finale T34B. Les faits T33 passent par l’outbox Domain Events existante ; Notifications/Automation finales restent T34B.

### T34 — Foundations, Authorization, Privacy, Events & Automation

T34 est désormais exécutée en **deux sous-phases ordonnées**. Ce découpage évite de continuer à ajouter de la logique Requirement spécifique à Services alors qu’un second consommateur horizontal, Subscriptions, est maintenant spécifié.

#### T34A — Horizontal Requirements Foundation

**Statut : implémentée dans la PR T34A ; à déclarer livrée seulement après squash merge et gates post-merge verts.**

**But :** extraire les primitives réellement communes de Requirements avant de construire un second moteur dans Subscriptions.

Runtime T34A :

- bounded context/app `requirements` sans modèle DB universel ;
- `RequirementMode` : `automatic`, `action`, `verification`, `external_check`, `payment`, `review` ;
- `RequirementAssessmentState` : `unassessed`, `pending`, `satisfied`, `unsatisfied`, `not_applicable` ;
- `RequirementEvaluationResult` non persistant avec `state`, `reason_code`, `actual_value`, `expected_value`, `observed_at`, `retryable` ;
- `EvaluatorRegistry` code-controlled avec enregistrement explicite, lookup, évaluation, validation stricte des paramètres/opérateurs/sujets, métadonnées `dependency_events` et `cache_policy` ;
- rejet des clés de configuration arbitraires, sans `eval`, `exec`, SQL/JavaScript configurable, import path DB ou moteur booléen générique ;
- aucun GFK/ContentType métier central ;
- `OpportunityRequirement` reste dans `opportunities` ; `ServiceRequirementAssessment`, Evidence, Step links et bridge Payment restent dans `services` ;
- migration en place des anciens pseudo-states T32 : `action_required/needs_review → pending`, `not_eligible → unsatisfied`, les autres valeurs conservées ;
- la colonne Services reste nommée `status` mais utilise le contrat horizontal ; aucun rename cosmétique ;
- conséquences Services `action_required`, `needs_review`, `payment_required`, `not_eligible` calculées depuis les propriétaires canoniques et non persistées ;
- bridge financier T33 : obligation non satisfaite → Assessment `pending`; toutes obligations satisfied/waived → `satisfied` ;
- kernel importable et exécutable par un consumer non-Services ;
- test de frontière empêchant `requirements → services/subscriptions/opportunities/payments/journeys/events/transport` ;
- tests PostgreSQL T34A explicites, y compris concurrence d’Assessment, en plus des régressions T31/T32/T33.

T34A n’ajoute aucun runtime Subscription, Entitlement ou Eligibility et n’ajoute pas de `mode` spéculatif à `OpportunityRequirement` faute de sémantique historique objectivement déductible.

**Gate T34A :** Services T31/T32/T33 reste vert, les Requirements Opportunity/Services continuent de fonctionner, le kernel horizontal est utilisable sans Services, les migrations historiques sont préservées et PostgreSQL/Beta seed/CI sont verts.

#### T34B — Services Authorization, Privacy, Events & Automation

**But :** stabiliser la matrice d’autorité et l’orchestration événementielle/attention Services sur la fondation Requirements finale.

Périmètre :

- permissions finales `activity.services.*` ;
- rôles Services ;
- selectors anti-IDOR ;
- frontière finale des artifacts restricted ;
- permissions Opportunity ;
- Domain Events finalisés ;
- notifications ;
- Automation et rappels/deadlines ;
- surfaces d’attention alimentées par les capacités personnelles existantes, sans second centre d’attention.

Principe non négociable : **Mandate = autorité ; JourneyAssignment = affectation opérationnelle.**

### T35 — Complete Services UX

**Statut : en cours sur `task-35-complete-services-ux`.**

**But :** livrer les surfaces produit complètes sur les domaines déjà sécurisés.

Périmètre :

- expérience participant ;
- console facilitateur/reviewer ;
- console Space/manager ;
- console staff Opportunity ;
- parcours mobile/accessibilité ;
- intake, progression, requirements, blockers, artifacts/reviews, paiements/preuves, rendez-vous, timeline, soumissions et outcomes selon les capacités introduites par T31–T34.

### T36 — Analytics, Hardening & V1 Release Gate

**But :** fermer la V1 seulement après validation transversale.

Périmètre :

- analytics Services ;
- performance/query-count ;
- concurrence finale ;
- security review ;
- E2E desktop/mobile ;
- beta seed ;
- compatibilité migrations/données historiques réellement nécessaires ;
- smoke tests environnement de test ;
- régressions Events/Transport/Access/Capacity/Commerce/Payments ;
- documentation opérationnelle ;
- release gate V1.

## 3. Parallélisation avec Subscriptions

La spécification [`subscriptions-entitlements-requirements.md`](subscriptions-entitlements-requirements.md) introduit un domaine horizontal qui partage uniquement le kernel Requirements avec Services.

La séquence recommandée est :

```text
T33 terminé
    ↓
T34A Requirements Foundation
    ↓
    ├── T34B Services Authorization/Events
    └── Subscriptions Foundation
            ↓
T35 Services UX          Subscriptions UX
            \            /
             \          /
              T36 / hardening transversal
```

### Règle de parallélisation

- **Ne pas commencer le runtime Subscription avant merge de T34A**, sinon Makolo créerait deux moteurs Requirement qu’il faudrait fusionner immédiatement.
- **Après merge de T34A, T34B et le chantier Subscription peuvent avancer en parallèle** sur des branches distinctes, car leurs responsabilités deviennent séparées.
- T34B ne doit pas introduire de nouvelle primitive générique réservée à Services sans vérifier d’abord `requirements`.
- Subscription ne doit pas importer `services` ni réutiliser `Journey` pour ses transitions.
- Les deux chantiers peuvent partager Domain Events/Notifications/Authorization seulement via leurs contrats canoniques, avec petits PRs et gates croisés.
- **Ne pas attendre T35/T36 pour commencer Subscription** : cela repousserait inutilement une fondation horizontale déjà spécifiée et augmenterait le coût d’intégration tardive.

### Révision des prochaines tâches

Le plan T31–T36 reste valide pour **Services** ; il n’est pas remplacé par le chantier Subscription. La numérotation des tâches globales Makolo doit simplement enregistrer un nouveau chantier horizontal après T34A au lieu de forcer Subscription à devenir « T37 Services ».

Le prochain travail après merge de T34A est donc, sur deux branches séparées :

1. **T34B — Services Authorization, Privacy, Events & Automation** ;
2. **Subscriptions Foundation**, commençant avec ses propres domaines Feature/Entitlement/Catalogue conformément à la spécification canonique et en consommant le kernel Requirements désormais stabilisé ;
3. poursuivre T35 Services UX ;
4. intégrer l’UX Subscription lorsque ses contrats serveur sont stabilisés ;
5. faire converger les hardening/release gates avant toute production réelle.

## 4. Mapping des anciens lots historiques

Le découpage historique détaillé n’est plus une séquence de 14 PR obligatoires. Il se mappe au plan consolidé de la façon suivante :

| Ancien lot | Découpage consolidé |
| --- | --- |
| anciens Tasks 31–33 : Journey long-running, collaboration/artifacts, Services vertical core | **T31** |
| anciens Tasks 34–35 : Opportunity + Journey/requirements | **T32**, puis extraction horizontale ciblée en **T34A** |
| anciens Tasks 36 et 38 : obligations financières + submissions/outcomes | **T33** |
| anciens Tasks 37 et 39 : authorization/privacy + automation/attention | **T34B** |
| anciens Tasks 40–42 : participant, facilitator/Space, curation Opportunity | **T35** |
| anciens Tasks 43–44 : analytics + hardening/release | **T36** |

Les décisions métier détaillées de ces anciens lots restent récupérables dans `services-opportunities.md` et l’historique Git, mais les futurs travaux doivent référencer les numéros consolidés T31–T36 et la sous-phase T34A lorsqu’ils touchent le kernel Requirements.

## 5. Scénarios de release obligatoires

La release Services V1 devra finalement couvrir au minimum :

1. **Service sans Opportunity** — Activity CV → Journey → Intake → plan → facilitateur → artifacts versionnés → review → fulfillment.
2. **Emploi avec Opportunity** — Opportunity → save → Journey → requirements → CV/review → blockers → paiement éventuel → submission → outcome.
3. **Bourse** — Opportunity/revision/source → requirements → artifacts → frais sandbox ou preuve externe → vérification → submission → outcome.
4. **Opportunity proposée par un utilisateur** — proposition → staff review → accepted/duplicate → Opportunity canonique → Journey éventuelle.
5. **Opportunity modifiée** — dossier pinné sur revision N → N+1 publiée → comparaison → adoption explicite ou maintien de N.
6. **Paiement commercial** — les bridges Commerce/Payment historiques restent compatibles pendant la généralisation vers PaymentObligation.
7. **Requirements horizontal** — T32/T33 restent fonctionnels après extraction du kernel et aucun modèle Services n’est requis pour évaluer une condition via le registry horizontal.

## 6. Gates transversaux

Chaque tâche doit vérifier les domaines réellement impactés. Les gates de référence sont :

```text
check Django
→ tests ciblés
→ tests de régression pertinents
→ makemigrations --check --dry-run
→ migrations
→ PostgreSQL
→ build frontend/E2E si requis
→ beta seed
→ CI PR verte
→ merge selon la stratégie décidée
→ main post-merge vert
```

Aucun test ne doit être supprimé ou affaibli pour obtenir du vert. Toute régression doit être corrigée à sa cause racine.