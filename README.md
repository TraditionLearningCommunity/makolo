# Makolo

> **Makolo marche pour vous.**

Makolo est un **réseau d’action** : découvrir des possibilités réelles, préparer ce qui peut l’être, orchestrer ce qui reste à faire, accompagner l’action réelle et capitaliser ce qui facilitera la suite.

Le produit n’est plus limité à une plateforme événementielle. Event reste une verticale importante, mais le noyau canonique est désormais centré sur des domaines transverses comme `Profile`, `Activity`, `Occurrence`, `Journey`, `Requirement`, `Proof`, `Access`, `Capacity`, `Commerce`, `Payment`, `Geography`, `Authorization`, `Notifications`, `Automation`, `Sharing`, `Discovery` et les projections d’expérience qui les composent.

Principe directeur :

> **Pas le plaisir de rester. Le plaisir d’avancer.**

---

## Trajectoire produit

La trajectoire actuelle est cumulative :

```text
Makolo Mature
    ↓
Makolo Mobile
    ↓
Makolo Intelligence Kernel
    ↓
Makolo Agent
    ↓
Compétences / agents spécialisés
```

- **Makolo Mature** : réseau d’action fiable, déterministe, backend/web/API, exploitable sans LLM.
- **Makolo Mobile** : client Flutter natif, actif et ambient, utilisant les capacités du téléphone sans déplacer la vérité métier hors du backend.
- **Makolo Intelligence Kernel** : perception, observations, contexte, mémoire, raisonnement, tools, policy et vérification.
- **Makolo Agent** : boucle bornée `observe → understand → plan → act → verify`.
- **Spécialisations** : bourses/opportunités, emploi, événements, voyage, opérations, services, etc., toutes construites sur le même Kernel.

Voir :

- [`docs/architecture/makolo-evolution-blueprint.md`](docs/architecture/makolo-evolution-blueprint.md)
- [`docs/architecture/current-program-status.md`](docs/architecture/current-program-status.md)

---

## État courant

L’état GitHub courant reste la vérité sur ce qui est réellement livré.

Au snapshot du **17 septembre 2026** :

- M1 → M7 sont documentés comme livrés ;
- le programme G — Profil, pertinence & réseau d’action — est terminé ;
- les grands trains Q/R/D/O sont largement intégrés ;
- l’Intelligence Foundation et Discover Intelligence existent déjà ;
- M9 Hardening a déjà été fermé sur une base auditée ;
- la PR #234 porte la convergence finale **M8 mobile-first mature personal experience** ;
- Mobile A0 est préparé mais Flutter n’est pas encore réellement engagé sur `main` ;
- le futur Intelligence Kernel doit étendre les fondations existantes, pas les dupliquer ;
- Makolo Agent n’est pas encore livré comme runtime agentique général.

Le snapshot détaillé est dans [`current-program-status.md`](docs/architecture/current-program-status.md).

---

## Invariants d’architecture

Quelques règles fondamentales :

- **Event est une verticale. Activity est le noyau.**
- Un `Profile` représente une personne globale ; il n’existe pas de « participant » ou « organisateur » global.
- `Assignment` = responsabilité. `Mandate` / `Permission` = autorité.
- Membership, Group ou Team n’accordent pas implicitement d’autorité.
- `Readiness` est une projection dérivée, pas un état générique à dupliquer.
- `Requirement`, `Form`, `Resource`, `JourneyArtifact`, `Proof`, `Credential Trust` et `AccessCredential` restent distincts.
- `Access` = droit ; `AccessCredential` = représentation/secret ; `AccessUse` = observation d’usage/passage.
- `Capacity` répond « combien ? » ; `Placement` répond « où ? ».
- Waitlist = attendre une place ; Live Queue = attendre son tour avec le droit pertinent.
- `JourneyStep` n’est pas un checkpoint opérationnel.
- `Dossier` = objectif actif composé ; `Project` = horizon durable ; aucun ne devient task manager générique.
- Posséder un document ≠ le retrouver ≠ satisfaire un Requirement.
- Toute projection publique/collective applique la divulgation minimale.
- Une composition ne transfère jamais implicitement Permission, Mandate, Access, Payment ou accès à des données privées.

---

