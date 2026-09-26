# Makolo — Profil d'exploitation ECC

ECC est un accélérateur optionnel de développement. Il ne remplace ni GitHub, ni les règles Makolo, ni les décisions de programme.

## Positionnement

Makolo est un produit mature en développement actif. ECC doit fonctionner en mode brownfield strict :

- lire avant d'écrire ;
- partir du `main` courant ;
- respecter `AGENTS.md` et `docs/operations/agent-orchestration.md` ;
- ne jamais redessiner Makolo hors scope ;
- ne jamais inférer qu'une roadmap signifie qu'un chantier reste à faire ;
- ne jamais créer modèle, migration, provider, API ou état persistant par défaut ;
- travailler sur branche dédiée et PR dédiée pour tout changement important.

## Équipe ECC par défaut

L'équipe de base est volontairement petite. Le maximum pratique reste cinq agents actifs en parallèle.

### 1. planner

Usage : cadrage d'un chantier avant écriture.

Contrat Makolo : inspecter runtime, tests, migrations, docs canoniques et PR pertinentes ; produire dépendances, write surfaces, risques et ordre d'exécution ; ne pas transformer une demande locale en refonte transverse.

### 2. architect

Usage : décisions qui traversent plusieurs domaines ou frontières.

Contrat Makolo : protéger les frontières canoniques ; vérifier si le besoin tient dans un domaine/service/read model existant avant tout nouveau modèle ; distinguer responsabilité, autorité, projection et présentation ; effectuer le collision audit avant parallélisation.

### 3. code-reviewer + python-reviewer

Usage : revue après modifications Python/Django. Reviewer le diff et ses call sites pertinents ; vérifier permissions/IDOR, transactions, requêtes, invariants et compatibilité anciennes données ; ne pas fabriquer de findings.

### 4. security-reviewer

Usage : surfaces sensibles, APIs, auth, uploads, paiements, Observer/Interpreter et données privées. Le serveur reste la frontière d'autorisation ; vérifier PII, secrets, AccessCredential, IDs privés et données cross-Space.

### 5. agent spécialisé du chantier

Choisir dynamiquement selon la surface : `flutter-reviewer` pour Mobile ; `e2e-runner` pour parcours navigateur ; `build-error-resolver` pour CI/build cassée avec correction minimale ; `spec-miner` seulement pour documenter un comportement brownfield existant ; agent Django/DB adapté si disponible dans l'installation ECC courante.

Le rôle spécialisé remplace un rôle générique dans l'équipe ; il ne s'ajoute pas automatiquement au-delà de cinq agents.

## Agents ECC à ne pas appliquer littéralement

Les agents ECC sont génériques. Leurs règles internes ne supplantent jamais Makolo. Exemple : le `tdd-guide` propose un seuil générique de couverture ; Makolo utilise les tests réellement pertinents et les gates du dépôt. De même, les commandes npm d'un reviewer générique ne remplacent pas les outils Django/Python déjà présents.

## Routage par type de tâche

### Nouveau chantier produit/backend

```text
planner
  -> architect si frontière transverse
  -> implémentation sur branche dédiée
  -> python-reviewer / code-reviewer
  -> security-reviewer si surface sensible
  -> CI
  -> statut programme: waiting ou ready-to-merge
```

### Bug ou CI rouge

```text
build-error-resolver
  -> correction minimale de cause racine
  -> code-reviewer
  -> gate ciblée
  -> suite pertinente
```

Ne jamais contourner ou affaiblir un test.

### Mobile

```text
planner
  -> flutter-reviewer
  -> Mobile CI
  -> ready-to-merge lorsque les contrats M10/mobile courants sont vérifiés
```

Une CI Mobile verte ne force pas le merge : vérifier aussi le handoff M10/mobile courant et l'absence de collision avec le main réel.

### Recherche

```text
research branch
  -> analyse/simulation
  -> revue méthodologique
  -> research
```

Une branche de recherche ne doit pas être convertie automatiquement en runtime ou en modèle persistant.

## Prompt de départ ECC

```text
Repository: TraditionLearningCommunity/makolo
Integration branch: main

Makolo is a mature brownfield product. Before any meaningful change, refresh current main, recent commits, relevant PRs/branches, CI, migrations and touched canonical docs.

Repository instructions in AGENTS.md and docs/operations/agent-orchestration.md are authoritative for collaboration. Current runtime, migrations and tests win over historical handoffs or roadmaps.

Do not redesign outside the assigned scope. Do not add a model or persistent state until existing domains, relations, services, selectors/read models, Readiness, Domain Events, Analytics and Presentation have been ruled out.

Use a dedicated branch and PR. State owner, base SHA, scope, forbidden surfaces, acceptance criteria, evidence and merge gate. Parallelize only non-overlapping write surfaces.

A green PR is not automatically mergeable by programme sequencing. It may remain green-waiting, research or blocked.

Never weaken tests. Fix root causes. Never expose secrets or unnecessary PII.
```

Après ce préambule, ajouter uniquement le contrat de la tâche courante.

## Modèle de carte ECC

```text
ID:
Objective:
Owner/agent:
Base SHA:
Branch:
Programme state: active | review | green-waiting | research | blocked | ready-to-merge

Scope:
- ...

Forbidden:
- ...

Dependencies:
- ...

Acceptance:
- ...

Evidence:
- targeted tests
- relevant suite
- migrations
- CI

Merge gate:
- ...
```

## Règle de parallélisme

Avant de lancer plusieurs agents, produire une matrice courte `Lane | Agent | Writes | Dependency | Parallel?`. Autoriser le parallèle uniquement lorsque les surfaces écrites ne se recouvrent pas et qu'aucune lane ne dépend d'un contrat encore instable produit par l'autre.

Le parallélisme n'est pas un objectif. Le débit de changements intégrables est l'objectif.

## État programme et PR

ECC ne doit jamais fusionner automatiquement une PR uniquement parce que la CI est verte.

Décision de merge = gates techniques vertes + branche réconciliée avec main + dépendances programme satisfaites + moment d'intégration approprié.

Une PR `green-waiting` est un état sain.

## Installation

ECC reste un outil développeur, pas une dépendance du dépôt Makolo.

Installation recommandée sur le poste qui l'utilise :

```bash
npx ecc-universal@2.2.2 install --guided --harness codex --dry-run
npx ecc-universal@2.2.2 install --guided --harness codex
```

Ne pas versionner les artefacts d'installation locaux dans Makolo sauf décision explicite et revue séparée.

## Critère de réussite

ECC est correctement intégré au mode de travail Makolo lorsque les agents récupèrent d'abord l'état courant ; chaque écriture appartient à une branche et un owner explicites ; les travaux indépendants continuent sans attendre la fermeture de toutes les PR ; une PR verte peut rester volontairement en attente ; Mobile, Recherche et runtime évoluent sans collision ; les agents laissent une preuve et un handoff exploitable ; `main` reste le seul point d'intégration.