# Makolo Services — Services, Opportunities et parcours d'accompagnement

> **Statut : canonique pour la cible Makolo Services.** Ce document complète [`makolo-domain-blueprint.md`](makolo-domain-blueprint.md). Le blueprint reste la source d'architecture globale ; le présent document précise la verticale Services, le domaine Opportunity et les extensions nécessaires à Journey/Payment. Toute implémentation doit conserver les invariants du blueprint et l'état réel du code courant. Les primitives horizontales de Requirements sont définies avec [`subscriptions-entitlements-requirements.md`](subscriptions-entitlements-requirements.md) et consommées ici sans déplacer les agrégats Services/Opportunity.

## 1. Intention produit

Makolo Services ne doit pas devenir un énième catalogue d'offres d'emploi, de bourses ou de programmes. Sa responsabilité est d'aider une personne à **accomplir réellement une démarche**, malgré les documents manquants, échéances, validations, paiements, contraintes externes et autres aléas qui séparent une opportunité de son résultat.

La formule fonctionnelle est :

- **Opportunity** : où la personne veut arriver ;
- **Service Activity** : l'aide qu'un Profil ou un Espace opère réellement ;
- **Journey** : le parcours individuel ;
- **Requirement** : ce qui est exigé par l'opportunité ;
- **JourneyStep** : ce qu'il faut faire ;
- **JourneyBlocker** : ce qui empêche d'avancer ;
- **JourneyArtifact** : ce qui est fourni ou produit ;
- **JourneyAssignment** : qui travaille sur le dossier ;
- **Mandate** : pourquoi cette personne a le droit d'agir ;
- **PaymentObligation** : ce qui doit être payé ;
- **Payment** : une transaction réellement traitée par Makolo/provider ;
- **PaymentEvidence** : la preuve d'un paiement effectué hors Makolo ;
- **ServiceSubmission** : la soumission réelle au tiers ;
- **ServiceOutcomeEvent** : ce que le tiers décide ensuite.

La cible V1 est une solution complète et exploitable. Les intégrations IA, M-PESA réel, autres providers réels et l'abonnement/feature gating Makolo sont hors de cette V1, mais les interfaces doivent permettre de les ajouter sans refaire les modèles métier.

## 2. Frontières de domaine

### `services`

Verticale composée au-dessus d'Activity/Journey. Elle porte :

- `ServiceDetails` ;
- templates de plan et intake ;
- `ServiceJourneyContext` ;
- évaluations de requirements ;
- preuves de requirements ;
- soumissions externes ;
- résultats externes.

Elle ne possède ni identité, ni permission, ni Payment provider, ni Access, ni Place, ni CommerceOrder.

### `opportunities`

Bounded context des possibilités externes : emploi, bourse, stage, admission, concours, programme, financement, volontariat, etc. Il porte leur identité, révisions, sources, exigences, géographie, sauvegardes et propositions utilisateur.

Une Opportunity n'est pas une Activity Makolo par défaut : son émetteur externe reste distinct de l'opérateur du service Makolo.

### `requirements`

Kernel horizontal de mécanique commune. Il porte le vocabulaire d'état, les modes, le résultat d'évaluation et le registre d'evaluators code-controlled. Il ne possède ni `OpportunityRequirement`, ni `ServiceRequirementAssessment`, ni un modèle cible polymorphe universel.

### `journeys`

Reste le propriétaire de la Démarche et reçoit les primitives génériques nécessaires aux parcours longs :

- `JourneyStep` ;
- `JourneyStepDependency` ;
- `JourneyAssignment` ;
- `JourneyStepAssignment` ;
- `JourneyBlocker` ;
- `JourneyArtifact` ;
- `JourneyArtifactReview` ;
- `JourneyNote`.

Ces primitives sont génériques et peuvent servir à d'autres verticales lorsqu'elles ont le même sens métier.

### `payments`

Reste le propriétaire des transactions provider, refunds, événements provider et idempotence. Il reçoit `PaymentObligation` et `PaymentEvidence` afin de représenter aussi les obligations financières qui ne sont pas une vente Makolo.

### `authorization`

Reste le propriétaire de Role/Permission/Mandate. Aucune portée `JOURNEY` n'est ajoutée dans la cible actuelle : l'autorité Services reste Activity-scoped et l'affectation dossier est séparée.

## 3. Composition Service Activity

### `ServiceDetails`

`ServiceDetails` spécialise une `Activity` par `OneToOneField`.

Champs cibles :

| Champ | Contrat |
|---|---|
| `activity` | OneToOne vers Activity |
| `service_kind` | `application_support`, `career_support`, `education_guidance`, `document_support`, `administrative_support`, `interview_preparation`, `orientation`, `other` |
| `opportunity_policy` | `required`, `optional`, `none` |
| `intake_policy` | `auto_confirm`, `review_required` |
| `allows_external_beneficiary` | booléen |
| `completion_policy` | enum contrôlé, pas moteur arbitraire |
| timestamps | audit |

`ServiceDetails` ne duplique pas prix, paiement, participant, facilitateur, permissions, lieux ou capacité.

## 4. Templates de parcours

