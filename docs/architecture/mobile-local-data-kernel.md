# Makolo Mobile — Local Data Kernel

> **Statut : analyse Bloc A fermée — entrée canonique de la phase de conception**
>
> **Objet :** fixer ce que l'application mobile doit conserver localement, ce qu'elle peut calculer, ce qu'elle doit toujours demander au serveur, et comment les API Makolo actuelles alimentent un working set local partagé.
>
> **Base runtime vérifiée lors de cette consolidation :** main@96f3992b38afc5352c1da2572a9a9b695359a5de — A1 Installed Makolo Core (#306).
>
> Le runtime courant gagne toujours sur ce document. Avant implémentation, revalider main, les PR/branches mobiles pertinentes, les contrats API, les migrations et les docs canoniques.

## 1. Objet

Le mobile Makolo doit devenir une vraie application installée, réactive et local-first, sans devenir une copie du serveur Makolo.

La contrainte structurante est double :

> **Les vérités partagées, les arbitrages métier, les calculs systémiques et les décisions qui dépendent de l'écosystème Makolo restent côté serveur.**

et :

> **Une fois une information légitimement reçue par l'application, le téléphone peut la conserver, la relire, l'indexer, la joindre, la filtrer, la trier, la regrouper ou effectuer des calculs déterministes qui ne nécessitent pas de connaissance nouvelle du reste de l'écosystème.**

Ce document ne décrit ni un mini-serveur mobile, ni une réplication de PostgreSQL, ni un nouveau domaine métier. Il ferme l'analyse du Local Data Kernel avant conception détaillée puis implémentation.

## 2. Architecture retenue

~~~
                    MAKOLO SERVER
        vérités partagées + calculs + arbitrages
                        |
                        v
                API / owner projections
                        |
                        v
                  Sync Engine
                        |
          +-------------+-------------+
          v                           v
  Projection snapshots        Structured local indexes
          |                           |
          +-------------+-------------+
                        v
                LOCAL KNOWLEDGE
                        |
              +---------+---------+
              v         v         v
          selectors   device   deterministic
                     local state  calculations
              |         |         |
              +---------+----+----+
                             v
                        EXPERIENCE
~~~

Sens inverse pour une action :

~~~
Experience
→ local intention
→ draft / optimistic overlay / outbox
→ owner API serveur
→ canonical decision
→ refetch / reconciliation
→ local transaction
→ Experience
~~~

Formule canonique :

> **Makolo Mobile connaît beaucoup de choses, calcule beaucoup de choses et prépare beaucoup de choses — mais il ne prétend jamais connaître seul ce qui dépend encore du reste de l'écosystème.**

## 3. Frontière d'autorité

### 3.1 Vérités autoritatives distantes

Le serveur reste propriétaire de toute vérité dont le résultat peut devenir faux uniquement parce qu'un autre acteur, un autre appareil ou un autre processus Makolo a changé l'état ailleurs.

Cela inclut notamment :

- Permission ;
- Mandate ;
- Access ;
- validité d'un AccessCredential ;
- Payment ;
- Capacity réelle ;
- Live Queue globale ;
- Placement opérationnel partagé ;
- décisions Requirement ;
- Readiness canonique ;
- états Journey partagés ;
- arbitrages transactionnels ;
- Discovery globale et pertinence calculée sur le monde Makolo ;
- toute opération nécessitant une connaissance d'écosystème non disponible localement.

Le mobile peut en conserver une observation, jamais une seconde vérité.

### 3.2 Calculs déterministes locaux

Le téléphone peut calculer sans appel serveur lorsqu'il possède déjà toutes les données nécessaires et que le résultat ne dépend pas d'un changement extérieur inconnu.

Exemples : somme, regroupement, tri, filtres, recherche dans le corpus local, distance à partir de coordonnées connues, conversion d'unité, chronologie locale, lecture calendrier à partir d'Occurrences connues ou route locale si le graphe nécessaire existe réellement sur l'appareil.

Test canonique :

> **Le résultat peut-il devenir faux uniquement parce que quelque chose a changé ailleurs dans Makolo ?**

Si non, un calcul local est généralement approprié. Si oui, il faut considérer fraîcheur, revalidation et autorité serveur.

### 3.3 Projection contextuelle locale

Le téléphone peut composer des faits déjà connus pour répondre à une question UX sans créer de vérité métier : Occurrence connue + heure locale → aujourd'hui ; Resource connue + fichier téléchargé → disponible hors ligne ; plusieurs Occurrences connues → lecture calendrier.

### 3.4 Vérité device-owned

Le device est propriétaire de réalités telles que : chemin d'un fichier téléchargé, présence dans le cache, brouillon non envoyé, staging d'un fichier capturé, progression locale d'un upload, état de navigation temporaire, identifiant d'installation opaque et état d'une opération outbox.

### 3.5 État optimiste

Une conséquence provisoire locale reste distincte du dernier état confirmé serveur. Exemple Capacity : serveur confirme 3, une intention locale réserve 1, l'UI peut montrer provisoirement 2, mais le serveur peut confirmer une autre valeur si l'écosystème a changé.

## 4. Audit : partir des API

Le Local Data Kernel est conçu à partir de ce que les API donnent au client, pas à partir d'une copie du schéma Django.

La question n'est pas : « cette table existe-t-elle côté serveur ? »

La question est :

> **Le téléphone a-t-il besoin de requêter, joindre, trier, synchroniser ou retenir cette information indépendamment pour rendre l'expérience locale immédiatement utile ?**

Si oui, une structure locale peut être justifiée. Sinon, snapshot et référence suffisent souvent.

## 5. Registre des sources API

| Source | Contrat | Forme locale | Working set | Fraîcheur / autorité |
| --- | --- | --- | --- | --- |
| Identité | GET /api/v1/accounts/auth/me/ | état minimal distinct de Moi | Profile courant | session / serveur |
| Maintenant | personal.now | snapshot racine | refs kind/id, Occurrence si fournie | SWR ; admission serveur |
| En cours | personal.ongoing | snapshot racine | ResourceIndex + OccurrenceFactsIndex | SWR |
| Moi | personal.me | snapshot racine | identité utile + ResourceIndex | SWR |
| Considérations | personal.me.considerations | snapshot profondeur | Interest/OpenTo/Watch/Bookmark refs | contextuel |
| Collectifs | personal.me.collectives | snapshot profondeur | Space/Team/Group refs | contextuel ; aucune autorité déduite |
| Passeport | personal.me.passport | snapshot protégé | Proof/Credential Trust refs | contextuel |
| Ressources | personal.me.resources | collection bornée | ResourceIndex + PersonalAsset/version metadata | contextuel |
| Resource detail | personal.resource.detail | snapshot détail | metadata/version/provenance | contextuel |
| Découvrir | discovery.items | query cache reconstructible | ResourceIndex si relation personnelle réelle | recherche globale serveur |
| Activity | activity.detail | snapshot détail | ResourceIndex | contextuel |
| Occurrence | occurrence.detail | snapshot détail | OccurrenceFactsIndex | contextuel |
| Journey | personal.journey.detail | snapshot + drafts séparés | ResourceIndex + OccurrenceFactsIndex | transitions serveur |
| Requirement | personal.journey.requirement.detail | snapshot détail | pas de modèle global par défaut | décision serveur |
| Dossier | objective.dossier.detail | snapshot détail | ResourceIndex | owner |
| Project | objective.project.detail | snapshot détail | ResourceIndex | owner |
| Mes accès | personal.accesses | collection bornée | ResourceIndex + refs Activity/Occurrence | aucune autorité locale |
| Access detail | personal.access.detail | snapshot minimal | ResourceIndex + OccurrenceFactsIndex | revalidation critique |
| AccessCredential | personal.access.credential | hors DB générale | aucune extraction | sensible |
| Historique | personal.history | collection paginée | ResourceIndex Journey/Access | lecture locale |
| Jour J | personal.occurrence.day_of | snapshot opérationnel | faits non volatils d'Occurrence | volatile |
| Offline Action Pack | operations.offline_action_pack v1 | snapshot borné | aucun nouvel owner | fresh_until/expires_at serveur |
| Operations Live | /api/v1/operations/occurrences/<id>/live/ | snapshot court | aucun fait autoritatif durable | volatile |
| Notifications | /api/v1/notifications/ | collection bornée | ResourceIndex destination si utile | SWR |
| Conversations | /api/v1/conversations/ | snapshot/collection d'abord | refs owner | contextuel/volatile |
| Recognition | /api/v1/recognition/me/ | snapshot owner | ResourceIndex éventuel | owner |
| Loyalty | /api/v1/loyalty/me/ | snapshot owner | ResourceIndex éventuel | owner |
| Partner | /api/v1/me/partners/ + détail | snapshot owner | ResourceIndex éventuel | owner |

Ce registre est un contrat de persistance, pas une liste d'écrans.

## 6. Schéma local conceptuel initial

Le noyau retenu reste volontairement petit :

~~~
MakoloDatabase
|
+-- ProjectionSnapshots
+-- ResourceIndex
+-- SyncSources
+-- OutboxOperations
+-- LocalDrafts
+-- FileRecords
+-- OccurrenceFactsIndex
~~~

Les six premières structures sont déjà présentes dans la fondation A1 auditée. OccurrenceFactsIndex est le premier enrichissement structuré justifié.

Aucune décision de ce document n'impose immédiatement des tables complètes Activity, Journey, Access, Dossier, Project, Group ou Requirement.

## 7. ProjectionSnapshots

ProjectionSnapshots conserve les contrats serveur reçus afin de :

- préserver la projection owner telle que reçue ;
- permettre un rendu local immédiat ;
- permettre une renormalisation future ;
- conserver les compositions déjà calculées par le serveur ;
- éviter de réimplémenter localement Readiness, actionabilité ou pertinence globale.

Un snapshot est une copie locale de lecture d'un contrat serveur observé, pas une nouvelle vérité métier.

## 8. ResourceIndex

ResourceIndex devient le répertoire d'identité local transversal.

Forme conceptuelle :

~~~
profile_id
resource_kind
resource_id
label?
projection_kind?
navigation_json?
updated_at
~~~

Il répond à : « le téléphone connaît-il déjà cette identité et sait-il où retrouver sa représentation locale ou son owner link ? »

Il ne devient pas une table EAV universelle contenant la ressource complète.

## 9. OccurrenceFactsIndex

L'Occurrence justifie le premier index spécialisé parce qu'elle traverse Discover, Activity, En cours, Maintenant, calendrier, Journey, Access, Jour J, carte et Historique.

Forme conceptuelle :

~~~
profile_id
occurrence_id
activity_id?

timing_kind?
timezone?
start_date?
end_date?
start_at?
end_at?

primary_place_id?
place_name?
locality?
latitude?
longitude?

source_observed_at?
received_at
last_verified_online_at?
~~~

Les champs exacts seront fixés en conception Drift à partir des API réelles.

N'entrent pas dans cet index générique :

- readiness ;
- capacity_remaining ;
- access_valid ;
- queue_position ;
- placement ;
- payment_status ;
- permission ;
- mandate ;
- credential.

Ces réalités restent dans leurs snapshots propriétaires et sont revalidées selon leur politique.

## 10. Classes de stockage

La conception garde des catégories distinctes :

1. base locale Makolo ;
2. cache reconstructible ;
3. stockage privé Makolo ;
4. export utilisateur hors contrôle Makolo ;
5. secure storage OS pour les secrets.

Invariant :

> **structured DB ≠ private files ≠ reconstructible cache ≠ secure storage**

La base Drift ne doit pas absorber des fichiers lourds. Le cache peut être supprimé sans perte métier. Les tokens et petites clés restent dans Keychain/Keystore ou équivalent.

## 11. Selectors locaux

Les expériences ne doivent pas consommer directement les blobs JSON comme unique modèle d'application.

~~~
ProjectionSnapshot
       +
ResourceIndex
       +
OccurrenceFactsIndex
       +
pending local state
       ↓
     Selector
       ↓
presentation model
       ↓
      UI
~~~

Exemple En cours : le selector conserve ordre et appartenance de personal.ongoing, joint les faits d'Occurrence connus et superpose un pending local pertinent.

Exemple calendrier : personal.ongoing fournit les Occurrence pertinentes, OccurrenceFactsIndex fournit temps/lieu, CalendarSelector produit jour/semaine/mois.

Le calendrier n'est donc ni un nouveau domaine ni une nouvelle API par défaut.

### Limite Maintenant

Le serveur possède personal.now. Le téléphone peut enrichir la présentation, mais ne redéfinit pas « ce qui mérite mon attention maintenant ».

### Limite Découvrir

Le mobile peut filtrer, trier, rechercher et cartographier un pack reçu. Il ne prétend pas connaître seul le corpus global, la pertinence globale ou les possibilités apparues ailleurs.

## 12. Appliers

La synchronisation entrante suit :

~~~
HTTP owner
→ Remote DTO
→ Contract parser
→ Applier
   → ProjectionSnapshot
   → ResourceIndex
   → indexes structurés autorisés
→ transaction COMMIT
→ Drift reactive streams
~~~

La transaction évite un état observable snapshot nouveau + index ancien.

Il ne faut pas de GenericProjectionNormalizer qui inspecte arbitrairement n'importe quel JSON. Préférer de petits appliers explicites : PersonalNowApplier, PersonalOngoingApplier, PersonalMeApplier, JourneyDetailApplier, OccurrenceDetailApplier, DiscoveryItemsApplier, DayOfApplier, AccessDetailApplier, etc.

Règle :

> **Un applier ne modifie que les champs dont son contrat fournit effectivement la connaissance.**

Il n'existe donc pas de hiérarchie globale arbitraire du type Occurrence detail > Journey > Ongoing > Now.

### Absence et null

Pour les champs structurés :

- champ absent → cette projection ne se prononce pas ;
- champ présent à null → cette projection indique explicitement l'absence, lorsque le contrat lui donne ce sens.

Une projection partielle ne doit pas effacer silencieusement un fait plus riche qu'elle ne transporte pas.

## 13. Freshness

Il n'existe pas un TTL universel.

Familles conceptuelles :

- très stable : nom Profile, titre Activity, coordonnées Place ;
- stable : structure Journey, metadata Resource ;
- changeable : statut Journey, Requirement, read state notification ;
- volatile : Capacity, Queue, Placement, Operations Live ;
- revalidation avant action critique : Access use, credential validity, Payment, authority, reservation/stock.

Ces catégories ne doivent pas être copiées mécaniquement comme enum dans chaque table.

Pour un fait distant, la sémantique locale pertinente est, lorsque disponible :

~~~
value
source
server version / updated_at
observed_at
received_at
freshness metadata
~~~

Une valeur « 3 places » observée à 12:31 signifie que le serveur a déclaré 3 à 12:31, pas que le téléphone sait qu'il reste encore 3 maintenant.

> **Ne pas jeter automatiquement une donnée ancienne ; ne jamais la présenter comme plus actuelle qu'elle ne l'est.**

## 14. Bootstrap

Bootstrap initial :

~~~
LOGIN
 |
 v
auth/me
 |
 +-----------+
 v           v
Now       Ongoing
 |           |
 +-----+-----+
       v
      Me
       |
       v
application transactionnelle
       |
       +-- snapshots roots
       +-- ResourceIndex
       +-- OccurrenceFactsIndex
       |
       v
app usable
~~~

Puis selon contexte : premier pack Discover, Notifications, détails réellement nécessaires, médias demandés.

Le téléphone devient utile rapidement avant d'avoir « tout Makolo ».

## 15. Lancement normal

Un lancement courant suit plutôt :

~~~
ouvrir DB
→ afficher immédiatement le réel local
→ traiter outbox
→ rafraîchir racines invalidées/stales
→ rafraîchir ressources actives selon contexte
→ appliquer les changements
~~~

Il n'existe pas une opération « sync tout Makolo ».

## 16. SyncSources

SyncSources conserve l'état local d'une source owner :

~~~
profile_id
source_key
route
schema_version_seen
last_success_at
generated_at_seen
cursor?  seulement si l'owner réel l'expose
invalidated
last_error_code?
~~~

Il ne fabrique pas de cursor universel.

## 17. Sync sortante et Outbox

~~~
UI action
→ local transaction
→ pending projection / draft
→ OutboxOperation
→ réseau
→ owner API
→ canonical response
→ reconciliation transaction
→ confirmed / rejected / conflict
~~~

L'outbox ne transforme pas toutes les mutations en retry aveugle.

Chaque classe d'opération doit choisir : replay-safe, revalidate-before-retry, no-blind-retry, confirmation requise ou résolution du résultat ambigu par refetch owner.

L'idempotence vient du contrat owner lorsqu'elle existe.

## 18. Conflits

Aucun last-write-wins global.

Le client peut préserver un brouillon, garder une variante non confirmée, refetch l'owner et ne montrer un conflit que lorsqu'une vraie décision humaine est nécessaire.

Un conflit de fichier, de formulaire, de réservation et de Permission n'a pas la même sémantique.

## 19. Suppression et rétention

La disparition d'une ressource d'une collection ne signifie pas DELETE de ResourceIndex ou OccurrenceFactsIndex.

La ressource peut rester référencée ailleurs, liée à un draft/outbox/fichier, utile en Historique ou visible dans un autre owner.

> **Collection membership ≠ existence de la ressource.**

Une garbage collection locale pourra supprimer une donnée reconstructible lorsqu'elle n'est plus référencée, suffisamment ancienne, sans draft, sans outbox et sans fichier durable dépendant.

Ce mécanisme est de la maintenance locale, pas une mutation métier.

## 20. Riverpod

La chaîne attendue est :

~~~
Drift
  ↓
Repository stream
  ↓
Selector
  ↓
Riverpod provider
  ↓
Widget
~~~

Riverpod porte l'état d'interaction : loading, tab sélectionné, expansion, filtres, contrôleurs et présentation temporaire.

Il ne doit pas devenir la vérité durable principale des listes Journey, Occurrence ou Activity lorsqu'elles doivent survivre au process et alimenter plusieurs surfaces.

## 21. Discover Pack

Le corpus Discover reçu peut être persisté de manière reconstructible et bornée. L'utilisateur peut le filtrer/rechercher localement et les médias associés peuvent utiliser un cache reconstructible.

Mais le mobile ne recrée pas le monde Discovery global.

Lorsqu'une possibilité devient personnellement pertinente par Bookmark, Watch, engagement ou relation owner réelle, son identité peut rejoindre le working set personnel.

## 22. Jour J et faible connectivité

Jour J combine personal.occurrence.day_of et Operations Live. Le runtime possède aussi l'Offline Action Pack viewer-aware.

Ce pack peut être conservé dans sa fenêtre fresh_until/expires_at.

Mais :

> **Il n'accorde aucune autorité offline.**

Le mobile n'en déduit pas localement un droit d'accès, une consommation de credential, un Payment réussi, une allocation de Capacity, une décision de Queue globale ou une autorité Permission/Mandate.

## 23. Credentials et données sensibles

Les secrets ne deviennent pas des lignes banales de la DB générale.

Sont notamment concernés : AccessCredential complet, QR/token sensible, payload Payment secret, refresh JWT, clés privées et contenu confidentiel inutile.

La stratégie est : secure storage OS, stockage privé protégé à la demande, ou aucune persistance locale.

## 24. Ce qui manque réellement côté serveur

### Aucun blocker Local Data Kernel

Le runtime fournit assez pour concevoir puis implémenter : bootstrap borné, snapshots, ResourceIndex, OccurrenceFactsIndex, selectors, sync owner-aware, pagination, drafts, outbox, Jour J et Offline Action Pack.

### Capacités transverses absentes mais non nécessaires maintenant

Il n'existe pas aujourd'hui de changefeed viewer-aware global, cursor sync transverse, ETag/version universelle ni WebSocket/SSE générique.

Le modèle retenu reste :

~~~
bootstrap borné
+
refresh/invalidation owner-scoped
+
tokens de source locaux
~~~

### Gaps fonctionnels à traiter dans leur scénario

Restent notamment hors Bloc A : upload PersonalAsset Mature générique, gestion Group mobile complète, ShareEnvelope Passport mobile, Universal/App Links, transport realtime générique, provider Payment production, modalité fichier générique du Mark et autorité terrain offline avancée.

## 25. Pas de /sync générique

Ne sont pas retenus :

~~~
POST /api/v1/mobile/sync/
GET  /api/v1/sync/?since=...
~~~

Makolo possède déjà des owners distincts : Journey, Access, Discovery, Operations, Notifications, Resources, Conversations, Recognition, Loyalty, etc.

Le moteur mobile orchestre ces owners.

Une primitive transverse ne deviendra légitime que si l'usage réel démontre un besoin commun et mesurable.

## 26. Anti-features

Le Bloc A ne doit pas dériver vers :

- copie SQLite du schéma Django ;
- serveur local Makolo ;
- moteur local Readiness ;
- moteur local Discovery globale ;
- moteur local Permission/Mandate ;
- moteur local Payment ;
- source locale autoritative de Capacity ;
- validation locale de credential ;
- table générique resources(id, kind, json) comme seul modèle ;
- merge JSON récursif universel ;
- last-write-wins global ;
- /api/v1/mobile/ parallèle ;
- /sync/ générique inventé ;
- table locale par modèle Django ;
- API par écran mobile ;
- requête réseau par tap lorsque la donnée est déjà locale ;
- cache HTTP déguisé en architecture local-first.

## 27. Décisions gelées

| Question | Décision |
| --- | --- |
| DB locale | SQLite + Drift, Profile-scoped |
| Serveur mobile parallèle | non |
| Copie Django locale | non |
| Snapshots | oui |
| Working set partagé | oui |
| Premier index spécialisé | OccurrenceFactsIndex |
| Tables Activity/Journey/Access complètes | non par défaut |
| Identité commune | kind/id serveur |
| ResourceIndex | oui, transversal |
| Calendrier comme domaine/API | non |
| Maintenant recalculé localement | non |
| Discovery globale locale | non |
| Calculs purs locaux | oui |
| Merge JSON récursif | non |
| Payload partiel | absence ≠ null |
| Optimistic mutation | overlay local séparé |
| Readiness locale | non |
| Credential dans DB générale | non |
| Freshness | par policy, owner-aware |
| Sync globale /sync | non |
| Bootstrap | borné |
| Incrémental | owner-scoped |
| Offline authority implicite | aucune |
| Pagination | owner-specific |
| Suppression | collection membership ≠ destruction ressource |
| UI durable en mémoire Riverpod | non ; Drift reste durable |

## 28. Critères de sortie de la phase de conception

La conception détaillée issue de ce document doit produire au minimum :

1. le schéma Drift exact et ses index ;
2. la migration depuis le schéma A1 courant ;
3. les DTO/parsers ;
4. les Appliers et leurs responsabilités champ par champ ;
5. les repositories ;
6. les selectors des premières expériences ;
7. les Freshness Policies codées ;
8. les triggers de pull/refetch/invalidation ;
9. les politiques outbox/retry/idempotence par classe d'opération ;
10. les règles de purge/logout/remove-account ;
11. les tests migration, crash/reprise, atomicité et réconciliation ;
12. la matrice confidentialité/persistance sensible ;
13. l'intégration Riverpod sans déplacer la vérité durable en mémoire ;
14. les critères de performance après baseline réelle.

La conception ne doit pas ouvrir de nouvelle vérité métier pour rendre l'architecture mobile plus confortable.

## 29. Gate avant implémentation

Avant de coder :

- revalider le main courant ;
- relire les PR mobiles ouvertes touchant mobile/lib/data, mobile/lib/sync, mobile/lib/network ou les docs concernées ;
- comparer le schéma Drift réellement présent ;
- relire mobile-api-contract.md, z13-mobile-api-handoff.md, mobile-a0-architecture-reconciliation.md et les contrats owner touchés ;
- vérifier les migrations Drift ;
- vérifier les dépendances réellement installées ;
- faire un collision audit avec A2/infrastructure ;
- fixer le plan de migration ;
- écrire les tests ciblés migration/atomicité avant de déplacer les premières sources.

Aucune implémentation ne doit commencer en supposant que ce document connaît le futur main.

## 30. État GitHub lors de la consolidation

Lors de la rédaction :

- main = 96f3992b38afc5352c1da2572a9a9b695359a5de ;
- A1 est merged ;
- plusieurs PR mobiles A2/infrastructure sont ouvertes ;
- elles sont traitées comme contexte de collision, jamais comme vérité canonique tant qu'elles ne sont pas merged ;
- ce document est placé sur une branche documentaire dédiée pour éviter de réécrire les branches mobiles actives.

Cette section est une trace d'analyse et ne remplace jamais la vérification runtime future.

## 31. Formule finale

Le Local Data Kernel de Makolo n'a pas pour mission de recréer Makolo sur le téléphone.

Il doit permettre à l'application installée de posséder **juste assez de connaissance structurée** pour être instantanée, cohérente entre surfaces, utilisable avec une connectivité imparfaite et capable de préparer l'action — tout en laissant les propriétaires canoniques décider ce qui dépend du monde partagé.

> **Une vérité serveur est reçue comme une observation autorisée, intégrée une seule fois dans le working set pertinent, réutilisée par plusieurs expériences locales, puis revalidée auprès de son propriétaire lorsque la réalité partagée l'exige.**

La traduction produit reste :

> **« Makolo marche pour vous. »**

Le téléphone doit donc pouvoir montrer immédiatement ce qu'il sait déjà, travailler localement avec ce qu'il possède déjà, et revenir au serveur uniquement lorsque la vérité, la fraîcheur, l'autorité ou le monde extérieur l'exigent réellement.
