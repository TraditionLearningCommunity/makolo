# Actor 6 — Persistateur Makolo

> Statut : spécification de fermeture Actor 6, auditée sur `main` au 23 septembre 2026.
>
> Référence d'audit : `0f884b1d034a0e96bca7f2be635efa53620257f8`.
>
> Le runtime, les migrations et les tests gagnent sur ce document en cas de divergence.

## Verdict

Actor 6 **n'est pas un nouveau composant runtime**.

Makolo possède déjà son Persistateur sous forme de responsabilités distribuées :

- modèles Django propriétaires ;
- services métier transactionnels ;
- contraintes et indexes PostgreSQL ;
- journaux et historiques spécialisés ;
- transactional outbox Domain Events ;
- états techniques durables propres aux acteurs ;
- stockages privés de blobs/documents ;
- protections d'Admin et de certaines écritures bulk ;
- procédures de migration, backup et restauration.

La fermeture Actor 6 consiste à **formaliser cette politique distribuée et à durcir les écarts réels**, sans créer `persistator/`, repository universel, table miroir, JSON store global, event store général ou nouvelle base.

Définition retenue :

> **Le Persistateur Makolo est la responsabilité interne distribuée qui rend durable, sous le propriétaire approprié et avec les garanties nécessaires, ce que Makolo a décidé de conserver, tout en empêchant les caches, projections, calculs et copies techniques de devenir des vérités métier concurrentes.**

Le Persistateur garantit la durabilité correcte d'une décision déjà prise par le domaine propriétaire et coordonnée par l'Orchestrateur. Il ne décide pas qu'un fait devient vrai.

---

## 1. Définition

Actor 6 couvre les garanties de persistance de Makolo, pas un package unique. Il relie :

```text
décision applicative autorisée
↓
service du propriétaire
↓
transaction / invariants / contraintes
↓
stockage durable approprié
↓
signal de changement utile
```

PostgreSQL, filesystem privé et journaux persistés sont des mécanismes ; aucun n'est à lui seul Actor 6.

## 2. Mission

Garantir qu'une vérité, un historique ou un artefact explicitement retenu :

- survive correctement au process ;
- reste sous le bon owner ;
- garde son identité métier ;
- n'entre pas en conflit avec une source canonique existante ;
- conserve l'intégrité requise ;
- respecte confidentialité et minimisation ;
- garde assez de provenance lorsque nécessaire ;
- soit idempotent et sûr sous concurrence ;
- reste compatible avec les anciennes données ;
- puisse être restauré ou reconstruit selon sa catégorie.

## 3. Pourquoi il existe

Makolo compose de nombreux domaines. Sans une politique explicite, trois dérives deviennent probables :

1. dupliquer les vérités pour faciliter une lecture ;
2. persister les projections comme si elles étaient canoniques ;
3. contourner les services propriétaires par ORM/Admin/bulk writes.

Actor 6 ferme ces dérives sans centraliser les données.

## 4. Objectifs

- clarifier la source de vérité de chaque famille ;
- distinguer canonique, historique, technique, projection et cache ;
- protéger les mutations multi-écritures ;
- protéger les identités métier sous concurrence ;
- fournir des Domain Events durables lorsque nécessaires ;
- conserver les blobs irremplaçables sans confondre identité physique et logique ;
- rendre la frontière Actor 6 → Actor 7 stable.

## 5. Non-objectifs

Actor 6 ne fournit pas :

- event sourcing complet ;
- base universelle Makolo ;
- ORM alternatif ;
- data lake ;
- repository générique ;
- décision de source authority ;
- calcul Readiness ;
- calcul Univers ;
- projection Home/attention ;
- exécution d'effets externes ;
- présentation ;
- provider de stockage de production inventé.

## 6. Responsabilités

Responsabilités distribuées :

- persister la mutation canonique dans le bounded context propriétaire ;
- appliquer transactions et locks lorsque l'opération l'exige ;
- placer les invariants critiques en DB lorsqu'ils sont exprimables efficacement ;
- conserver historique/audit lorsque le domaine l'exige ;
- fournir une idempotence alignée sur l'intention logique ;
- séparer secrets et représentations publiques ;
- assurer cohérence DB/blob autant que le mécanisme actuel le permet ;
- publier un Domain Event atomiquement avec la mutation lorsqu'un signal durable est requis ;
- documenter reconstruction, rétention, backup et restore.

