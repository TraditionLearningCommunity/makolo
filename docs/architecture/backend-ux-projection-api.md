# Z1 — Contrat transversal Backend UX Projection & API Composition

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

`docs/architecture/mobile-api-contract.md` reste le contrat historique du premier MVP Event/Ticket pour les endpoints qu'il documente. Il n'est plus le contrat complet de l'expérience Mature.

## 15. Lots suivants

```text
Z2 → Maintenant
Z3 → Découvrir + détail/conservation/veille selon réconciliation
Z4 → Moi + capital personnel/collectifs + Recognition/Loyalty/Partner
Z5 → Journey / Activity / Occurrence / Dossier détails utiles
Z6 → Access / History / Requirements / Readiness / Capacity gaps seulement
Z7 → Makolo Mark et gaps restants, sans faux moteur intelligent
Z8+ → autres surfaces secondaires et handoff mobile
```

## 16. Critères de sortie Z1

Z1 est fermé lorsque l'enveloppe est définie/testée ; `/api/v1/me/` est réservé sans route vide ; auth `me` et UX `Moi` sont distincts ; types/erreurs/vide/null/unknown/confidentialité sont contractés ; serveur vs présentation client est explicite ; capabilities restent serveur ; Flutter n'a pas à parser du texte ; les APIs domaine restent réutilisables ; aucune migration, aucun modèle et aucun algorithme/ranking/score n'est ajouté ; tests ciblés et contrôle migrations restent verts.
