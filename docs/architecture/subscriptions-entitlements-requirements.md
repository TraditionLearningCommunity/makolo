# Makolo — Subscriptions, Entitlements, Eligibility & Requirements

> **Statut : canonique pour la cible d'architecture.** Ce document complète [`makolo-domain-blueprint.md`](makolo-domain-blueprint.md). Il fixe la frontière horizontale des abonnements Makolo, des capacités produit et des conditions d'éligibilité avant l'introduction des prix/billing réels. Lorsqu'il traite de Requirements partagés, il complète la sémantique Services/Opportunity décrite dans [`services-opportunities.md`](services-opportunities.md) sans transformer `subscriptions` en dépendance de la verticale `services`.

## 1. Intention

Makolo doit pouvoir proposer des formules produit à des millions de Profils et d'Espaces sans attribution manuelle systématique par le Staff et sans coder un nouveau plan commercial à chaque évolution du catalogue.

Le fonctionnement normal est :

```text
Staff configure le catalogue
        ↓
Makolo filtre les plans pertinents
        ↓
Profile / Space consulte son abonnement
        ↓
choisit une formule
        ↓
Makolo évalue les conditions
        ↓
actions / vérifications / revue / paiement éventuels
        ↓
activation automatique
        ↓
Entitlements effectifs
        ↓
Domain Events → Notifications / Automation / Analytics
```

L'intervention Staff sur une Subscription individuelle reste exceptionnelle : support, bêta, partenariat, correction, grandfathering, geste commercial ou revue explicitement requise.

## 2. Séparation des concepts

Quatre questions différentes restent séparées :

- **Subscription** : quelle formule produit ce Profil ou cet Espace utilise-t-il ?
- **Entitlement** : quelles capacités produit et limites cette formule rend-elle disponibles ?
- **Permission** : cette personne a-t-elle le droit d'effectuer cette action dans cette portée ?
- **Requirement** : quelle condition doit être vraie ou satisfaite ?

Une opération premium peut donc exiger :

```text
Entitlement satisfait
AND Permission satisfaite
AND Requirements métier satisfaits
AND invariants du domaine satisfaits
```

Un Entitlement ne donne jamais une Permission. Une Permission ne donne jamais une capacité commerciale. Une Subscription ne contourne jamais Role/Permission/Mandate.

## 3. Frontières de domaine

### `subscriptions`

Propriétaire de :

- catalogue de plans ;
- versions de plans ;
- avantages marketing ;
- FeatureDefinitions et valeurs d'Entitlement ;
- conditions d'acquisition/conservation des plans ;
- éligibilité ;
- Subscription d'un Profil/Espace ;
- add-ons ;
- changements de plan ;
- grants exceptionnels ;
- résolution des Entitlements effectifs.

### `requirements`

Noyau horizontal propriétaire de :

- modes de Requirement ;
- états génériques d'évaluation ;
- registre d'évaluateurs ;
- validation des configurations d'évaluateurs ;
- contrat de résultat d'évaluation.

Il **ne possède pas** une table universelle capable de pointer arbitrairement vers n'importe quel agrégat métier.

### `authorization`

Reste propriétaire de Permission, Role, Mandate et de `can(...)`.

### `payments`

Reste propriétaire de Payment, PaymentObligation, PaymentEvidence, providers, idempotence et refunds.

### `trust`

Reste propriétaire des vérifications lorsqu'elles existent. Subscription consomme leur résultat au lieu de créer un modèle de vérification parallèle.

### Domain Events / Notifications / Automation / Analytics

Subscription émet des faits métier. Notifications, Automation et Analytics les consomment ; Subscription ne leur vole pas leur responsabilité.

### Verticales

Events, Services, Transport et les autres verticales consomment les Entitlements du propriétaire logique de leur Activity. Elles ne créent jamais `EventSubscription`, `ServiceSubscription` ou `TransportSubscription`.

## 4. Sujet d'une Subscription

Une Subscription appartient exactement à :

```text
Profile XOR Space
```

