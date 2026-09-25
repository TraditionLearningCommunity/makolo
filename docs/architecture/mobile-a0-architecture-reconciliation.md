# A0 — Mobile Architecture Reconciliation

> **Statut : architecture mobile canonique après M10 — 25 septembre 2026**
>
> **Base auditée :** 'main@42ba16ea4b08814cba568994c691cca87a110474'
>
> Le code, les migrations, les tests et le 'main' courant restent prioritaires si ce document vieillit. A0 ne remplace pas les vérités des domaines Makolo : il fixe la manière dont un client Flutter installé les consomme, les projette localement et les synchronise.

## 1. Objet et verdict

A0 répond à une question unique :

> **Comment construire Makolo comme véritable application installée local-first, tout en restant un client des vérités et calculs autoritatifs du serveur Makolo ?**

La réponse retenue est :

~~~
Serveur Makolo
vérités partagées + calculs + arbitrages
              ↕
       sync owner-scoped
              ↕
 projection locale par Profile/appareil
       ↙                 ↘
 outbox durable      fichiers privés
       ↘                 ↙
          repositories
               ↓
               UI
~~~

Pour une donnée déjà présente sur l'appareil, l'UI lit le store local. Le réseau sert à synchroniser, enrichir, rafraîchir, confirmer, arbitrer, découvrir globalement et exécuter les opérations intrinsèquement distantes.

Le client n'est ni un navigateur Django emballé, ni une copie SQLite de PostgreSQL, ni un mini-serveur Makolo, ni une seconde implémentation des règles métier.

**Verdict A0 : aucun nouveau domaine backend, aucune migration et aucun endpoint '/api/v1/mobile/' ou '/sync/' générique ne sont nécessaires pour commencer A1.**

## 2. Sources de vérité réconciliées

Ordre appliqué pendant A0 :

1. code, migrations et tests du 'main' audité ;
2. 'makolo-domain-blueprint.md' ;
3. docs canoniques M8/Z/M10 et docs des domaines propriétaires ;
4. Product Language et Brand ;
5. 'Makolo Application Behavior & Interaction System v1.1' du 25 septembre 2026 ;
6. 'Makolo Local-First Synchronization & Offline Execution Architecture' du 25 septembre 2026 ;
7. état GitHub courant ;
8. historique mobile seulement comme contexte.

L'ancienne expérimentation A0/#248 reste une source d'idées. Elle n'est pas une base d'intégration.

## 3. État runtime audité

### 3.1 Git et mobile

À la base auditée :

- 'main' est '42ba16ea4b08814cba568994c691cca87a110474' ;
- la CI agrégée du commit est verte ;
- aucun package Flutter 'mobile/' n'existe sur 'main' ;
- la branche historique 'mobile/a0-phase-0-foundation' existe mais sa PR #248 est fermée sans merge ;
- les PR W5/W6 modifient surtout les surfaces Web/Expanded et n'entrent pas en collision avec le store/sync mobile ; W6 touche cependant le shell global et doit être relu avant toute copie visuelle en A2 ;
- la PR Space archetypes comporte des migrations mais n'est pas une base du mobile.

A0 part donc exclusivement du 'main' courant.

### 3.2 Contrat backend Mature

Les cinq repères personnels restent :

| Surface | API autoritative |
| --- | --- |
| Maintenant | 'GET /api/v1/me/now/' |
| Découvrir | 'GET /api/v1/discovery/items/' |
| Makolo Mark | 'POST /api/v1/me/mark/' |
| En cours | 'GET /api/v1/me/ongoing/' |
| Moi | 'GET /api/v1/me/' |

Le bootstrap d'identité reste distinct : 'GET /api/v1/accounts/auth/me/'.

Les profondeurs owner-backed déjà disponibles comprennent notamment Journey, Requirement, Activity, Occurrence, Dossier, Project, Access, AccessCredential, Historique, Jour J, Operations Live, Passeport, Resources, Group, Partner, Recognition, Loyalty, Notifications et Conversations.

Les projections Z utilisent déjà une enveloppe comprenant 'meta.projection', 'meta.schema_version', 'meta.generated_at' et 'meta.scope'. 'generated_at' indique l'instant de composition, pas la fraîcheur de chaque vérité sous-jacente.

### 3.3 Authentification

Le runtime expose déjà JWT avec :

- access token court ;
- refresh token ;
- rotation des refresh ;
- blacklist après rotation ;
- logout du refresh présenté ;
- révocation de tous les refresh lors d'un changement/reset de mot de passe ;
- suppression de compte distincte.

Le client doit sérialiser le refresh : un refresh rotatif n'est pas un secret immuable utilisable en parallèle.

### 3.4 Appareils et sessions

Le runtime possède déjà 'UserDevice' et 'UserSession'. Leur usage actuel est surtout lié au Web et à la mémoire de comptes/appareils navigateur. Il n'existe pas, dans le runtime A0, de contrat natif complet qui lie un JWT mobile à un appareil enregistré et permette une révocation distante granulaire de ce JWT par appareil.

Conséquences :

- A0 n'ajoute pas un second modèle Device ;
- A1 possède un 'device_instance_id' local opaque pour provenance locale/outbox uniquement ;
- ce marqueur local n'accorde aucune confiance serveur ;
- la vraie gestion native appareil/session, si requise, doit réutiliser Accounts et est classée A6 sauf besoin concret plus tôt.

