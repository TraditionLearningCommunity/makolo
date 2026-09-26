# Audit Makolo pour le laboratoire Frontière d’opportunité

Référence vérifiée avant création du laboratoire :

```text
repository = TraditionLearningCommunity/makolo
branch     = main
HEAD       = a840455af8cd3cfc185404b4dc8c28a53bbb9eb6
```

Ce HEAD contient le merge de la PR #221 (shell/navigation M8). La PR #222 — Discover, Activity & Possibility Experience — reste ouverte au moment de l’audit. Le laboratoire est placé dans un dossier racine isolé et ne touche aucun fichier de ces chantiers.

## 1. Question étudiée

Le laboratoire ne cherche pas encore à modifier le grand bouton Makolo. Il cherche à répondre expérimentalement à :

> À partir des contrats actuels de Makolo, peut-on construire une projection personnelle, dynamique et multiobjectif qui conserve les règles métier fortes puis expose une Frontière d’opportunité sans score arbitraire ?

Contexte d’acteur strict :

```text
actor = Profile
represented_space = None
```

Une capacité obtenue uniquement parce que ce Profile possède une Permission/Mandate sur un Space appartient au futur contexte Space, pas à ce calcul personnel.

## 2. Accueil Mature : composition existante

`core/home_presentation.py` compose déjà :

```text
Journey / Readiness
Dossier
Prepared Start
Conversation attention
Action Network
Recognition
```

puis transmet les conséquences actionnables à `resolve_contextual_actions()` et projette :

```text
primary_attention
primary_action
action_items
knowledge_items
upcoming
all_clear
```

Le laboratoire ne remplace pas ce moteur et ne modifie pas `build_mature_home()`. Il utilise cette architecture comme contrainte : les propriétaires métier produisent des faits/projections ; la composition transverse ne doit pas les recopier.

## 3. Journey / Readiness

`readiness/types.py` définit les états :

```text
ReadinessStatus:
READY | ACTION_REQUIRED | WAITING | BLOCKED | COMPLETE

ReadinessCheckState:
SATISFIED | NOT_APPLICABLE | ACTION_REQUIRED | WAITING | BLOCKING
```

`readiness/resolver.py` réduit les checks dans l’ordre :

```text
BLOCKING > ACTION_REQUIRED > WAITING > READY
```

et `resolve_journey_readiness(..., viewer=profile)` refuse la projection si le viewer n’est pas le `beneficiary` de la Journey.

`readiness/selectors.participant_readiness_queryset(profile, ...)` filtre également sur `beneficiary=profile`.

La Journey est donc une source propre pour le contexte personnel.

## 4. Contributors Readiness audités

`readiness/contributors.py` fournit notamment les règles suivantes, reprises dans les scénarios du laboratoire :

### Journey

- draft -> action requise `continue_journey` ;
- pending approval -> attente ;
- pending payment sans obligation distincte -> action `pay` ;
- invitation submitted -> réponse participant requise ;
- rejected/cancelled/expired -> blocking.

### Steps / blockers

- step requis bloqué -> blocking ;
- dépendance non satisfaite -> waiting ;
- step requis assigné au bénéficiaire -> action participant ;
- blocker actif -> blocking.

### Payment

- obligation `SATISFIED/WAIVED` -> satisfied ;
- `PROCESSING` -> waiting ;
- `PENDING` et payeur = bénéficiaire (ou aucun payeur explicite) -> `ACTION_REQUIRED / payment_required` ;
- payeur tiers -> waiting ;
- autre état indisponible -> blocking.

### Capacity

Une réservation sécurise la capacité si :

```text
status == COMMITTED
or
status == HELD and (expires_at is None or expires_at > now)
```

Sinon Readiness produit `BLOCKING / capacity_not_secured`.

### Access

Readiness considère :

- `VALID` ou `USED` -> disponible ;
- `PENDING` -> waiting ;
- autres statuts -> blocking `access_unavailable`.

Pour l’état personnel courant, `core.participant_selectors.participant_active_accesses()` ajoute les contraintes de validité temporelle (`valid_until`) et d’Occurrence encore pertinente. La simulation applique donc statut **et** fenêtre de validité pour déterminer si l’Access personnel est utilisable.

### Occurrence

Une Occurrence `CANCELLED` produit un blocking `occurrence_cancelled`. R2 reclassifie ce reason code comme terminal.

## 5. Formulaires obligatoires

`readiness/questionnaire_contributor.py` distingue :

