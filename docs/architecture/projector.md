# Actor 7 — Projecteur Makolo

> **Statut : fondation Actor 7 réconciliée avec le `main` incluant Actor 6.**
> Ce document décrit le contrat réellement implémenté. Il ne transforme pas une
> roadmap scientifique en runtime déjà disponible.

## Décision de J0

Le Projecteur est la frontière de traduction :

```text
faits canoniques commités
        ↓
change signal minimal + snapshot owner borné
        ↓
Projecteur
        ↓
UniverseSnapshot / UniverseDelta
        ↓
UniverseProjectionPort
        ↓
Actor 8
```

La source de vérité reste le backend canonique. Le Projecteur ne possède aucune
vérité métier et Actor 8 ne devient pas une seconde base métier.

La première projection retenue est volontairement petite : une `Occurrence`
canonique peut produire une **déclaration de réalisation planifiée** dans
l'Univers. Cette structure est une planification, **pas un CorpsMakolo**. Une
Occurrence annulée reste une planification historique annulée. Une Occurrence
terminée ne prouve pas à elle seule qu'un `CorpsRéalisation` a réellement
existé.

Ce choix protège la distinction scientifique actuelle :

```text
Occurrence backend (prévue/décrite)
≠
déroulement réel
≠
CorpsRéalisation Univers
```

Aucune masse, charge, température, énergie, force ou distance Makolo n'est
déduite de champs Django dans Actor 7.

---

# J0 — Audit métier

| Domaine backend | Faits canoniques pertinents | Owner / lecture | Change signal actuel | Décision Actor 7 |
|---|---|---|---|---|
| Activity | identité canonique nécessaire pour contextualiser une Occurrence | Activities | publication/réouverture | **RETENU comme contribution**, jamais Corps/Système par simple type ORM |
| Occurrence | identité, Activity, lifecycle, timing, timezone | Activities, snapshot `activities.projector_snapshots` | création, replanification, annulation, réouverture | **RETENU** comme déclaration de réalisation planifiée |
| Geography / Place | lieux, coordonnées et relations de lieu | Geography / Activities | pas encore requis par le mapping v1 | **CANDIDAT** ; un `Place` n'est pas automatiquement un CorpsSite |
| Profile | personne globale | Accounts | aucun signal générique nécessaire au mapping v1 | **OUVERT** ; jamais CorpsActeur 1:1 |
| Organization / Space | contexte collectif/opérateur | Organizations | signaux partiels | **OUVERT** ; aucune représentation corporelle directe retenue |
| Journey | processus utilisateur et transitions | Journeys | lifecycle/steps/blockers/artifacts | **CANDIDAT** pour dynamique/conditions futures, hors v1 |
| Requirement | exigence propriétaire | domaine propriétaire | hétérogène | **CANDIDAT** pour conditions de possibilité, jamais Readiness primitive |
| Proof | fait/preuve | Trust / owners | hétérogène | **CANDIDAT**, sans conclure automatiquement qu'un Requirement est satisfait |
| Access | droit, portée, validité | Access | issued/used/revoked/expired/transferred | **CANDIDAT** pour conditions/relations, aucun credential secret |
| Capacity | quantité disponible/engagée | Capacity | aucun signal Actor 7 requis en v1 | **CANDIDAT** ; distinct de Placement |
| Placement | où une capacité/unité est placée | Operations | assigned/changed/unassigned | **CANDIDAT**, distinct de Capacity |
| Dossier | objectif actif composé | Objectives | événements dédiés | **OUVERT**, aucun Corps automatique |
| Project | horizon durable | Objectives | événements dédiés | **OUVERT**, aucun Corps automatique |
| Payment | obligations/transferts métier | Payments | événements dédiés | **REJETÉ** comme masse/énergie/charge automatique ; pertinence relationnelle ouverte |
| CRM / notifications / analytics | projections/opérations produit | owners respectifs | divers | **REJETÉ** du mapping v1 |

### Frontière Actor 6 → Actor 7