Un même Profile peut déjà ouvrir des sessions distinctes sur plusieurs appareils. Le serveur reste le point de convergence métier.

### 3.5 Domain Events, Notifications et sync existante

'DomainEventOutbox' est une infrastructure interne durable et idempotente. Il n'existe pas de flux API viewer-aware/cursor qui l'expose au mobile. Il ne doit donc pas être transformé en protocole sync brut.

Notifications expose une projection privée, structurée et navigable, mais pas un changefeed général 'since/cursor'.

Conclusion : le runtime possède les briques de provenance, timestamps, versions, notifications et événements, **mais pas un protocole incrémental transverse prêt à exposer**.

### 3.6 Offline Action Pack

Operations expose déjà un 'offline_action_pack' viewer-aware :

- schema version 1 ;
- fraîcheur actuelle : 1 minute ;
- expiration maximale actuelle : 15 minutes, bornée par la fin de l'Occurrence ;
- minimisation des contacts, paiements, credentials, QR/tokens/secrets et données non nécessaires ;
- aucune autorité offline ;
- toute mutation est revalidée par l'état serveur courant.

Ce pack est une projection de lecture utile au local-first. Il ne devient jamais un OfflineGrant.

### 3.7 Idempotence existante

A0 conserve les contrats propriétaires au lieu d'inventer une clé universelle :

- Recognition redeem : 'idempotency_key' obligatoire ;
- Loyalty redeem : clé d'idempotence propriétaire ;
- commandes : intention + 'idempotency_key' stable et contrainte serveur ;
- création Payment : idempotence propriétaire ;
- Scanner connecté : 'client_reference' ;
- Resource reuse : convergence owner-backed ;
- Form submit et certaines décisions terminales : pas de retry aveugle si l'issue est ambiguë ;
- JWT refresh : rotation sérialisée.

Une nouvelle intention utilisateur crée un nouvel identifiant. Un retry technique de la même intention réutilise l'identifiant propriétaire lorsque ce contrat existe.

## 4. Invariants d'autorité

Le local-first ne modifie aucune frontière métier :

- Profile = personne globale ;
- Assignment = responsabilité ;
- Permission/Mandate = autorité ;
- Membership/Group/Team n'accorde pas automatiquement l'autorité ;
- Readiness reste dérivée ;
- Requirement, Form, Resource, JourneyArtifact, Proof, Credential Trust et AccessCredential restent distincts ;
- Access = droit ; AccessCredential = représentation/secret ; AccessUse = observation ;
- Capacity = combien ; Placement = où ;
- Waitlist != Live Queue ;
- JourneyStep != Checkpoint opérationnel ;
- Dossier != Project ;
- posséder un document != le retrouver != satisfaire un Requirement ;
- composition != transfert implicite de Permission, Mandate, Access, Payment ou données privées.

## 5. D1 — Flux de données

Architecture retenue :

~~~
UI
 ↓ observe
feature controller / use-case
 ↓
repository owner-aware
 ├── lit/écrit la projection locale
 ├── enregistre l'intention locale/outbox
 └── demande sync/remote owner quand nécessaire
          ↓
sync engine
 ├── push outbox
 ├── pull/refresh owner-scoped
 └── applique transactionnellement au store
          ↓
backend Makolo
~~~

Règles :

1. un widget ne devient pas client HTTP ;
2. le repository ne devient pas propriétaire métier ;
3. une réponse distante est normalisée puis appliquée au store avant que l'UI n'observe la nouvelle projection ;
4. les données distantes non persistables peuvent rester éphémères, mais passent quand même par un repository/use-case ;
5. l'UI peut superposer un état local 'pending' sans réécrire la vérité serveur.

## 6. D2 — Base locale : SQLite + Drift

Décision A0 :

> **SQLite via Drift est le store structuré de référence pour A1.**

Motifs :

- transactions atomiques nécessaires à 'donnée locale + outbox' ;
- migrations explicites ;
- index et relations ;
- requêtes réactives sans imposer un store mémoire comme vérité ;
- tests in-memory ;
- support Android/iOS ;
- fichiers DB séparables par Profile ;
- capacité à conserver durablement brouillons/outbox pendant les migrations.

Snapshot de dépendances vérifié le 25 septembre 2026 :

| Capacité | Choix A1 | Version auditée |
| --- | --- | --- |
| Flutter | stable | 3.47.3 |
| State/DI | flutter_riverpod | 3.4.3 |
| Routing | go_router | 18.0.1 |
| DB | drift | 2.35.0 |
| ouverture Flutter DB | drift_flutter | 0.3.1 |
| secrets | flutter_secure_storage | 11.2.0 |
| HTTP | http | 1.6.0 |
| chemins privés/cache | path_provider | 2.1.6 |
| signal réseau | connectivity_plus | 7.3.1 |

Références de vérification : changelog Flutter officiel et pages de versions 'pub.dev'. Les versions seront **pinées au démarrage A1**, puis mises à jour intentionnellement ; A0 ne crée pas encore 'pubspec.yaml'.

'connectivity_plus' fournit un signal de transport, pas une preuve d'accès Internet. La sync doit toujours tolérer timeout, DNS, captive portal et erreur serveur.

