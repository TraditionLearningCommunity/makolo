# ZS6 — Space Projection Final Handoff

**Programme :** ZS — Space UX Projection  
**Branche d’intégration :** `zs6-space-projection-reconciliation`  
**Base initiale vérifiée :** `main@ef1e0f5a25233cfe240588d42c5902cbdf70ebe9`  
**Statut :** réconciliation finale en cours de gate CI ; l’état « intégré » n’est déclaré qu’après merge réel.

## 1. Périmètre et résultat

ZS6 assemble les checkpoints ZS sans créer de nouvelle vérité métier.

Chaîne finale :

~~~text
vérité owner
→ selector / service / autorisation
→ projection UX serveur
→ API stable
→ Web / Mobile
~~~

ZS6 n’ajoute :

- aucun modèle ;
- aucune migration ;
- aucun template ;
- aucun CSS ;
- aucun code Flutter ;
- aucun ranking, score, recommandation ou moteur Molongo ;
- aucun cache métier persistant ;
- aucun second système Permission, Readiness ou Live.

Une collection vide est un résultat valide.

## 2. Checkpoints réconciliés

La branche ZS6 conserve les checkpoints publiés comme parents Git identifiables :

| Checkpoint | Branche | HEAD intégré | Rôle |
| --- | --- | --- | --- |
| ZS1 | `zs1-space-ux-projection-foundation` | déjà présent dans `main@ef1e0f5...` | contexte Space, autorité, responsabilités, langage |
| ZS3 | `zs3-space-work-archetype-projections` | `36cc131cd803c8c368bd3013d5087b89a141588b` | Métier |
| ZS4 | `zs4-space-us-relations-pilot-projections` | `39df7713b2a044fa0f9863ba6403b2f47fc14afb` | Nous, Relations, Piloter |
| ZS5 | `zs5-space-day-of-live-scanner-mark` | `235ce2220c3e9a56425ed364a3d297a7ebef1266` | Jour J, Live, Scanner, Mark |

Les collisions de `organizations/api/urls.py` sont résolues par composition : aucune route d’un checkpoint n’est choisie au détriment d’une autre.

## 3. État réel de ZS2

L’audit GitHub/runtime n’a trouvé :

- aucune branche ZS2 ;
- aucune PR ZS2 ;
- aucun endpoint Space `now/` ou `discover/` livré sous un autre nom.

L’ancien `overview_for_console()` ne constitue pas le contrat ZS2 : il dérive notamment des compteurs d’attention depuis Payments, Capacity, Requests ou Automation et ne doit pas devenir par accident un algorithme de sélection « Maintenant ».

ZS6 ferme donc uniquement le gap minimal compatible avec le programme :

~~~text
GET /api/v1/organizations/workspaces/<slug>/now/
GET /api/v1/organizations/workspaces/<slug>/discover/
~~~

Ces deux projections sont :

- authentifiées ;
- actor-scoped ;
- authority-aware ;
- privacy-safe ;
- bornées ;
- sans ranking ;
- sans heuristique métier.

En l’absence de sélecteur owner/Molongo suffisamment sûr, leur contrat volontaire est :

~~~json
{
  "selection": {
    "state": "unavailable",
    "reason": "no_safe_selection_contract"
  },
  "items": [],
  "has_more": false
}
~~~

`items=[]` signifie collection connue vide pour cette projection. `selection.state=unavailable` signifie qu’aucun mécanisme de sélection défendable n’est actuellement disponible. Le client ne doit ni reranker ni inventer des candidats.

## 4. Endpoints Space finaux