- formulaire complété + réponse soumise -> satisfied ;
- avant `opens_at` -> waiting ;
- après `due_at` -> blocking `form_response_deadline_passed` ;
- sinon formulaire requis -> action `complete_form`, reason `form_response_required`.

Le laboratoire conserve ces relations temporelles et ne transforme pas une échéance en score de préférence.

## 6. Prepared Start / Trusted Reuse

`preparation/prepared_start.py` expose cinq états distincts :

```text
READY
REVIEW_REQUIRED
CONFIRMATION_REQUIRED
UNKNOWN
MISSING
```

Ils restent distincts dans la simulation :

- `READY` -> aucune fausse action ;
- `REVIEW_REQUIRED` -> attente humaine ;
- `CONFIRMATION_REQUIRED` -> action explicite ;
- `UNKNOWN` -> vérification, jamais converti en `MISSING` ;
- `MISSING` -> préparation d’un élément absent.

Le laboratoire ne copie ni Action Memory ni Proof : il simule uniquement la conséquence projetée de ces contrats.

## 7. R2 Contextual Actions

`preparation/contextual_actions.py` est le garde-fou principal avant Pareto.

Priorités :

```text
P0_CRITICAL
P1_REQUIRED
P2_TIME_CONSTRAINED
P3_PROGRESS
P4_INFORMATION
```

Actionability :

```text
TERMINAL
BLOCKING
ACTIONABLE
WAITING
ADVICE
INFORMATION
```

Deadline states :

```text
OVERDUE
DUE_TODAY
FUTURE
NONE
```

Le tri R2 est déterministe :

```text
priority
-> actionability
-> deadline state
-> distance à la deadline
-> mandatory
-> identité stable
```

Un `TERMINAL` supprime `primary_action`. Un `BLOCKING` n’autorise comme action primaire qu’une action de priorité au moins aussi forte.

R2 déduplique uniquement par identité canonique exacte :

```text
source_domain
source_key
action_key
context_type
context_id
```

jamais par texte, URL, similarité ou IA.

### Conséquence pour la Frontière

Le laboratoire applique Pareto **après** :

```text
actor context
R2 priority
R2 actionability
R2 deadline state
terminal/blocking semantics
```

Cela corrige une traduction naïve importante : comparer directement toutes les actions obligatoires seulement par temps/argent pourrait faire dominer un paiement obligatoire par une réponse très rapide à une proposition, alors que ces actions changent différemment l’état de la personne.

## 8. Performance utilisée par le laboratoire

Une fois le gate sémantique passé, un plan reçoit :

```text
(deadline_minutes,
 user_effort_min,
 cash_cdf,
 travel_min,
 elapsed_min,
 interactions,
 p0_after,
 p1_after,
 p2_after,
 p3_after)
```

Toutes les coordonnées sont minimisées.

`p0_after ... p3_after` comptent la charge personnelle restante après la transition simulée. Ces composantes représentent la conséquence sur l’état futur, pas un score de goût. Elles rendent explicite le principe de continuation : une action est évaluée aussi par l’état depuis lequel Makolo continuera ensuite.

Les valeurs numériques du scénario restent synthétiques ; la structure et les règles sont celles auditées.

## 9. Capacity

`capacity/models.py` distingue `HELD`, `COMMITTED`, `RELEASED`, `EXPIRED`.

`capacity/services.py` compte comme consommée :

- toute réservation `COMMITTED` ;
- une réservation `HELD` seulement tant qu’elle n’est pas expirée.

Le laboratoire comporte un hold qui expire avec le passage du temps. Sans action utilisateur, l’état passe alors à un blocker P0. Un événement ultérieur sécurise une capacité `COMMITTED`, ce qui fait disparaître ce blocker. Cela teste une frontière qui change parce que **le monde change**.

## 10. Access

`access/models.py` distingue le droit `Access` de son credential et de son usage. Le laboratoire ne crée aucun pseudo-credential.

Un Access personnel est utilisable dans la simulation seulement si son statut est `valid` et si `valid_until` n’est pas dépassé. Une révocation déclenche :

```text
Readiness P0 BLOCKING: access_unavailable
+
M6 P0 ACTIONABLE: access_action
```

Le blocker reste l’attention primaire, mais la réparation M6 peut être l’action primaire à ce même niveau critique, conformément au resolver R2.

## 11. M6 / mobilité réelle

`spatiotemporal/mobility.py` calcule :

```text
recommended_departure = target_arrival - route_duration - safety_buffer
```

