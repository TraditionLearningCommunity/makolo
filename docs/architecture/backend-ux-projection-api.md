# Programme Z — Contrat Backend UX Projection & API Composition

> **Statut : canonique pour les projections API UX du programme Z.**
> Base auditée : `main@8ef40aa16e7367f13b0a5df7941057b68a8a242f`. Le runtime courant gagne toujours sur ce snapshot.

## 1. Mission

Makolo possède déjà les vérités utiles : Journey/Readiness, Access, Capacity, Payment, Dossier, Prepared Start, Occurrence Live, Discovery, Trust, Personal Assets, Recognition, Loyalty, Partner, etc.

Z ne recrée pas ces domaines. Il expose côté HTTP leur **signification déjà résolue côté serveur** afin que Web, Flutter et les futurs clients ne reconstruisent ni ORM ni logique métier.

```text
domaines canoniques
  → selectors / services / read models propriétaires
  → composition UX serveur
  → projection API stable
  → clients
```

> **Le backend Makolo décide. Le client présente et orchestre.**

## 2. Ce que Z1 ne fait pas

Z1 n'ajoute aucun modèle, migration, état global, Readiness parallèle, CRUD générique, provider IA, moteur de recommandation, ranking, score de pertinence, probabilité, confiance synthétique ou algorithme transversal.

Lorsqu'un ordre est nécessaire, Z2+ réutilise l'ordre déjà produit par les selectors/resolvers propriétaires. Les champs `score`, `rank`, `relevance`, `probability` et `confidence` ne font pas partie de l'enveloppe Z1. Un domaine qui possède déjà un contrat explicite de ce type peut le garder ; Z ne le généralise pas.

Une projection peut composer plusieurs domaines sans devenir propriétaire d'aucun fait. Elle ne transfère jamais implicitement Permission, Mandate, Access, Payment, Capacity, secret ou donnée privée.

## 3. Namespace

La base reste `/api/v1/`.

Le namespace réservé aux projections personnelles Mature est :

```text
/api/v1/me/
```

Lots suivants :

```text
GET /api/v1/me/             → Moi
GET /api/v1/me/now/         → Maintenant
GET /api/v1/me/ongoing/     → En cours
```

Z1 réserve le contrat mais ne crée pas de route vide.

`GET /api/v1/accounts/auth/me/` reste l'identité/auth bootstrap. Il ne devient pas la projection UX `Moi`.

Les APIs domaine existantes restent dans leurs namespaces lorsqu'elles sont déjà adaptées, par exemple Operations, Trust, Preparation, Loyalty et Discovery. Une profondeur UX les référence plutôt que les dupliquer.

Discover continue sous `/api/v1/discovery/`. Z3 alignera l'API sur la composition Mature existante sans créer un second moteur de recherche. Makolo Mark n'obtient pas de route générique en Z1.

## 4. Enveloppe commune

Les nouvelles projections Z utilisent :

```json
{
  "meta": {
    "projection": "personal.now",
    "schema_version": 1,
    "generated_at": "2026-09-20T17:30:00+02:00",
    "scope": "personal"
  },
  "data": {}
}
```

`meta.projection` est un code technique stable (`personal.now`, `personal.ongoing`, `personal.me`). Il n'est pas destiné à l'affichage et ne porte aucune permission.

`meta.schema_version` commence à `1`. Un ajout rétrocompatible peut rester dans la même version ; une rupture de forme ou de sens doit être explicitement versionnée.

`meta.generated_at` est l'instant timezone-aware de composition. Il n'affirme ni la date de modification de tous les objets ni la fraîcheur d'un provider externe.

`meta.scope` vaut `personal` pour les surfaces personnelles. Aucun Profile ID n'est requis : le sujet est `request.user`.

`data` est toujours un objet JSON, jamais une liste nue. Les surfaces principales peuvent y porter plusieurs sections bornées.

`core.api.projections.projection_envelope()` ne fait que construire cette enveloppe. Il ne classe, n'autorise, n'infère ni ne copie aucun fait métier.

## 5. Types et identités

| Concept | Contrat |
| --- | --- |
| UUID métier | chaîne |
| Decimal / argent | chaîne décimale, jamais float |
| datetime | ISO-8601 avec timezone |
| date seule | `YYYY-MM-DD`, sans heure inventée |
| enum / état | code machine stable, label facultatif |
| collection connue vide | `[]` |
| objet optionnel absent | `null` |
| booléen | seulement si le fait est réellement binaire |
| fait inconnu pertinent | état explicite `unknown` |

Une date-only ne devient jamais artificiellement `00:00`.

Ressource canonique exposable :

```json
{"kind": "journey", "id": "uuid"}
```

Ligne strictement dérivée :

```json
{"kind": "attention", "key": "opaque-stable-key"}
```

Le client ne parse jamais `key` pour retrouver un modèle, une relation ou une permission. Une clé de projection n'est pas une nouvelle identité métier.

## 6. Connu, absent, inconnu et caché

Un fait **connu** peut être sérialisé directement.

Un objet optionnel connu comme absent/non applicable peut être `null`.

Un fait que Makolo ne peut pas légitimement conclure doit rester explicite :

```json
{"state": "unknown", "reason": "not_observed"}
```

Les raisons restent propriétaires du domaine concerné ; Z1 ne crée pas une taxonomie universelle.

Une donnée **cachée par confidentialité** n'est pas transformée en `unknown` si cela révélerait son existence. Lorsqu'un read model canonique possède déjà une influence cachée privacy-safe, comme Collective Readiness d'un Dossier, la projection peut garder un signal opaque (`partial=true`, signal générique) sans sérialiser l'objet caché.

## 7. Backend vs frontend

Le serveur reste propriétaire de : visibilité, autorité, validité Access, Readiness, satisfaction Requirement, état Payment, disponibilité/capacité, actionabilité, attente, blockers, échéances canoniques, inclusion dans Maintenant, continuité dans En cours et capabilities permises.

