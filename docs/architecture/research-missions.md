# Missions de recherche Makolo — Pré-Actor 3

**Statut : contrat d'architecture et runtime léger**  
**Base d'audit : `main@bee273500a383941ac89796156e1e429ed9de345`**  
**Périmètre : besoin de connaissance → Prospecteur → Observateur → contexte en lecture seule pour un futur enrichissement Actor 3**

## 1. Décision d'architecture

`ResearchMission` et `ProspectingMission` ont deux responsabilités distinctes.

~~~text
Besoin Makolo
     ↓
ResearchMission
     ↓
ProspectingPlan
     ↓
ProspectingMission
     ↓
Actor 1 — Prospecteur
     ↓
Actor 2 — Observateur
     ↓
ObservationMaterial v2
     ↓
future Actor 3 + ResearchContextSourcePort
~~~

`ResearchMission` exprime **pourquoi Makolo cherche et quelle question reste ouverte**.
Elle n'est ni une vérité métier, ni une Journey, ni un Dossier, ni une Veille, ni
une Activity, ni une Opportunity, ni un état Readiness, ni un task manager.

`ProspectingMission` reste le contrat technique existant de couverture : TLD,
langues, termes de chemin, types MIME, budget de candidats et contexte de
politique. Le Prospecteur continue à répondre à **où regarder ?**, pas à
**qu'est-ce que cette page signifie réellement ?**

## 2. Persistance : aucune nouvelle table

Le chantier retient l'option minimale : **contrat pur + provenance Prospecteur
existante**. Aucune table `ResearchMission` et aucune migration ne sont ajoutées.

Ce choix suffit parce que :

- l'identité logique existe via un fingerprint déterministe ;
- la projection `ResearchMission → ProspectingMission` embarque un snapshot
  versionné du contexte de recherche ;
- `IndexProspector` propage déjà `ProspectingMission.context` dans
  `policy_context.mission_context` ;
- `ProspectorFrontierEvidence.policy_context` conserve durablement chaque
  attribution, y compris lorsque plusieurs missions découvrent la même cible ;
- la Frontier conserve le `target_key` stable ;
- `ObservationTarget` et `ObservationMaterial v2` conservent ce `target_key`
  sans transporter le contexte métier ;
- un read model Prospecteur peut reconstruire le contexte pour Actor 3 sans
  accès ORM sauvage depuis l'Interpréteur.

Une persistance dédiée ne deviendrait nécessaire que si un futur
admission/scheduler devait posséder un cycle de vie durable de Mission avant
toute prospection. Ce scheduler est hors périmètre.

## 3. Huit familles de Mission

Les familles organisent la **question de recherche**. Elles ne créent aucun
bounded context et ne remplacent aucun domaine canonique.

| Famille | Question directrice | Exemples de réalités susceptibles d'être rencontrées |
|---|---|---|
| `POSSIBILITY` | Qu'est-ce qu'on peut faire, vivre ou obtenir ? | Activity, Occurrence potentielle, Opportunity, service, programme, emploi, bourse, stage, formation, examen, transport, financement |
| `REQUIREMENT` | Qu'est-ce qui doit être vrai ou satisfait ? | éligibilité, âge, diplôme requis, expérience, langue, lieu, condition financière, deadline, prérequis |
| `QUALIFICATION` | Qu'est-ce qui prouve, atteste ou matérialise une condition ? | Credential, certificat, diplôme, résultat de test, Proof-like evidence, document requis, validité, issuer |
| `ACTOR` | Qui fait quoi ? | Organization, Space, université, société, ONG, autorité, ambassade, centre de test, issuer, opérateur, contact |
| `SPATIOTEMPORAL` | Où, quand et avec quelle disponibilité ? | date, heure, durée, session, Occurrence, Place, Zone, origine, destination, arrêt, Capacity, disponibilité |
| `PROCEDURE` | Comment fait-on concrètement ? | inscription, candidature, rendez-vous, réservation, soumission, étapes, formulaires, instructions, procédure d'accès |
| `ECONOMIC` | Combien et selon quelles modalités économiques ? | prix, frais, devise, Offer, mode de paiement, financement, couverture, aide, remboursement, fenêtre économique |
| `REFERENCE` | Quelle règle ou ressource officielle permet de comprendre ou accomplir l'action ? | guide officiel, règlement, FAQ, formulaire, PDF, documentation, URL, contact officiel |