Une solution exploitable ne doit pas reconstruire chaque dossier à la main.

### `ServicePlanTemplate`

Lie un template versionné à un ServiceDetails :

- `service` ;
- `key` métier stable ;
- `version` ;
- `name` ;
- `status = draft | published | retired` ;
- `created_by` ;
- timestamps.

Contrainte : `service + key + version` unique.

Une version publiée est structurellement immuable. Une évolution crée une nouvelle version.

### `ServicePlanTemplateStep`

Snapshot réutilisable d'une étape : titre, description, `kind`, position, caractère obligatoire et délai relatif éventuel.

Kinds initiaux :

`action`, `document`, `review`, `payment`, `meeting`, `submission`, `follow_up`, `decision`, `other`.

### `ServicePlanTemplateStepDependency`

Décrit les dépendances entre étapes du template. Les cycles sont interdits.

Au démarrage opérationnel d'une Journey, le template est matérialisé en véritables `JourneyStep`/`JourneyStepDependency`. Une modification future du template ne réécrit jamais un dossier existant.

## 5. Intake structuré

### `ServiceIntakeQuestion`

Question attachée au service ou à une version de template.

Types contrôlés :

`short_text`, `long_text`, `boolean`, `date`, `single_choice`, `multiple_choice`.

Les fichiers ne sont jamais stockés dans une réponse d'intake : ils passent par `JourneyArtifact`.

### `ServiceIntakeAnswer`

Lie `Journey + ServiceIntakeQuestion + valeur`. Une valeur JSON validée par type est acceptable car elle représente ici une valeur de formulaire variable, pas une relation métier polymorphe.

Les réponses constituent un snapshot historique du dossier.

## 6. Journey Services

Une demande complète Makolo Services reste une `Journey`. Il n'existe pas de `ServiceRequest` parallèle.

### Workflow

Ajouter `WorkflowKind.SERVICE`.

### État global

Ajouter `JourneyStatus.IN_PROGRESS` et `started_at`.

Cycle normal :

```text
draft
  -> submitted
  -> [pending_approval -> approved]
  -> [pending_payment]
  -> confirmed
  -> in_progress
  -> fulfilled
```

Sorties terminales : `rejected`, `cancelled`, `expired`.

`pending_payment` reste un état global uniquement lorsqu'un paiement conditionne la confirmation de toute la Journey. Un paiement apparaissant au milieu d'un dossier bloque l'étape concernée sans faire quitter `in_progress` à la Journey.

### Sémantique de `fulfilled`

`fulfilled` signifie que Makolo a accompli le résultat contractuel de la Journey, par exemple préparer et soumettre correctement un dossier. Il ne signifie pas que le recruteur, l'université ou un autre tiers a accepté la personne.

## 7. `JourneyStep`

Champs cibles :

- `journey` ;
- `kind` ;
- `title` ;
- `description` ;
- `status = pending | ready | in_progress | blocked | completed | skipped | cancelled` ;
- `position` ;
- `is_required` ;
- `due_at` nullable ;
- `occurrence` nullable pour un rendez-vous réellement opéré dans Makolo ;
- `origin = manual | template | automation | future_ai` ;
- `started_at`, `completed_at`, `skipped_at`, `cancelled_at` ;
- `created_by` nullable pour automation ;
- timestamps.

`overdue` est dérivé de `due_at` et du statut ; ce n'est pas un état persistant.

### Transitions

Parcours normal : `pending -> ready -> in_progress -> completed`.

Branches :

- `ready|in_progress -> blocked` ;
- `blocked -> ready|in_progress` selon la présence de `started_at` ;
- non terminal -> `skipped` avec raison et autorité suffisante ;
- non terminal -> `cancelled`.

`pending -> ready` peut être automatique quand toutes les dépendances requises sont satisfaites.

Une étape ne peut pas devenir `completed` si un blocker actif la concerne ou si une obligation nécessaire à cette étape reste insatisfaite.

## 8. Dépendances et affectations

### `JourneyStepDependency`

`step -> depends_on`, avec contraintes : même Journey, pas d'auto-référence, couple unique, cycles interdits par service de domaine.

### `JourneyAssignment`

Affectation opérationnelle au dossier :

- `journey` ;
- `profile` ;
- `responsibility = lead | facilitator | reviewer | support` ;
- `status = active | ended | cancelled` ;
- `is_primary` ;
- `assigned_by`, `assigned_at`, `ended_at`.

Une seule affectation lead primaire active par Journey.

### `JourneyStepAssignment`

Affectation ciblée à une étape. Elle organise le travail, mais ne donne aucune permission.

**Invariant : Mandate = autorité ; Assignment = responsabilité opérationnelle.**

## 9. Aléas

### `JourneyBlocker`

Champs :

- `journey` ;
- `step` nullable ;
- `category = missing_document | eligibility | external_dependency | administrative | technical | logistics | financial | deadline | other` ;
- `severity = low | medium | high | critical` ;
- `title`, `description` ;
- `status = active | resolved | waived` ;
- `responsible_profile` nullable ;
- `detected_by`, `detected_at`, `due_at` ;
- `resolved_by`, `resolved_at`, `resolution_note`.

