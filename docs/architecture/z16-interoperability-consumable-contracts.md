# Z16 — Exposition consommable de l’interopérabilité Makolo

**Statut : contrat backend Z16 — à intégrer après CI verte**  
**Base auditée : `main@ce1525075b61a7255e2a33ee8779af8a08c40008` — 28 septembre 2026**

## 1. Objectif

Z16 transforme les primitives M7 légitimement exposables en un contrat serveur stable pour les clients Web et Mobile, sans créer un second système de providers, Connections, Actions, Extensions, Webhooks, Permissions ou Domain Events.

Z16 reste un chantier de projection/read-model/API. Il ne construit ni W8, ni l’Avatar, ni une page Connexions, ni Flutter, ni la Console Espace, ni le shell Platform.

## 2. État réel avant Z16

L’audit du runtime courant établit :

- `InteroperabilityRegistry`, `ActionRegistry`, `ExtensionRegistry` et `WebhookSubscription` constituent bien le kernel générique M7 ;
- leurs instanciations présentes dans le dépôt sont actuellement des tests : aucun catalogue M7 générique installé en runtime n’est inventé par Z16 ;
- `intelligence.ProviderConnection` est en revanche une persistance réelle, avec scopes `PROFILE`, `SPACE`, `PLATFORM`, routes, état de santé et credential chiffré ;
- le routage automatique Intelligence continue de composer les routes Platform/Space/Profile sans être remplacé ;
- `GET /api/v1/platform/capabilities/` reste le contrat Platform existant et conserve `space_modules_included=false` et `personal_modules_included=false`.

Conséquence : une liste vide est une réponse valide et explicite. Z16 ne crée aucun faux provider, Action, Extension ou Webhook pour remplir un écran.

## 3. Contrat HTTP

Les namespaces existants sont réutilisés :

```text
PROFILE   GET /api/v1/me/interoperability/
SPACE     GET /api/v1/organizations/workspaces/<slug>/interoperability/
PLATFORM  GET /api/v1/platform/interoperability/
```

Le payload est versionné :

```json
{
  "schema_version": "z16.v1",
  "context": "profile",
  "providers": [],
  "connections": [],
  "actions": [],
  "extensions": [],
  "webhooks": [],
  "links": {"self": "/api/v1/me/interoperability/"}
}
```

Les réponses sont privées et `no-store`.

## 4. Available, connected, usable, manageable

Ces notions restent distinctes :

- `available` : une implémentation ou configuration exposable existe réellement ;
- `connected` : une Connection persistée existe ;
- `usable` : cette Connection peut actuellement être utilisée par cet acteur selon le contrat courant, son activation, son health et au moins une route active ;
- `manageable` : l’acteur possède l’autorité nécessaire pour administrer cette Connection.

Pour `ProviderConnection` Intelligence, le runtime courant ne possède pas de Permission atomique distincte « use » versus « manage ». Z16 n’invente donc pas une nouvelle galaxie de permissions : le même gate canonique gouverne actuellement l’usage explicite et l’administration, tandis qu’une Connection désactivée reste administrable mais non utilisable.

## 5. Projection des Connections Intelligence

Z16 ne déplace pas la persistance de `intelligence.ProviderConnection`. Il la projette via la frontière générique `ConnectionRef` et expose uniquement :

```text
id
scope
owner = intelligence
provider_protocol
display_name
available
connected
usable
manageable
enabled
status
health
capabilities
permissions.use
permissions.manage
```

`provider_protocol` reflète le protocole réellement persisté. Il ne prétend pas être un identifiant commercial de provider.

Le health est volontairement grossier : `invalid_credentials` est ramené à `unavailable` dans la projection client.

Ne sont jamais sérialisés :

```text
base_url
default_model
timeout_seconds
priority
last_latency_ms
ProviderCredential.encrypted_secret
ProviderCredential.key_hint
credential material
```

## 6. Autorité par scope

### Profile

Une Connection `PROFILE` est sélectionnée par `ProviderConnection.profile.user == request.user`. Un Profil ne peut donc pas lire la Connection personnelle d’un autre Profil.

### Space

Le contrat Z16 exige actuellement `space.manage` porté par un Mandate **directement scoped à l’Espace**. `TeamMembership`, `GroupMembership`, Assignment ou autorité Platform ne suffisent pas.

Z16 corrige aussi `authorize_provider_connection()` pour utiliser ce resolver direct Space lors d’une action explicite sur une Connection. Cela ferme le risque où `platform.manage`, qui s’étend légitimement aux permissions Platform dans le resolver général, pouvait être interprété comme autorité Space.

### Platform