Ces familles ne produisent aucun mapping rigide. `REQUIREMENT` n'est pas
synonyme du modèle Django `Requirement` et `POSSIBILITY` n'est pas synonyme
d'`Activity`.

Les distinctions canoniques restent intactes :

~~~text
Requirement != Proof
Proof != Credential
Credential Trust != AccessCredential
JourneyArtifact != Resource
Access = droit
Capacity = combien
Place/Placement = où
~~~

## 4. Contrat ResearchMission

Le contrat framework-independent porte :

~~~text
mission_ref / mission_key stable
primary_family
subject
questions
known_context
unknowns
origins
reasons
priority éventuelle
scope
limits
~~~

Il est immuable. Les structures JSON sont gelées après validation.

### Identité logique

Le fingerprint v1 dépend uniquement du besoin sémantique :

~~~text
primary_family
+ subject normalisé
+ ensemble des questions normalisées
+ ensemble des unknowns normalisés
+ scope canonique
~~~

Il exclut volontairement :

~~~text
origins
reasons
known_context
priority
limits
horodatages
IDs accidentels
~~~

Ainsi plusieurs bourses qui conduisent à la même question TOEFL peuvent partager
le même `mission_ref`, tout en gardant des provenances distinctes.

`known_context` n'entre pas dans l'identité : améliorer la connaissance ne doit
pas créer artificiellement un nouveau besoin tant que sujet, questions,
inconnues et scope restent les mêmes.

## 5. ResearchMissionCandidate

Une dépendance ou un fait insuffisamment compris peut produire un candidat :

~~~text
fait / dépendance insuffisamment comprise
        ↓
ResearchMissionCandidate
  subject
  primary_family
  questions
  origin
  reason
  priority éventuelle
        ↓
admission future contrôlée
~~~

Construire un candidat ne l'exécute jamais. `candidate.to_mission()` établit
seulement un contrat admis en mémoire ; il ne lance ni crawler, ni worker, ni
scheduler.

L'admission future pourra appliquer budget, priorité, profondeur,
déduplication, fraîcheur, scope et policy.

## 6. Origines et provenance

Les origines formalisées sont :

~~~text
initial
watch
canonical_reality
requirement
unresolved_dependency
previous_processing
~~~

Chaque origine peut porter une `source_ref` stable et un petit contexte JSON.
Les raisons sont conservées séparément de l'identité logique.

Deux candidates ayant le même besoin mais des origines différentes ont donc le
même fingerprint. Une Mission peut agréger plusieurs origines sans changer de
`mission_ref`.

Une Veille peut être une origine ; elle ne devient pas une Mission de recherche.

## 7. Projection vers Actor 1

La transformation est explicite :

~~~text
ResearchMission
        +
ProspectingPlan
  host_tlds
  languages
  path_terms
  media_types
  max_candidates
        ↓
ProspectingMission
~~~

Aucun sélecteur n'est dérivé automatiquement de `primary_family`, `subject`
ou `questions`. Une Mission `REQUIREMENT` ne force donc ni chemin URL, ni
site, ni type de résultat.

Le `ProspectingMission.mission_key` reçoit le `ResearchMission.mission_ref`.
Son `context` reçoit un snapshot versionné `research_mission`. Les sélecteurs
et budgets restent ceux du plan technique.

Le fingerprint de `ProspectingMission` identifie le **plan de prospection**.
Celui de `ResearchMission` identifie le **besoin de connaissance**.

## 8. Actor 1 : réutiliser la provenance existante

Aucune seconde Frontier, campagne ou profondeur n'est créée.

~~~text
IndexProspector
→ ProspectingCandidate.policy_context
→ DjangoFrontierStore
→ ProspectorFrontierEvidence.policy_context
~~~

`mission_key`, `mission_fingerprint`, `campaign_key`, `branch_key`,
`depth` et la provenance technique continuent à vivre dans leurs contrats
actuels. L'expansion structurelle réutilise le contexte du parent et
`depth + 1`.

Le snapshot `research_mission` reste une hypothèse de recherche. Il n'autorise
jamais Actor 1 à conclure qu'une URL est réellement une Activity, un Requirement
ou une qualification.