Jamais à une Activity, Event, Journey ou verticale.

Pour une Activity personnelle :

```text
Activity.owner_profile → Subscription du Profile
```

Pour une Activity opérée collectivement :

```text
Activity.space → Subscription du Space
```

Lorsqu'un collaborateur agit pour une Activity d'un Espace :

```text
Entitlements = ceux du Space
Permissions  = celles du Profile via ses Mandates
```

Cette distinction est un invariant central.

## 5. Plan de base universel

Tout Profil et tout Espace possède une Subscription durable avec exactement un plan BASE actif lorsqu'il est utilisable.

Il existe un plan BASE par défaut pour les Profils et un plan BASE par défaut pour les Espaces. La création du sujet initialise sa Subscription avec la version publiée courante correspondante.

Le plan par défaut ne doit pas dépendre d'une condition d'acquisition pouvant laisser un sujet sans socle produit.

Un utilisateur qui « annule Pro » effectue normalement une transition vers le plan BASE ; l'identité Subscription n'est pas supprimée.

## 6. `SubscriptionPlan`

Identité durable d'une formule.

Champs conceptuels :

```text
id
code
plan_type = base | addon
subject_type = profile | space
is_default
is_active
current_version
created_by
timestamps
```

Invariants :

- `code` est stable et unique ;
- un Plan cible un seul `subject_type` ;
- un add-on ne peut pas être le plan par défaut ;
- un seul BASE par défaut actif existe par type de sujet.

L'UI peut parler de « formule » ou « offre Makolo », mais le backend ne réutilise pas le nom `Offer`, déjà canonique dans Commerce.

## 7. `PlanVersion`

Une version représente le contrat produit précis proposé à un instant donné.

Champs conceptuels :

```text
plan
version
status = draft | published | retired
name
short_description
description
catalog_visibility = public | unlisted | internal
acquisition_mode = self_service | staff_only
display_order
change_summary
created_by
published_at
retired_at
```

`plan + version` est unique.

Une version publiée est structurellement immuable. Une évolution crée N+1. La publication de N+1 ne modifie jamais silencieusement les abonnés ou transitions pinnés sur N.

`retired` signifie indisponible pour une nouvelle acquisition normale, pas invalide historiquement.

## 8. `PlanBenefit`

Les Benefits sont des éléments de présentation : titre, description, icône, ordre, mise en avant.

Ils ne contrôlent jamais l'accès. Une phrase marketing comme « équipe plus grande » n'est pas la source d'une limite ; la limite vient d'un Entitlement.

## 9. `FeatureDefinition`

Une FeatureDefinition représente une capacité technique connue de Makolo.

Exemples de forme :

```text
activities.active
team.members
analytics.basic
analytics.advanced
crm.contacts
automation.workflows
data.export
events.operations
services.operations
transport.operations
custom_roles
```

La liste réelle doit être dérivée des capacités effectivement implémentées.

Le code contrôle :

- `code` ;
- domaine ;
- type de valeur ;
- unité éventuelle ;
- types de sujets acceptés ;
- stratégie d'agrégation ;
- provider d'usage/quotas ;
- politique d'enforcement.

Le Staff peut composer des Plans à partir de Features existantes. Il ne peut pas inventer une nouvelle Feature technique arbitraire.

Types de valeur initiaux :

```text
boolean
integer
decimal
enum
```

## 10. `PlanEntitlement`

Relie une PlanVersion à une FeatureDefinition :

```text
plan_version
feature
value
```

`plan_version + feature` est unique.

La valeur est validée strictement selon la Feature. Une version publiée rend ses Entitlements immuables.

## 11. Agrégation des Entitlements

La stratégie est une propriété technique de la Feature, pas une option libre du Staff.

Stratégies initiales :

```text
BOOLEAN_OR
SUM
MAX
REPLACE
```

Les sources peuvent être :

```text
BASE
+ ADDONS
+ GRANTS
```

Pour `REPLACE`, la priorité initiale recommandée est :

```text
explicit grant > addon > base plan
```