Le package obsolète 'sqlite3_flutter_libs' ne doit pas être ajouté directement ; la pile sqlite3 3.x actuelle a remplacé son ancien rôle.

## 7. D3 — Modèle et isolation locale

La DB n'est pas une copie des modèles Django.

Entités locales minimales :

- 'projection_snapshots' : enveloppes serveur allowlistées ;
- 'resource_index' : index léger 'kind/id' pour recherche/navigation locale ;
- 'sync_sources' : état par owner/endpoint ;
- 'outbox_operations' et dépendances ;
- 'local_drafts' ;
- 'file_records' ;
- tables structurées owner-specific uniquement lorsqu'une requête locale réelle le justifie.

Clé de projection conceptuelle :

~~~
Profile local
+ projection kind
+ resource kind/id éventuel
+ variante éventuelle
~~~

Isolation :

~~~
Profile A
├── DB A
├── secure namespace A
├── private files A
└── outbox A

Profile B
├── DB B
├── secure namespace B
├── private files B
└── outbox B
~~~

A1 peut livrer **un seul Profile actif à la fois dans l'UX** tout en utilisant cette isolation dès le premier schéma. L'UX multi-comptes complète peut arriver plus tard sans refonte de stockage.

## 8. D4 — Secure storage et protection locale

'flutter_secure_storage' porte :

- access/refresh tokens ;
- éventuelle clé de chiffrement DB/fichiers ;
- secret de déverrouillage local ;
- petits secrets device strictement nécessaires.

Interdits dans preferences, logs ou DB en clair :

- tokens JWT ;
- QR/credential secrets ;
- payloads Payment sensibles ;
- clés privées ;
- secrets de providers.

La DB et les fichiers privés doivent être placés dans le sandbox applicatif. A1 doit définir explicitement exclusion/autorisation de backup OS par catégorie. Les documents uniques non synchronisés ne doivent pas dépendre d'un cache reconstructible.

Biométrie/PIN locale peut protéger l'ouverture de données sensibles. Elle ne crée jamais Permission, Mandate, Access ou OfflineGrant.

## 9. D5 — Outbox durable

Une intention synchronisable acceptée localement est persistée **dans la même transaction locale** que son état local associé.

Structure minimale :

| Champ | Rôle |
| --- | --- |
| operation_id | UUID stable local |
| profile_id | isolation |
| device_instance_id | provenance technique locale |
| operation_kind | politique owner/retry |
| owner | domaine/API propriétaire |
| resource kind/id | scope |
| payload ou file pointer | minimum nécessaire |
| dependency_ids | ordre causal |
| sequence_group | ordre seulement si nécessaire |
| observed_at | heure locale observée |
| state | queued/in_flight/awaiting_confirmation/confirmed/conflict/failed/cancelled |
| attempts / next_retry_at | retry borné |
| last_error_code | diagnostic sans secret |
| intent_id | même intention à travers retries |
| owner_idempotency_key | seulement si le domaine le supporte |
| replay_policy | safe/idempotent/refetch-before-retry/no-blind-retry |

Garantie :

> même intention + retries techniques = au plus un effet métier lorsque l'owner fournit l'idempotence nécessaire.

Une mutation terminale sans contrat d'idempotence n'est jamais rejouée aveuglément. Après résultat réseau ambigu, le client refetch l'owner et demande une décision humaine seulement si la situation ne peut pas être résolue.

## 10. D6 — Synchronisation entrante

### 10.1 Bootstrap A1

Un nouvel appareil ne clone pas un ancien. Il construit sa projection :

1. auth ;
2. 'auth/me' ;
3. projections personnelles minimales : Maintenant, En cours, Moi ;
4. index des owner links nécessaires à ces projections ;
5. détails importants à la demande ou selon politique locale ;
6. Discover Pack borné ;
7. ressources lourdes seulement à la demande.

### 10.2 Stratégie incrémentale retenue

A0 **ne crée pas** '/sync/'.

La stratégie A1 est :

> **bootstrap borné + refresh/invalidation owner-scoped + tokens de source locaux.**

Chaque 'sync_source' peut conserver :

- route owner ;
- schema version vue ;
- dernier succès ;
- 'generated_at' observé ;
- 'updated_at' / cursor owner lorsque réellement exposé ;
- pagination/ETag éventuelle si le runtime l'ajoute ;
- état d'invalidation ;
- dernière erreur.

Le client ne considère jamais 'generated_at' comme version métier universelle.

Au lancement normal, au resume ou après retour réseau, il ne recharge pas « tout Makolo ». Il rafraîchit :

- les petites projections racines nécessaires ;
- les ressources explicitement invalidées ;
- les ressources actives dont la policy de fraîcheur l'exige ;
- les mutations en attente.

Si plusieurs owners finissent par exiger une séquence viewer-aware commune, un protocole d'invalidation transverse pourra être ajouté ultérieurement. 'DomainEventOutbox' interne n'est pas exposé brut pour forcer cette solution.

## 11. D7 — Versionnement du protocole

Deux niveaux sont distingués :

1. **schema serveur** : 'meta.schema_version' déjà livré par les projections ;
2. **compatibilité client** : registry locale A1 indiquant quelles versions chaque parser/mutation sait consommer.