Le client peut posséder mise en page, animation, iconographie, regroupement purement visuel et formulation éditoriale. Il peut par exemple afficher « Tout est en ordre. ✓ » lorsqu'une projection valide ne contient rien exigeant l'attention.

Le backend peut fournir titres/labels/résumés déjà issus des projections existantes, mais Flutter ne doit jamais parser une phrase pour décider d'un état ou d'une action.

Interdit :

```text
si summary contient "paiement" → afficher Payer
```

Attendu :

```json
{
  "state": "payment_required",
  "capabilities": ["pay"],
  "summary": "Votre demande est approuvée. Vous pouvez maintenant effectuer le paiement."
}
```

## 8. Links et capabilities

`links` décrit des relations de navigation/API. Flutter ne doit pas être obligé de lire une page HTML pour comprendre une vérité métier.

`capabilities` expose uniquement des actions réellement permises par les services/permissions serveur :

```json
{"capabilities": ["respond", "cancel"]}
```

Le client ne déduit jamais une capability depuis Membership, Assignment, statut affiché, type de Profile ou simple possession d'un ID.

Une mutation exposée plus tard doit pointer vers une vraie API qui réutilise le service canonique. Z ne POSTe pas vers un formulaire HTML depuis Flutter.

Aucun AccessCredential, token QR, secret de partage ou URL contenant un secret ne doit être placé dans une projection générale.

## 9. Authentification, acteur et IDOR

Les surfaces personnelles Z sont `IsAuthenticated` et utilisent exclusivement `request.user` comme Profile personnel.

Interdit :

```text
GET /api/v1/me/now/?profile_id=<autre-profile>
GET /api/v1/me/<profile-id>/ongoing/
```

Une profondeur personnelle résout l'objet dans un selector déjà borné :

```python
get_object_or_404(selector_visible_to(request.user), pk=resource_id)
```

Pour une ressource privée, `404 not_found` reste le pattern normal lorsqu'il faut éviter une fuite d'existence.

Un futur « agir comme un Espace » devra distinguer identité authentifiée, acteur représenté, portée d'autorité et bénéficiaire éventuel. Membership, Team, Group et Assignment ne suffisent jamais à accorder l'autorité.

Occurrence Live garde sa perspective serveur existante (`participant/operator/space`) ; Z ne la remplace pas.

## 10. Collections et pagination

`Maintenant`, `En cours` et `Moi` sont des compositions bornées, pas des exports de tables. Elles peuvent retourner des previews et des liens vers des profondeurs.

Les collections profondes continuent à utiliser la pagination DRF existante :

```json
{"count": 42, "next": "...", "previous": null, "results": []}
```

Discover reste paginé. Z ne crée pas de scroll infini artificiel pour remplir une surface calme. Une collection vide est une réponse complète.

## 11. Erreurs

Z réutilise l'enveloppe globale actuelle :

```json
{
  "error": {
    "code": "not_found",
    "message": "Ressource introuvable.",
    "fields": {}
  }
}
```

Codes existants : `validation_error`, `authentication_required`, `permission_denied`, `not_found`, `throttled`, `method_not_allowed`, `api_error`.

Z1 ne crée aucun système d'erreurs « mobile ». Un état métier valide `waiting`, `blocked` ou `unknown` peut être un HTTP 200 normal.

## 12. Fraîcheur et persistance

Les projections Z sont recomposées depuis les vérités courantes. `generated_at` est un instant de lecture, pas un nouvel événement métier.

Aucun `NowState`, `OngoingState`, `MeState`, `ProjectionSnapshot` ou équivalent n'est créé.

Un cache futur ne peut être ajouté que pour une raison mesurée de performance ; il reste dérivé, invalidable et non propriétaire de la vérité. Une source externe indisponible ne justifie jamais l'invention d'un fait.

## 13. Confidentialité minimale

Une projection Z n'inclut pas par défaut : email d'un tiers, notes internes, réponses privées de formulaire, CRM, Mandates/Permissions bruts, AccessCredential, token QR, secret, paiement sensible ou relation cachée utilisée seulement pour le calcul.

`Access` = droit, pas credential. Posséder un document ≠ satisfaire un Requirement. Une influence cachée peut modifier une projection collective sans que la ressource cachée soit sérialisée.

## 14. Réutilisation des APIs existantes

Z1 ne force pas toutes les APIs existantes à adopter `meta/data`. Les contrats domaine déjà consommés restent stables jusqu'à décision explicite.

Exemples à réutiliser :

```text
Occurrence Live  → /api/v1/operations/occurrences/{id}/live/
Journey resources → /api/v1/preparation/journeys/{id}/resources/
Trust             → /api/v1/trust/...
Loyalty personnel → /api/v1/loyalty/me/
```

`docs/architecture/mobile-api-contract.md` est désormais le point d'entrée canonique du contrat mobile. Il renvoie au handoff final [`z13-mobile-api-handoff.md`](z13-mobile-api-handoff.md) pour l'expérience Mature, tout en conservant les contrats détaillés Event/Ticket/Scanner encore valides pour leur verticale.

## 15. Lots suivants

```text
Z2 → Maintenant + En cours
Z3 → Découvrir + conservation / Veilles / handoff propriétaire
Z4 → Moi + capital personnel / collectifs + Recognition / Loyalty / Partner
Z5 → détails engagés : Journey, Requirement, Activity, Occurrence, Access, Dossier, Project et Capacity projetée
Z6 → surfaces secondaires : Mes accès, Historique, Jour J et Makolo Live par réutilisation des owners
Z7 → Makolo Mark et gaps restants, sans faux moteur intelligent
Z8+ → handoff mobile et autres gaps réellement démontrés
```

Z6 ne reprend pas les détails Z5. `Mes accès` possède la collection personnelle des droits ; le détail Access reste une profondeur propriétaire. `Historique` est une projection temporelle transverse. `Jour J` est la surface contextuelle majeure d'une Occurrence actuelle et `Makolo Live` lui appartient.