## 12. `EntitlementGrant`

Exception contrôlée accordée directement à un Profil ou Espace.

Cas d'usage : bêta, partenariat, support, grandfathering, geste commercial, expérimentation.

Champs conceptuels :

```text
profile XOR space
feature
value
valid_from
valid_until
reason
granted_by
granted_at
revoked_by
revoked_at
revocation_reason
```

Un Grant ne change pas la PlanVersion. Il est temporalisable, révocable et audité.

## 13. Entitlements effectifs

`EffectiveEntitlement` est un résultat calculé, pas une table canonique.

```text
active base item
+ active addon items
+ active grants
+ Feature Requirements satisfaits
= Effective Entitlements
```

Le résultat peut exposer :

```text
feature_code
effective_value
sources
usage
remaining
allowed
reason_code
```

Une projection/cache pourra être ajoutée pour les performances, sans devenir source de vérité.

Le code métier demande une Feature ; il ne teste jamais le nom commercial d'un plan.

Interdit :

```python
if plan.code == "business":
    ...
```

Cible :

```text
require_entitlement(subject, "feature.code")
```

## 14. Usage et quotas

Les compteurs restent dans leurs domaines canoniques. `team.members` ne crée pas un second compteur Subscription des membres.

Une Feature quantitative déclare un provider de mesure connu du code.

Lors d'un downgrade sous l'usage actuel, Makolo ne détruit pas automatiquement les données.

Exemple :

```text
23 membres existants
nouvelle limite = 10
```

Politique initiale recommandée :

```text
preserve_existing_block_new
```

Les 23 restent ; les nouvelles créations/invitations sont bloquées jusqu'au retour sous la limite.

## 15. Le noyau horizontal `requirements`

Le refactoring Requirements généralise la **mécanique**, pas les agrégats métier.

Le noyau commun fournit :

```text
RequirementMode
RequirementAssessmentState
EvaluatorRegistry
RequirementEvaluationResult
configuration validation
```

Il ne fournit pas un modèle polymorphe universel :

```text
Requirement(target_type, target_id)
```

Interdits comme fondation :

- GenericForeignKey métier ;
- `ContentType` comme cible métier centrale ;
- code Python en base ;
- SQL configurable ;
- JavaScript configurable ;
- langage de règles arbitraire.

Les modèles persistants restent dans leurs domaines :

```text
OpportunityRequirement
PlanRequirement
EntitlementRequirement
ServiceRequirementAssessment
SubscriptionRequirementAssessment
```

## 16. Modes de Requirement

Modes initiaux :

```text
automatic
action
verification
external_check
payment
review
```

- `automatic` : Makolo possède l'information et l'évalue.
- `action` : une action interne doit être accomplie.
- `verification` : dépend du domaine Trust/Verification.
- `external_check` : dépend d'un tiers ou système externe.
- `payment` : dépend d'une obligation financière.
- `review` : une personne autorisée doit décider.

Le prix normal d'un abonnement futur ne doit pas être saisi manuellement comme une fausse condition ; les termes commerciaux créeront la PaymentObligation appropriée.

## 17. États génériques d'Assessment

Le noyau générique sépare la vérité de la condition de la prochaine action UI.

États :

```text
unassessed
pending
satisfied
unsatisfied
not_applicable
```

`action_required`, `needs_review`, `payment_required`, `waiting_verification` ou `not_eligible` sont des conséquences/présentations dérivées du Requirement, de l'Assessment et de la policy ; ce ne sont pas des vérités génériques concurrentes.

Pour le runtime T32 existant, le refactoring cible le mapping conceptuel :

```text
unassessed      → unassessed
satisfied       → satisfied
action_required → pending
needs_review    → pending
not_applicable  → not_applicable
not_eligible    → unsatisfied
```

Ce mapping doit être réalisé avec tests de non-régression avant de supprimer les anciens contrats.

## 18. Registry d'évaluateurs

Le code expose des évaluateurs contrôlés.

Exemples de forme :