Créer un blocker actif lié à une étape peut la passer à `blocked`. Résoudre/waiver le dernier blocker actif recalcule l'état de l'étape.

Un blocker n'est jamais supprimé pour effacer l'historique et ne devient pas un JourneyStatus global.

## 10. Documents, versions et reviews

### `JourneyArtifact`

Champs :

- `journey`, `step` nullable ;
- runtime actuel : `kind = cv | cover_letter | certificate | transcript | recommendation | identity_document | form | payment_receipt | other` ;
- `title` ;
- fichier via stockage privé ;
- `status = draft | submitted | in_review | accepted | rejected | superseded` ;
- `sensitivity = normal | sensitive | restricted` ;
- `supersedes` nullable ;
- `version` ;
- `uploaded_by`, `uploaded_at` ;
- taille, MIME, hash pour contrôle technique.

Le vocabulaire cible avait envisagé `submission_receipt`, mais ce kind n'existe pas dans le noyau Journey T31 actuellement mergé. T33 ne crée pas un stockage ou un modèle parallèle : `ServiceSubmission.receipt_artifact` référence un `JourneyArtifact` de la même Journey, et les nouveaux reçus de soumission utilisent `other` tant qu'un vocabulaire Journey plus précis n'est pas introduit explicitement dans le noyau.

Un remplacement crée une nouvelle version ; le fichier précédent n'est pas écrasé.

### `JourneyArtifactReview`

Lie un artifact à un reviewer :

`requested | in_progress | approved | changes_requested | cancelled`, avec requester, reviewer, commentaire, dates et audit.

### `JourneyNote`

Note textuelle liée à Journey, éventuellement à Step :

- `visibility = beneficiary_visible | internal` ;
- `author` ;
- `body` ;
- timestamps.

Une note interne n'est jamais exposée au bénéficiaire. Les fichiers ne passent pas par JourneyNote.

## 11. Opportunity : identité et révisions

### `Opportunity`

Porte l'identité durable :

- `kind = job | scholarship | internship | education | grant | competition | program | volunteering | other` ;
- `publication_status = draft | published | withdrawn | archived | merged` ;
- `current_revision` ;
- `merged_into` nullable ;
- `created_by`, `published_at`, timestamps.

L'état temporel `upcoming | open | closed` est dérivé des dates de la révision courante, pas stocké comme un second workflow de publication.

### `OpportunityRevision`

Une révision publiée est immuable. Toute correction crée une nouvelle version.

Champs :

- `opportunity`, `version` ;
- `title`, `summary`, `issuer_name` ;
- `opens_at`, `deadline_at`, timezone ;
- `application_instructions` ;
- `remote_allowed` nullable ;
- `change_summary` ;
- `created_by`, `created_at`.

Contrainte : `opportunity + version` unique.

Cette versioning garantit que Makolo peut expliquer exactement quelles conditions étaient en vigueur lorsque le dossier a été préparé.

## 12. Géographie, sources et contrôle des changements

### `OpportunityZone`

Lie une OpportunityRevision à une `Zone` avec `role = location | eligibility`.

Une localisation du poste et une zone d'éligibilité restent des concepts distincts.

### `OpportunitySource`

Champs :

- `opportunity` ;
- `source_type = official | trusted_partner | aggregator | user_supplied` ;
- `source_name`, `url`, `external_reference` nullable ;
- `is_primary` ;
- `status = active | changed | unreachable | removed` ;
- `last_checked_at`, `verified_at`, `verified_by`.

Une seule source primaire active.

### `OpportunitySourceCheck`

Historique append-only d'un contrôle de source :

`unchanged | changed | unreachable | removed`, date, auteur éventuel, fingerprint éventuel, note.

Un changement détecté ne réécrit jamais silencieusement l'Opportunity : après revue, une nouvelle OpportunityRevision est créée si nécessaire.

## 13. Requirements

La mécanique générique est fournie par le kernel horizontal `requirements`, tandis que les modèles persistants restent propriétaires de leurs domaines.

### `OpportunityRequirement`

Lié à une OpportunityRevision.

Types :

`eligibility`, `education`, `experience`, `document`, `language`, `location`, `age`, `financial`, `deadline`, `other`.

Porte titre, description, obligatoire et position. Cette taxonomie `kind` reste spécifique à Opportunity et ne doit pas être confondue avec `RequirementMode`, qui décrit le mécanisme de satisfaction d'une condition.

Un frais de candidature est donc d'abord un requirement financier de l'Opportunity, pas une Offer Makolo.

T34A n'ajoute pas de champ `mode` à `OpportunityRequirement` simplement pour utiliser l'enum horizontal : le runtime historique ne permet pas de déduire sans ambiguïté un mode pour chaque Requirement existant.

### `ServiceRequirementAssessment`

Lie un `ServiceJourneyContext` à un Requirement de la révision pinnée. La colonne persistante reste nommée `status`, mais son contrat est désormais `RequirementAssessmentState` :

```text
unassessed
pending
satisfied
unsatisfied
not_applicable
```

Sémantique :