## 9. Actor 2 reste ignorant du sens métier

`ObservationTarget` reste volontairement minimal :

~~~text
handoff_key
target_key
handoff_generation
locator
kind
requested_at
observation_hints
~~~

Il ne reçoit ni `ResearchMission`, ni `primary_family`, ni questions, ni
provenance métier. Le gros contexte n'est pas copié dans l'Observateur.

`ObservationMaterial v2` reste la matière technique observée.

## 10. Frontière de contexte pour un futur Actor 3

Le port est :

~~~text
ResearchContextSourcePort
  contexts_for_target(target_key)
      -> tuple[ResearchContext, ...]
~~~

L'adaptateur Django est possédé côté Prospecteur :

~~~text
DjangoProspectorResearchContextSource
~~~

Le chemin est :

~~~text
ObservationMaterial.target_key
        ↓
ResearchContextSourcePort
        ↓
ProspectorFrontierEvidence.policy_context
        ↓
ResearchContext
~~~

Le port expose seulement une projection en lecture seule : identité de Mission,
famille principale, sujet, questions, contexte connu utile, unknowns, origines,
raisons et scope. Il n'expose ni permissions utilisateur, ni secrets, ni objets
ORM métier, ni mutation de Mission.

Si une même cible a été découverte plusieurs fois pour le même besoin logique,
le read model conserve le snapshot le plus récent et agrège les origines et
raisons associées au même `mission_ref`. Sans contexte ResearchMission, il
retourne un tuple vide.

La requête est strictement bornée au `target_key` demandé : le contexte d'une
autre cible n'est jamais joint accidentellement.

## 11. primary_family n'est jamais un filtre destructif

Une Mission :

~~~text
primary_family = REQUIREMENT
subject = Bourse X
question = Quelles sont les conditions ?
~~~

peut conduire à une page exprimant simultanément :

~~~text
Bourse X              → possibilité candidate
Université Y          → acteur candidat
TOEFL >= 80           → requirement candidat
Diplôme               → qualification et/ou requirement selon le sens
12 novembre           → fait temporel / condition selon le contenu
URL de candidature    → procédure candidate
0 USD                 → fait économique
Guide officiel        → référence candidate
~~~

Actor 3 devra interpréter **ce que le matériau exprime réellement**. Le contexte
de Mission l'oriente ; il ne réécrit pas l'observation et ne supprime pas les
autres informations pertinentes.

~~~text
Mission = hypothèse de recherche
Observation = réalité acquise
Interprétation = candidats sémantiques
Résolution = rapprochement
vérité métier = domaines propriétaires
~~~

## 12. Anti-features et frontières

Ce chantier ne crée pas :

~~~text
MissionActivity / MissionVisa / MissionScholarship / ...
huit apps Django
huit pipelines
scheduler autonome
crawler récursif illimité
ranking global de Missions
Journey de recherche
Dossier de recherche
Readiness de recherche
objet métier canonique depuis une Mission
~~~

Il n'introduit aucune dépendance vers Actors 8+ et aucune dépendance vers
Univers Makolo.

## 13. Replay et compatibilité

Une Mission exécutée via Actor 1 est rejouable à partir de son snapshot versionné
dans les evidences Prospecteur. Les anciennes evidences qui ne possèdent pas
`mission_context.research_mission` restent valides : le read model retourne
simplement aucun contexte ResearchMission.

Aucun backfill n'est nécessaire. Aucune migration destructive ou artificielle
n'est requise.

## 14. Critères de fermeture

Le Pré-Actor 3 est fermé lorsque :

- les huit familles sont contractuelles et testées ;
- le besoin possède une identité déterministe indépendante des origines et budgets ;
- `ResearchMissionCandidate` représente une suggestion sans exécution automatique ;
- plusieurs origines sont conservables sans multiplier l'identité logique ;
- la projection vers `ProspectingMission` reste explicitement technique ;
- Actor 1 conserve l'attribution via sa provenance durable existante ;
- `ObservationTarget` reste exempt du gros contexte ResearchMission ;
- le port de lecture seule retrouve le contexte depuis `target_key` ;
- l'isolation entre cibles est testée ;
- aucune table et aucune migration ne sont ajoutées ;
- aucun domaine canonique, Actor 8+ ou Univers Makolo n'est modifié.