```text
profile.account_age_days
space.account_age_days
space.member_count
space.activity_count
profile.verification_status
space.verification_status
subscription.current_plan
```

Chaque évaluateur déclare :

```text
key
supported_subject_type
parameter_schema
result_type
operators
dependency_events
cache_policy
```

Exemple configuré par le Staff :

```text
evaluator = space.account_age_days
operator = >=
value = 90
```

Le Staff configure des paramètres validés ; il ne fournit jamais la fonction d'exécution.

## 19. `RequirementEvaluationResult`

Résultat non polymorphe du moteur :

```text
state
reason_code
actual_value
expected_value
observed_at
retryable
```

Les valeurs conservées/retournées doivent respecter la minimisation des données. Une Assessment n'est pas un stockage secondaire de documents sensibles.

## 20. `PlanRequirement`

Condition attachée à une PlanVersion.

Champs conceptuels :

```text
plan_version
key
title
description
phase = acquisition | ongoing | renewal
mode
evaluator_key
config
is_mandatory
position
failure_policy
grace_period_days
disclosure = visible | generic | internal
```

Une version publiée rend ses PlanRequirements immuables.

### Phase acquisition

Condition pour obtenir la formule.

### Phase ongoing

Condition devant rester vraie pendant l'utilisation.

### Phase renewal

Condition évaluée lors d'un renouvellement futur.

## 21. Policies des Requirements

Pour une condition `acquisition` :

```text
block
deny
```

`block` signifie que la condition peut être satisfaite plus tard et produit `conditionally_available`.

`deny` signifie que le changement ne peut pas continuer dans l'état actuel et produit `not_eligible`.

Pour `ongoing` :

```text
warn
grace
suspend
```

Le Requirement constate ; la policy Subscription décide de la conséquence.

## 22. Pas de moteur booléen arbitraire en V1

Tous les Requirements obligatoires applicables doivent être satisfaits.

Pas de configuration arbitraire du type :

```text
(A AND B) OR (C AND (D OR E))
```

Une future extension pourra introduire des groupes non imbriqués `ALL`, `ANY` ou `AT_LEAST` si un besoin réel apparaît.

## 23. `EntitlementRequirement`

Une Feature précise peut avoir une condition sans rendre tout le Plan inaccessible.

Exemple :

```text
Subscription active
Plan contient analytics.advanced
Feature Requirement = Space vérifié
```

Tant que la vérification n'est pas satisfaite, seule cette Feature reste verrouillée.

## 24. Discovery et Eligibility

La consultation du catalogue est une projection dérivée :

```text
Profile / Space
      ↓
candidate PlanVersions
      ↓
EligibilityResolver
      ↓
PlanEligibilityResult
```

États externes :

```text
available
conditionally_available
not_eligible
hidden
```

- `available` : toutes les conditions d'acquisition obligatoires applicables sont satisfaites.
- `conditionally_available` : au moins une condition `block` reste à satisfaire, sans `deny` bloquant.
- `not_eligible` : au moins une condition `deny` obligatoire est actuellement non satisfaite.
- `hidden` : le plan ne doit pas être montré dans ce contexte.

`disclosure` contrôle ce que l'utilisateur peut apprendre de la condition.

## 25. Pas de matérialisation massive d'Eligibility

Makolo ne crée pas :

```text
subject × plan × requirement
```

pour tous les utilisateurs.

Une simple consultation évalue à la demande et ne crée aucune `SubscriptionRequirementAssessment`.

Les résultats peuvent être cachés/projetés plus tard. Le cache ne devient jamais la source canonique.

## 26. Éligibilité événementielle

Pour notifier qu'un plan vient de devenir accessible, Makolo ne scanne pas périodiquement toute la population.

Les évaluateurs déclarent leurs événements de dépendance. Lorsqu'un fait pertinent change pour un sujet, seuls les plans concernés par ce type de changement peuvent être réévalués pour ce sujet.

Une notification « désormais éligible » doit être dédupliquée et respecter les préférences de notification.

## 27. `Subscription`

