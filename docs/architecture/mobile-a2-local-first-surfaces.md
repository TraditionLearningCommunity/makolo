# A2 — Local-first surface matrix

> **Statut : contrat A2-P0**
>
> A2 suit : UI → repository → store local ↔ sync owner-scoped ↔ backend.
>
> Aucune surface ne contourne le repository pour faire GET → spinner → écran à chaque visite.

## 1. Règles communes

Deux axes sont toujours distincts.

### État de contenu

~~~text
initial
loading
content
empty
success
error
~~~

### État de synchronisation

~~~text
synced
syncing
pending
offline
conflict
failed
stale
~~~

Le store local possède l'expérience personnelle déjà disponible sur l'appareil. Le serveur possède les vérités partagées, globales, concurrentes ou autoritatives.

Classes d'opérations :

- **A** — entièrement locale ;
- **B** — locale puis synchronisée ;
- **C** — préparable localement, confirmée à distance ;
- **D** — intrinsèquement distante.

## 2. Matrice

| Surface | Store local | Sync source | Offline | Freshness | Mutation locale | Classe |
|---|---|---|---|---|---|---|
| Maintenant | projection_snapshots, source A1 personal.now | GET /api/v1/me/now/ | lecture du dernier snapshot utile | meta.generated_at + dates locales de réception/vérification ; signaler stale si décision sensible | aucune inclusion recalculée ; drafts owner-safe seulement | A lecture, C/D actions owner |
| Découvrir | cible A2 : pack borné dans projection_snapshots/resource_index + cache média autorisé | GET /api/v1/discovery/items/ | parcourir/rechercher seulement le corpus déjà acquis | TTL/policy du pack à fixer centralement ; stale explicite | query/filtres/scroll A ; save/watch seulement via owner | A lecture locale, B/C selon owner, D global discovery |
| Makolo Mark | local_drafts pour l'intake ; résultat serveur non inventé | POST /api/v1/me/mark/ | conserver le texte ; ne pas prétendre l'avoir compris/envoyé | âge du draft, pas fraîcheur métier | brouillon local ; pas de blind queue sensible | A draft, D orchestration, C pour action à confirmer |
| En cours | projection_snapshots, source A1 personal.ongoing | GET /api/v1/me/ongoing/ | lecture des engagements connus | même discipline que Maintenant ; revalidation avant action sensible | aucun status/readiness recalculé | A lecture, C/D actions owner |
| Moi | projection_snapshots, source A1 personal.me | GET /api/v1/me/ | consultation privée locale | section par section ; identité/autorité à revalider si action | préférences/drafts owner-safe seulement | A lecture, B/C selon owner |
| Avatar | session/token store + identité minimale ; éventuellement projection locale de contexte autorisé centralisée | GET /api/v1/accounts/auth/me/ + GET /api/v1/organizations/workspaces/ lorsque nécessaire | afficher identité déjà connue et actions purement locales ; aucune autorité nouvelle | auth et contextes d'autorité exigent vérification serveur | contexte UX local possible ; changement d'autorité jamais local | A UX, D autorité |
| Notifications si utilisées | source locale bornée à installer centralement si A2 les expose | /api/v1/notifications/ + unread-count/detail/read | lecture locale connue ; pas de push requis en A2 | refresh court selon besoin | read peut être sync explicite si contrat retenu | A lecture, B/C read selon implémentation |
| Conversations si utilisées | aucune racine A1 actuelle ; slice à décider centralement | /api/v1/conversations/ | uniquement conversations déjà mises en cache si slice installé | conversation owner/server authoritative | drafts possibles ; envoi distant | A draft/lecture, C/D envoi |

Les clés exactes de nouvelles sources locales A2 sont figées par l'orchestrateur en P1 après merge A1. Une lane ne modifie pas seule Drift ou SyncEngine.

## 3. Maintenant

### Première ouverture

Si personal.now n'existe pas encore :

- montrer un état de première synchronisation ;
- ne pas afficher Tout est en ordre ;
- skeleton seulement si la synchronisation est réellement en cours et aucun contenu local n'existe.