Actor 7 consomme deux choses complémentaires :

1. un **change signal durable minimal** disant qu'une vérité canonique pertinente
   a changé ;
2. un **snapshot owner read-only** fournissant l'état canonique courant nécessaire
   à la composition.

Le change signal n'est pas un snapshot métier. Pour les Occurrences, le signal
porte des identités minimales. Actor 7 recharge ensuite le snapshot actuel.

Le runtime ne dépend donc pas de l'ordre d'arrivée de payloads complets anciens :
un signal ancien peut déclencher une relecture de la vérité courante.

---

# J0 — Audit scientifique / matrice Univers

| Fait / hypothèse | Représentation Univers | Justification | Dépendances | Confidentialité | Statut |
|---|---|---|---|---|---|
| Occurrence prévue/décrite | `declared_realization_plan` | la planification est distincte du déroulement réel | Activity + timing | ids + temps minimal | **RETENU** |
| Activity référencée par Occurrence | contribution d'identité/source | plusieurs faits peuvent composer une structure sans créer un corps | Activity id | aucun texte public/PII | **RETENU** |
| Occurrence = CorpsRéalisation | aucune | une Occurrence annulée peut exister sans réalisation ; une Occurrence peut donner plusieurs réalisations | observation du déroulement réel | — | **REJETÉ** |
| Occurrence terminée = CorpsRéalisation historique | aucune conclusion automatique | un statut backend ne prouve pas à lui seul le corps réel | observations futures | — | **REJETÉ** |
| Activity = SystèmeMakolo | aucune conclusion automatique | le nom de modèle ne définit pas un système scientifique | frontière/phénomène à définir | — | **REJETÉ** comme règle générale |
| Profile = CorpsActeur | aucune conclusion automatique | SujetActeur et manifestations Presence/Ancrage/Canal doivent être établis par faits | facts de localisation/manifestation | forte minimisation | **REJETÉ** comme 1:1 |
| Place = CorpsSite | à déterminer | le CorpsSite exige locus causalement adressable, pas une row `Place` | régime/site réel | géographie minimale | **CANDIDAT** |
| Requirement / Access / Capacity | conditions/relations possibles | peuvent modifier les transitions accessibles | owners correspondants | jamais secret/credential | **CANDIDAT** |
| Readiness | aucune primitive | projection dérivée du backend | faits propriétaires | — | **REJETÉ** comme vérité primitive |
| Activity.price → masse/énergie | aucune | aucune définition scientifique | — | — | **REJETÉ** |
| popularity/likes/followers → charge | aucune | aucune définition scientifique | — | — | **REJETÉ** |
| created_at/updated_at → temps Univers | aucune | timestamps techniques != temps métier/Univers | temps sémantique du fait | — | **REJETÉ** |
| `updated_at` comme source revision | fence technique uniquement | permet de rejeter une projection calculée sur une révision plus ancienne | owner snapshot | interne | **RETENU**, non physique |

Les grandeurs physiques restent dans leur métrologie SI et les constantes
physiques restent inchangées. Actor 7 ne crée aucune unité ou constante Makolo.

---

# 1. Définition

Le Projecteur Makolo est l'acteur interne qui transforme de manière
**déterministe, minimale, traçable et reconstructible** des faits canoniques
pertinents en structures d'entrée de l'Univers Makolo.

Il traduit ; il ne calcule pas la dynamique de l'Univers.

# 2. Mission

- sélectionner les faits effectivement nécessaires au mapping retenu ;
- charger un snapshot canonique borné via l'owner ;
- composer plusieurs faits sans recopier les tables ;
- préserver `UNKNOWN`, `NOT_APPLICABLE` et les temporalités ;
- produire un contrat stable pour Actor 8 ;
- permettre bootstrap et delta de même sémantique.

# 3. Pourquoi il existe

Sans frontière explicite, Actor 8 devrait connaître Django, les noms de tables,
les compatibilités legacy et les secrets de chaque bounded context. Actor 7
absorbe ce couplage tout en laissant la vérité chez les owners.