Le contrat complet du checkpoint Z6.0/Z6.1 est documenté dans [`z6-secondary-surfaces.md`](z6-secondary-surfaces.md). Aucune route `/api/v1/me/live/` n'est présumée : l'API Operations Live existante reste propriétaire tant qu'un gap réel n'est pas démontré.

## 16. Critères de sortie Z1

Z1 est fermé lorsque l'enveloppe est définie/testée ; `/api/v1/me/` est réservé sans route vide ; auth `me` et UX `Moi` sont distincts ; types/erreurs/vide/null/unknown/confidentialité sont contractés ; serveur vs présentation client est explicite ; capabilities restent serveur ; Flutter n'a pas à parser du texte ; les APIs domaine restent réutilisables ; aucune migration, aucun modèle et aucun algorithme/ranking/score n'est ajouté ; tests ciblés et contrôle migrations restent verts.


## 17. Z2.1 — Contrat sémantique de Maintenant et En cours

> **Statut : canonique pour Z2.**
> Réconciliation runtime : `main@6a4c59fd6388d481834ca33cbd7e561682c127a1`.
> Z2 travaille sur une seule branche : `task-z2-attention-continuity-projections`.
> Le runtime courant reste prioritaire si `main` évolue avant l'intégration finale.

Z2 possède deux projections distinctes :

```text
Maintenant → conséquence humaine qui mérite réellement l'attention à cet instant
En cours   → continuité d'une réalité déjà engagée
```

La règle de frontière est :

> **En cours garde le fil. Maintenant reprend la main lorsque l'intervention de l'acteur redevient utile.**

Une même réalité peut apparaître dans les deux projections. Aucune exclusion réciproque n'existe. En revanche, `Maintenant` n'est ni une sous-vue de `En cours`, ni une vue des notifications, ni la liste de tout ce qui est techniquement faisable.

### 17.1. Frontend et interprétation

Les interprétations éditoriales et agrégées restent côté client.

Le serveur peut retourner :

```json
{"data": {"items": []}}
```

Le client peut alors afficher :

> **Tout est en ordre. ✓**

Le serveur ne crée donc pas de champ `all_clear`, `urgent_count`, `attention_count`, `has_actions` ou équivalent pour piloter cette phrase.

De même, trois éléments courants ne deviennent pas une vérité serveur « 3 urgences ». Le backend expose trois éléments structurés ; Flutter choisit leur représentation.

Le backend reste toutefois propriétaire de l'inclusion : Flutter ne décide jamais qu'un Payment, une Journey, un Access ou une Notification « mérite Maintenant » en reconstruisant les règles métier.

## 18. Projection `personal.now`

### 18.1. Question

`Maintenant` répond à :

> **« Qu'est-ce qui mérite que je fasse quelque chose maintenant ? »**

Ses dimensions sémantiques sont :

```text
action      → faire maintenant
decision    → décider maintenant
adaptation  → modifier maintenant le prochain pas
```

Ces codes décrivent la conséquence serveur. Ils ne prescrivent ni trois sections, ni trois cartes, ni un ordre visuel.

### 18.2. Shape v1

```json
{
  "meta": {
    "projection": "personal.now",
    "schema_version": 1,
    "generated_at": "2026-09-21T09:00:00+02:00",
    "scope": "personal"
  },
  "data": {
    "items": [
      {
        "key": "opaque-stable-key",
        "kind": "journey.action",
        "dimension": "action",
        "source": {
          "kind": "journey",
          "id": "uuid"
        },
        "state": "action_required",
        "title": "Action requise",
        "summary": null,
        "timing": {},
        "capabilities": [],
        "links": {}
      }
    ]
  }
}
```

Contrat :

- `data.items` est l'unique collection de premier niveau de `personal.now` v1 ;
- `key` est opaque et stable pour la ligne dérivée ; le client ne la parse pas ;
- `kind` est un code technique de conséquence, pas un nom de modèle Django ;
- `dimension` vaut exactement `action`, `decision` ou `adaptation` ;
- `source` identifie la ressource visible qui ancre la conséquence ; aucun objet caché n'est utilisé comme source sérialisée ;
- `state` est un code stable issu de la conséquence propriétaire déjà résolue ; Z2 ne crée pas une taxonomie universelle de statuts métier ;
- `title` et `summary` sont de la présentation fournie par le serveur et ne doivent jamais être parsés pour décider d'une action ;
- `timing` contient seulement des faits temporels canoniques déjà connus ; `{}` est valide ;
- `capabilities` ne contient que des actions réellement autorisées et réellement exposables côté serveur ;
- `links` ne contient que des destinations existantes ; Z2 n'invente pas un futur endpoint Z5 ;
- une collection vide est une réponse complète.

Aucun champ `upcoming` n'appartient à `personal.now` v1. Futur ne signifie pas attention actuelle.

### 18.3. Admission depuis `ContextualAction`

Z2 réutilise `ContextualAction` et `resolve_contextual_actions()` pour la déduplication par identité stable et l'ordre déterministe déjà existant. Il ne crée aucun score.

Mais `ContextualAction` est plus large que `Maintenant`. Les règles suivantes sont donc nécessaires :

- `WAITING` n'entre pas dans `Maintenant` ;
- `INFORMATION` n'entre pas dans `Maintenant` ;
- `ADVICE` n'entre pas automatiquement dans `Maintenant` ;
- `TERMINAL` ou un blocker qui invalide le prochain pas peut produire une `adaptation` ;
- une action explicitement attendue par un selector propriétaire peut produire une `action` ;
- une décision explicitement attendue par un selector propriétaire peut produire une `decision` ;
- une action seulement possible ou de progression facultative ne suffit pas ;
- `ReadinessStatus.ACTION_REQUIRED` n'est pas, à lui seul, la définition de `Maintenant`.