## 7. Frontières et interdictions

Interdits :

```text
PersistedObject(type, payload)
CanonicalEntity miroir
Profile.readiness_state
Activity.readiness
Journey.generic_ready
Activity.mass
Occurrence.temperature
save_this_json(anything)
```

L'Orchestrateur appelle un owner métier ; il n'appelle pas un stockage générique.

## 8. Entrées

Les entrées sont des **intentions de mutation déjà autorisées** ou des états techniques appartenant à un acteur :

- appel d'un service propriétaire ;
- callback validé et résolu ;
- run technique Actor 1–4 ;
- observation/artifact admis ;
- événement à journaliser ;
- état worker/checkpoint réellement nécessaire.

Actor 6 ne prend pas `ResolvedMaterial` comme ordre brut de sauvegarde.

## 9. Sorties

- nouvelle version durable de la vérité propriétaire ;
- historique/audit spécialisé ;
- état technique durable propre à l'acteur ;
- metadata DB + blob privé lorsque justifié ;
- Domain Event durable minimal ;
- aucun résultat persistant lorsqu'il s'agit d'une projection non matérialisée.

## 10. Contrats

Contrat principal :

```text
Orchestrateur
→ service owner
→ transaction
→ modèles + contraintes
→ commit
→ Domain Event durable éventuel
```

Les payloads Domain Events sont versionnés, JSON borné, idempotents et refusent des clés sensibles.

## 11. Sources de vérité

La source canonique reste le réseau des domaines :

- Activity/Occurrence → `activities`
- Profile → `accounts`
- Organization/Space → `organizations`
- Permission/Role/Mandate → `authorization`
- Geography → `geography`
- Journey → `journeys`
- Opportunity/Requirement → `opportunities` + kernel `requirements`
- Trust/Proof → `trust`
- Access/Credential/Use → `access`
- Capacity → `capacity`
- Commerce → `commerce`
- Payment/ledger → `payments`
- Dossier/Project → `objectives`

Les compatibilités Event/Ticket existantes ne deviennent pas une seconde autorité.

## 12. Données possédées / référencées / dérivées

Actor 6 ne possède pas un modèle central.

- **Possédées** : par les domaines/acteurs existants.
- **Référencées** : FK, identifiants stables, source refs, provenance bornée.
- **Dérivées** : Readiness, états Discovery/Home, statistiques, analytics, caches et futurs calculs Univers restent non canoniques.

## 13. Dépendances

- Django ORM et migrations ;
- PostgreSQL pour validation forte de concurrence/locks/contraintes ;
- filesystem privé actuel pour plusieurs artefacts ;
- transactional outbox Domain Events ;
- services propriétaires ;
- Authorization pour les mutations sensibles.

PythonAnywhere est un environnement bêta temporaire et ne définit pas l'architecture finale.

## 14. Consommateurs

- services et selectors métier ;
- Domain Event consumers ;
- Automation/Notifications/CRM/Analytics ;
- futur Actor 7 Projecteur via faits canoniques/signaux stables ;
- exploitation/DR.

## 15. Déclencheurs

- mutation métier explicite ;
- transition de lifecycle ;
- callback externe validé ;
- run Actor 1–4 ;
- schedule/worker ;
- upload ou capture ;
- opération d'administration autorisée lorsqu'elle est réellement une voie supportée.

## 16. Modes d'exécution

- synchrone transactionnel ;
- worker avec claim/lease ;
- traitement Domain Events après commit ;
- reconstruction explicite de certaines projections ;
- migration contrôlée ;
- maintenance/DR.

Aucun appel réseau long ne doit être tenu dans une transaction DB sans nécessité.

## 17. Temporalité et fraîcheur

Toujours distinguer :

- `created_at/updated_at` : temps technique ;
- dates métier : deadline, starts_at, issued_at, valid_from/valid_until ;
- futur déclaré : canonique si le domaine le déclare ;
- futur calculé : projection.

`null` peut signifier inconnu et ne doit pas devenir `false` arbitrairement.

## 18. Cycle de vie

Chaque nouvelle donnée durable doit préciser :

- création ;
- transitions autorisées ;
- état terminal ;
- révocation/remplacement ;
- suppression/archivage ;
- rétention ;
- reconstruction.

Le soft delete n'est pas généralisé.

## 19. Idempotence / concurrence

Le dépôt utilise déjà selon les owners :