- `unassessed` : la condition n'a pas encore été évaluée ;
- `pending` : sa vérité terminale n'est pas encore établie, par exemple en attente d'action, preuve, revue, paiement ou réponse externe ;
- `satisfied` : condition satisfaite ;
- `unsatisfied` : condition constatée non satisfaite, sans conséquence Journey automatique ;
- `not_applicable` : condition non applicable au dossier.

Les anciens pseudo-states T32 sont historiques. T34A les normalise en place :

```text
unassessed      → unassessed
satisfied       → satisfied
action_required → pending
needs_review    → pending
not_applicable  → not_applicable
not_eligible    → unsatisfied
```

Les conséquences `action_required`, `needs_review`, `payment_required` et `not_eligible` ne sont plus stockées comme states. Services les dérive des propriétaires canoniques : JourneySteps actionnables, Evidence soumise, PaymentObligations non satisfaites et nature du Requirement. Il n'existe pas de seconde colonne persistante `next_action` pouvant diverger.

Pour la completion des Requirements obligatoires, seuls `satisfied` et `not_applicable` satisfont la condition. `unassessed`, `pending` et `unsatisfied` bloquent la completion concernée ; `unsatisfied` ne transforme jamais automatiquement la Journey en `rejected`.

### `ServiceRequirementEvidence`

Lie une Assessment à un `JourneyArtifact` avec `submitted | accepted | rejected`.

Ces états décrivent la preuve, pas l'Assessment. Plusieurs pièces peuvent soutenir un Requirement ; une même pièce peut soutenir plusieurs Requirements via plusieurs relations explicites.

Une Evidence `submitted` sur une Assessment `pending` peut produire la conséquence dérivée `needs_review`. Une preuve acceptée/rejetée ne change l'Assessment que via les services métier qui possèdent cette décision ; les deux modèles ne sont pas fusionnés.

### `ServiceRequirementStepLink`

Conserve la relation explicite entre Assessment et JourneyStep. Une Step actionnable reliée à une Assessment `pending` peut produire la conséquence dérivée `action_required`. Assessment et JourneyStep restent deux responsabilités différentes.

### Requirement financier

Pour un Requirement `financial`, T33 compose l'Assessment avec Payments via `ServiceRequirementPaymentObligation`. Ce bridge appartient à `services` et relie explicitement `ServiceRequirementAssessment ↔ PaymentObligation`; `payments` ne dépend donc pas du domaine Opportunity. Plusieurs obligations peuvent être reliées à une même Assessment si le métier l'exige ultérieurement, sans imposer une cardinalité one-to-one artificielle.

T34A fixe la synchronisation :

```text
au moins une obligation requise non satisfied/waived
→ Assessment = pending
→ conséquence dérivée possible = payment_required

toutes les obligations liées satisfied/waived
→ Assessment = satisfied
```

Un Payment échoué mais retryable ne rend donc pas l'Assessment `unsatisfied`. Une PaymentEvidence externe seulement `submitted` ne la satisfait pas ; lorsque la preuve est vérifiée et que l'obligation devient `satisfied`, le bridge Services peut faire passer l'Assessment à `satisfied`, sans créer de faux Payment.

### Kernel horizontal

`requirements` fournit `RequirementMode`, `RequirementAssessmentState`, `RequirementEvaluationResult` et `EvaluatorRegistry`. Il ne connaît ni Services, ni Opportunities, ni Payments, ni Journeys et ne persiste aucune Assessment universelle. Les evaluators sont enregistrés par le code ; leur configuration valide uniquement des paramètres/opérateurs connus et ne peut exécuter ni Python, ni SQL, ni JavaScript, ni import path venant des données.

## 14. Découverte, sauvegarde et proposition utilisateur

### `OpportunitySave`

Relation `Profile + Opportunity`, unique, permettant de retrouver une opportunité sans créer prématurément une Journey.

### `OpportunitySubmission`

Permet à un utilisateur d'apporter une URL ou une opportunité inconnue.

Cycle : `pending -> under_review -> accepted | rejected | duplicate`.

Une soumission acceptée crée ou rejoint une Opportunity canonique.

La curation/publication initiale des Opportunities reste une capacité plateforme Makolo ; ouvrir plus tard la publication directe aux employeurs/universités devra réutiliser Space/Mandate plutôt qu'introduire une autorité parallèle.

## 15. `ServiceJourneyContext`

OneToOne avec Journey :

- `journey` ;
- `opportunity` nullable selon `opportunity_policy` ;
- `opportunity_revision` pinnée ;
- `service_plan_template` version utilisée ;
- `objective` ;
- `current_outcome` ;
- timestamps.

Si la révision courante de l'Opportunity change, le dossier reste sur sa révision historique. Makolo avertit qu'une nouvelle version existe ; l'adoption d'une nouvelle révision est explicite et auditée. L'adoption est monotone sous verrouillage : une concurrence entre plusieurs révisions publiées ne doit jamais faire régresser le dossier vers une version plus ancienne.

Une Journey Services peut exister sans Opportunity, par exemple pour « refaire mon CV ».

## 16. Soumission externe et résultat tiers

### `ServiceSubmission`

Conserve les tentatives réelles vers le tiers :