Agrégat durable du Profil/Espace.

Champs conceptuels :

```text
id
profile XOR space
status = active | grace | suspended | closed
grace_until
status_reason
created_at
updated_at
closed_at
```

`active` : Entitlements normaux.

`grace` : maintien temporaire selon policy.

`suspended` : capacités supplémentaires suspendues sans destruction des données ; le socle sûr du plan de base reste disponible selon la policy.

`closed` : agrégat fermé avec son sujet.

## 28. `SubscriptionItem`

Élément BASE ou ADDON actif/historique :

```text
subscription
plan_version
status = scheduled | active | ended
starts_at
ends_at
created_via_transition
ended_reason
```

Invariants :

- exactement un BASE actif pour une Subscription utilisable ;
- une version `draft` ne peut pas être utilisée ;
- le `subject_type` du Plan doit correspondre au sujet ;
- un même add-on ne doit pas posséder deux Items actifs concurrents.

## 29. Add-ons

Une Subscription possède :

```text
1 BASE
0..N ADDONS
```

L'UI initiale peut ne montrer que le BASE, mais la fondation ne doit pas forcer une reconstruction future pour les add-ons.

## 30. `SubscriptionTransition`

Tout changement durable est explicite. Aucun service ne remplace directement un plan actif.

Champs conceptuels :

```text
subscription
kind = base_switch | addon_add | addon_remove
source_plan_version
target_plan_version
requested_by
request_origin
status
requested_at
expires_at
ready_at
completed_at
cancelled_at
failed_at
reason
failure_code
idempotency_key
```

Lifecycle :

```text
requested → in_progress → ready → completed
```

Sorties :

```text
rejected
cancelled
expired
failed
```

`payment_required`, `action_required`, `needs_review` et `waiting_verification` sont dérivés des Assessments ; ils ne deviennent pas des statuts concurrents de Transition.

## 31. Version pinning et concurrence

Une Transition pinne exactement sa `target_plan_version`.

Si v4 est publiée pendant une transition vers v3, la transition reste sur v3. Une adoption de v4 nécessite une décision explicite.

V1 : une seule transition mutante principale ouverte à la fois par Subscription.

L'application `ready → completed` :

- verrouille la Subscription ;
- est transactionnelle ;
- respecte un `idempotency_key` ;
- ne peut pas créer deux BASE actifs sous concurrence.

## 32. `SubscriptionRequirementAssessment`

Créée uniquement lorsqu'une vraie Transition démarre.

Champs conceptuels :

```text
transition
plan_requirement
state
reason_code
actual_value
assessed_by
assessed_at
last_evaluated_at
note
```

`transition + plan_requirement` est unique.

Les Requirements sont matérialisés depuis la PlanVersion pinnée. Une nouvelle PlanVersion ne réécrit jamais ces Assessments.

Un historique append-only des changements significatifs d'Assessment est recommandé.

## 33. Readiness d'une Transition

Une Transition devient `ready` lorsque :

- tous les Requirements obligatoires applicables sont satisfaits ;
- aucun Requirement d'acquisition `deny` n'est non satisfait ;
- les obligations financières nécessaires sont satisfaites ;
- aucune revue bloquante n'est en attente ;
- les invariants du domaine restent valides.

L'application de la transition est atomique.

## 34. Prix et Payment

Le premier chantier Subscription ne nécessite pas de prix réel.

Le futur modèle commercial sera attaché à la version exacte du plan, conceptuellement via `PlanPrice` ou équivalent versionné.

Une condition financière normale suit :

```text
PlanVersion / termes commerciaux
        ↓
SubscriptionTransition
        ↓
PaymentObligation
        ↓
Payment
```

Jamais :

```text
Subscription.is_paid = true
```

Le Payment actuel ne doit pas être détourné directement par une nouvelle FK opaque. `PaymentObligation` reste le contrat de composition prévu pour les contextes non Commerce/Ticket.

## 35. Verification et revue