- `transaction.atomic` ;
- `select_for_update` ;
- `UniqueConstraint` conditionnelles ;
- clés `source_key` / `idempotency_key` ;
- locks PostgreSQL ;
- consumers idempotents.

Une UUID de ligne n'est pas une identité métier. Les contraintes doivent porter sur l'intention logique pertinente.

## 20. Erreurs / retry

- crash avant commit : aucune mutation partielle visible ;
- crash après commit avant consommation : l'outbox durable reste récupérable ;
- événement doublé : consumption idempotente ;
- worker interrompu : leases/recovery propriétaires ;
- erreur externe : retry hors de la transaction canonique lorsque possible ;
- migration incertaine : pas de backfill métier inventé.

## 21. Sécurité / confidentialité

- secrets complets interdits dans Domain Events/logs/analytics/projections ;
- AccessCredential est distinct du droit Access et de l'usage AccessUse ;
- documents privés ont un storage non public ;
- credentials Intelligence sont chiffrés au repos via une master key d'environnement ;
- données financières interdisent des clés metadata sensibles ;
- PII suit minimisation, visibilité et lifecycle du domaine.

## 22. Reconstruction

Classification :

- **IRREMPLAÇABLE** : vérité canonique non dérivable, certains artefacts externes historiques ;
- **HISTORIQUE** : ledger, transitions, source checks, runs utiles ;
- **RECONSTRUCTIBLE** : projections/statistiques dont les faits de base sont présents ;
- **PROJECTION** : Readiness et compositions viewer-aware ;
- **CACHE** : supprimable sans perte métier.

Un cache qui ne peut pas être perdu n'est pas un cache.

## 23. Échelle

Surveiller avant optimisation :

- contention / hot rows ;
- taille historique ;
- write amplification ;
- taille JSON ;
- blobs ;
- N+1 d'écriture ;
- durée locks ;
- queue/outbox lag.

Aucun Kafka/Redis/Cassandra/Elasticsearch/object store n'est ajouté par Actor 6.

## 24. Coût

Coûts à surveiller :

- croissance PostgreSQL ;
- indexes ;
- backups ;
- duplication de blobs ;
- historiques longs ;
- fichiers privés locaux en bêta.

La dénormalisation n'est pas une solution par défaut.

## 25. Observabilité

Surfaces attendues :

- échecs migrations ;
- deadlocks/constraint violations ;
- retries ;
- DB latency ;
- storage failures et digest mismatch ;
- Domain Event pending/failed/lag ;
- worker leases expirées ;
- backup freshness dans l'environnement qui le supporte.

Les logs restent dépourvus de secrets/contenus privés inutiles.

## 26. Cas nominaux

### A — Activity

```text
Actor 5
→ activities.services.create_activity/update...
→ transaction
→ Activity
→ Domain Event si transition pertinente
```

Aucune table Actor 6.

### B — Occurrence

Occurrence porte la réalité temporelle. Activity ne reçoit pas une copie de ses dates.

### C — Requirement

Le Requirement reste dans son owner/version. Aucun `activity.toefl_score` opportuniste.

### D — Observation historique

Observer conserve Observation/Attempt/ObservedArtifact et bytes privés selon sa politique. La vérité métier peut évoluer séparément.

### E — Payment

Payment combine transaction, provider reference, idempotence, historique/webhook et ledger spécialisé sans journaliser de secret provider.

### F — Access

```text
Access = droit
AccessCredential = représentation
AccessUse = observation d'usage
```

### G — Readiness

Readiness est calculée depuis les faits canoniques et ne crée aucune nouvelle vérité générique.

### H — Actor 7

Une mutation canonique peut produire un Domain Event minimal après commit. Actor 7 consommera un contrat stable, pas un scan arbitraire de toutes les tables.

## 27. Cas limites

- deux créations de même identité → contrainte/lock owner ;
- dernière capacité → `capacity` sérialise le pool ;
- callbacks paiement dupliqués → identité provider/idempotence ;
- deux AccessUse → client reference/idempotence ;
- deux workers → claim/lease + locks ;
- deux résolutions → identité technique/fingerprint du Resolver ;
- blob écrit puis row échoue → Observer peut adopter l'orphelin content-addressed ;
- row blob mais fichier absent → erreur explicite de lecture/intégrité ;
- ancienne donnée sans champ nouveau → rester inconnue si aucune preuve ;
- projection publique → ne copie pas un champ privé disponible en DB.