- `context`, `attempt` ;
- `mode = external_web | email | in_person | makolo_integrated | other` ;
- `status = prepared | submitted | acknowledged | failed | withdrawn` ;
- `submitted_at`, `external_reference` ;
- `receipt_artifact` nullable ;
- `submitted_by`, `failure_reason`.

Plusieurs tentatives peuvent exister sans perdre l'historique. `(context, attempt)` est unique et le prochain numéro est réservé sous verrou transactionnel du contexte afin d'éviter deux `attempt=2` concurrents. Une tentative `failed` ne redevient pas `submitted` ; un retry crée une nouvelle tentative.

La completion policy historique `required_steps` reste compatible avec les Services T31. La policy opt-in `required_steps_and_submission` exige les étapes requises puis au moins une `ServiceSubmission` réellement `submitted` ou `acknowledged`. Elle n'exige jamais un résultat externe `successful` pour considérer le travail Makolo accompli.

### `ServiceOutcomeEvent`

Historique append-only du résultat externe :

`submitted`, `acknowledged`, `under_review`, `action_required`, `interview`, `successful`, `unsuccessful`, `withdrawn`, `other`.

Chaque événement porte date externe, date d'enregistrement, auteur, note et référence éventuelle.

`ServiceJourneyContext.current_outcome` est une projection transactionnelle pour les requêtes. La projection est déterminée par `occurred_at`, puis par un tie-breaker stable (`created_at`, `id`) ; l'ordre d'insertion ne suffit pas. Enregistrer tardivement un événement historiquement plus ancien ne fait pas régresser `current_outcome`.

Les transitions `ServiceSubmission -> submitted|acknowledged|withdrawn` alimentent la même timeline externe via `ServiceOutcomeEvent`, ce qui évite deux sources de vérité concurrentes : la Submission décrit la tentative, l'OutcomeEvent décrit l'évolution externe, et `current_outcome` reste la projection de lecture.

**Invariant : `Journey.status = fulfilled` et `current_outcome = unsuccessful` sont compatibles.** Makolo peut avoir accompli correctement le parcours même si un tiers refuse la candidature. Réciproquement, un résultat externe `successful` ne passe jamais automatiquement la Journey à `fulfilled`.

## 17. Paiements : `PaymentObligation`

### Définition

`PaymentObligation` représente une somme qui doit être réglée dans un contexte Makolo afin de satisfaire une obligation métier. Elle appartient au bounded context `payments`.

Champs implémentés T33 :

- `journey` ;
- `commerce_order` nullable ;
- `step` nullable ;
- `reason = commerce | opportunity_requirement | service_process | access_requirement | other` ;
- `label` ;
- `amount`, `currency` ;
- `processing_mode = makolo_provider | external` ;
- `status = pending | processing | satisfied | waived | expired | cancelled | refunded` ;
- `payee_space` nullable ;
- `payee_profile` nullable ;
- `external_payee_name` nullable ;
- `due_at`, `satisfied_at` ;
- `source_key` nullable pour provenance/idempotence ;
- `created_by`, timestamps.

Pour les nouvelles données, le bénéficiaire économique doit être explicite. Makolo n'est pas automatiquement le bénéficiaire parce que la transaction passe par sa plateforme ou son provider. Les codes devise sont normalisés en majuscules et les obligations exigent un montant strictement positif.

### Paiement traité par Makolo/provider

Une obligation `makolo_provider` peut avoir plusieurs `Payment` attempts. Un seul paiement `succeeded` peut la satisfaire, garanti par contrainte DB. Une tentative `failed` ou `cancelled` ne détruit pas l'obligation et permet une nouvelle tentative ; l'obligation revient à `pending` lorsqu'aucune autre tentative active ne la maintient en traitement.

Exemple commercial :

`Offer -> CommerceOrder -> PaymentObligation -> Payment -> confirmation -> Access`.

Exemple Opportunity :

`OpportunityRequirement -> Assessment -> JourneyStep -> PaymentObligation -> Payment -> étape satisfaite`.

Le pipeline T33 introduit un contrat provider minimal centralisant `initiate`, `confirm`, `cancel` et `refund`. Les adapters réellement présents sont `sandbox` et `manual`. Le sandbox existant est réutilisé pour Commerce/Event et Services ; aucun second sandbox n'est créé. M-PESA, Airtel Money et autres providers réels restent différés.

`manual` reste un provider transactionnel contrôlé par l'autorité financière existante. Il ne doit jamais être utilisé pour transformer un paiement réellement effectué sur le portail d'un tiers en faux Payment réussi.

### Compatibilité Commerce/Tickets

T33 applique une migration expand-compatible : `Payment.order` et `Payment.commerce_order` restent en place, et `Payment.obligation` est ajouté de façon nullable. Un Payment peut donc temporairement porter les relations legacy et l'obligation lorsque ces références décrivent le même contexte canonique.

Les nouveaux paiements Commerce/Event payants obtiennent ou créent une obligation Commerce déterministe avant la tentative Payment. Le backfill ne matérialise une obligation historique que lorsque Journey, montant, devise et bénéficiaire économique peuvent être déduits objectivement. Aucune transaction, réussite ou payee n'est inventé.