# 4. Objectifs

- découplage ORM ;
- déterminisme ;
- minimisation des données ;
- reconstruction complète ;
- convergence snapshot + deltas ;
- versionnement de stratégie ;
- conservation de la différence entre backend et Univers.

# 5. Non-objectifs

Actor 7 n'est pas :

- un moteur de recommandation ;
- un parser Web ;
- un résolveur d'identité externe ;
- un moteur de Readiness ;
- un solveur de trajectoires ;
- Actor 8 ;
- Actor 9 ;
- un présentateur ;
- un exécuteur ;
- une seconde source de vérité.

# 6. Responsabilités

Le module `projector` possède les contrats, le mapping, les adaptateurs de
change signals et les services snapshot/delta. Le domaine Activities expose
seulement un snapshot read-only borné pour Occurrence.

# 7. Frontières et interdictions

Interdit :

- `apps.get_models()` puis projection automatique ;
- `1 row = 1 CorpsMakolo` ;
- passage d'instances Django, QuerySet ou relations lazy au contrat Actor 8 ;
- lecture de secrets, credentials ou documents privés ;
- mutation du backend par le Projecteur ;
- exécution d'actions externes ;
- appel Internet ;
- calcul de géodésiques, masse, charge, force ou trajectoire dans Actor 7.

# 8. Entrées

## Change signal

`ProjectionChangeSignal` contient :

- `change_ref` ;
- `fact_kind` ;
- `fact_id` ;
- `event_type`.

Le payload Domain Event n'est pas pris comme vérité complète.

## Canonical snapshot

`OccurrenceProjectorSnapshot` contient uniquement :

- occurrence id ;
- activity id ;
- lifecycle ;
- timing kind ;
- dates/heures sémantiques ;
- timezone ;
- source revision technique.

# 9. Sorties

Deux formes partagent la même sémantique :

- `UniverseSnapshot` : bootstrap/rebuild d'un scope ;
- `UniverseDelta` : upserts/removals incrémentaux.

# 10. Contrats Actor 7 → Actor 8

Le contrat public est constitué de dataclasses immuables :

```text
UniverseSnapshot
  scope_ref
  strategy_version
  roots[]
  semantic_fingerprint

UniverseDelta
  scope_ref
  strategy_version
  change_ref
  upserts[]
  removals[]

UniverseProjectionRoot
  projection_ref
  projection_kind
  strategy_version
  source_revision
  source_facts[]
  plans[]
  bodies[]
  relations[]
  conditions[]
  states[]
  parameters[]
  semantic_fingerprint
```

La v1 utilise `plans[]`. Les autres collections existent dans le contrat pour
laisser Actor 8 indépendant des prochaines extensions, mais restent vides tant
qu'un mapping scientifique n'est pas retenu.

`UniverseProjectionPort` ne connaît aucun provider :

```python
apply_snapshot(snapshot)
apply_delta(delta)
```

Actor 8 doit appliquer une **fence de révision** : une projection calculée sur
une révision canonique plus ancienne ne peut pas écraser une plus récente.

# 11. Sources de vérité

1. owner canonique du domaine ;
2. snapshot read-only owner ;
3. Domain Event comme signal durable ;
4. état Projecteur uniquement reconstructible ;
5. projection Univers jamais autoritative pour le métier.

# 12. Données possédées / référencées / dérivées

Actor 7 ne possède actuellement aucune table.

Référencé :
- ids Activity/Occurrence.

Dérivé :
- projection ref ;
- fingerprints ;
- lifecycle Universe de la déclaration ;
- représentation explicite KNOWN/UNKNOWN/NOT_APPLICABLE.

# 13. Dépendances

- Activities pour le snapshot ;
- Domain Events pour les signaux ;
- Actor 8 seulement via `UniverseProjectionPort`.

Aucune dépendance vers UX, payments providers, Internet ou workers Actor 1–4.