Pour Journey/Readiness, Z2 conserve une règle particulièrement prudente : une intervention du bénéficiaire peut rester visible dans `En cours` sans être promue dans `Maintenant`. Une échéance future n'est pas transformée par Z2 en fenêtre d'urgence artificielle. Lorsqu'un owner fournit déjà un fait actuel — blocker/terminal, échéance due ou dépassée, ou autre conséquence opérationnelle explicitement actuelle — la promotion est défendable. Sinon Z2 n'invente pas de seuil « bientôt ».

Cette règle protège le cas :

```text
une attestation reste nécessaire avant une échéance future
→ En cours : oui
→ Maintenant : non tant qu'aucun fait propriétaire ne rend son moment actuel
```

Si le runtime ne fournit pas une fenêtre utile antérieure à l'échéance, Z2 documente ce manque ; il ne construit pas l'algorithme qui l'estimerait.

## 19. Projection `personal.ongoing`

### 19.1. Question

`En cours` répond à :

> **« Pour ce que j'ai déjà engagé, puis-je avancer tranquille — et sinon, quelle est la plus petite chose utile qu'il me reste à faire ? »**

Les quatre questions internes restent des dimensions de compréhension, pas quatre sections imposées :

```text
ce qui est déjà prêt
ce qui dépend encore de moi
ce qui continue sans moi
ce qui vient ensuite
```

### 19.2. Shape v1

```json
{
  "meta": {
    "projection": "personal.ongoing",
    "schema_version": 1,
    "generated_at": "2026-09-21T09:00:00+02:00",
    "scope": "personal"
  },
  "data": {
    "items": [
      {
        "kind": "journey",
        "source": {
          "kind": "journey",
          "id": "uuid"
        },
        "state": "waiting",
        "title": "Inscription",
        "ready": [],
        "actor_interventions": [],
        "continuation": {
          "state": "waiting",
          "summary": null
        },
        "blocker": null,
        "next": null,
        "timing": {},
        "place": null,
        "capabilities": [],
        "links": {}
      }
    ]
  }
}
```

Contrat :

- `data.items` est l'unique collection de premier niveau de `personal.ongoing` v1 ;
- une ligne représente une réalité engagée, pas une table ou une catégorie de navigation ;
- `state` exprime l'état de continuité que le propriétaire sait réellement établir ;
- `ready` est une liste compacte de faits déjà réglés qui réduisent réellement le travail ou l'incertitude ; elle peut être vide ;
- `actor_interventions` contient uniquement les interventions que le serveur sait appartenir à l'acteur ; `[]` permet au client de formuler « rien à faire de votre côté » sans champ serveur dédié ;
- `continuation` décrit seulement une continuité propriétaire connue, par exemple une attente normale ; elle peut être `null` ;
- `blocker` reste `null` lorsque la réalité attend normalement ;
- `next` est la prochaine transition significative seulement lorsqu'elle est réellement connue ; aucune date ou étape n'est inventée pour remplir le contrat ;
- `timing`, `place`, `capabilities` et `links` restent compacts et privacy-safe ;
- un champ propriétaire non connaissable reste `null`, `[]` ou explicitement `unknown` selon le contrat Z1.

Aucun `tone`, `has_waitlist`, `has_transfers`, `has_personal_dossiers` ou autre helper de template Web n'appartient au contrat API.

### 19.3. Sous-objets compacts

Une entrée `ready` peut suivre la forme :

```json
{
  "kind": "access",
  "state": "available",
  "title": "Accès disponible"
}
```

Une intervention peut suivre la forme :

```json
{
  "key": "opaque-stable-key",
  "state": "action_required",
  "title": "Compléter l'information",
  "timing": {},
  "capabilities": [],
  "links": {}
}
```

Un blocker peut suivre la forme :

```json
{
  "state": "blocked",
  "title": "La suite est empêchée",
  "summary": null
}
```

Une influence cachée déjà autorisée par Collective Readiness ne reçoit ni ID, ni titre, ni bénéficiaire caché dans ces sous-objets. Le signal reste opaque.

## 20. Matrice Z2.1 des sources réelles