## Expérience produit

### Accueil / Maintenant

Question centrale :

> **Qu’est-ce qui compte maintenant ?**

La surface doit rester privée, contextuelle et orientée accomplissement. Elle doit pouvoir conclure :

> **Tout est en ordre. ✓**

### Discover / Découvrir

Question centrale :

> **Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?**

Discover est exploratoire, visuel, cartographique et éventuellement multimédia.

Le produit ne doit pas être optimisé pour watch time, scroll infini artificiel, likes ou popularité. Les métriques centrales restent liées à l’action réelle.

### No Orphan Content / No Orphan Media

Tout contenu ou média doit avoir contexte et finalité. Presentation représente les faits ; elle ne les possède pas.

---

## Makolo Mature

Le cœur Mature porte notamment :

```text
Profile / Space / Group
Activity / Occurrence
Journey / JourneyRequest
Requirements / Readiness
Forms / Resources / Personal Assets
Trust / Proof / Action Memory
Capacity / Commerce / Payment
Access / AccessCredential / AccessUse
Notifications / Automation / Domain Events
Social Action Network
Spatiotemporal Intelligence
Preparation
Dossier / Project / Collaboration
Operations
Interoperability / Connections / Extensions
```

Makolo Mature doit rester fonctionnel même si :

- aucun provider IA n’est disponible ;
- Internet est partiellement inaccessible ;
- une Connection externe est révoquée ;
- une observation est stale ou contradictoire.

L’IA augmente Makolo ; elle ne doit jamais devenir sa seule source de vérité.

---

## Makolo Mobile

Le mobile suit la règle :

> **Le backend Makolo décide. Le mobile présente, orchestre et utilise les capacités du téléphone.**

Programme :

```text
A0 — Phase 0 / foundation
A1 — Application native Flutter
A2 — Native Capabilities
A3 — Ambient Makolo
A4 — Operations & Offline R&D
```

Capacités natives prévues progressivement :

```text
push
biométrie locale
caméra / scanner
share sheet
contacts consentis
localisation native
geofencing
voice / intents
haptique
widgets / lock screen / Live Activities
background sync / offline borné
```

Le mobile ne réimplémente pas Readiness, Permissions, Payment state, Access validity, Hazards ou ranking.

---

## Makolo Intelligence Kernel

Le Kernel futur doit étendre les fondations déjà présentes :

```text
intelligence gateway / providers / routing
Action Memory / Trusted Reuse
Domain Events
Automation / Autopilot
Notifications
Prepared Start / NextAction
M7 Connections / Actions / Extensions
Geography / Hazards
Opportunity source provenance / checks
```

Architecture cible :

```text
MONDE EXTÉRIEUR
      │
      ▼
PERCEPTION
      │
      ▼
OBSERVATIONS
      │
      ├──────── Makolo Core
      ├──────── Action Memory
      ├──────── Domain Events
      └──────── Mobile signals
                │
                ▼
         CONTEXT BUILDER
                │
                ▼
         REASONER / PLANNER
                │
                ▼
     POLICY / CONSENT / AUTH
                │
                ▼
           TOOL GATEWAY
                │
                ▼
        ACTION / RESULT
                │
                ▼
      VERIFIER / FEEDBACK
                └──────→ nouveau contexte
```

Invariant central :

> **Observation ≠ Fact.**

Une donnée externe doit conserver provenance, fraîcheur et scope avant d’influencer une vérité ou une action.

---

## Makolo Agent

Makolo Agent n’est pas « un chatbot ajouté dans l’application ».

Il existe lorsque Makolo peut poursuivre un objectif sur plusieurs étapes :

```text
Goal
  ↓
Observe
  ↓
Understand
  ↓
Plan
  ↓
Act through allowed tools
  ↓
Verify
  ↓
Replan or stop
```

Le modèle n’écrit jamais directement dans l’ORM pour modifier une vérité métier.

```text
LLM / Planner
    ↓
Tool Gateway
    ↓
Policy / Authorization
    ↓
Canonical service
    ↓
Domain Event
```

Les actions à fort impact restent bornées par Permission, Mandate, Consent, Access, Payment et confirmation utilisateur lorsque nécessaire.

---

## Stack actuelle