# 14. Consommateurs

Le seul consommateur du contrat est Actor 8 ou un fake de contrat en test.

# 15. Déclencheurs

Mapping v1 :

- `occurrence.created` ;
- `occurrence.rescheduled` ;
- `occurrence.cancelled` ;
- `occurrence.reopened` ;
- bootstrap explicite.

La création via le service owner et la matérialisation des schedules émettent
`occurrence.created`. Les bridges Event runtime passent par ce service. Les
migrations historiques ne sont pas rejouées ; le bootstrap couvre les données
déjà présentes.

# 16. Modes d'exécution

- **BOOTSTRAP/REBUILD** : toutes les Occurrences supportées, ordre déterministe ;
- **CONTINUOUS** : change signal ciblé → reload owner → delta local ;
- **REQUEST TIME** : non retenu pour un rebuild global.

Aucun consumer automatique n'est enregistré tant qu'Actor 8 n'existe pas : il
ne faut pas marquer un Domain Event consommé sans cible durable.

# 17. Temporalité et fraîcheur

Le mapping utilise le temps sémantique Occurrence :

- date/heure de début ;
- date/heure de fin ;
- timezone ;
- timing kind.

`updated_at` est seulement une révision technique de source. Il n'est jamais
interprété comme temps physique ou temps de l'Occurrence.

Pour `DATE_ONLY`, l'heure inconnue reste `UNKNOWN`.
Pour `ALL_DAY`, l'heure est `NOT_APPLICABLE`.
Aucun minuit artificiel n'est inventé.

# 18. Cycle de vie

`declared_realization_plan` v1 :

- draft → `declared` ;
- scheduled → `scheduled` ;
- cancelled → `cancelled` ;
- completed → `closed`.

`closed` ne signifie pas « CorpsRéalisation observé ».

# 19. Idempotence / concurrence

Même snapshot canonique + même stratégie produit le même
`semantic_fingerprint`.

Le change signal est at-least-once compatible : le delta recharge la vérité
courante, puis upsert la même projection logique.

Actor 8 doit refuser :

- révision source plus ancienne ;
- même révision avec fingerprint contradictoire ;
- stratégie incompatible sans reprojection.

# 20. Erreurs / retry

Familles :

- unsupported fact ;
- missing canonical dependency ;
- inconsistent canonical state ;
- stale Universe projection ;
- Universe unavailable, futur adaptateur runtime.

Une donnée métier valide mais non supportée n'est pas une erreur métier.

Une dépendance manquante ne produit jamais une suppression Univers inventée.

# 21. Sécurité / confidentialité

Le mapping v1 ne projette :

- ni email ;
- ni téléphone ;
- ni adresse complète ;
- ni nom de Profile ;
- ni credential ;
- ni QR/token ;
- ni notes privées ;
- ni contenu de documents.

Les IDs canoniques restent internes au contrat. Toute future projection
collective devra appliquer la divulgation minimale.

# 22. Reconstruction

`build_full_snapshot()` :

1. demande au port owner la liste déterministe des Occurrences ;
2. charge chaque snapshot borné ;
3. applique la stratégie v1 ;
4. trie les roots par `projection_ref` ;
5. calcule un fingerprint stable ;
6. fournit `UniverseSnapshot`.

Aucun historique Domain Event n'est nécessaire au rebuild.

# 23. Échelle