### Données déjà locales

- rendre immédiatement le snapshot ;
- lancer un refresh discret selon lifecycle/policy ;
- mettre à jour le store avant de remplacer l'UI.

### Refresh

- garder les items visibles ;
- indiquer syncing de manière discrète ;
- ne jamais recalculer localement la priorité ou l'appartenance à Maintenant.

### Offline

Avec snapshot :

~~~text
content + offline
~~~

Sans snapshot :

- expliquer qu'une première connexion est nécessaire ;
- aucune fausse conclusion all-clear.

### Stale

Afficher stale seulement si l'ancienneté peut changer l'action. Une donnée ancienne reste utile à la compréhension tant qu'elle n'est pas mensongère.

### Retour réseau

Sync → store → UI. Pas de reset de route.

### Erreur serveur

Conserver le snapshot ; afficher un message récupérable.

### Session expirée

Conserver le store Profile ; demander reconnexion ; revalider les actions distantes après auth.

### Resume

Même onglet, même scroll autant que possible, refresh discret.

## 4. En cours

La source A1 personal.ongoing contient déjà une projection composée par le serveur.

Le client ne recalcule jamais :

- Readiness ;
- blocking ;
- waiting ;
- actionability ;
- Access validity ;
- Capacity ;
- Payment state.

Il présente les champs fournis : kind/source/state/title/ready/actor_interventions/continuation/blocker/next/timing/place/capabilities/links lorsqu'ils existent.

Offline :

- les engagements déjà connus restent consultables ;
- toute mutation sensible suit son owner ;
- un état local ancien n'est pas présenté comme confirmation actuelle d'une capacité partagée.

## 5. Moi

personal.me est déjà une racine A1.

Le cache est privé et isolé par Profile.

A2 présente les previews serveur :

- identity ;
- passport ;
- considerations ;
- collectives ;
- resources ;
- support ;
- links.

A2 ne transforme pas ces previews en nouvelles tables métier ni en profil social.

L'autorité d'un Espace ne se déduit jamais des teams/groups. Le serveur fournit séparément authorized_spaces dans la projection collectives.

## 6. Découvrir — changement local partagé attendu

A1 ne bootstrappe pas encore Discovery.

A2 doit rendre Découvrir utile après acquisition d'un pack borné sans copier l'écosystème complet sur le téléphone.

Cible :

~~~text
GET /api/v1/discovery/items/
→ repository Discovery
→ snapshot/pack local borné
→ resource_index
→ média cache autorisé
→ UI
~~~

Le pack local peut conserver ce qui est nécessaire à l'usage :

- identity/candidate key ;
- representation ;
- timing ;
- place ;
- owner display ;
- availability connue ;
- price connue ;
- personal_relation ;
- saved/watch state ;
- capabilities ;
- links ;
- provenance minimale utile ;
- pagination/page boundary nécessaire au corpus acquis.

Il ne conserve pas :

- moteur de ranking global ;
- copie de toutes les Activities ;
- calcul de disponibilité globale ;
- Permission/Capacity recalculée ;
- média sans contexte.

Recherche offline :

- seulement dans le corpus local ;
- l'UI dit implicitement ou explicitement que la recherche est limitée au contenu disponible hors connexion lorsque cela peut prêter à confusion.

Fin de corpus :

- vraie fin ;
- option d'élargir quand le réseau permet une nouvelle recherche ;
- jamais de relâchement silencieux des critères pour continuer le scroll.

### Ownership du changement partagé

Si une migration Drift, une nouvelle sync source ou un index supplémentaire est nécessaire :

1. la lane Explore/Self décrit le besoin ;
2. l'orchestrateur implémente le changement sur mobile/a2-integration ;
3. la migration est testée ;
4. les lanes se réconcilient sur ce checkpoint.

## 7. Makolo Mark

Le draft est local-first ; l'interprétation ne l'est pas.

### Draft

- stocker le texte sous Profile ;
- restaurer après background/relaunch si approprié ;
- supprimer/archiver après résolution selon comportement défini ;
- ne jamais inscrire un résultat completed localement sans serveur.