A0 fixe 'mobile-sync-contract = 1' comme **version de contrat documentaire/client**, pas comme nouveau champ API serveur.

Si une projection reçue devient incompatible :

- le sync de cet owner s'arrête proprement ;
- la dernière donnée locale sûre peut rester consultable en read-only ;
- les mutations incompatibles sont bloquées ;
- aucune DB n'est supprimée ;
- les autres owners compatibles continuent.

Un endpoint de négociation serveur ne sera ajouté que lorsqu'un besoin runtime le démontre.

## 12. D8 — Appareil et session

A1 génère un identifiant d'installation aléatoire local. Il sert à :

- distinguer les outbox locales ;
- diagnostiquer un conflit multi-device sans PII ;
- préparer un futur enregistrement serveur.

Il **ne sert pas** à :

- créer une autorité ;
- signer une Permission ;
- rendre un JWT plus puissant ;
- simuler un device de confiance serveur.

Le runtime Accounts existant reste l'owner d'une future registration/révocation native. La liaison JWT↔device et la révocation granulaire sont classées **A6** sauf scénario A1/A2 qui démontre plus tôt un blocker de sécurité.

## 13. D9 — Logout, retrait local et suppression du compte

Trois opérations distinctes :

### Logout

Si réseau disponible, appeler le logout backend avec le refresh courant. Puis retirer les credentials actifs du secure storage.

Les données locales peuvent être soit purgées soit conservées **verrouillées** pour reconnexion selon la politique de sensibilité de la catégorie. Elles ne doivent plus synchroniser.

### Retirer ce compte de cet appareil

Opération locale destructrice :

- traiter explicitement une outbox non vide ;
- effacer tokens/keys ;
- fermer et effacer DB du Profile ;
- effacer fichiers privés/staging/projections/cache associés.

Si le réseau est disponible, tenter d'abord le logout distant. Le client ne doit pas prétendre avoir « révoqué l'appareil côté serveur » tant que cette API n'existe pas.

### Supprimer le compte Makolo

Reste la mutation backend distincte existante. Elle ne doit jamais être confondue avec un purge local.

## 14. D10 — Fraîcheur

La fraîcheur est metadata de projection, pas un nouveau champ métier sur chaque domaine.

Primitives locales :

- 'received_at' ;
- 'source_generated_at' ;
- 'source_updated_at' lorsque exposé ;
- 'last_verified_online_at' ;
- 'fresh_until' lorsque owner explicite ;
- 'expires_at' lorsque owner explicite ;
- 'freshness_policy_id'.

État dérivé :

~~~
fresh
stale_useful
verification_required
expired
~~~

Une donnée peut être disponible mais trop ancienne pour une décision.

Exemple : « 5 places restantes » d'hier peut rester utile comme contexte historique, mais toute réservation dépendant de Capacity exige une revalidation serveur fraîche.

## 15. D11 — Conflits

Aucune stratégie globale 'last-write-wins'.

| Type | Politique |
| --- | --- |
| préférence simple | stratégie déterministe seulement si l'owner l'autorise |
| collection additive | fusion par identités stables si opérations indépendantes |
| brouillon | préserver les deux versions en cas de concurrence réelle |
| Form draft | contenu local conservé jusqu'à acceptation serveur |
| Journey | état serveur autoritatif ; préparation locale séparée |
| Access | serveur autoritatif |
| Capacity | serveur arbitre la concurrence |
| Placement / Live Queue | Operations serveur arbitre |
| Permission / Mandate | Authorization serveur |
| Payment | serveur + provider |
| document/version | version explicite, jamais écrasement silencieux |
| suppression | tombstone/confirmation owner quand la ressource synchronisée l'exige |

## 16. D12 — Quatre espaces de stockage

### DB Makolo locale

Structuré, privé, migrable :

- projections allowlistées ;
- sync metadata ;
- indexes ;
- outbox ;
- drafts ;
- file metadata.

### Cache

Reconstructible et supprimable :

- thumbnails ;
- médias retéléchargeables ;
- Discover Pack expiré/recréable ;
- tuiles cartographiques ;
- previews.

### Stockage privé Makolo

Non exposé arbitrairement au filesystem public :

- document offline explicitement choisi ;
- capture native en staging ;
- JourneyArtifact local avant upload ;
- ressource personnelle téléchargée ;
- credential seulement si une future policy owner l'autorise.

### Export utilisateur

Une action explicite copie/exporte vers Files/Galerie. Exporter ne change ni l'owner métier ni l'état de synchronisation.

## 17. D13 — 'private, no-store' et projection locale

Contrat réconcilié :

> **'Cache-Control: private, no-store' interdit de transformer une réponse privée en cache HTTP/browser/intermédiaire implicite. Il n'interdit pas qu'un client installé, après authentification, absorbe explicitement des champs allowlistés dans sa projection applicative locale protégée.**

Cette persistance applicative doit être intentionnelle :

- parser la projection, pas archiver aveuglément le body HTTP ;
- minimiser les champs ;
- appliquer une policy de sensibilité et rétention ;
- porter freshness/invalidation ;
- être supprimable par Profile/appareil ;
- exclure les secrets qui ne doivent pas persister.

Les headers serveur restent inchangés et restent utiles contre les caches HTTP non contrôlés.