| Source | Owner/runtime à réutiliser | Maintenant | En cours | Règle Z2 |
| --- | --- | --- | --- | --- |
| Journey / Readiness | `participant_readiness_queryset()`, `resolve_many()`, `actions_from_readiness()` | conditionnel | oui | `WAITING`/READY ne montent pas. ACTION_REQUIRED reste une intervention de continuité mais ne devient Maintenant que si le runtime fournit un caractère actuel défendable ; blocker/terminal peut imposer adaptation. |
| Dossier / Collective Readiness | `dossiers_for_profile()`, `resolve_dossier_readiness()`, `actions_from_dossier()` | conditionnel | oui | Toujours consommer le read model privacy-safe. Une influence cachée peut changer l'état sans fuite d'identité. |
| Project | `projects_for_profile()` + lifecycle propriétaire | non générique | oui | DRAFT/ACTIVE personnel peut garder une continuité ; aucun blocker, next ou Readiness n'est inventé faute de resolver propriétaire équivalent. |
| Access | `participant_active_accesses()` | non comme simple droit | oui | Un Access actif signifie qu'un droit existe. Aucun AccessCredential n'est sérialisé. Une conséquence live actuelle reste propriétaire d'Operations/Occurrence Live. |
| Occurrence / spatiotemporal | `get_hazards()`, `get_action_advices()`, `actions_from_action_advices()` | conditionnel | via Journey/Access | `cancelled` peut produire adaptation ; `leave_now` ou `access_action` peuvent produire action. Warning/information seuls ne suffisent pas. |
| Prepared Start | `prepared_start_for_revision()`, `actions_from_prepared_start()` | **pas depuis l'ancre actuelle** | non pré-engagement | Le Home actuel part de `saved_opportunities()`. Une sauvegarde n'est pas un engagement ni une preuve que le moment d'action est venu. Le moteur Prepared Start reste réutilisable, mais Z2 ne consomme pas cette ancre tant qu'un owner n'apporte pas un signal plus fort. |
| Conversations | `attention_points_for_profile()` | conditionnel | non générique | Seuls les points où le backend sait qu'une action est attendue (`respond`, `acknowledge`, `form`, `resolve`) peuvent alimenter Maintenant. `unread` n'est jamais utilisé. `revisit` n'est pas promu sans preuve temporelle actuelle supplémentaire. |
| Action Network | `action_proposals_requiring_actor_response()` | décision | non par défaut | Le selector est explicitement un inbox de propositions pending, non expirées, que l'acteur peut répondre. Z2 n'absorbe pas la surface Action Network. |
| Recognition | `redemptions_requiring_beneficiary_response()` | décision | non par défaut | Consentement bénéficiaire seulement. Balance, avantages, historique et compte Recognition restent hors Maintenant/En cours et appartiennent à Z4. |
| Waitlist | `get_waitlist_entries_visible_to()`, `is_offer_active` | OFFERED actif → décision | WAITING/OFFERED → oui | WAITING = attendre une place, pas blocker. OFFERED reste En cours tout en montant dans Maintenant. |
| Ticket Transfer | `get_ticket_transfers_visible_to()`, `is_pending_active` | entrant actif → décision | entrant/sortant pending actif → oui | Un transfert sortant attend le tiers ; il ne devient pas une décision personnelle actuelle. |
| Standalone Payment | `get_payments_visible_to()` | non générique | PENDING/PROCESSING pertinent → oui | Seulement paiements personnels non déjà représentés par une Journey. Pending/processing = continuité, pas blocker. Une obligation Journey actionnable vient de Readiness. |
| Live Queue / Checkpoints | Operations / Occurrence Live | seulement par conséquence owner existante | pas de seconde expérience live | Waitlist et Live Queue restent distinctes. JourneyStep et Checkpoint restent distincts. |
| Notifications | canal | non | non | Notification n'est jamais la source de vérité d'une projection Z2. |
| Domain Events | infrastructure métier | non directement | non directement | Un événement peut faire évoluer un owner ; Z2 consomme ensuite la conséquence owner, pas l'événement brut. |

## 21. Sources explicitement refusées comme déclencheurs génériques

Les faits suivants ne suffisent jamais, seuls, à produire un item `personal.now` :

```text
unread
notification créée
domain event émis
bookmark / OpportunitySave
nouvelle Opportunity pertinente
status backend modifié
action techniquement possible
Membership
Assignment sans autorité
AccessCredential disponible
solde Recognition
future Occurrence simplement planifiée
timestamp simplement présent
```

De même, ils ne suffisent pas à déclarer un blocker.

## 22. Waiting, blocker et intervention de l'acteur

Z2 fixe les distinctions suivantes :

```text
waiting != blocked
possible != current
responsibility != authority
unknown != missing
unread != attention
future != now
```

Dans `personal.ongoing`, une réalité `WAITING` peut avoir :

```json
{
  "actor_interventions": [],
  "continuation": {"state": "waiting", "summary": null},
  "blocker": null
}
```

Le client peut alors exprimer la tranquillité sans que le serveur invente une phrase de synthèse.

Une Journey `READY` reste une continuité valable dans `En cours` avec aucune obligation personnelle fabriquée.

## 23. Gaps assumés après réconciliation Z2.1

### 23.1. Fenêtre « reste de mon côté, mais pas encore Maintenant »

Le runtime sait très bien distinguer bénéficiaire/tiers, WAITING, blocker, action requise et échéances canoniques. Il ne possède toutefois pas une règle universelle permettant de calculer combien de jours avant une échéance une intervention future doit devenir `Maintenant`.

Z2 ne crée pas cette règle. Une intervention future reste dans `En cours` lorsqu'aucun fait propriétaire ne justifie encore sa promotion.

### 23.2. Prepared Start pré-Journey

`prepared_start_for_revision()` fournit une excellente projection de réutilisation et de préparation, mais l'ancre utilisée par le Home courant est `saved_opportunities()`. Le fait d'avoir sauvegardé une Opportunity ne suffit pas au nouveau contrat `Maintenant`.

Z2.1 conserve donc Prepared Start comme capacité réutilisable mais bloque son admission générique depuis une simple sauvegarde.

### 23.3. Project

Le runtime possède un lifecycle Project mais pas de projection transverse équivalente à Journey Readiness permettant d'affirmer un blocker, une intervention ou une prochaine transition. Z2 expose uniquement ce qui est réellement connu.

### 23.4. Access et expérience live

Un Access actif peut contribuer à `En cours` comme droit déjà disponible. Z2 ne déduit pas depuis cet Access une action live. L'expérience opérationnelle reste propriétaire d'Occurrence Live, Placement, Checkpoints et Queue.

### 23.5. Profondeurs API futures

Z5 possédera plusieurs profondeurs Journey/Activity/Occurrence/Dossier. Z2.1 ne crée aucun faux lien vers des endpoints qui n'existent pas encore. `links: {}` est valide.

## 24. Collision audit Z2.1

À la base auditée :

- aucune branche ou PR Z2, Z3, Z4 ou Z5 n'existe ;
- la PR ouverte #252 concerne les archétypes d'Espace et le gating Transport ; elle ne touche pas les surfaces Z2 auditée ;
- `config/urls.py` ne possède encore aucun include `/api/v1/me/` ;
- Z2.1 ne modifie ni `config/urls.py`, ni `core/home_presentation.py`, ni `core/mature_experience_views.py`.

La couture de routing personnelle est donc reportée à Z2.5, lorsqu'elle sera réellement nécessaire, afin de minimiser les collisions avec Z4.

## 25. Critères de sortie Z2.1

Z2.1 est fermé lorsque :