| Expérience | Endpoint | Owner principal | Scope | Règle client |
| --- | --- | --- | --- | --- |
| Bootstrap Space | `GET /api/v1/organizations/workspaces/<slug>/` | Organizations + Authorization | Space / Activity-limited | utiliser contexte, responsabilités, links et capabilities serveur |
| Maintenant | `GET /api/v1/organizations/workspaces/<slug>/now/` | composition multi-owner future | Space / responsibility | rendre `items`; ne pas inventer sélection ou urgence |
| Découvrir | `GET /api/v1/organizations/workspaces/<slug>/discover/` | Discovery/owners futurs | Space | rendre `items`; ne pas reranker |
| Métier | `GET /api/v1/organizations/workspaces/<slug>/work/` | Activity + owners verticaux | Space / Activity | rendre les sections owner-backed |
| Nous | `GET /api/v1/organizations/workspaces/<slug>/us/` | Organizations / Authorization / Trust | authority-aware | identité collective, responsabilités et ownership selon scope |
| Relations | `GET /api/v1/organizations/workspaces/<slug>/relationships/` | Team / Groups / CRM / Audiences / Partners | authority-aware | préserver chaque relation kind |
| Piloter | `GET /api/v1/organizations/workspaces/<slug>/pilot/` | Analytics + owners | Space authority | distinguer zéro, inconnu et données insuffisantes |
| Makolo Mark | `POST /api/v1/organizations/workspaces/<slug>/mark/` | orchestration + owner | acting Space | suivre le handoff owner, confirmer puis refetch |
| Jour J opérateur | `GET /api/v1/operations/occurrences/<id>/day-of/` | Occurrence + Operations | Occurrence | ouvrir seulement lorsqu’une perspective opérateur réelle existe |
| Live | `GET /api/v1/operations/occurrences/<id>/live/` | Operations | Occurrence | ne jamais transformer du planifié en observé |
| Scanner | `GET /api/v1/scanner/occurrences/<id>/context/` | Scanner + Access/Operations | Occurrence / Activity | capability et autorité serveur ; Assignment seul ne suffit pas |

Aucun namespace `/api/v1/mobile/` n’est créé.

## 5. Matrice de convergence réelle

| Surface | Source canonique réelle | Owner | Projection ZS | Handoff |
| --- | --- | --- | --- | --- |
| Maintenant | aucun sélecteur Space sûr livré à ce jour | owners futurs | Space Now vide + selection unavailable | aucun faux owner link par item |
| Découvrir | Discovery globale existe, mais aucun sélecteur collectif Space sûr n’est livré | Discovery + owners | Space Discover vide + selection unavailable | aucun faux owner link par item |
| Métier | Activity, Occurrence, Journey, Offer, CommerceOrder, TransportRoute, Vehicle | domaines concernés | Work | Activity/Occurrence ou owner disponible |
| Nous | Organization, Team, Mandate, Trust | Organizations / Authorization / Trust | Us | owners existants |
| Relations | TeamMembership, Group, CRMContact, Audience, Partner | owners respectifs | Relationships | collections owner lorsque disponibles |
| Piloter | Analytics portfolio et droits Analytics | Analytics | Pilot | overview Analytics |
| Jour J | Occurrence + Operations | Activities / Operations | Day-of | Live / readiness / queues / checkpoints / placements |
| Live | observations et projections Operations | Operations | Live | owner Operations |
| Scanner | Occurrence + permission canonique + Access owner | Scanner / Access | Scanner context | Scan seulement si endpoint owner compatible |
| Mark | intention + acting Space | orchestrateur + owners | Mark | Operations, Scanner, Organizations selon intention reconnue |

Invariant :

~~~text
une réalité canonique
→ un owner
→ plusieurs projections UX
→ même kind + id
→ links + capabilities
~~~

La projection ne devient jamais propriétaire de la réalité.

## 6. Métier et archétypes

Les sections communes ZS3 restent :

~~~text
preparation
upcoming
active
blocked
completed
~~~

Ce sont des regroupements UX dérivés ; les états owners restent sérialisés séparément.

Le vocabulaire primaire reste centralisé dans `organizations.space_product` :

| Archetype | Label |
| --- | --- |
| generic | Activités |
| creative | Créations |
| media | Productions |
| education | Programmes |
| commerce | Commerce |
| service_provider | Prestations |
| transport_operator | Transport |
| community | Initiatives |

L’archetype ne donne aucune Permission.

`blocked` n’est produit pour Journey que depuis un `JourneyBlocker` owner actif. Requirement, Payment ou archetype ne deviennent pas heuristiquement blocker.