`PaymentObligation.commerce_order` reste nullable et utilise `SET_NULL` : cette décision préserve l'obligation et son historique lorsqu'un test/mécanisme de compatibilité reconstruit une ancienne projection Commerce. Les nouveaux writes Commerce conservent néanmoins la relation explicite. Les relations legacy seront supprimées, si nécessaire, uniquement lors d'un futur cutover observé et séparé.

### JourneyStep de paiement

Le noyau `journeys` ne dépend pas de Payments. La verticale Services compose `JourneyStep(kind=payment)` et vérifie, avant completion, que les obligations reliées sont `satisfied` ou `waived`. Une condition financière non encore remplie n'est pas automatiquement transformée en `JourneyBlocker` : le blocker reste réservé à un véritable aléa métier.

Un paiement intermédiaire ne modifie jamais artificiellement la Journey globale en `pending_payment`; cet état reste réservé au paiement qui conditionne la confirmation/démarrage de la Journey entière.

### Paiement fait hors Makolo

Aucun faux `Payment(status=succeeded)` n'est créé.

`PaymentEvidence` porte :

- `obligation` ;
- `artifact` reçu/preuve ;
- `external_reference` nullable ;
- `paid_at` ;
- `status = submitted | verified | rejected` ;
- `submitted_by`, `verified_by`, `verified_at`, `review_note`.

Une preuve est réservée à une obligation `processing_mode=external` et son Artifact doit appartenir à la même Journey. Une preuve vérifiée satisfait l'obligation transactionnellement sans créer de transaction provider Makolo. Une preuve rejetée et son Artifact restent audités ; une nouvelle preuve peut être soumise selon le lifecycle autorisé.

### Refunds et settlement

Refund conserve son domaine existant pour les transactions réellement traitées. Le runtime T33 conserve le comportement de remboursement total existant ; il n'invente pas de remboursement partiel si le modèle courant ne le supporte pas. Une obligation devient `refunded` lorsque le Payment qui l'avait satisfaite est réellement remboursé selon le service canonique.

Les mécanismes futurs de payout/settlement dépendent du provider financier réel et ne doivent pas être inventés avant intégration d'un provider qui les exige.

## 18. Permissions et confidentialité

### Pas de Mandate Journey

Les portées restent Platform/Space/Group/Activity. L'autorité Services est Activity-scoped ; l'affectation au dossier est `JourneyAssignment`.

### Permissions Activity Services

Codes cibles :

- `activity.services.configure` ;
- `activity.services.cases.view_all` ;
- `activity.services.cases.view_assigned` ;
- `activity.services.cases.manage` ;
- `activity.services.assignments.manage` ;
- `activity.services.steps.manage` ;
- `activity.services.blockers.manage` ;
- `activity.services.artifacts.view` ;
- `activity.services.artifacts.manage` ;
- `activity.services.artifacts.restricted_view` ;
- `activity.services.reviews.manage` ;
- `activity.services.notes.internal` ;
- `activity.services.outcomes.manage` ;
- `activity.services.payment_evidence.verify`.

Ces codes constituent la matrice finale visée pour **T34B** ; T34A ne les crée pas. En attendant, les writes réutilisent la frontière déjà disponible : bénéficiaire pour ses propres actions explicitement permises, ou autorité Activity existante combinée à une `JourneyAssignment` active pour le travail sur dossier. Les opérations financières sensibles, la confirmation manuelle, les refunds et la vérification de preuves restent deny-by-default hors staff/autorité financière ou de dossier explicite disponible.

Les données financières provider, refunds et opérations financières complètes continuent d'utiliser les permissions Finance canoniques.

### Rôles système

- **Service Manager** : configuration, supervision, affectations et dossiers de l'Activity ;
- **Service Facilitator** : dossiers où une JourneyAssignment active existe ;
- **Service Reviewer** : reviews/dossiers affectés selon permissions.

Ces rôles sont Activity-scoped, jamais des flags sur User.

### Accès dossier

Un bénéficiaire peut accéder à son propre dossier dans les limites des données qui lui sont destinées.

Un manager peut voir tous les dossiers seulement avec `view_all`.

Un facilitateur/reviewer doit réunir :

`Mandate Activity valide + permission requise + JourneyAssignment active`.

TeamMembership seule, JourneyAssignment seule ou appartenance au même Space ne suffisent pas.

### Documents sensibles

Les Artifacts Services sont privés par défaut. `restricted` couvre notamment les pièces d'identité et documents particulièrement sensibles.

Le téléchargement passe par un endpoint autorisé ; aucune URL publique permanente. Les notifications n'incluent pas le contenu sensible et les logs techniques ne doivent pas contenir le contenu des fichiers.

## 19. Permissions Opportunity

Portée plateforme initiale :

- `opportunities.manage` ;
- `opportunities.review_submissions` ;
- `opportunities.sources.verify` ;
- `opportunities.merge`.

Les Opportunities publiées sont consultables selon leur visibilité sans abonnement Makolo.

## 20. Domain Events et Automation