- `personal.now` et `personal.ongoing` possèdent des shapes v1 distinctes ;
- `data.items: []` est le contrat du calme, sans `all_clear` serveur ;
- les dimensions `action / decision / adaptation` sont sémantiques et non des sections obligatoires ;
- En cours expose la continuité sans `tone` ou helpers de template ;
- la matrice des owners/selectors à réutiliser est explicite ;
- Prepared Start n'est pas admis depuis une simple Opportunity sauvegardée ;
- Readiness ACTION_REQUIRED n'est pas défini comme synonyme universel de Maintenant ;
- waiting reste distinct de blocked ;
- Waitlist reste distincte de Live Queue ;
- JourneyStep reste distinct de Checkpoint ;
- aucune Notification, Domain Event, Membership ou Assignment n'est promu en vérité Z2 ;
- aucun modèle, migration, score, ranking, cache ou état persistant n'est ajouté ;
- les gaps non défendables par le runtime sont documentés plutôt que simulés.


## 26. Z2.2 à Z2.6 — Implémentation livrée sur la branche Z2

Le runtime Z2 est porté par :

```text
core.home_presentation.resolve_mature_home_contextual_actions()
core.api.personal_projections.build_personal_now_projection()
core.api.personal_projections.build_personal_ongoing_projection()
core.api.personal_views.PersonalNowAPIView
core.api.personal_views.PersonalOngoingAPIView
```

Les endpoints actifs sont :

```text
GET /api/v1/me/now/
GET /api/v1/me/ongoing/
```

Ils sont strictement `IsAuthenticated`, utilisent `request.user` et l'enveloppe Z1.

Le refactoring de Home garde la compatibilité Web existante : `build_mature_home()` continue à consommer Prepared Start. La projection API Z2 réutilise la même composition transversale mais appelle explicitement `include_prepared_start=False`, car une simple Opportunity sauvegardée ne satisfait pas le contrat mature de `Maintenant`.

`personal.now` conserve l'ordre déterministe de `resolve_contextual_actions()` et applique seulement le filtre d'admission Z2 :

- décisions explicitement attendues : Action Proposal, consentement Recognition, Waitlist OFFERED active, Transfer entrant actif ;
- Conversation : seulement les points d'attention où une action explicite est attendue ; `revisit` seul n'est pas promu ;
- Occurrence/spatiotemporel : annulation → adaptation ; `leave_now` / `access_action` → action ;
- blocker/terminal → adaptation ;
- action Readiness avec échéance explicitement future → reste dans En cours ;
- aucune règle « bientôt » n'est inventée.

`personal.ongoing` compose Journey/Readiness, Access, Dossier/Collective Readiness, Project, Waitlist, Transfer et Payment autonome. Une attente normale conserve `blocker: null`. Les dates-only restent des dates et ne produisent pas minuit artificiel.

Les capabilities Z2 ne sont exposées que lorsque l'action existe réellement dans une API actuelle. En particulier, Waitlist et Transfer pointent vers leurs mutations DRF existantes ; Conversation expose `respond` ou `acknowledge` uniquement lorsqu'un point canonique le permet. Z2 ne fabrique pas d'API Recognition ou Action Network inexistante.

Tests ciblés Z2 : authentification, vide stable, frontière Journey future→actuelle, IDOR Journey, date-only, Waitlist WAITING versus OFFERED. Les suites existantes M8/UX2 continuent de couvrir la composition Home, Recognition, Action Network et Transfer réutilisée. Aucun modèle ni migration n'est introduit.


## 27. Z4 — Moi et capital personnel / collectifs

Z4 ferme la projection personnelle `Moi` sans créer de nouveau domaine. La question reste :

> **« Qu'est-ce qui est déjà en place autour de moi pour que Makolo marche mieux pour moi ? »**

Le namespace personnel partagé avec Z2 devient :

```text
GET /api/v1/me/                  → Moi
GET /api/v1/me/now/              → Maintenant
GET /api/v1/me/ongoing/          → En cours
GET /api/v1/me/considerations/   → Ce qui compte pour moi
GET /api/v1/me/collectives/      → Mes collectifs
GET /api/v1/me/passport/         → Passeport Makolo
GET /api/v1/me/resources/        → Mes ressources
GET /api/v1/me/partners/         → Mes relations partenaire personnelles
GET /api/v1/me/accesses/         → Mes accès actuels / achats pour autrui
GET /api/v1/me/history/          → Historique personnel métier
GET /api/v1/me/occurrences/<uuid>/day-of/ → Jour J personnel d’une Occurrence actuelle
```

Toutes ces routes sont privées, utilisent exclusivement `request.user` et l'enveloppe Z1. Aucun `profile_id` client ne peut changer le sujet.

### 27.1. Projection racine `personal.me`

La racine est une composition bornée destinée au shell Mature. Elle expose :

```text
identity
passport
considerations
collectives
resources
support
links
```

Chaque famille est un aperçu compact ; les profondeurs réutilisent les mêmes selectors propriétaires.

`identity` reste une identité humaine et non un dump Account : nom d'affichage, avatar, bio, profession, localisation générale choisie, choix `public_profile/searchable` et activation de Profile déjà dérivée. Email, téléphone, adresse précise, coordonnées, préférences de notification, Permissions et Mandates bruts restent hors projection.

### 27.2. Ce qui compte pour moi

`personal.me.considerations` maintient les concepts séparés :

```text
Interest
Open to
Veille
Favorite / Bookmark
Follow Space
Follow Profile
```

Aucun comportement observé n'est réécrit en Interest. Une Veille garde ses critères privés dans le domaine Discovery : la projection `Moi` expose son identité/statut utile, pas son contenu sensible de recherche.

### 27.3. Mes collectifs

`personal.me.collectives` distingue :

- Espaces où une autorité réelle existe, résolus par `authorized_spaces()` ;
- Team memberships, présentés comme relation de membership uniquement ;
- Groupes visibles via `groups_for_profile()`.

Un Team/Group/Membership ne reçoit jamais `can_act=true` par simple composition. La projection ne sérialise ni rôle brut, ni Permission, ni Mandate.

