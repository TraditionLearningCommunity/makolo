# Z5 — Projections de détail des réalités engagées

> **Statut : implémenté.**
>
> Branche de réalisation : `task-z5-engaged-detail-projections`.
>
> Réconciliation initiale : Z2 déjà intégré, Z3 intégré avant le wiring Z5. Z4 restait parallèle ; Z5 isole donc ses routes personnelles dans `core.api.detail_urls` au lieu de réécrire la composition `core.api.urls`.

## 1. Mission

Z5 expose les profondeurs utiles des réalités déjà engagées ou suffisamment déterminées, sans demander au client de reconstruire le métier depuis l'ORM :

```text
owner domain
→ selector / service / read model canonique
→ projection de détail serveur
→ API stable
→ Web / Flutter / futur client
```

Aucun modèle, migration, cache métier, ranking, score, deuxième Readiness ou progression universelle n'est introduit.

## 2. Endpoints livrés

### Personnel

```text
GET /api/v1/me/journeys/<uuid>/
GET /api/v1/me/journeys/<journey_uuid>/requirements/<assessment_uuid>/
GET /api/v1/me/accesses/<uuid>/
```

### Activity / Occurrence

```text
GET /api/v1/activities/<uuid>/
GET /api/v1/occurrences/<uuid>/
```

### Objectives

```text
GET /api/v1/objectives/dossiers/<uuid>/
GET /api/v1/objectives/projects/<uuid>/
```

Les APIs spécialisées existantes restent propriétaires de leur profondeur :

```text
Occurrence Live    → /api/v1/operations/occurrences/<uuid>/live/
Preparation        → /api/v1/preparation/journeys/<uuid>/resources/
Questionnaires     → /api/v1/questionnaires/requests/...
Payments           → /api/v1/payments/payments/...
Trust              → /api/v1/trust/...
```

## 3. Journey

`personal.journey.detail` est résolu exclusivement depuis :

- `participant_journeys(request.user)` ;
- `participant_readiness_queryset(...)` ;
- `resolve_journey_readiness(..., viewer=request.user)` ;
- JourneyRequest ;
- Commerce/Payments existants ;
- Access existant ;
- FormRequest existant ;
- Service Requirement Assessment lorsqu'il existe ;
- Occurrence Live participant lorsqu'il existe.

La projection distingue explicitement :

```text
ready
actor_interventions
waiting
blockers
next
```

Ainsi :

```text
waiting ≠ blocked
ready ≠ completed
Readiness ≠ Journey.status
Readiness ≠ progress
```

Les Journeys terminées restent ouvrables par leur bénéficiaire tant que le selector participant les autorise.

## 4. Requirement

Z5 ne crée aucun Requirement universel.

La profondeur livrée est actuellement celle d'un `ServiceRequirementAssessment` appartenant à une Journey Service visible par le bénéficiaire.

Le payload expose :

- identité de l'assessment et du Requirement ;
- kind, label, description et caractère obligatoire ;
- état canonique de l'assessment ;
- conséquence dérivée par `derive_requirement_consequence()` ;
- moyens structurels déjà reliés (par exemple Payment obligation ou JourneyStep).

Il n'expose pas :

```text
assessment.note
review_note
private evidence
form answers
assessed_by
raw evaluator metadata
```

Un PersonalAsset, JourneyArtifact, Proof ou Credential existant ne change jamais à lui seul l'état de satisfaction.

## 5. Activity et Occurrence

Les détails owner-domain sont distincts du détail exploratoire Z3.

Une Activity publique non-draft/non-archived peut être ouverte publiquement. Une Activity privée n'est ouverte que par son propriétaire ou une autorité Activity canonique.

La relation personnelle réutilise :

```text
participant_state_context_for_activities()
participant_state_context()
resolve_participant_activity_state()
```

Flutter ne recompose donc pas Journey + Access + Commerce + Payment.

Occurrence conserve strictement la temporalité canonique :

- date-only reste date-only ;
- aucune heure `00:00` n'est inventée ;
- cancelled/completed restent des états explicites.

Le lien Live n'est exposé que si `resolve_participant_occurrence_live()` fournit réellement une perspective participant.

## 6. Capacity

Z5 ne crée pas d'endpoint Capacity universel.

Activity/Occurrence projettent seulement les agrégats autorisés de `CapacityAvailability` :

```text
total
available
unlimited
sold_out
```

