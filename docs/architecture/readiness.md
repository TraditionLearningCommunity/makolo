# Readiness — projection READY Makolo Mature

## Pourquoi Readiness existe

Readiness répond à une question transversale : **cette personne est-elle prête pour la prochaine chose qu’elle doit accomplir ?** Si non, la projection explique ce qui manque, ce qui bloque, ce qui attend un tiers et la prochaine action réellement utile.

Readiness n’est pas un nouveau domaine propriétaire. C’est un read model horizontal qui compose les faits canoniques existants.

> READY est une projection de la réalité canonique, pas un nouvel état métier propriétaire.

Il n’existe donc ni `Journey.is_ready`, ni `Journey.ready_status`, ni table `ReadinessState`, ni cache canonique de READY.

## Contrat

Le package `readiness` expose des types Python non persistants :

- `ReadinessResult` : `status`, `is_ready`, `checks`, `blocking_items`, `waiting_items`, `action_items`, `next_action`, `observed_at` ;
- `ReadinessCheck` : `key`, `source`, `state`, `blocking`, `reason_code`, `summary`, `next_action` ;
- `NextAction` : action publique minimale et stable ;
- `ReadinessStatus` : état synthétique de la projection.

Les `reason_code` sont techniques et stables. Les résumés publics ne doivent jamais recopier une note interne, une raison de revue confidentielle ou un champ réservé aux opérateurs.

## États

- `READY` : aucune condition obligatoire applicable ne manque pour le prochain engagement connu.
- `ACTION_REQUIRED` : le bénéficiaire peut et doit agir maintenant.
- `WAITING` : aucune action immédiate du bénéficiaire n’est utile ; une décision, un opérateur, un payeur tiers ou un état externe est attendu.
- `BLOCKED` : un fait canonique empêche réellement la progression.
- `COMPLETE` : aucune préparation pertinente ne reste dans le contexte observé.

La priorité de synthèse est : `BLOCKED` > `ACTION_REQUIRED` > `WAITING` > `READY`, avec `COMPLETE` seulement lorsque le contexte est réellement clos. Une Journey `fulfilled` n’est donc pas automatiquement `COMPLETE` si une Occurrence future ou un Access encore valable reste pertinent.

## Contributeurs

Le resolver central ne contient pas de branchement `if event`, `if transport` ou `if service`. Il exécute des contributeurs explicites enregistrés dans `readiness.registry`.

Les contributeurs lisent notamment :

- Journey et JourneyRequest ;
- JourneyStep, dépendances et responsabilités ;
- JourneyBlocker ;
- PaymentObligation ;
- CapacityReservation ;
- Access ;
- Occurrence ;
- évaluations Requirements du contexte Services ;
- FormRequest/FormResponse obligatoires du moteur `questionnaires`.

Chaque domaine reste propriétaire de ses transitions. Readiness ne modifie aucun de ces objets.

## Règles de composition

### Journey

La Journey fournit le contexte, le bénéficiaire, le workflow, l’Activity et l’Occurrence éventuelle. Les transitions restent dans les services Journey/verticales propriétaires.

### Steps et Blockers

Une étape obligatoire réellement attribuée au bénéficiaire peut produire `ACTION_REQUIRED`. Une étape interne non terminée produit `WAITING`. Une dépendance non satisfaite produit une attente. Un `JourneyBlocker` actif produit `BLOCKED`. Aucun second blocker n’est persisté.

### Requirements

Le kernel `requirements` et les évaluations propriétaires restent la vérité. Readiness ne crée pas de `ReadinessRequirement` et n’utilise pas de `GenericForeignKey` universel. Le contributeur Services lit les `ServiceRequirementAssessment` matérialisées et leurs conséquences canoniques ; les actions concrètes restent représentées par JourneyStep ou PaymentObligation lorsque ces domaines les portent.

### Questionnaires

M2 ajoute `questionnaire_contributor` sans modifier le contrat du resolver. Une `FormRequest` obligatoire, ouverte et non soumise produit `ACTION_REQUIRED` avec le reason code stable `form_response_required` et une `NextAction` vers la Request. Une Request future produit `WAITING`. Une Request dont la deadline est passée et qui n’est plus éditable produit `BLOCKED`. Une Response soumise satisfait le check. Une Request optionnelle ne bloque pas READY.