## 28. Anti-patterns

- PersistenceService universel ;
- table miroir ;
- tout en JSONField ;
- tout append-only ;
- soft delete généralisé ;
- persister `is_actionable` ou Readiness comme vérité ;
- déduire date métier depuis timestamp technique ;
- recopier Observation dans chaque domaine ;
- Event Sourcing par mode architecturale ;
- analytics/logs comme source de vérité.

## 29. Tests

Selon la surface :

- contraintes modèles ;
- services transactionnels ;
- concurrence PostgreSQL ;
- idempotence ;
- migration check ;
- anciennes données ;
- privacy/secret non-leak ;
- Domain Events ;
- blob integrity ;
- reconstruction ;
- tests de **non-persistance** pour Readiness/projections.

## 30. Critères de sortie

Actor 6 est fermé lorsque :

- ownership majeur est clair ;
- aucune base parallèle n'existe ;
- canonique / historique / technique / projection / cache sont distingués ;
- transactions/contraintes/idempotence importantes sont solides ;
- migrations restent sûres ;
- anciennes données restent valides ;
- secrets et PII restent protégés ;
- Observer/Interpreter/Resolver gardent leurs stores ;
- Domain Events sont cohérents et durables ;
- reconstruction/DR sont documentés ;
- frontière Actor 7 est stable ;
- CI et PostgreSQL sont verts.

---

# Matrice P0 — ownership et catégorie