Un Requirement `verification` consomme Trust/Verification. Aucune duplication `SubscriptionVerification` n'est créée si le noyau Trust porte déjà le sens nécessaire.

Une condition `review` ne transforme pas tous les abonnements en workflow manuel. Elle est utilisée seulement par les plans qui en ont besoin, avec Permission/Mandate et audit.

## 36. Authorization Profile / Space / Staff

### Profil propre

Un Profil authentifié peut voir et gérer sa propre Subscription sous réserve des règles générales du compte.

Il n'existe pas de portée Mandate Profile ; l'autorité vient ici de la relation « soi-même ».

### Espace

Permissions cibles :

```text
space.subscription.view
space.subscription.manage
```

Plus tard, lorsque le billing existe :

```text
space.subscription.billing.manage
```

Répartition initiale recommandée :

- `space-owner` : view + manage ;
- `space-admin` : view par défaut ;
- délégation possible via rôle Space personnalisé.

Un simple TeamMembership ne suffit pas.

### Plateforme Makolo

Permissions cibles :

```text
platform.subscriptions.catalog.view
platform.subscriptions.catalog.manage
platform.subscriptions.view
platform.subscriptions.manage
platform.subscriptions.grants.manage
platform.subscriptions.reviews.manage
```

Toute action Staff métier passe par Permission/Mandate ; `is_staff` seul n'est pas une autorité business universelle.

## 37. Staff Console

Le Staff autorisé peut :

- créer un Plan et un brouillon de version ;
- composer Benefits, Entitlements et Requirements ;
- prévisualiser ;
- publier/retirer ;
- voir Subscriptions et Transitions ;
- appliquer/révoquer un Grant ;
- traiter une revue ;
- effectuer une intervention de support auditée.

Le Staff ne modifie jamais une version publiée en place.

## 38. Self-service UX

Ajouter une surface **Abonnement** :

- au Profil ;
- à la Console Espace selon Permission.

Elle présente au minimum :

- formule actuelle ;
- capacités et limites principales ;
- usage ;
- add-ons actifs ;
- conditions ongoing ;
- plans pertinents ;
- états d'éligibilité ;
- transition éventuelle en cours ;
- conséquences d'un changement.

Une condition publiquement explicable doit afficher pourquoi elle bloque et, si possible, l'action suivante.

## 39. Preview avant changement

Avant mutation, Makolo peut produire un `SubscriptionChangePreview` dérivé :

- Features gagnées/perdues ;
- quotas augmentés/diminués ;
- ressources déjà au-dessus d'une nouvelle limite ;
- Requirements ;
- paiement futur éventuel ;
- conséquences connues.

Le preview ne modifie rien.

## 40. Ongoing Requirements

Les Requirements ongoing sont réévalués :

- lors d'opérations sensibles ;
- lorsque leurs Domain Events de dépendance surviennent ;
- éventuellement par Automation à une échéance précise.

Pas de scan global permanent.

Exemple :

```text
verification.expired
    ↓
Requirement unsatisfied
    ↓
policy grace
    ↓
Subscription active → grace
    ↓
Domain Event
    ↓
Notification / Automation
```

Aucune donnée métier n'est détruite automatiquement.

## 41. Domain Events

Contrats cibles, à stabiliser dans `domain_events` lors de l'implémentation :

```text
subscription.transition.requested
subscription.transition.ready
subscription.transition.completed
subscription.transition.rejected
subscription.transition.cancelled
subscription.transition.failed
subscription.transition.expired
subscription.requirement.changed
subscription.plan.changed
subscription.addon.activated
subscription.addon.removed
subscription.grace.started
subscription.suspended
subscription.reactivated
subscription.entitlement.granted
subscription.entitlement.grant_revoked
subscription.eligibility.available
```

Un Domain Event décrit un fait déjà commis.

## 42. Notifications / Automation / Analytics

Notifications consomme les événements et déduplique les messages.

Automation peut gérer rappels, grace period, expiration de Grants et futurs renewals.

Analytics observe notamment :