## 7. Nous, Relations et Piloter

### Nous

`Nous` représente l’identité collective, les responsabilités, Team, ownership et Trust autorisés. Il n’est pas Settings.

Une autorité Activity-only reçoit une projection volontairement réduite et ne récupère pas Team globale ni ownership global.

### Relations

Les relations restent distinctes :

~~~text
TeamMember
CRMContact
GroupMember
Partner
Mandate holder
participant
~~~

Une même personne peut être référencée dans plusieurs relations sans création d’une identité parallèle.

### Piloter

`0` reste une valeur connue lorsqu’elle est réellement mesurée.

Une métrique non interprétable reste par exemple :

~~~json
{
  "state": "insufficient_data",
  "value": null
}
~~~

`signals: []` est valide. Aucun health score, performance score, relevance score ou tendance synthétique n’est ajouté.

## 8. Jour J, Live, Scanner et Mark

### Jour J

Jour J est occurrence-scoped. Aucun état global `Space = live` n’existe.

### Live

Live reste propriété d’Operations. ZS5 compose la projection Operations existante et ne transforme pas une planification en observation.

### Scanner

`ScannerAssignment` reste une responsabilité opérationnelle. `user_can_scan_activity()` décide l’autorité réelle avant d’exposer la capability Scanner.

Lorsque l’owner scan générique n’existe pas pour une Activity non Event, la projection expose honnêtement `next_scan.state=unavailable` au lieu d’inventer un endpoint.

### Makolo Mark

Le Mark Space :

- résout le Space depuis le serveur ;
- n’accepte pas une Permission/Mandate/actor fournie par le client ;
- traite la responsabilité comme contexte, jamais comme autorité ;
- revalide l’autorité au moment de la mutation ;
- remet la mutation au service owner lorsqu’il existe ;
- ne crée pas directement une vérité métier par ORM dans l’orchestrateur.

## 9. Autorité finale

| Acteur | Accès attendu |
| --- | --- |
| non authentifié | refus auth |
| outsider | 404 privacy-safe |
| Space Owner | projections autorisées par Permissions |
| Space Admin / Manager | projections selon Mandates/Permissions réels |
| Finance | uniquement profondeurs autorisées ; aucune autorité Team implicite |
| Activity-scoped Mandate | uniquement Space minimal + Activities mandatées ; aucune donnée globale étrangère |
| Scanner Permission | Scanner uniquement dans son scope réel |
| TeamMember sans Mandate | aucune autorité Space |
| GroupMember sans Mandate | aucune autorité Space |
| Assignment sans Mandate | aucune autorité Space |
| Partner | relation, jamais autorité implicite |
| Platform authority seule | aucune autorité Space |
| multi-Mandate | union des droits canoniques, jamais de droit inventé par une responsabilité UX |
| Mandate révoqué | capability précédente invalide ; nouveau GET/POST revalide et refuse |

Les tests ZS1, ZS3, ZS4, ZS5 et ZS6 couvrent ensemble ces frontières, y compris activity-scoped authority, minimal disclosure et révocation.

## 10. TOCTOU et IDOR

Une capability de projection est informative, pas un token.

Le contrat reste :

~~~text
GET projection
→ capability présente
→ Mandate révoqué
→ mutation owner
→ refus
~~~

Les checkpoints couvrent notamment Team, Scanner et Mark. Les ressources étrangères privées restent 404/privacy-safe et leurs métadonnées ne sont pas exposées par les projections racines.

## 11. Secrets et divulgation minimale

Les projections ZS générales ne transportent pas :

- AccessCredential secret ;
- QR/token brut ;
- private storage key ;
- private proof evidence ;
- review staff notes ;
- API token ;
- provider secret ;
- private key.

Access, AccessCredential et AccessUse restent trois réalités distinctes.

## 12. Known / absent / unknown / unavailable / hidden

Les contrats finaux conservent les distinctions sémantiques :