Les transitions passent par des services transactionnels et émettent des faits stables. Types cibles au minimum :

- `journey.in_progress` ;
- `journey.step.ready|started|completed|blocked` ;
- `journey.blocker.created|resolved` ;
- `journey.assignment.created|ended` ;
- `journey.artifact.created` ;
- `journey.artifact.review_requested|completed` ;
- `payment.obligation.created|satisfied` ;
- `payment.evidence.submitted|verified|rejected` ;
- `opportunity.revision.published` ;
- `opportunity.source.changed` ;
- `opportunity.withdrawn` ;
- `service.submission.submitted` ;
- `service.outcome.changed`.

T33 ajoute également les faits stables de lifecycle effectivement nécessaires (`payment.obligation.refunded`, et les événements `service.submission.acknowledged|failed|withdrawn` lorsqu'une transition correspondante a lieu) via la même outbox canonique. Les payloads restent minimaux et ne doivent jamais contenir de secret provider, token, donnée bancaire complète ou contenu d'Artifact.

Notifications et Automation consomment ces faits ; elles ne modifient jamais les modèles en contournant les services de domaine.

Les rappels peuvent exploiter : opening/deadline Opportunity, Journey expiration, Step due date, Blocker due date, PaymentObligation due date et Occurrence. Les notifications doivent être dédupliquées et ne plus rappeler une condition déjà satisfaite. Le branchement Notifications/Automation Services final est **T34B**. T34A n'ajoute pas une avalanche d'événements Requirements ; il change seulement le contrat d'état consommé par Services.

## 21. Surfaces fonctionnelles requises en V1

### Participant

- découverte/recherche/filtrage des Opportunities ;
- détail avec sources, dates, requirements et géographie ;
- sauvegardes ;
- proposition d'une Opportunity inconnue ;
- démarrage d'une Journey Services ;
- intake ;
- dossier global ;
- évaluations des requirements ;
- étapes et prochaines actions ;
- blockers ;
- documents/versioning/review ;
- paiements provider sandbox et preuves externes ;
- rendez-vous/Occurrences ;
- notes visibles ;
- timeline ;
- soumissions externes ;
- suivi du résultat tiers.

### Facilitateur

- mes dossiers ;
- attention : deadlines, blockers, reviews, inactivité ;
- dossier complet autorisé ;
- plan/étapes/dépendances ;
- requirements et preuves ;
- documents/reviews ;
- blockers ;
- rendez-vous ;
- obligations de paiement dans sa portée ;
- notes internes/visibles ;
- soumissions ;
- outcomes.

### Service Manager / Espace

- configuration des Activities Services ;
- templates et intake ;
- équipe/Mandates ;
- charge/affectations ;
- dossiers à risque ;
- analytics opérationnels sans élargissement des PII.

### Staff Makolo

- inbox OpportunitySubmission ;
- curation ;
- sources et SourceChecks ;
- révisions ;
- publication/retrait/archive ;
- déduplication/fusion ;
- changements critiques touchant des Journey actives.

## 22. Analytics

Mesures minimales :

- volume de Journey Services ;
- taux de démarrage et d'accomplissement ;
- temps jusqu'à fulfillment ;
- temps par étape ;
- blockers par catégorie/sévérité ;
- échéances manquées ;
- Opportunity -> Journey ;
- Journey -> ServiceSubmission ;
- résultats externes ;
- charge des facilitateurs ;
- reviews ;
- obligations de paiement créées/satisfaites/échouées ;
- paiements provider vs preuves externes.

**Le taux d'accomplissement Makolo et le taux de succès externe sont deux métriques distinctes.**

## 23. Invariants Services

1. Une demande complète de service est une Journey.
2. Une Opportunity externe n'est pas une Activity Makolo par défaut.
3. Activity décrit ce qui est réellement opéré par un Profil ou un Espace.
4. Une Journey Services peut exister sans Opportunity.
5. Une Opportunity peut être poursuivie par plusieurs Journey.
6. Une Journey Services travaille sur une OpportunityRevision explicite.
7. Une nouvelle revision ne réécrit jamais silencieusement un dossier existant.
8. JourneyStatus décrit le parcours global ; JourneyStep décrit l'action ; JourneyBlocker décrit l'aléa.
9. Mandate exprime l'autorité ; JourneyAssignment exprime l'affectation.
10. Une affectation n'accorde jamais une permission ; une permission ne rend pas automatiquement affecté à tous les dossiers.
11. Les dossiers Services et leurs documents sont privés par défaut.
12. Les fichiers sensibles sont versionnés, audités et servis via contrôle d'autorisation.
13. Le paiement est une capacité transversale et peut faire partie d'Activity, Journey, Commerce, Access ou du parcours vers une Opportunity.
14. Une PaymentObligation n'est pas nécessairement une vente Makolo.
15. Un Payment ne signifie pas que Makolo est le bénéficiaire économique.
16. Un paiement réalisé hors Makolo n'est jamais transformé en faux Payment réussi.
17. Un paiement intermédiaire bloque son étape sans faire repasser toute la Journey à `pending_payment`.
18. Payment, CommerceOrder, Journey et Access conservent des cycles de vie séparés.
19. Le résultat du tiers est distinct du fulfillment Makolo.
20. Notifications/Automation réagissent aux faits du domaine ; elles ne sont pas la source de vérité.
21. Les intégrations IA et providers futurs passent par les mêmes services/invariants et ne contournent pas le domaine.
22. Aucun abonnement Makolo n'est requis pour les capacités Services de cette V1.
23. Plusieurs tentatives Payment peuvent exister pour une obligation, mais au plus une peut être `succeeded`.
24. Une PaymentEvidence externe satisfaite ne crée aucun Payment provider Makolo.
25. ServiceSubmission décrit une tentative réelle de soumission ; elle n'est pas synonyme de Journey fulfilled.
26. ServiceOutcomeEvent est append-only et ne modifie jamais automatiquement Journey.status.
27. `current_outcome` suit la chronologie externe (`occurred_at`), pas simplement l'ordre d'insertion.
28. Requirement state décrit la vérité fondamentale d'une condition ; la prochaine action Services est une projection dérivée.
29. `pending` n'est synonyme ni d'`action_required`, ni de `needs_review`, ni de `payment_required`.
30. `unsatisfied` ne rejette automatiquement ni Journey ni futur abonnement.
31. `requirements` fournit la mécanique commune ; il ne connaît aucun modèle Services.

## 24. Extensions différées sans dette architecturale

Peuvent être ajoutés plus tard sans modifier les fondations ci-dessus :

- assistants IA pour analyse d'offre, CV, lettre, matching et suggestions de plan ;
- M-PESA et autres providers réels ;
- payout/settlement adapté au provider ;
- publication directe d'Opportunities par des Espaces vérifiés ;
- abonnement/feature gating Makolo ;
- moteurs d'import ou de monitoring de sources externes ;
- nouveaux kinds d'Opportunity ou de Service.

Ces extensions doivent composer les propriétaires canoniques existants, pas créer des modèles parallèles de Journey, Payment, Permission, Access ou Activity.

## 25. État d'implémentation T33

T33 matérialise la séparation suivante dans le runtime :

```text
OpportunityRequirement
    = exigence publiée du tiers

ServiceRequirementAssessment
    = état individuel de cette exigence dans un dossier

PaymentObligation
    = somme due dans la Journey

Payment
    = tentative transactionnelle réellement traitée par Makolo/provider

PaymentEvidence
    = preuve d'un paiement réellement effectué ailleurs

CommerceOrder
    = transaction commerciale Makolo

JourneyStep
    = action du parcours

ServiceSubmission
    = tentative réelle d'envoi au tiers

ServiceOutcomeEvent
    = évolution ou décision externe append-only

Journey.status
    = accomplissement du parcours Makolo

ServiceJourneyContext.current_outcome
    = projection de l'état externe observé
```

Les migrations T33 suivent `expand -> backfill certain -> double compatibilité -> nouveaux writes via obligation`. Elles ne suppriment ni `Payment.order`, ni `Payment.commerce_order`, ni les bridges Ticket/Commerce existants. Le beta seed T33 couvre les quatre familles de scénario : Commerce + obligation, frais Opportunity sandbox, frais externe + Evidence sans faux Payment, puis Submission + Outcome externe distinct du fulfillment.

La matrice finale `activity.services.*`, les Notifications/Automation Services complètes, l'UX finale et l'analytics/release gate restent respectivement T34B, T35 et T36.

## 26. État d'implémentation T34A

T34A extrait une seule fois la mécanique horizontale Requirements sans refaire T32 ni déplacer ses modèles persistants.

Le runtime fournit :

```text
requirements.RequirementMode
requirements.RequirementAssessmentState
requirements.RequirementEvaluationResult
requirements.EvaluatorRegistry
```

Le package `requirements` ne possède aucune table métier et n'importe pas `services`, `subscriptions`, `opportunities`, `payments`, `journeys`, `events` ou `transport` pour exécuter sa mécanique fondamentale. Un test de frontière protège cette direction, et un consumer Opportunities de test utilise le registry sans dépendre de Services.

La migration Services T34A transforme les anciens states en place, conserve les IDs, contexte, Requirement, auteur/date/note et toutes les relations Evidence/Step/Payment. Les indexes existants sur `context + status` et `requirement + status` sont conservés. La distinction perdue entre `action_required` et `needs_review` est volontairement normalisée en `pending`; le reverse ne prétend donc pas reconstruire une information qui n'existe plus.

Le registry est défini par le code, valide les paramètres, opérateurs et types de sujets, et expose `dependency_events`/`cache_policy` comme métadonnées techniques. Les données de configuration ne peuvent fournir aucun `expression`, SQL, JavaScript ou `import_path` exécutable. L'évaluation retourne un `RequirementEvaluationResult` non persistant ; le domaine consommateur décide ensuite s'il persiste son propre Assessment et quelle conséquence métier appliquer.

Aucun runtime Subscription, Entitlement ou Eligibility n'est créé dans T34A. Après merge et gates post-merge verts, T34B et Subscriptions Foundation peuvent partir sur deux branches distinctes qui consomment le même kernel horizontal.