## 18. D14 — Multi-device

~~~
Téléphone A ─┐
Desktop ─────┼── Serveur Makolo
Téléphone B ─┘
~~~

Aucun appareil maître.

Chaque appareil possède :

- sa DB bornée ;
- ses fichiers ;
- son outbox ;
- son état de freshness.

Le serveur assure la convergence des vérités partagées. Les DB n'ont pas à devenir identiques bit-à-bit.

Une opération créée sur A et déjà confirmée par l'owner ne doit pas être recréée sur B comme une nouvelle intention. Les identités serveur, idempotence owner et refresh des projections résolvent cette convergence.

## 19. D15 — Classes A/B/C/D

| Classe | Sens | UX |
| --- | --- | --- |
| A | entièrement locale | résultat local immédiat |
| B | vraie localement puis synchronisée | 'Enregistré sur cet appareil' puis 'Synchronisé' |
| C | préparée localement, confirmée à distance | 'En attente de confirmation' ; jamais faux succès |
| D | intrinsèquement distante | expliquer le besoin réseau sans détruire le contexte local |

Exemples :

- brouillon : A/B ;
- préférence synchronisable : B ;
- Resource reuse / Form submit / candidature / demande Access : C selon owner ;
- réservation/Capacity partagée : C ;
- global Discovery : D ;
- Payment confirmation : D ;
- Permission/Mandate : D ;
- live shared arbitration : D.

## 20. D16 — Frontière offline opérationnelle

Politiques disponibles conceptuellement :

~~~
NETWORK_REQUIRED
OFFLINE_INDEPENDENT
LOCAL_COORDINATOR
DELEGATED_ALLOCATION
HYBRID
~~~

A0/A1 n'implémentent que les deux premières dans les scénarios sûrs et la lecture de projections déjà autorisées.

'OfflineGrant' n'existe pas comme contrat runtime canonique A0. Aucun modèle n'est créé.

A5 possède l'étude/implémentation de :

- scanner offline réel ;
- Access offline ;
- double-use/double-spend ;
- clock skew ;
- delegated Capacity ;
- Placement/Queue coordonnés localement ;
- OfflineGrant si le besoin est démontré ;
- réconciliation terrain.

## 21. D17 — Behavior & Interaction System

A1 doit fournir des primitives partagées plutôt que les réinventer écran par écran :

- AppShell ;
- Splash ;
- LoadingState / Skeleton ;
- EmptyState ;
- ErrorState ;
- OfflineBanner ;
- SuccessFeedback ;
- Toast / UndoToast ;
- InlineMessage ;
- ConfirmationDialog ;
- BottomSheet ;
- DraftPersistence ;
- SessionRecovery ;
- DeepLinkResolver ;
- PermissionExplainer ;
- NetworkStateIndicator ;
- MotionTokens ;
- HapticFeedback ;
- NotificationRouter.

Les deux axes 'content' et 'sync' sont orthogonaux.

Un écran 'content + offline' est normal. Une perte réseau ne remplace pas du contenu local utile par une erreur plein écran.

## 22. D18 — Design system Flutter

Le mobile traduit la charte existante, il n'en crée pas une autre.

Tokens de base :

| Token | Valeur |
| --- | --- |
| primary | '#5232DB' |
| deep | '#2B176E' |
| coral accent | '#FF704D' |
| warm/light text | '#FAF7F5' |
| ink | '#0F172A' |
| success | '#07806F' |
| warning | '#B45309' |
| danger | '#C83C3C' |
| info | '#2563EB' |

Le corail reste un accent.

Le Makolo Mark provient uniquement des assets canoniques 'static/brand/makolo-mark-*.svg'. A1 les copie vers le bundle Flutter avec provenance explicite ; il ne redessine pas un M.

Typographie :

- Manrope pour marque/titres ;
- Inter pour UI/texte ;
- fallback système obligatoire.

A0 **ne package aucune fonte**. A1 vérifie licences et fichiers réellement présents avant tout embarquement.

Motion :

- courte ;
- orientée progression ;
- jamais requise pour comprendre l'état ;
- Reduce Motion obligatoire ;
- pas de confettis génériques.

## 23. D19 — Navigation et deep links

Navigation primaire personnelle :

> **Maintenant | Découvrir | [Makolo Mark] | En cours | Moi**

Quatre destinations + une action centrale.

Routing retenu pour A1 : 'go_router', avec registry de destinations structurées.

Le resolver reçoit en priorité :

~~~
kind/id
+ links
+ navigation structurée
~~~

Il revalide :

- auth ;
- Profile actif ;
- visibilité ;
- scope ;
- capability/autorité via owner.

Il ne parse pas une URL HTML pour reconstruire une permission.

Retour système, bottom sheets, détail→retour, scroll/filtres et contexte doivent être restaurables.

A0 n'invente aucun domaine Universal Links/App Links, bundle ID ou package ID. Ces décisions appartiennent à A4 lorsqu'une identité native officielle existe.

## 24. D20 — Tests et CI A1

A1 doit rendre indépendants les tests mobile-only :

~~~
dart format --output=none --set-exit-if-changed .
flutter analyze
flutter test
~~~

Puis ajouter progressivement :