La soumission d’un Form ne satisfait jamais implicitement un Requirement. Si un autre domaine exige ensuite une validation opérateur, l’attente ou le blocage appartient au contributeur de ce domaine, pas à une pseudo-review Form.

Une `ActivityResource` informative ne contribue pas à Readiness. Un futur acknowledgement devra être une obligation explicite et auditée.

### Payments

Seules les `PaymentObligation` réellement rattachées à la Journey contribuent. `satisfied` et `waived` satisfont la préparation. Une obligation `pending` due par le bénéficiaire peut demander une action ; une obligation en traitement ou due par un tiers produit une attente. Readiness ne touche ni allocation, ledger, custody, Settlement, Payout ni provider.

### Capacity

Capacity ne devient applicable que si le workflow possède déjà une réservation canonique. Une réservation active/engagée satisfait la condition. Une capacité globale ensuite épuisée ne retire pas arbitrairement la préparation d’un participant qui possède déjà son droit.

### Access

Access est le droit ; `AccessCredential` n’est qu’une représentation. Readiness ne teste jamais l’existence d’un QR. Un Access existant et valide peut satisfaire la condition ; un Access pending peut produire `WAITING`. L’absence d’Access n’est pas, à elle seule, une erreur : les Journeys qui n’en exigent pas restent applicables.

### Occurrence

Une Journey sans Occurrence est valide et n’est pas pénalisée. Lorsqu’une Occurrence existe, Readiness vérifie seulement les faits canoniques nécessaires, notamment qu’elle ne soit pas annulée. Il ne fait ni routing, ni météo, ni trafic, ni ETA, ni geofencing.

## Dépendances et performance

`journeys` ne dépend pas de Payments, Services, Events ou Transport pour calculer READY. Le package `readiness` est la couche de composition qui peut lire ces domaines.

`readiness.selectors.readiness_queryset()` regroupe `select_related` et `prefetch_related`, y compris les FormRequests M2, afin que le resolver reste à croissance bornée après préchargement. `/me/` charge un nombre borné de Journeys candidates puis les résout en batch ; aucun état Readiness persistant ou cache métier n’est introduit pour masquer un N+1.

## Permissions et disclosure

La projection participant vérifie le bénéficiaire côté serveur. Un autre utilisateur ne peut pas résoudre la Readiness personnelle d’une Journey qui ne lui appartient pas. Les checks publics n’exposent que des intitulés et raisons déjà appropriés au participant ; descriptions de blockers, notes de review, réponses de formulaire et métadonnées internes ne sont pas remontées.

## Web, API et extensions

Le resolver est indépendant des templates et peut être consommé par le web actuel, une API, l’Automation ou un client mobile. La synthèse est exposée à `/me/` et au détail Journey ; M2 fournit une NextAction exploitable vers le formulaire requis.

Les tâches Mature ultérieures pourront ajouter un `resource_acknowledgement_required` seulement si une vraie obligation de lecture est modélisée, ou enrichir la compréhension spatio-temporelle, sans créer un événement `readiness.changed` à chaque lecture.

## Extensions stratégiques R / D / O

[`strategic-action-roadmap.md`](strategic-action-roadmap.md) réutilise explicitement la philosophie Readiness pour trois projections stratégiques :

- **R — Prepared Start** : expliquer ce qui est déjà prêt avant qu'une Journey complète soit matérialisée, lorsque Requirements et contexte permettent une évaluation légitime ;
- **D — Collective Readiness** : agréger des états autorisés pour un Dossier/Groupe/Espace sans exposer les détails individuels inutiles ;
- **O — Operational Readiness** : projeter si une Occurrence est opérationnellement prête à partir d'Access, Capacity, Scanner/Assignments, Resources et capacités Placement/Flow.

Ces trois usages **ne créent pas automatiquement de modèle persistant** `PreparedStartState`, `CollectiveReadinessState` ou `OperationalReadinessState`. Ils doivent d'abord composer les faits canoniques et conserver les mêmes principes : résultat explicable, `NextAction`, disclosure minimale, aucune mutation métier depuis le resolver.

L'Accueil contextuel M8 peut consommer ces projections, mais ne devient pas la source de vérité de Readiness.

## Migrations

M1 n’ajoutait aucun modèle. M2 ajoute ses propres modèles Forms/Resources mais n’ajoute toujours aucun modèle Readiness : READY reste entièrement dérivé.