Les Connections `PLATFORM` ne sont exposées qu’à `platform.manage`. La projection Platform n’inclut aucune Connection Profile ou Space.

Une capacité Platform utilisée en interne au bénéfice d’un Profil ne révèle pas pour autant la Connection Platform au Profil.

## 7. Providers, Actions, Extensions et Webhooks

Les registries M7 restent les abstractions canoniques. Z16 ajoute uniquement des méthodes d’inspection déterministes de leurs métadonnées stables ; aucun handler, callable, adapter ou objet runtime n’est sérialisé.

Le contrat sait projeter :

- un `ProviderDefinition` : `code`, `available`, `capabilities` ;
- une `ActionDefinition` : `code`, `capability`, `owner`, `requires_connection`, `available`, `authorized`, `idempotency_required` ;
- une `ExtensionDefinition` : `code`, `actions`, `read_projections`, `ui_slots`, `available`, `enabled` ;
- un `WebhookSubscription` : métadonnées minimales seulement, et familles d’événements uniquement lorsqu’un contrat appelle explicitement cette divulgation.

Le runtime courant n’installe aucun de ces catalogues génériques hors tests. Les API Z16 retournent donc actuellement `providers: []`, `actions: []`, `extensions: []`, `webhooks: []` plutôt que d’inventer un catalogue.

Un Webhook projeté ne révèle jamais endpoint brut, `signing_key_id`, secret de signature, payload privé, replay state ou internals de worker.

## 8. Domain Events

Z16 ne rend pas `DomainEventOutbox`, `DomainEventConsumption`, payloads privés, retries ou workers consommables par l’UX. Les Events ne peuvent apparaître qu’indirectement dans un contrat Extension/Webhook explicitement allowlisté.

## 9. Sécurité

Les tests Z16 couvrent explicitement :

- Profile A ne voit pas Connection Profile B ;
- TeamMembership seule n’ouvre pas les Connections Space ;
- autorité Platform seule n’ouvre pas une Connection Space ;
- autorité d’un autre Space n’ouvre pas le Space courant ;
- Connection désactivée : `usable=false` ;
- credential, `encrypted_secret`, `key_hint` et endpoint provider ne sont jamais sérialisés ;
- Platform ne reçoit que les Connections Platform ;
- les registres ne sérialisent ni handler, ni callable, ni adapter ;
- les Webhooks ne sérialisent ni endpoint ni référence de secret.

## 10. Persistance et migrations

Z16 n’ajoute aucune vérité métier persistante et ne nécessite aucune migration. Il compose selectors, projections et APIs autour des owners existants.

Les adapters Payments, Spatiotemporal, Geocoding, Notifications et autres providers spécialisés restent dans leurs domaines propriétaires tant qu’un besoin réel ne justifie pas une composition M7.

## 11. Handoff W8 et programme A2.x

Après Z16, W8 et les sous-tâches pertinentes du programme A2.x peuvent consommer le même contrat pour le Profil :

```text
Profil
→ Avatar
→ Connexions
→ GET /api/v1/me/interoperability/
```

Ils reçoivent sans réinterpréter le métier :

- le catalogue réellement installé, aujourd’hui possiblement vide ;
- les Connections personnelles réellement persistées ;
- leur état non sensible ;
- les Actions autorisées lorsqu’un owner en installe réellement ;
- les Extensions allowlistées lorsqu’elles existent ;
- des liens serveur stables et des empty states explicites.

Ils n’ont jamais besoin de connaître `InteroperabilityRegistry` Python, `ActionRegistry`, `ExtensionRegistry`, l’ORM, les credentials, `DomainEventOutbox` ou les workers.

Le handoff ne préjuge pas de la hiérarchie UX W8/A2.x et ne crée aucune page. A2 est un groupe de sous-tâches ; un checkpoint d’intégration ne vaut pas fermeture de l’ensemble du programme.

## 12. Frontières / non-objectifs

Z16 ne construit pas de marketplace, plugin runtime arbitraire, nouveau scheduler, event bus, système de Permissions, Connector fictif, provider commercial, credential store, UI Web ou mobile.

Il ne réécrit pas le Space Workspace Z15/W7, ne déplace aucun owner métier et ne transforme pas M7 en propriétaire des vérités spécialisées.

## 13. Lecture correcte de M7

```text
M7 kernel livré
≠ tous les providers/extensions installés
≠ toutes les Connections exposées aux clients
```

Après intégration de Z16 :

```text
M7 kernel livré
+ Z16 contrat consommable livré
+ providers/actions/extensions concrets seulement lorsqu’un owner les installe réellement
```