- collection connue vide → `[]` ;
- absence connue → `null` lorsque le contrat le prévoit ;
- sélection non disponible → état `unavailable` explicite ;
- donnée insuffisante → `insufficient_data` ;
- ressource privée étrangère → omission ou 404 privacy-safe ;
- zéro mesuré → `0`, jamais « inconnu ».

Le frontend ne transforme pas `unknown` en `false`, `unavailable` en `0` ou `hidden` en absence métier.

## 13. Performance et bornes

ZS6 n’ajoute aucun cache.

Les bornes existantes sont conservées :

- Work : preview de 20 items par section ;
- Relationships : preview de 12 items par collection ;
- Pilot : Analytics réutilise son coverage owner borné ;
- Jour J/Scanner : projections occurrence-scoped ;
- Maintenant/Découvrir ZS6 : collection vide constante tant qu’aucun sélecteur sûr n’existe.

Aucune optimisation spéculative n’est introduite. La CI finale et les tests de performance déjà canoniques restent le gate global.

## 14. Handoff Web / Mobile

Le contrat commun est :

~~~text
Web / Flutter
→ afficher
→ naviguer via links
→ appeler une action owner
→ refetch
~~~

et non :

~~~text
Web / Flutter
→ reconstruire Permission
→ déduire blocked
→ déduire Live depuis l’heure
→ déduire Scanner depuis Assignment
→ convertir absence métrique en 0
→ reranker Maintenant/Découvrir
~~~

Le client conserve sa pile de navigation ; aucun état persistant `came_from_*` n’est créé.

## 15. Gaps volontairement hors ZS

Restent volontairement hors de ce programme :

- algorithmes Molongo ;
- ranking, pertinence, priorité et recommandation ;
- enrichissement futur de Maintenant Space ;
- enrichissement futur de Découvrir Space ;
- W/templates et pixel design ;
- Flutter ;
- nouvelle capacité métier qui n’a pas encore d’owner API stable ;
- scan générique non-Event tant que l’owner ne possède pas un endpoint de mutation adéquat.

Ces gaps n’obligent pas le frontend à inventer une autorité ou une vérité métier.

## 16. Gates ZS6

Avant merge final, le HEAD de la PR doit satisfaire :

- tests ZS1 ;
- tests ZS3 ;
- tests ZS4 ;
- tests ZS5 ;
- tests ZS6 de réconciliation ;
- sécurité/IDOR/TOCTOU concernés ;
- Operations/Scanner/Access concernés ;
- `python manage.py check` ;
- `python manage.py makemigrations --check --dry-run` ;
- CI GitHub obligatoire complète.

Aucun test ne doit être affaibli pour obtenir du vert.

## 17. État final intégré

Le programme ZS est intégré.

- PR finale : **#419 — ZS6 — Final Space projection reconciliation and Web/Mobile handoff**.
- Merge réel : `be289f4c0e1c044d297228505b73d0bab789e99c`.
- Base de `main` immédiatement avant le merge ZS6 : `e2afe23b9cd42fc4dff5a1f4b8fd84db44599a05` (Performance — transversal read-path foundation v2, #418).
- Checkpoints ZS3 / ZS4 / ZS5 intégrés et reconnus par GitHub comme merged/closed : #414, #415, #416.
- État ZS2 réel : aucune branche/PR historique ; gap minimal fermé dans ZS6 par les contrats Space Now/Discover sans ranking ni heuristique.
- CI finale de #419 : verte sur CI, Security supply chain, Beta seed validation, Funding PostgreSQL, Conversation PostgreSQL, Observer PostgreSQL et Subscriptions.
- Diff ZS6 : aucun modèle, aucune migration, aucun template, aucun CSS, aucun Flutter, aucun algorithme Molongo.
- Vérification post-merge : routes Space `now/`, `discover/`, `work/`, `us/`, `relationships/`, `pilot/`, `mark/` présentes ; routes Jour J, Live et Scanner occurrence-scoped présentes.
- Aucun checkpoint ZS ne reste ambigu à merger indépendamment.

Le HEAD ci-dessus est le merge ZS6 lui-même ; un commit documentaire post-merge peut naturellement avancer `main` après cette clôture sans modifier le contenu fonctionnel du train.