- tests DB in-memory ;
- tests migrations locales avec outbox non vide ;
- tests sync engine ;
- tests repository/contract parsers ;
- tests deep links ;
- golden tests seulement pour primitives stables ;
- integration tests ;
- build Android ;
- build iOS sur runner approprié.

La CI doit utiliser des filtres de chemins :

- changement 'mobile/**' seul : ne déclenche pas mécaniquement toutes les matrices PostgreSQL ;
- changement backend seul : backend normal ;
- changement d'un contrat backend consommé par mobile : tests backend ciblés + tests contractuels mobile.

Le workflow mobile doit pinner Flutter stable au patch retenu et vérifier le lockfile. Aucun nouveau workflow A0 n'est créé avant l'existence du package 'mobile/' afin d'éviter un check obligatoire qui ne peut pas s'exécuter.

## 25. Architecture de code A1

Structure recommandée, sans en faire une vérité métier :

~~~
mobile/
├── lib/
│   ├── app/
│   ├── design/
│   ├── navigation/
│   ├── auth/
│   ├── data/
│   │   ├── local/
│   │   │   ├── database/
│   │   │   └── migrations/
│   │   ├── remote/
│   │   └── files/
│   ├── sync/
│   │   ├── engine/
│   │   ├── outbox/
│   │   └── policies/
│   ├── repositories/
│   └── features/
└── test/
~~~

Frontière qui compte :

~~~
UI
↓
repositories / use-cases
↓
local projection + sync + remote owner
~~~

## 26. Matrice des surfaces UX

| Surface | Projection locale | Online | Offline | Freshness/pending | Actions |
| --- | --- | --- | --- | --- | --- |
| Maintenant | dernier 'personal.now' allowlisté | refresh discret | lire dernière projection | afficher ancienneté ; pending séparé | C/D selon owner ; jamais recalculer Now |
| Découvrir | Discover Pack borné + cache média | Discovery globale | parcourir/rechercher localement le pack | TTL/policy ; pack stale reste explicite | save éventuellement B ; global search D |
| Makolo Mark | brouillon d'intake seulement | orchestration serveur | conserver texte à envoyer | 'Enregistré sur cet appareil', pas 'compris' | interprétation D ; modalité text seule |
| En cours | dernier 'personal.ongoing' | refresh owner | consultation locale | pending annotation locale | mutations via owners C/D |
| Moi | sous-ensemble 'personal.me' | refresh | consultation privée locale | policy par section | préférences B ; vérités owner |
| Avatar | identité minimale + contexte UX | auth/session/owner scopes | ouvrir compte local protégé | contexte visuel != autorité | logout/remove ; Agir comme revalidé |
| Journey | détail + drafts/resources utiles | owner Journey/Readiness | consulter + préparer | serveur autoritatif sur statut/Readiness | draft A/B ; submit C |
| Access | projection minimale, pas secret par défaut | Access/credential owner | contexte seulement | stale != valide | validation/usage D ; A5 pour autorité offline |
| Jour J | day-of + pack O5 éventuel | Live/Operations | lecture pack non expiré | fresh_until/expires_at réels | opérations partagées C/D ; avancé A5 |
| Historique | corpus borné synchronisé | refresh/pagination | lecture | ancien reste utile | navigation locale |
| Resources | metadata + téléchargements explicites | owner Resources | lecture fichier privé dispo | version/freshness | reuse C owner-idempotent ; upload natif A4/A3 selon owner |

États vides et erreurs suivent le Behavior contract. Maintenant peut légitimement finir par **« Tout est en ordre. ✓ »**.

## 27. Matrice des domaines

| Domaine | Local | Classe | Autorité | Bootstrap / incoming | Outgoing / conflit | Freshness/idempotence | Offline / sensible | API / gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Profile | partiel | B/D | serveur Accounts/Profile | auth/me + Moi | prefs owner ; jamais profile override | par champ owner | privé/chiffré | livré ; device hardening A6 |
| Journey | oui partiel | A/B/C | serveur Journeys | En cours + detail links | drafts locaux ; transitions serveur | refetch après ambiguïté | bon candidat local-first | '/api/v1/me/journeys/<id>/' ; A3 |
| Dossier/Project | partiel | C | Objectives | liens En cours/Moi | owner mutation ; scope revalidé | owner timestamps si exposés | composition ne divulgue pas | APIs Objectives ; A3 |
| Forms | draft local | A/B/C | serveur à submit | Journey/forms | conserver draft si refus | submit sans blind retry si non idempotent | privé | owner Forms ; A3 |
| Resources | metadata + fichier choisi | A/C | Personal Assets | Moi/resources | reuse owner-backed | reuse convergent | fichier privé, cache séparé | lecture/reuse livré ; upload générique gap A4/A3 |
| JourneyArtifact | staging possible | A/C | Journey/owner | Journey detail | staging→upload→validation | version explicite | très sensible | A3/A4 capture |
| Access | projection minimale | C/D | Access serveur | Ongoing/detail | serveur tranche | revalidation avant décision | credential secret minimisé | livré ; offline authority A5 |
| Scanner | non en A1 | D | Scanner/Access serveur | assignments/events online | 'client_reference' | replay technique idempotent | QR jamais loggé | connecté livré ; offline A5 |
| Capacity | affichage snapshot | C/D | Capacity serveur | via projections owner | concurrence serveur | vérification fraîche | pas d'allocation locale A1 | owner actuel ; delegated A5 |
| Placement | affichage partiel | C/D | Operations | Jour J/Live | serveur | conflit serveur | données minimales | APIs Operations ; coordinator A5 |
| Live Queue | affichage partiel | C/D | Operations | Live | serveur arbitre ordre | refresh contextuel | partagé | A5 pour coordinator offline |
| Payment | référence/status minimal | C/D | serveur + provider | owner detail | jamais 'succeeded' offline | idempotence Payment existante | données sensibles minimisées | provider final non inventé |
| Discover | pack/cache | B/D | Discovery serveur pour global | bounded pack | save/watch owner | TTL + owner retry policy | médias cache | global D ; A2 |
| Notifications | borné | B/C | Notifications serveur | list + navigation | mark read | dedup owner ; pas changefeed | privé | livré ; push A4 |
| Sharing | résultat minimal | C | Sharing serveur | owner links | create/revoke seulement si API | secret jamais inventé | très sensible | mobile ShareEnvelope gap A4/A3 |
| Trust | projection seulement | D | Trust owner | Moi/Passport/Resources | aucune inférence locale | provenance/freshness owner | divulgation minimale | A3 |
| Group | détail visible | C/D | Group/Authorization | Moi + group detail | gestion seulement API owner | serveur | Membership != authority | lecture livrée ; mutations si besoin A3+ |