### 27.4. Passeport Makolo

`personal.me.passport` réutilise `sharing.passport.build_profile_passport()` et ses variantes canoniques :

```text
public
complete
thematic
custom
```

La projection conserve les trois natures de faits :

- `declared` : Interests / Open to ;
- `established` : Proofs Makolo ;
- `issued` : Credentials Trust.

Le Passeport reste une représentation/export ; il ne devient ni une nouvelle vérité, ni un score humain, ni un Credential universel.

### 27.5. Mes ressources

`personal.me.resources` compose :

- Personal Assets contrôlés par le Profile ;
- Proofs du Profile ;
- Credentials Trust délivrés au Profile.

Les fichiers privés ne sont jamais placés dans la projection générale. Aucun chemin de stockage, contenu, hash, URL privée ou AccessCredential n'est exposé. Posséder un Personal Asset ne signifie jamais satisfaire un Requirement.

### 27.6. Recognition, Loyalty et Partner

Ces trois réalités restent des domaines distincts.

**Recognition** obtient une API personnelle dans son domaine :

```text
GET  /api/v1/recognition/me/
POST /api/v1/recognition/rewards/<reward-id>/redeem/
POST /api/v1/recognition/redemptions/<redemption-id>/accept/
POST /api/v1/recognition/redemptions/<redemption-id>/decline/
```

Les mutations délèguent aux services transactionnels Recognition existants. La clé d'idempotence est obligatoire pour une utilisation de Reward. Une décision de bénéficiaire est résolue par le selector personnel et retourne 404 à un autre Profile. Le `fulfillment_snapshot` interne n'est pas exposé.

**Loyalty** conserve son API propriétaire existante :

```text
GET /api/v1/loyalty/me/
```

Z4 ne mélange jamais Loyalty organisationnelle et Recognition plateforme.

**Partner** conserve ses APIs métier existantes. `personal.me.partners` ajoute seulement une lecture minimale des relations où `Partner.user == request.user`, sans email, téléphone, notes internes ni données d'acheteurs.

### 27.7. Bornes Z4

Z4 n'ajoute :

- aucun modèle ;
- aucune migration ;
- aucun `MeState`, snapshot ou cache propriétaire ;
- aucun score/ranking ;
- aucune inférence d'autorité ;
- aucun clone de Passport, Personal Asset, Proof, Credential, Recognition, Loyalty ou Partner.

Le GET `Moi` ne crée pas silencieusement de `UserProfile` manquant : un ancien compte peut être projeté avec une extension vide en mémoire.

La forme racine est bornée à six éléments par famille. Les profondeurs Z4 restent bornées à cinquante éléments ; elles ne deviennent pas des exports de tables ni un scroll infini artificiel.


## 28. Z6-A — Mes accès

Z6-A ajoute la surface secondaire personnelle sans modifier le domaine Access.

```text
GET /api/v1/me/accesses/
GET /api/v1/me/accesses/<uuid>/credential/
```

La collection par défaut est strictement bénéficiaire et actuelle. La relation `purchased_for_other` est une vue transactionnelle séparée pour les droits issus des propres CommerceOrders de l'acheteur.

La collection ne sérialise jamais un AccessCredential complet ni son token. Pour une relation `beneficiary`, elle peut exposer seulement une synthèse de représentation et la capability `present_credential` lorsque la profondeur protégée est disponible. Pour `purchased_for_other`, aucune disponibilité de credential, capability de présentation ni lien vers le secret du titulaire n'est exposé. Le endpoint credential est `private, no-store`, strictement bénéficiaire et retourne 404 à l'acheteur, aux tiers, ou lorsque l'Access n'est plus présentable.

`personal.me` référence `Mes accès` par link seulement ; aucune copie de vérité Access n'entre dans Moi.

Aucun modèle, migration, score, ranking, cache ou état Access parallèle n'est introduit.


## 29. Z6-B — Historique

`GET /api/v1/me/history/` expose `personal.history`, projection privée et paginée des faits passés dont le Profile authentifié est réellement bénéficiaire.

Les seules sources Z6-B sont les selectors historiques canoniques Journey et Access. La composition déduplique une Journey lorsqu'un Access représente déjà la même expérience.

Le timestamp Journey n'est plus un `updated_at` systématique : `participant_unified_history_journeys()` annote `history_at` depuis `fulfilled_at`, `cancelled_at`, `expires_at` ou la transition terminale persistée ; `updated_at` reste uniquement le fallback des anciennes lignes incomplètes. Le Web History réutilise cette même annotation.

Notification, Domain Event, audit technique, Goal numérique, AccessCredential et donnée d'un acheteur pour un autre bénéficiaire restent hors projection.

La collection est `private, no-store`, recherche après scope personnel, pagination `limit/offset` bornée à 50 et ordre déterministe. Depuis le merge de Z5 dans `main`, les items pointent vers les détails canoniques Journey/Access déjà livrés ; Z6 ne duplique pas ces profondeurs. Aucun modèle, migration, snapshot History ou backfill n'est introduit.


## 30. Z6-C — Jour J fondation

`GET /api/v1/me/occurrences/<uuid>/day-of/` expose la racine `personal.occurrence.day_of`.

Cette projection est strictement participant-safe : elle appelle `resolve_participant_occurrence_live()` pour l'autorisation et la situation Operations, puis compose seulement les Access du bénéficiaire. Elle ne remplace ni l'Occurrence, ni Operations Live.

Le payload distingue la destination planifiée de la position actuelle du participant. Tant qu'aucune position volontaire et légitime n'est réellement observée, `current_position` reste `unknown`.

Les horaires et lieux canoniques sont `planned`; une mobilité n'est `estimated` que lorsqu'une estimation existe réellement ; états Access, prochain mouvement et hazards sont des observations courantes ; une valeur inconnue reste inconnue.

Le credential n'est jamais sérialisé dans Jour J. La racine expose uniquement le bridge vers la profondeur sécurisée Z6-A lorsqu'elle est présentable.