Ne sont jamais exposés dans cette projection :

```text
held
committed
identité des réservants
réservations tierces
Placement
Live Queue
```

Une lecture de disponibilité ne réserve rien. Les mutations Capacity restent atomiques dans le domaine propriétaire.

## 7. Dossier

`objective.dossier.detail` consomme `resolve_dossier_readiness(dossier, viewer=request.user)`.

La projection conserve :

- état collectif ;
- `partial` ;
- signal caché privacy-safe ;
- items visibles ;
- dépendances visibles ;
- responsabilité personnelle ;
- prochaine intervention personnelle uniquement lorsqu'elle vient du resolver.

Une dépendance cachée peut influencer l'état collectif sans jamais révéler :

```text
hidden Journey id
hidden title
hidden Profile
hidden Requirement
hidden URL
```

Assignment reste une responsabilité et n'accorde aucune autorité.

## 8. Project

`objective.project.detail` expose l'horizon durable et seulement les Dossiers visibles.

Il n'introduit jamais :

```text
Task
Kanban
milestone artificiel
completion percentage
Project Readiness synthétique
```

Dossier et Project restent distincts.

## 9. Access

`personal.access.detail` consomme `participant_accesses_visible_to_buyer(request.user)`.

Deux relations sont distinguées :

```text
beneficiary
purchased_for_other
```

La visibilité transactionnelle de l'acheteur ne le transforme jamais en bénéficiaire et ne lui ouvre pas la Journey privée du titulaire.

Le détail général Access n'expose jamais :

```text
AccessCredential.public_id
QR payload
signed token
barcode payload
AccessUse actor data
```

Access, AccessCredential et AccessUse restent trois réalités distinctes.

## 10. Capabilities et links

Z5 n'annonce une capability que lorsque le serveur connaît réellement l'action et que le handoff est consommable.

Dans la v1, le principal handoff explicitement exposé est `open_live` lorsqu'Operations confirme la perspective participant.

Les mutations qui n'ont aujourd'hui qu'une surface Web ne sont pas maquillées en capabilities Flutter. Le détail Journey lie les APIs existantes Preparation, Questionnaire, Payment et les nouveaux détails owner-domain sans copier leur contenu profond.

## 11. Confidentialité et IDOR

Règle personnelle :

```python
get_object_or_404(participant_scoped_queryset(request.user), pk=id)
```

Dossier/Project utilisent leurs selectors Objectives visibles.

Activity/Occurrence filtrent la visibilité avant le lookup UUID.

Le contrat de tests couvre notamment :

- Journey d'un autre Profile → 404 ;
- Access d'un tiers → 404 ;
- buyer autorisé mais bénéficiaire distinct ;
- Activity/Occurrence privées → 404 hors scope ;
- Dossier/Project hors scope → 404 ;
- Assignment seul → aucune autorité ;
- dépendance cachée Dossier → influence opaque sans fuite ;
- AccessCredential absent des payloads ;
- PersonalAsset existant ≠ Requirement satisfait.

## 12. Invariants fermés

```text
Profile ≠ rôle global
Assignment = responsabilité
Mandate/Permission = autorité
Readiness = projection dérivée
Requirement ≠ Form ≠ Resource ≠ Artifact ≠ Proof ≠ Credential
Access ≠ AccessCredential ≠ AccessUse
Capacity = combien ?
Placement = où ?
Waitlist ≠ Live Queue
JourneyStep ≠ Checkpoint
Dossier ≠ Project
buyer ≠ beneficiary
waiting ≠ blocked
ready ≠ completed
unknown ≠ absent ≠ false
```

## 13. Fichiers Z5

```text
core/api/detail_projections.py
core/api/detail_views.py
core/api/detail_urls.py
activities/api_views.py
activities/api_urls.py
activities/occurrence_api_urls.py
objectives/api_views.py
objectives/api_urls.py
core/test_z5_detail_api.py
config/urls.py
docs/architecture/z5-engaged-detail-projections.md
```

## 14. Migration

Z5 ne nécessite aucune migration et ne crée aucun backfill.

## 15. Critère de merge

La branche Z5 n'est mergée que si :

- checks Django verts ;
- `makemigrations --check --dry-run` vert ;
- tests Z5 ciblés verts ;
- suites CI pertinentes vertes ;
- aucun secret/credential/private evidence ne fuit ;
- la branche est reconciliée avec le `main` courant ;
- la PR reste mergeable.