- Python 3.10
- Django 5.2
- Django REST Framework
- Django Templates
- HTMX
- Alpine.js
- Tailwind CSS
- SQLite pour le développement initial
- PostgreSQL pour les gates et opérations qui exigent ses garanties

Flutter est le choix retenu pour l’application mobile native à venir.

---

## Installation locale sous PowerShell

Créer et activer un environnement Python dédié, puis installer les dépendances :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

L’application est disponible sur <http://127.0.0.1:8000/>.

Pour observer Autopilot en développement, lancer dans un second terminal :

```powershell
python manage.py autopilot_worker --poll-seconds 10
```

---

## Vérifications avant commit

```powershell
python -m pip check
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Les changements importants doivent passer par une branche dédiée + PR, sauf décision explicite contraire. Ne jamais merger avec CI rouge et ne jamais affaiblir un test pour obtenir du vert.

---

## CI

La CI couvre plusieurs niveaux :

- checks Django ;
- migrations ;
- matrices PostgreSQL ;
- sécurité / supply chain ;
- E2E ;
- agrégation `ci/aggregate` sur `main`.

Le détail exact des workflows évolue : toujours vérifier l’état GitHub courant avant un changement important.

---

## Autopilot

Les opérations temporelles et réactives utilisent le moteur Automation/Autopilot existant. En environnement approprié, un worker persistant peut être lancé avec :

```text
python manage.py autopilot_worker --poll-seconds 30 --delivery-limit 100
```

Le futur Agent doit réutiliser Automation et Domain Events ; il ne doit pas créer un second scheduler générique.

---

## Sécurité et confidentialité

- aucune clé réelle, token, secret ou credential ne doit être versionné ;
- Permission / Mandate / Access restent vérifiés côté serveur ;
- les données privées sont minimisées dans les projections, logs et analytics ;
- un compte externe ou réseau social ne constitue pas automatiquement un consentement d’import ;
- les agents futurs restent provider-neutral, auditables et bornés ;
- aucun profil psychologique opaque ou score humain universel ne doit être introduit.

Voir :

- [`docs/architecture/authorization-boundaries.md`](docs/architecture/authorization-boundaries.md)
- [`docs/architecture/security-threat-model.md`](docs/architecture/security-threat-model.md)
- [`docs/architecture/m9-hardening-quality-gate.md`](docs/architecture/m9-hardening-quality-gate.md)

---

## Documents canoniques à lire en priorité

1. [`docs/architecture/makolo-domain-blueprint.md`](docs/architecture/makolo-domain-blueprint.md)
2. [`docs/architecture/mature-program-roadmap.md`](docs/architecture/mature-program-roadmap.md)
3. [`docs/architecture/strategic-action-roadmap.md`](docs/architecture/strategic-action-roadmap.md)
4. [`docs/architecture/profile-relevance-action-network.md`](docs/architecture/profile-relevance-action-network.md)
5. [`docs/architecture/mature-experience-principles.md`](docs/architecture/mature-experience-principles.md)
6. [`docs/architecture/makolo-evolution-blueprint.md`](docs/architecture/makolo-evolution-blueprint.md)
7. [`docs/architecture/current-program-status.md`](docs/architecture/current-program-status.md)
8. [`docs/operations-runbook.md`](docs/operations-runbook.md)

Documents transverses utiles :

- [`docs/architecture/domain-events-automation.md`](docs/architecture/domain-events-automation.md)
- [`docs/architecture/spatiotemporal-intelligence.md`](docs/architecture/spatiotemporal-intelligence.md)
- [`docs/architecture/intelligence-discover-program.md`](docs/architecture/intelligence-discover-program.md)
- [`docs/architecture/m9-hardening-quality-gate.md`](docs/architecture/m9-hardening-quality-gate.md)

---

## Source de vérité

Toujours privilégier, dans cet ordre :

1. code, migrations et tests actuels ;
2. `makolo-domain-blueprint.md` ;
3. roadmaps et docs canoniques pertinentes ;
4. `docs/operations-runbook.md` ;
5. état GitHub courant ;
6. historique et documents de transfert comme contexte.

Une roadmap décrit une cible et un séquencement ; elle ne prouve pas qu’un élément est déjà livré.