```text
catalog_viewed
plan_viewed
transition_started
transition_completed
transition_abandoned
requirement_blocked
requirement_satisfied
downgrade_completed
addon_added
addon_removed
```

Aucun de ces domaines ne devient la source de vérité de la Subscription.

## 43. Sécurité et anti-IDOR

Tous les contrôles critiques sont serveur-side.

Un UUID de Subscription ou Transition ne confère aucune autorité.

Les selectors vérifient :

- propriétaire Profile ;
- ou autorité sur Space ;
- ou Permission plateforme.

Ordre conceptuel avant mutation premium :

```text
acteur authentifié
→ sujet résolu
→ Entitlement
→ Permission
→ Requirement/règle métier
→ quota
→ mutation
```

L'ordre technique peut être optimisé mais toutes les garanties doivent exister avant la mutation.

## 44. Performance et échelle

Pour des millions de sujets :

- catalogue publié petit et indexé ;
- filtrage par `subject_type` ;
- Eligibility à la demande ;
- batch/selectors ;
- Assessments persistés seulement pour une Transition ;
- caches facultatifs ;
- invalidation événementielle ;
- compteurs possédés par les domaines métier ;
- aucune matérialisation globale `subject × plan × requirement`.

## 45. Refactoring T32/T33

La sémantique utile livrée par T32 est conservée :

```text
Requirement = ce qui est exigé
Assessment = état de cette exigence dans un dossier
JourneyStep = action à accomplir
Evidence = preuve métier
```

Mais la mécanique générique doit sortir de `services` avant qu'un second moteur soit introduit dans Subscription.

`OpportunityRequirement` reste dans `opportunities` et garde sa FK explicite vers `OpportunityRevision`.

`ServiceRequirementAssessment` reste dans `services` et garde ses FKs explicites vers `ServiceJourneyContext` et `OpportunityRequirement`.

`ServiceRequirementEvidence`, `JourneyArtifact`, `ServiceRequirementStepLink` et `JourneyStep` restent dans leurs domaines actuels.

Le noyau `requirements` fournit seulement les primitives réellement communes.

Le bridge financier T33 `ServiceRequirementAssessment ↔ PaymentObligation` reste propriétaire de Services ; `payments` ne dépend pas d'Opportunity/Services.

## 46. Subscription n'utilise pas Journey

Une `SubscriptionTransition` n'est pas une Journey.

Journey reste un processus lié à une Activity. Subscription possède son workflow léger afin d'éviter une fausse Activity technique, un `activity=null` artificiel ou une extension sémantique incontrôlée de Journey.

## 47. Scénarios d'acceptation structurants

La première implémentation doit couvrir au minimum :

1. création d'un Profil → Subscription + BASE Profile ;
2. création d'un Espace → Subscription + BASE Space ;
3. Activity personnelle → Entitlements Profile ;
4. Activity d'Espace → Entitlements Space ;
5. consultation catalogue sans création d'Assessment ;
6. plan d'un mauvais `subject_type` absent ;
7. conditions satisfaites → `available` ;
8. condition `block` → `conditionally_available` ;
9. condition `deny` → `not_eligible` ;
10. plan sans obligation → transition automatique jusqu'à `completed` ;
11. vérification/revue/paiement → transition reste `in_progress` jusqu'à satisfaction ;
12. membre Space sans Permission → 403 sur mutation ;
13. owner / rôle personnalisé autorisé → mutation possible ;
14. publication vN+1 ne réécrit ni SubscriptionItem ni Transition vN ;
15. double soumission → idempotence ;
16. concurrence → un seul BASE actif ;
17. Entitlement présent + Permission absente → refus ;
18. Permission présente + Entitlement absent → refus de capacité premium ;
19. downgrade sous quota → données conservées, nouvelles créations bloquées ;
20. expiration d'un Grant → disparition de son effet ;
21. Requirement ongoing échoue → policy warn/grace/suspend, sans suppression de données ;
22. T32 reste fonctionnel après extraction du kernel Requirements ;
23. Subscription n'importe aucun modèle Services.