La v1 est O(nombre d'Occurrences) au rebuild et O(1 root + lecture owner) pour
un delta. Aucun SLA n'est fixé avant mesure. Le rebuild futur pourra être batché
sans changer le contrat.

# 24. Coût

Pas de nouvelle base, queue, Kafka, Redis ou service. Aucun coût provider
nouveau. Le coût principal est la lecture DB bornée et la sérialisation
déterministe.

# 25. Observabilité

À brancher avec Actor 8/runtime :

- changes reçus/ignorés ;
- projections réussies/échouées/différées ;
- rebuilds/deltas ;
- roots affectées ;
- stale revisions ;
- unsupported facts ;
- durée/fingerprint de rebuild.

Ne jamais logger le snapshot complet par défaut.

# 26. Cas nominaux

## A — Bootstrap

Backend déjà rempli → `UniverseSnapshot`.

## B — Nouvelle Occurrence

création owner → `occurrence.created` → snapshot courant → delta local.

## C — Occurrence replanifiée

`occurrence.rescheduled` → reload → même projection ref, nouvelle révision.

## D — Requirement ajouté

**CANDIDAT, non implémenté en v1.** Aucune condition n'est inventée.

## E — Profile change

hors mapping v1 ; aucune PII n'est projetée.

## F — Access accordé

candidat futur ; AccessCredential est explicitement exclu.

## G — Capacity change

candidat futur ; ne pas fusionner avec Placement.

## H — annulation

la déclaration passe à `cancelled`, sans CorpsRéalisation.

# 27. Cas limites

- événement dupliqué → même état logique ;
- événement hors ordre → reload courant + fence Actor 8 ;
- dépendance manquante → erreur/déféré, jamais fabrication ;
- valeur absente → UNKNOWN, pas zéro ;
- mapping v2 → nouvelle `strategy_version` + reprojection ;
- delete technique → aucune sémantique de disparition automatique ;
- rebuild pendant delta → snapshot atomique par scope + fence de révision côté Actor 8.

# 28. Anti-patterns

Rejetés :

```python
for model in apps.get_models():
    make_universe_body(model)
```

ainsi que :

- Activity = planète/système par nom de classe ;
- Occurrence = CorpsRéalisation ;
- Profile = Véhicule/CorpsActeur universel ;
- price = mass/energy ;
- likes = charge ;
- Readiness persistée = état Univers ;
- full rebuild après chaque mutation ;
- Projecteur qui modifie Activity ou exécute Payment ;
- Universe comme source de vérité métier.

# 29. Tests

Le runtime v1 couvre :

- composition Activity + Occurrence → une structure Univers ;
- absence de Django models/QuerySets dans le contrat ;
- déterminisme/fingerprint ;
- UNKNOWN et NOT_APPLICABLE ;
- completed/cancelled sans création de CorpsRéalisation ;
- création/reschedule/cancel par Domain Events ciblés ;
- snapshot + delta = rebuild final ;
- événement dupliqué ;
- ancien delta refusé après une projection plus récente ;
- dépendance manquante ;
- absence de PII/credential/Readiness.

La CI PostgreSQL reste obligatoire pour les changements Domain Events et
transactions owner.

# 30. Critères de sortie

Fondation Actor 7 fermable lorsque :

- Actor 6 est intégré sur `main` ;
- la branche Actor 7 est réconciliée avec ce `main` ;
- snapshot et delta sont contractuels et testés ;
- création/replanification/annulation/réouverture ont un signal durable ;
- aucun ORM ne traverse le contrat Actor 8 ;
- aucun mapping 1:1 CorpsMakolo n'est imposé ;
- rebuild et delta convergent ;
- idempotence et fence hors ordre sont testées ;
- privacy tests sont verts ;
- aucune migration Actor 7 n'est créée ;
- CI complète est verte ;
- PR Actor 7 est mergée et le `main` final vérifié.

---

## Handoff Actor 8

Actor 8 peut commencer avec un fake ou un moteur in-process implémentant
`UniverseProjectionPort`. Il doit recevoir les structures telles quelles, sans
réimporter les modèles Django.

Actor 8 devra décider et calculer les structures scientifiques qui lui
appartiennent. Actor 7 ne préjuge pas :

- de l'existence d'un CorpsRéalisation ;
- de la géométrie calculée ;
- des trajectoires ;
- des interactions ;
- des champs ;
- des grandeurs physiques.

La prochaine extension d'Actor 7 ne doit être ajoutée que lorsqu'un nouveau
mapping scientifique est **RETENU** et que son owner fournit un snapshot/change
signal canonique suffisant.
