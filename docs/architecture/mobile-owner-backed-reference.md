# Mobile owner-backed reference depth

**Statut :** référence d’implémentation Mobile  
**Programme :** A2 / REF-1  
**Verticale de référence :** Journey + Questionnaire  
**Principe :** le mobile conserve l’expérience locale utile ; les owners serveur conservent les vérités métier et l’autorité.

## 1. Objet

Cette verticale démontre le contrat owner-backed complet attendu pour les futures profondeurs Mobile.

Lecture :

```text
Owner API
  -> SyncSourceDefinition
  -> ProjectionSnapshots keyed
  -> Freshness
  -> feature selector
  -> presentation adapter
  -> UI locale
```

Mutation :

```text
FormRequest owner
  -> LocalDraft
  -> intention submit
  -> Outbox
  -> Questionnaires owner
  -> reconciliation
  -> refresh FormRequest
  -> invalidate/refresh Journey
  -> nouvelle vérité serveur
  -> UI converge
```

Ce document ne transfère aucune vérité métier au client.

## 2. Journey : lecture de référence

La source Journey est keyed :

```text
sourceKey       = journey:<journey-id>
owner           = Journeys
path            = api/v1/me/journeys/<journey-id>/
projectionKind  = personal.journey.detail
resourceKey     = <journey-id>
category        = keyedDetail
```

Le `JourneyRepository` lit et observe uniquement la projection Drift. Le réseau alimente le store via le `SyncEngine` commun.

Le comportement attendu est :

- projection locale présente : affichage immédiat, évaluation de fraîcheur, refresh discret si nécessaire ;
- projection absente : état d’acquisition honnête puis pull owner ;
- 403/404 : invalidation de la projection keyed concernée uniquement ;
- données locales anciennes : elles peuvent rester visibles lorsque le contrat de fraîcheur l’autorise.

## 3. Readiness et capabilities

Le client ne calcule jamais Readiness à partir de Journey, Form ou Requirement.

Il présente les groupes déjà fournis par l’owner :

- `ready` ;
- `actor_interventions` ;
- `waiting` ;
- `blockers` ;
- `next`.

De même, une action Form n’est exposée comme actionnable que si l’owner Journey fournit `complete_form`.

Aucun statut Journey ne sert de substitut à cette capability.

## 4. Questionnaire : owner-specific SyncSource

Le détail FormRequest n’utilise pas le `ProjectionEnvelope` personnel. Il s’agit d’un contrat owner-specific direct :

```text
GET /api/v1/questionnaires/requests/<id>/
```

La source locale est néanmoins normalisée dans le noyau commun :

```text
sourceKey       = questionnaire-request:<id>
owner           = Questionnaires
projectionKind  = questionnaire.form.request.detail
resourceKey     = <id>
category        = keyedDetail
```

Le parser valide le contrat owner avant écriture locale.

Les types de questions consommés sont ceux du backend :

- `short_text` ;
- `long_text` ;
- `boolean` ;
- `number` ;
- `date` ;
- `single_choice` ;
- `multiple_choice`.

Le client consomme aussi les contraintes owner : required, min/max length, min/max value, choices et help text.

La validation locale sert au confort. Le serveur reste autoritaire.

## 5. LocalDraft

Le brouillon Form utilise `LocalDrafts`, sans table parallèle.

Scope :

```text
Profile
+ owner = Questionnaires
+ resource_kind = form_request
+ resource_id = <request-id>
```

Le brouillon est sauvegardé localement avec debounce pendant l’édition.

Une reprise de l’application recharge le brouillon local. Lorsqu’un brouillon local existe, il n’est jamais écrasé silencieusement par une réponse serveur plus ancienne ou non confirmée.

Le brouillon ne devient pas une FormResponse canonique.

## 6. Submit : une intention humaine, deux appels owner

L’intention durable est :

```text
operation_kind = questionnaire.form.submit
owner          = Questionnaires
replay_policy  = refetch-before-retry
```

Le payload durable contient l’identifiant FormRequest, le Journey, les réponses et les liens owner déjà fournis par Journey.

L’exécution serveur respecte le contrat réel :

```text
POST <save-link>   { answers: ... }
POST <submit-link>
```

Le mobile n’invente pas d’endpoint de commit combiné.

## 7. Résultats ambigus et reprise

Un timeout ou une perte de réponse après envoi ne devient ni succès automatique ni échec définitif.

Avec `refetch-before-retry` :

1. l’opération passe en attente de confirmation si le résultat est ambigu ;
2. une lecture GET du FormRequest owner vérifie la vérité ;
3. si l’owner indique `submitted/completed`, l’intention est confirmée ;
4. si l’owner montre encore un draft/reopened actionnable, la tentative peut être rejouée après relecture ;
5. si l’état ou l’autorité ont changé, l’opération devient conflict/failed selon le cas.

Les opérations `awaiting_confirmation` restent éligibles à la réconciliation après redémarrage.

## 8. Validation serveur

Un rejet 400 du owner ne supprime jamais le travail local.

Les réponses restent dans LocalDraft et les erreurs serveur peuvent être présentées à l’utilisateur pour correction.

Le double submit est bloqué tant qu’une intention active existe déjà pour le même FormRequest.

## 9. Convergence après confirmation

Une soumission n’est considérée confirmée que lorsque l’owner l’atteste.

Après confirmation :

1. la projection FormRequest est mise à jour depuis la réponse owner ;
2. un refresh FormRequest est demandé ;
3. le draft local est supprimé ;
4. la source `journey:<id>` est invalidée ;
5. Journey est rafraîchie ;
6. la nouvelle projection Journey owner remplace l’ancienne ;
7. l’UI se met à jour depuis Drift.

Le client ne modifie jamais localement Readiness pour simuler cette convergence.

## 10. Runtime Outbox

`SyncLifecycle` exécute aussi le `OutboxProcessor` au démarrage synchronisable, au retour réseau, au resume et lors des refresh normaux.

Cela permet de poursuivre une intention durable sans demander à l’utilisateur de la recréer après interruption.

## 11. Navigation

La route réelle de référence est :

```text
StructuredDestination(kind=journey, id=...)
  -> /journeys/<id>
  -> JourneyDetailScreen
```

Depuis Journey, un Form actionnable ouvre la profondeur Questionnaire avec les liens owner portés par la projection Journey.

Les autres profondeurs Activity, Occurrence, Access, Dossier, Project et Group restent hors REF-1.

## 12. Anti-patterns

Ne pas créer :

- `JourneySyncEngine` ;
- `JourneyDatabase` ;
- `JourneyCache` ;
- une seconde Outbox ;
- une table Form mobile parallèle ;
- un calcul local de Readiness ;
- une capability déduite d’un status ;
- un endpoint mobile parallèle ;
- un faux succès offline ;
- une suppression globale de l’identité historique d’une ressource après 403/404.

## 13. Réutilisation future

Pour une nouvelle profondeur owner-backed :

1. identifier le vrai owner et son endpoint ;
2. définir un `SyncSourceDefinition` keyed ;
3. parser le contrat owner sans inventer de vérité ;
4. écrire dans `ProjectionSnapshots` ;
5. lire l’UI depuis Drift ;
6. définir la freshness ;
7. créer un selector de feature borné ;
8. conserver capabilities et décisions autoritatives telles que reçues ;
9. pour les mutations, documenter replay/reconciliation avant de mettre en Outbox ;
10. tester offline, restart, ambiguïté, invalidation scoped et convergence.

Journey + Questionnaire constitue la verticale de référence, pas un moteur métier générique à copier aveuglément.