| Donnée / état | Propriétaire | Type | Reconstruction | Confidentialité | Signal / remarque | Audit |
| --- | --- | --- | --- | --- | --- | --- |
| Profile / UserProfile | Accounts | canonique | irremplaçable | PII | events ciblés selon workflow | CORRECTE |
| Organization / Space | Organizations | canonique | irremplaçable | mixte | lifecycle/authority events | CORRECTE |
| Role / Permission / Mandate | Authorization | canonique + historique lifecycle | irremplaçable | sensible | services + contraintes scope | CORRECTE |
| Activity | Activities | canonique | irremplaçable | selon visibilité | Activity events | CORRECTE |
| Occurrence / schedules | Activities | canonique, futur déclaré possible | irremplaçable | faible à mixte | reschedule/cancel/reopen events | CORRECTE |
| Place / Zone | Geography | canonique | irremplaçable | emplacement selon contexte | contraintes coordonnées | CORRECTE |
| Journey | Journeys | canonique process | irremplaçable | privée | transitions + events | CORRECTE |
| JourneyTransition | Journeys | historique | historique | privée | audit de transition | CORRECTE |
| Opportunity / Revision / Source | Opportunities | canonique + provenance | irremplaçable | publique/interne | revisions immuables publiées | CORRECTE |
| OpportunitySourceCheck | Opportunities | historique append-oriented | historique | interne | source changed event | CORRECTE |
| Requirement | Opportunities / Requirements | canonique versionné | irremplaçable | mixte | pas copié sur Activity | CORRECTE |
| RequirementReuseApplication | Requirements | historique/audit | historique | privée | append-only | CORRECTE |
| Proof / Trust | Trust | canonique + historique | irremplaçable | sensible | disclosure limitée | CORRECTE |
| JourneyArtifact | Journeys | canonique document de démarche | irremplaçable | privé/restricted | bytes storage privé | CORRECTE |
| PersonalAssetVersion | Personal Assets | canonique versionné | irremplaçable | privé/restricted | bytes storage privé | CORRECTE |
| Access | Access | canonique droit | irremplaçable | privée | services uniquement | CORRECTE |
| AccessCredential | Access | canonique secret/représentation | rotation, pas projection | secret | pas de credential brut dans events | CORRECTE |
| AccessUse | Access | historique d'usage | historique | privée | client_reference idempotente | CORRECTE |
| CapacityPool | Capacity | canonique | irremplaçable | interne/publique selon selector | locks owner | CORRECTE |
| CapacityReservation | Capacity | canonique transactionnel | irremplaçable | privée | concurrence PostgreSQL testée | CORRECTE |
| Placement / Live Queue | Operations | canonique opérationnel | irremplaçable selon workflow | opérationnelle | events ciblés | CORRECTE |
| Offer / CommerceOrder | Commerce | canonique | irremplaçable | privée | snapshots financiers structurés | CORRECTE |
| Payment / Refund | Payments | canonique | irremplaçable | financière sensible | idempotence + locks | CORRECTE |
| PaymentEvent | Payments | historique provider | historique | sensible | payload allowlist, raw secret non stocké | CORRECTE |
| Allocation / Ledger | Payments | historique financier append-oriented | historique critique | financière | ImmutableFinancialQuerySet | CORRECTE |
| Dossier / Project | Objectives | canonique | irremplaçable | privée/collaborative | Readiness collective non persistée | CORRECTE |
| Notifications | Notifications | technique + produit delivery | partiellement reconstructible | privée | dedup/delivery state | CORRECTE |
| AutomationRun / Execution | Automation | technique/historique | partiel | interne | Domain Events consumers | CORRECTE |
| CRM canonical | CRM | canonique métier CRM / projections explicitement nommées | selon sous-modèle | PII | ne remplace pas Profile/Commerce | À DÉTERMINER par sous-surface, hors refactor Actor 6 |
| Sharing envelope/link | Sharing | canonique de partage + delivery history | irremplaçable | sensible | token hash, events privacy-safe | CORRECTE |
| ObserverHandoff | Observer | technique durable | reconstructible partiellement | interne | actor-owned | CORRECTE |
| ObservationSeries / Observation / Attempt | Observer | technique + historique acquisition | partiel | privé | leases/constraints | CORRECTE |
| ObservedArtifact | Observer | historique technique irremplaçable | bytes potentiellement irremplaçables | privé | identité logique distincte du SHA | CORRECTE |
| ObserverBlob | Observer | stockage physique dédupliqué | non si source a changé | privé | content-addressed + digest | CORRECTE |
| InterpretationRun / Candidates | Interpreter | technique/historique | reconstruisible depuis Observer retenu | privé | fingerprint/version | CORRECTE |
| ResolutionRun / Assertions | Resolver | technique/historique | reconstruisible depuis Interpreter retenu | privé | immutable finalized history | CORRECTE |
| Prospector frontier/checkpoints | Prospector | technique opérationnel | convergence possible depuis sources selon doc | privé | leases/checkpoints | CORRECTE |
| DomainEventOutbox | Domain Events | historique de changement + delivery state | essentiel pour consumers non rejoués | payload minimal | transactional outbox | À DURCIR : fait immuable vs bookkeeping mutable |
| DomainEventConsumption | Domain Events | technique delivery | reconstructible partiellement | interne | consumer idempotence | CORRECTE |
| Readiness | Readiness | projection | reconstruisible | viewer-aware | jamais vérité canonique | CORRECTE |
| Discovery/Home participant state | Discovery/Core | projection | reconstruisible | viewer-aware | composition depuis faits | CORRECTE |
| AnalyticsFact | Analytics | projection/observation | reconstruisible selon events conservés | minimisée | jamais source canonique | CORRECTE |
| ProviderCredential Intelligence | Intelligence | secret technique nécessaire | non reconstructible sans secret externe | secret chiffré | master key env | CORRECTE |
| future Univers quantities | Actor 8 | dérivé | calcul | selon inputs | **non persisté par Actor 6 par défaut** | CORRECTE par absence |

---

# Audit des garanties

## Transactions

Le dépôt possède déjà de nombreux services `@transaction.atomic` : Activities, Journeys, Access, Capacity, Payments, Authorization, Opportunities, Services, Observer et autres. Les chemins critiques PostgreSQL sont couverts par les shards CI.

## Contraintes PostgreSQL

Les domaines principaux utilisent des `UniqueConstraint`, `CheckConstraint`, FKs et indexes ciblés. Exemples structurants :

- Activity : propriétaire logique unique + slug contextualisé ;
- Occurrence : fenêtre temporelle et slot schedule unique ;
- Journey : exactement un bénéficiaire ;
- Access : fenêtre, bénéficiaire et `journey/source_key` ;
- Mandate : scope cible valide + unicité active conditionnelle ;
- Domain Events : idempotency key unique ;
- paiement : unicités/provider refs et contraintes financières spécialisées.

## Domain Events

Le runtime actuel est :

```text
mutation owner dans transaction
↓
emit_domain_event()
↓
DomainEventOutbox dans la même transaction
↓
commit
↓
transaction.on_commit(process)
↓
consumption persistée par consumer
```

Le crash après commit avant processing ne perd pas le fait : Autopilot/commande `process_domain_events` reprend les pending/stale.