## 48. Ordre d'implémentation recommandé

### Fondation A — Requirements kernel

Créer les primitives communes et refactorer T32/T33 sans régression.

### Fondation B — Feature / Entitlement

Créer FeatureDefinition, registry, PlanEntitlement, resolver, Grants et contrats d'usage.

### Fondation C — Catalogue

Créer SubscriptionPlan, PlanVersion, PlanBenefit, PlanRequirement et EntitlementRequirement.

### Fondation D — Subscription

Créer Subscription, SubscriptionItem et bootstrap des plans BASE.

### Fondation E — Eligibility

Créer resolver/catalog selectors sans persistence massive.

### Fondation F — Transition

Créer SubscriptionTransition, Assessments, audit, concurrence et idempotence.

### Fondation G — Authorization / Events

Ajouter Permissions, selectors anti-IDOR, Domain Events et projections nécessaires.

### Fondation H — UX

Ajouter les surfaces Profile, Space et Staff.

### Fondation I — Pricing/Billing ultérieur

Ajouter prix, renewals, invoices/taxes/providers réels sans reconstruire la fondation.

## 49. Hors du premier chantier

Ne pas construire immédiatement :

- provider réel Subscription ;
- factures/taxes ;
- coupons complexes ;
- prorata ;
- renouvellement automatique ;
- moteur booléen arbitraire ;
- code Staff programmable ;
- IA de choix de plan ;
- tarification dynamique ;
- scans globaux d'éligibilité ;
- suppression automatique de données après downgrade.

## 50. Invariants canoniques

1. Subscription appartient exactement à Profile XOR Space.
2. Activity consomme la Subscription de son opérateur logique.
3. Activity et verticales n'ont pas leurs propres Subscriptions.
4. Permission, Entitlement et Requirement restent distincts.
5. Staff métier agit via Permission/Mandate, jamais seulement `is_staff`.
6. Le Staff peut recomposer des plans avec des Features existantes sans code.
7. Une nouvelle Feature technique nécessite du code.
8. Aucun Requirement n'exécute du code arbitraire stocké en DB.
9. Requirements n'utilise pas de cible métier GenericForeignKey.
10. Les modèles persistants de Requirement restent dans leurs domaines.
11. Les états génériques d'Assessment décrivent la satisfaction, pas la prochaine action UI.
12. Eligibility de catalogue est dérivée à la demande.
13. Une consultation de catalogue ne matérialise pas d'Assessments.
14. Une vraie Transition matérialise les Requirements de sa version pinnée.
15. Une PlanVersion publiée est immuable.
16. N+1 ne réécrit jamais silencieusement N.
17. Une Subscription utilisable possède exactement un BASE actif.
18. Benefits marketing ne contrôlent aucun droit.
19. Le code métier vérifie des Feature codes, jamais des noms de Plans.
20. EffectiveEntitlement est dérivé de sources canoniques.
21. Un downgrade ne détruit pas automatiquement les données métier.
22. Payment reste propriétaire des transactions.
23. Verification reste propriétaire des vérifications.
24. Subscription ne détourne pas Journey.
25. Domain Events représentent des faits déjà commis.
26. Notifications/Automation réagissent aux événements au lieu d'être implémentées dans Subscription.
27. Les changements concurrents sont transactionnels et idempotents.
28. Les Grants sont audités, temporalisables et révocables.
29. Les données sensibles restent dans leur domaine propriétaire.
30. L'architecture doit fonctionner à grande échelle sans `subject × plan × requirement` persistant.

## 51. Critère de prêt à coder

Le code Subscription ne doit commencer qu'après :

- publication de cette spécification ;
- reconnaissance de `requirements` et `subscriptions` dans le blueprint ;
- mise à jour du plan Services ;
- refactoring du kernel Requirements planifié avant tout second moteur ;
- maintien explicite des invariants T31/T32/T33 ;
- définition de tests de non-régression du refactoring.

Les noms commerciaux des plans, leurs prix futurs et les providers de paiement réels ne bloquent pas cette fondation.