## 28. Matrice des opérations importantes

| Intention | Classe | Outbox ? | Confirmation |
| --- | --- | --- | --- |
| lire projection locale | A | non | locale |
| rédiger brouillon | A/B | oui si synchronisable | local puis sync |
| modifier préférence synchronisable | B | oui | serveur pour convergence |
| rechercher dans corpus local | A | non | locale |
| global Discovery | D | non | serveur |
| envoyer Mark textuel | C/D | seulement comme intake en attente, pas comme résultat compris | serveur |
| sauvegarder une possibilité | B/C selon owner | oui si replay-safe | owner |
| soumettre Form/candidature | C | oui mais policy no-blind-retry si nécessaire | owner |
| Resource reuse | C | oui | owner, convergence existante |
| réservation / Capacity | C | oui | serveur frais |
| demande Access | C | oui | Access owner |
| utilisation/validation Access | D en A1 | non blind | Access/Scanner |
| paiement | C/D | seulement intention sûre | serveur/provider |
| mutation Permission/Mandate | D | non locale | Authorization |
| scanner connecté | D | queue seulement si réseau intermittent et même client_reference | Scanner serveur |
| scanner offline | A5 | A5 | délégation/conciliation future |

## 29. Product Language

Le store peut utiliser les codes techniques stables. L'UI ne les expose pas lorsque le contexte fournit un mot humain.

Exemples :

- Journey générique → Démarche ;
- Journey Event → Inscription / Réservation / Achat de billet ;
- Occurrence Transport → Départ ;
- Access Event/Transport → Billet / Invitation / Confirmation ;
- AccessCredential → généralement invisible ;
- Moi → Passeport Makolo, Ce qui compte pour moi, Mes collectifs, Mes ressources.

Le contexte change le vocabulaire, jamais la vérité.

## 30. Cache, sauvegarde et rétention

Chaque classe persistée A1 doit déclarer :

~~~
persist locally?
purpose
sensitivity
retention
freshness policy
backup policy
delete policy
sync owner
export policy
~~~

Baseline :

- tokens : secure storage, jamais backup applicatif volontaire ;
- DB personnelle : privée, backup OS désactivé par défaut tant que le threat model n'autorise pas l'inverse ;
- outbox/drafts uniques : jamais cache, ne pas effacer avant résolution explicite ;
- private files : backup explicite selon sensibilité/owner, jamais galerie par défaut ;
- media/Discover cache : reconstructible, supprimable ;
- AccessCredential : non persistant par défaut en A1 ; policy dédiée requise pour usage offline futur ;
- Payment secrets : jamais persistés.

## 31. Migrations locales

La DB mobile est versionnée dès A1.

Règles :

1. migration forward testée ;
2. sauvegarde logique des outbox/drafts avant transformation risquée ;
3. transaction lorsque SQLite le permet ;
4. reprise après interruption ;
5. jamais 'schema incompatible → delete DB → resync' comme stratégie normale ;
6. fixture de migration avec outbox non vide et fichier privé référencé ;
7. rollback produit = version applicative compatible, pas destruction silencieuse des données.

## 32. Push et background

> **Push = signal. Sync = vérité.**

A1 ne dépend d'aucun worker perpétuel.

Triggers compatibles :

- launch ;
- resume ;
- retour réseau ;
- action manuelle ;
- après mutation locale ;
- fenêtre background future ;
- push futur.

A0 ne choisit pas encore de package background. A4 le fera à partir des contraintes iOS/Android réelles.

## 33. Sécurité des deep links et notifications

Une notification transporte une destination structurée, pas une Permission.

Le client :

1. résout la cible 'kind/id/links' ;
2. vérifie le Profile actif ;
3. ouvre/rafraîchit via l'owner ;
4. accepte 404/403 comme résultat normal de scope changé ;
5. n'affiche pas une donnée privée étrangère conservée d'un autre Profile.

## 34. Gaps classés