Le système reste state-based + Domain Events ; Actor 6 ne bascule pas vers Event Sourcing.

## Readiness et projections

`readiness.resolve_*` retourne des dataclasses calculées depuis Journey/Access/Capacity/Payment/Occurrence/Requirements. Les tests montrent qu'elle n'introduit pas de modèle canonique `readiness_state`.

## Blobs

Observer sépare :

```text
ObservedArtifact = identité logique
ObserverBlob = bytes physiques dédupliqués par SHA-256
```

Le store :

- vérifie digest et longueur ;
- refuse de réhydrater silencieusement un blob purgé ;
- adopte un fichier orphelin valide après crash entre write storage et commit DB ;
- détecte un fichier absent/corrompu à la lecture.

Le SHA n'est donc pas traité comme identité métier.

## Secrets

- Access ne stocke pas de credential brut dans `AccessUse`.
- Domain Events refusent les clés `password/secret/token/credential/qr_code/bearer/kyc`.
- Sharing persiste un hash de token.
- Intelligence chiffre les provider secrets avec une master key externe.
- Payments interdit des metadata financières secrètes et ne conserve pas le corps webhook brut.

---

# Écarts Actor 6 réellement retenus

## P6-A — Domain Event fact immutability

Le modèle documentait déjà « immutable domain fact plus mutable delivery bookkeeping », mais l'ORM permettait encore de réécrire directement les champs factuels après création.

Correction Actor 6 :

- empêcher `save()`, `QuerySet.update()` et `bulk_update()` de modifier le fait persistant ;
- conserver mutables uniquement les champs de delivery/retry ;
- aucune migration de données ou table nouvelle ;
- tests explicites.

Cette correction protège la frontière Actor 7 : un signal canonique déjà émis ne doit pas changer de signification sous le même id/idempotency key.

## Différés volontairement

- revue exhaustive de chaque JSONField du dépôt : hors scope de fermeture, à traiter seulement lorsqu'un invariant métier opaque est démontré ;
- nouveau object store : non justifié ;
- nouvelle politique de rétention globale : non justifiée ;
- Event Store : rejeté ;
- refactor complet CRM/legacy bridges : non justifié par Actor 6 ;
- migration PostgreSQL du PythonAnywhere bêta : décision opérationnelle future, pas architecture Actor 6.

---

# Frontière Actor 6 → Actor 7 Projecteur

Contrat de départ proposé :

```text
mutation canonique commitée
↓
Domain Event ciblé lorsque la représentation Univers peut être affectée
↓
Actor 7 consumer/port
↓
projection vers Univers
```

Actor 7 ne doit pas :

- scanner toutes les tables ;
- lire arbitrairement les modèles techniques Observer/Interpreter/Resolver ;
- dépendre des détails ORM de chaque domaine ;
- traiter la présence d'une row comme un fait Univers sans contrat.

Les événements utiles à Actor 7 doivent être **sélectionnés**, pas globaux par défaut. Leur payload transporte des identités stables et le minimum nécessaire ; Actor 7 peut charger un snapshot canonique via un port owner lorsque le payload ne doit pas dupliquer les données.

Actor 6 ne définit aucune grandeur Univers et ne matérialise aucun calcul.

---

# Train de fermeture révisé

L'audit montre qu'un grand train P0→P8 créerait du travail artificiel.

Train retenu :

```text
P0 — audit + classification + ownership
P1 — hardening du fait Domain Event
P2 — documentation reconstruction / privacy / DR / frontière Actor 7
P3 — tests PostgreSQL + migration gate + CI
P4 — merge + vérification main + fermeture Actor 6
```

Aucun nouveau modèle n'est prévu.

---

# Migration gate

Pour toute PR Actor 6 :

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
```

PostgreSQL doit exécuter au minimum les tests Domain Events et les shards propriétaires déjà couverts par la CI lorsqu'une surface correspondante change.

Aucune data migration Actor 6 n'est nécessaire dans cette fermeture.

---

# Handoff Actor 7

Actor 7 reçoit :

- identités canoniques stables ;
- événements de changement durables sélectionnés ;
- provenance minimale lorsque le domaine la fournit ;
- possibilité de charger un snapshot owner via un contrat stable.

Actor 7 ne reçoit pas :

- toutes les tables ;
- payloads externes bruts ;
- secrets ;
- Readiness persistée ;
- états techniques des workers ;
- quantités Univers prématurément ajoutées aux modèles métier.