avec un buffer par défaut de 10 minutes.

Lorsque `now >= recommended_departure`, le statut devient `leave_now`.

`spatiotemporal/hazards.py` adapte notamment :

```text
cancelled     -> terminal
access_action -> action critique
leave_now     -> action time-constrained
warning       -> advice
information   -> information
```

Le laboratoire simule une route de 35 minutes et un buffer de 10 minutes vers une arrivée cible à 20:00 ; à 19:20 le `leave_now` devient donc une vraie action P2.

## 12. Dossier / privacy

Le modèle `Dossier` impose exactement un propriétaire : Profile **ou** Space.

`objectives.readiness.resolve_dossier_readiness()` est une projection privacy-safe. Une influence provenant d’une Journey cachée devient le signal opaque :

> Un élément non visible affecte actuellement l’avancement de ce dossier.

Le laboratoire reprend ce comportement sans exposer l’identité de l’objet caché.

Lorsqu’un `DossierNextAction` visible porte l’identité technique du même check Journey, R2 peut dédupliquer exactement cette projection avec la Journey. Le scénario contient volontairement le formulaire visa à la fois comme action Journey et comme projection Dossier avec la même identité ; le moteur vérifie qu’il ne devient pas deux obligations.

Pour le contexte personnel, seuls les Dossiers `owner_profile=profile` sont légitimes. Les Dossiers accessibles uniquement par autorité Space sont injectés comme contre-exemples `SPACE` et doivent être exclus avant R2/Pareto.

## 13. Action Network

`social.profile_search.action_proposals_requiring_actor_response()` est une inbox d’acteur générale : elle peut inclure les propositions visant un `candidate_space` ou un `need.space` si l’acteur a l’autorité correspondante.

Le laboratoire personnel ne retient que :

```text
OWNER_TO_CANDIDATE avec candidate_profile == Profile
CANDIDATE_TO_OWNER avec need.owner_profile == Profile
```

Une proposition Space volontairement plus urgente et moins coûteuse est présente dans les données ; son exclusion prouve que Pareto ne peut pas contourner le contexte d’autorité.

## 14. Conversations

`attention_points_for_profile()` est viewer-aware, mais `resolve` peut dépendre de `can_manage_conversation()`, qui accepte des permissions contextuelles Space/Activity/Dossier.

Le laboratoire sépare donc :

- un `revisit` personnel ;
- un `resolve` qui n’existe que grâce à l’autorité Space.

Le second ne rentre jamais dans le pool personnel.

## 15. Discover

Discover reste un univers de possibilités, pas une source d’obligations. Dans le laboratoire, les candidats Discover sont P4 et ne deviennent comparables qu’une fois les régimes P0–P3 personnels dégagés.

Avant Pareto :

- Occurrence annulée -> exclue ;
- capacité nulle -> cible inaccessible ;
- seules les possibilités viables conservent des plans.

Le scénario final contient une exposition proche et un atelier plus éloigné avec plusieurs modes de déplacement. Les deux restent sur la Frontière parce qu’ils représentent de vrais compromis ; aucune règle artificielle de diversité n’est ajoutée.

## 16. Collision audit courant

- PR #221 : mergée dans `main` ; elle concerne le shell/navigation.
- PR #222 : encore ouverte ; elle concerne Discovery Presentation.
- ce laboratoire n’ajoute que `frontiere_opportunite_lab/*`.
- aucune migration.
- aucun changement de modèle.
- aucun changement Permission/Mandate/Access/Capacity.
- aucun template ou route.

## 17. Critères de sortie

La simulation doit démontrer par assertions :

1. `represented_space=None` et exclusion des cibles Space avant R2 ;
2. déduplication canonique Journey/Dossier ;
3. priorité/deadline/actionability avant Pareto ;
4. expiration Capacity par simple évolution temporelle ;
5. blocker Access + réparation M6 ;
6. `leave_now` issu du temps courant ;
7. signal Dossier caché opaque ;
8. Prepared Start sans fusion de `UNKNOWN`, `MISSING`, confirmation et review ;
9. occurrence annulée terminale ;
10. Discover : cancelled exclue, sold-out inaccessible, cible dominée screenée ;
11. plusieurs cibles Pareto simultanées lorsqu’aucune ne domine l’autre ;
12. aucune cible de Frontière éliminée par safe screening.

Le laboratoire ne prétend pas encore que ces performances sont les dimensions finales du futur produit. Il sert à tester si la théorie peut être appliquée sans casser les frontières canoniques de Makolo.