### bloque A1

**Aucun gap backend identifié par A0.**

A1 doit implémenter sa fondation locale ; ce travail n'est pas un blocker A0, c'est A1 lui-même.

### A1

- créer 'mobile/' depuis le 'main' courant ;
- pinner Flutter et dépendances auditée ;
- DB Drift + migrations ;
- repositories ;
- secure JWT + refresh sérialisé ;
- outbox durable ;
- bootstrap + sync owner-scoped ;
- CI mobile path-filtered ;
- tests crash/reprise/migrations.

### A2 — Personal Makolo

- Maintenant ;
- Découvrir + Discover Pack ;
- Mark text ;
- En cours ;
- Moi ;
- Avatar ;
- context restoration.

### A3 — Action Continuity

- Journey ;
- Forms ;
- Requirements/Readiness presentation ;
- Access online ;
- Resources/JourneyArtifact ;
- Dossier/Project ;
- Historique/Jour J profondeur.

### A4 — Native & Ambient

- caméra/fichiers ;
- share sheet ;
- localisation native ;
- push ;
- notification routing OS ;
- widgets/Live Activities ;
- Universal/App Links ;
- generic PersonalAsset upload contract si l'expérience le nécessite ;
- background sync package selon besoin réel.

### A5 — Field Operations & Delegated Offline Authority

- scanner offline ;
- OfflineGrant si démontré ;
- delegated Capacity ;
- Placement/Queue local coordinator ;
- double-use, clock skew et réconciliation terrain.

### A6 — Mobile Mature & Release

- registration/révocation native par appareil et éventuelle liaison JWT↔device ;
- multi-Profile UX complète si retenue ;
- hardening sécurité ;
- performance/stockage faible ;
- observabilité privacy-safe ;
- builds release et stores.

### non nécessaire / interdit

- '/api/v1/mobile/' ;
- copie locale du schéma Django ;
- moteur local Readiness ;
- moteur global Discovery local ;
- 'last-write-wins' universel ;
- OfflineGrant générique en A0/A1 ;
- exposer DomainEventOutbox brut comme sync feed.

## 35. Programme A réconcilié

~~~
A0 — Mobile Architecture Reconciliation
  ↓
A1 — Installed Makolo Core
Flutter + auth + DB locale + sync + outbox + design foundation
  ↓
A2 — Personal Makolo
Maintenant · Découvrir · Mark · En cours · Moi · Avatar
  ↓
A3 — Action Continuity
Journey · Forms · Access · Resources · Jour J · profondeurs
  ↓
A4 — Native & Ambient Makolo
caméra · fichiers · localisation · share · push · widgets · deep links
  ↓
A5 — Field Operations & Delegated Offline Authority
Scanner · Access offline · Capacity · Placement · Queue
  ↓
A6 — Mobile Mature & Release
devices · hardening · performance · sécurité · stores
~~~

Le local-first est transversal dès A1. A5 n'est pas « rendre l'app offline » ; A5 ajoute une autorité terrain bornée que A1 ne possède pas.

## 36. Critères de sortie A0

A0 est fermé si les assertions suivantes sont stables :

- l'UI sait d'où elle lit : store local ;
- la vérité partagée sait où elle vit : server owner ;
- le bootstrap nouvel appareil est défini ;
- l'incoming sync n'exige pas un faux '/sync/' ;
- l'outbox est durable et owner-aware ;
- le retry distingue intention et tentative technique ;
- la fraîcheur est metadata locale ;
- no-store HTTP est réconcilié avec persistance applicative explicite ;
- les stores sont isolables par Profile ;
- le multi-device converge via serveur ;
- logout/remove/delete sont distincts ;
- Access/Capacity/Payment/Permission ne deviennent pas vérité locale ;
- Offline Action Pack reste lecture sans autorité ;
- A5 possède la délégation terrain avancée ;
- DB, routing, state/DI, secure storage et HTTP sont choisis ;
- navigation/Behavior/Brand/Product Language sont fixés ;
- aucune migration backend n'est nécessaire.

## 37. Handoff A1

A1 doit commencer depuis le 'main' post-A0, pas depuis #248.

Premier incrément recommandé :

~~~
mobile/ scaffold
→ design tokens + Makolo Mark
→ secure token store + serialized refresh
→ Drift schema v1
→ profile-local storage resolver
→ projection snapshot repository
→ outbox
→ sync source registry/engine
→ auth bootstrap
→ AppShell / route registry
→ tests first launch online + normal launch offline
→ CI mobile
~~~

Tests de fondation prioritaires :

- first launch online ;
- first launch offline sans bootstrap : explication propre ;
- normal launch offline ;
- online→offline→online ;
- kill app avec outbox ;
- crash pendant sync ;
- session expirée avec draft local ;
- deux appareils même Profile ;
- changement de Profile sans fuite ;
- migration DB avec outbox ;
- stale projection ;
- mutation C pending ;
- retry idempotent ;
- conflit draft ;
- suppression locale avec outbox ;
- stockage presque plein.

La définition de succès reste :

> **Makolo Mobile est, dès sa première ligne, une application personnelle locale synchronisée avec Makolo, utile sans réseau dans les limites de ce qu'elle connaît, tout en restant cliente des vérités et arbitrages autoritatifs du serveur.**