### Submit

Contrat actuel :

~~~text
POST /api/v1/me/mark/

input:
  kind: text
  value: ...
context:
  ...
~~~

Le serveur accepte aujourd'hui le texte et borne la valeur. Les états métier normaux incluent :

~~~text
resolved
completed
needs_clarification
needs_confirmation
unknown
unsupported
forbidden
~~~

Ils ne sont pas automatiquement des erreurs HTTP.

### Offline

- garder le draft ;
- afficher une indication courte ;
- ne pas lancer automatiquement une action sensible à la reconnexion ;
- ne pas inventer une compréhension locale.

### Confirmation

La conséquence humaine est expliquée. Après confirmation, le serveur/owner revalide encore l'autorité et l'état courant. Une clé d'idempotence est utilisée si le contrat owner l'exige.

## 8. Avatar et contexte acteur

Identité auth :

~~~text
GET /api/v1/accounts/auth/me/
~~~

Inventaire permissionné des Espaces :

~~~text
GET /api/v1/organizations/workspaces/
~~~

Cette collection vient des Permissions/Mandates et non d'une membership brute.

Important :

> inventaire d'Espaces autorisés ≠ contrat local pour devenir cet acteur.

Le runtime personnel rejette les paramètres client qui tentent de créer une autorité comme act_as_space ou space_id. A2 ne crée donc aucun switch d'autorité silencieux.

Si un vrai handoff de contexte devient disponible avant P1, l'orchestrateur l'ajoute au contrat. Sinon A2 montre seulement les actions de compte réellement supportées et n'affiche pas un faux Agir comme.

Logout :

- ne pas perdre silencieusement un draft ou une opération pending ;
- distinguer logout de suppression de compte/appareil ;
- fermer l'accès aux secrets locaux selon le mécanisme A1 ;
- l'isolation Profile reste obligatoire au prochain login.

## 9. Notifications

Le backend dispose déjà de :

- GET /api/v1/notifications/
- GET /api/v1/notifications/?filter=unread
- GET /api/v1/notifications/unread-count/
- GET /api/v1/notifications/<id>/
- POST /api/v1/notifications/<id>/read/

A2 n'a pas besoin de push pour être correct.

Décision P0 :

- pas d'icône Notification dans le header tant qu'une destination mobile stable n'est pas raccordée ;
- si l'orchestrateur accepte le slice, il est owner-scoped, borné, privé et local-first pour les lignes déjà acquises ;
- la navigation structurée de la notification passe par le DeepLinkResolver ;
- aucune PII inutile dans les previews.

## 10. Conversations

Le backend expose /api/v1/conversations/ et des profondeurs owner-scoped.

Décision P0 :

- aucune icône morte ;
- pas de reconstruction d'un chat générique pour satisfaire le header ;
- si une liste courte et stable entre dans A2, l'orchestrateur installe d'abord son repository/store contract ;
- drafts peuvent être locaux ;
- envoi et autorité restent distants.

## 11. Freshness

Chaque repository exposant une projection A2 doit pouvoir déterminer au minimum :

- snapshot présent ou absent ;
- received_at ;
- generated_at lorsque fourni ;
- dernière vérification online lorsque disponible ;
- état sync ;
- besoin éventuel de revalidation avant mutation.

Aucune règle universelle de TTL n'est inventée. Le TTL dépend du domaine/risque.

Exemples :

- bio personnelle : peut rester utile longtemps ;
- Capacity ou disponibilité : peut exiger fraîcheur stricte ;
- notification déjà lue : convergence serveur ;
- Discovery pack : politique bornée explicite ;
- Mark draft : son âge n'est pas une fraîcheur métier.

## 12. Résilience

Pour chaque surface tester :

~~~text
launch online
launch offline avec snapshot
launch offline sans snapshot
refresh online
refresh qui échoue
passage online → offline
passage offline → online
background → resume
session expirée
logout/relogin autre Profile
~~~

Le résultat attendu est la continuité, pas un écran d'erreur global.