La phase `arrival/live` expose un handoff vers l'API Operations Live existante ; aucun `/api/v1/me/live/`, moteur Live, modèle, migration ou état persistant Jour J n'est créé.


## 31. Z6-C — Jour J opérationnel

La racine Jour J compose maintenant Queue, Placement, Checkpoints et Operational Readiness depuis le resolver participant-safe Operations.

Queue n'expose que l'entrée du Profile ; Placement n'expose que son unité ; les Checkpoints restent des checkpoints opérationnels ; Capacity reste distincte et n'est pas projetée comme placement.

Readiness est une conséquence dérivée et non un score. En phase `after`, Jour J retire le handoff Live, conserve `next.type=none` et expose le passage vers l'Historique personnel.

Aucun modèle, migration, Waitlist dans Live Queue, JourneyStep déguisé en Checkpoint ou état persistant Jour J n'est ajouté.


## 32. Z6-D/E — Makolo Live et bridges

Makolo Live reste l'API Operations `/api/v1/operations/occurrences/<uuid>/live/`. Le runtime audité possède les dimensions opérationnelle, spatiale et temporelle ; aucune source média Occurrence canonique n'existe encore, donc Z6 ne crée aucun stream ou modèle Media.

Les bridges Mature pointent vers la racine Jour J depuis En cours, les détails Journey/Access/Occurrence et, lorsqu'une action spatiotemporelle actuelle est portée par une Journey, Maintenant. Les liens Mes accès et Historique sont exposés depuis En cours ; Moi conserve ses links déjà livrés.

Un buyer-only Access ne reçoit jamais de lien Jour J.


## 33. Z6-F — Fermeture

Z6 est désormais composé de :

```text
Mes accès      → /api/v1/me/accesses/
Historique     → /api/v1/me/history/
Jour J         → /api/v1/me/occurrences/<uuid>/day-of/
Makolo Live    → /api/v1/operations/occurrences/<uuid>/live/
```

Jour J est la racine personnelle contextuelle ; Operations Live reste l'owner de la projection Live. Les détails Journey/Access/Occurrence restent Z5/owners et sont seulement reliés.

La fermeture Z6 n'introduit aucun modèle, migration, HistoryItem, DayOfState, LiveState, UserTimeline, score, ranking ou cache propriétaire. Les gates CI, IDOR, privacy et absence de migration sont des critères de merge, pas des options.


## Z8 — profondeurs Passport, Resources et Groupes

Z8 conserve `GET /api/v1/me/` comme aperçu et ajoute/ferme les profondeurs owner-backed suivantes :

```text
GET  /api/v1/me/passport/
GET  /api/v1/me/resources/
GET  /api/v1/me/resources/<asset-id>/
GET  /api/v1/me/resources/versions/<version-id>/download/
POST /api/v1/me/resources/versions/<version-id>/reuse/
GET  /api/v1/me/collectives/groups/<group-id>/
```

Les vérités restent propriétaires : Passport réutilise Sharing/Trust, Resources réutilise Personal Assets/Trust, Groups réutilise Groups/Authorization. Aucune nouvelle vérité persistante ni migration Z8 n'est introduite.

Frontières contractuelles :

```text
Passport != Profile
Proof != Credential Trust
Credential Trust != AccessCredential
PersonalAsset != JourneyArtifact
PersonalAsset != Proof
posséder != satisfaire Requirement
Membership != authority
Assignment != Mandate
Group membership != Space authority
```

Resources est paginé et controller-scoped ; le détail expose versions/provenance/validité sans storage path, hash ou URL privée. Download/reuse passent par les services propriétaires. La réutilisation crée un JourneyArtifact et ne déclare aucun Requirement satisfait.

Le détail Group part de `groups_for_profile()`, rend un outsider en 404 et projette seulement la relation/capabilities dérivées des autorisations serveur. Aucun Permission/Mandate brut ni PII membre n'est sérialisé.

Voir `docs/architecture/z8-personal-capital-secondary-surfaces.md` pour le contrat complet.


## Z9 — Recognition, Loyalty et Partner

Z9 ferme les profondeurs personnelles de valeur mobilisable sans créer de domaine transversal de wallet ou de points.

```text
Recognition -> GET /api/v1/recognition/me/
Loyalty     -> GET /api/v1/loyalty/me/
Partner     -> GET /api/v1/me/partners/
               GET /api/v1/me/partners/<uuid>/
```

Recognition et Loyalty conservent leurs APIs personnelles owner-domain existantes ; Z9 les approfondit au lieu de les dupliquer. Partner conserve l'index compact Z4 et ajoute un détail strictement scoped au Profile connecté.

Invariants :

```text
Recognition != Loyalty != Partner
pas de wallet universel
pas de Makolo Points
pas de total de valeur transversal
pas de score social/ranking humain
Loyalty membership != authority
Partner relation != authority
Decimal + currency, sans somme inter-devise
GET side-effect free
```

Voir `docs/architecture/z9-mobilizable-value-surfaces.md`.


## Z10 — Continuité inter-surfaces

Z10 ne crée aucune vérité transverse. Il harmonise les identités canoniques, les links et les handoffs entre Maintenant, En cours, Historique, Jour J, Moi et Makolo Mark.

Les principaux ajouts sont :

- références Occurrence explicites dans les projections Ongoing/Now lorsqu'elles existent ;
- links owner-backed pour Dossier/Project et Mes accès ;
- handoff ActionProposal API vers le service Action Network canonique, avec contexte Space explicite lorsqu'il est requis ;
- décisions Recognition depuis Maintenant vers les endpoints Recognition existants ;
- Mark Jour J/Live rendu à Operations ;
- réutilisation PersonalAsset → JourneyArtifact idempotente sans modifier la sémantique Requirement.

Aucun modèle ni migration Z10 n'est ajouté. Voir `docs/architecture/z10-cross-surface-continuity.md`.
