# Makolo — Mature Program Roadmap

> **Statut : canonique pour le séquencement de clôture Makolo Mature et le handoff mobile.** Ce document complète [`makolo-domain-blueprint.md`](makolo-domain-blueprint.md) et [`strategic-action-roadmap.md`](strategic-action-roadmap.md). Le code, les migrations, les tests et l’état GitHub du `main` courant restent la vérité sur ce qui est effectivement livré.

## 1. Rôle de cette roadmap

Makolo possède désormais deux lectures complémentaires de sa suite :

- **stream M** : colonne vertébrale de maturité du produit, jusqu’au backend/web/API prêt pour le mobile ;
- **trains P→U** : capacités produit stratégiques qui enrichissent ce produit par composition.

Ces deux lectures ne doivent pas être traitées comme des files de tâches équivalentes lancées sans coordination.

Le stream M ferme le produit et définit les gates vers le mobile. Les trains P→U alimentent cette colonne vertébrale lorsqu’ils doivent faire partie de l’expérience Mature.

Principe général :

> **Le backend Makolo décide. Le web présente et orchestre. Le mobile présente, orchestre et utilise les capacités du téléphone. Les providers externes exécutent leurs capacités spécialisées. Les extensions ajoutent des capacités sans prendre possession des domaines canoniques.**

## 2. État du stream M

Les responsabilités suivantes sont considérées comme déjà livrées et ne doivent pas être recréées dans P→U :

```text
M1 ✅ Readiness Engine
M2 ✅ Forms, Questionnaires & Preparation Resources
M3 ✅ Presentation System
M4 ✅ Trust & Quality
M5 ✅ Social Action Network & Useful Engagement
M6 ✅ Spatiotemporal Intelligence, Hazards & Last-Minute
```

Frontières à préserver :

- `Readiness` reste une projection dérivée ;
- `Form` collecte des données structurées ;
- `ActivityResource` informe/prépare au niveau Activity/Occurrence ;
- `JourneyArtifact` reste un artefact individuel de Journey ;
- Presentation représente les faits sans les posséder ;
- Trust porte des faits de confiance précis, pas un score humain universel ;
- M5 porte le réseau social d’action et ses projections ;
- M6 porte les projections spatio-temporelles, `Hazard` et `ActionAdvice` sans persister ETA, météo, trafic ou position utilisateur comme vérités métier.

## 3. Séquence de clôture Mature

La séquence de clôture retenue est :

```text
M7 — Interoperability, Connections & Extension Platform
M8 — Makolo Mature Web Experience
M9 — Mature Hardening & Quality Gate
M10 — Mature Closure, Production Readiness & Mobile Handoff
```

M9 et M10 restent séparés :

- **M9** prouve la cohérence technique, fonctionnelle, sécurité, performance, migrations, accessibilité et résilience ;
- **M10** ferme l’exploitation du produit, la production readiness réelle et le handoff mobile.

M10 n’est pas un nouveau domaine métier.

## 4. Positionnement actuel de P→U dans cette séquence

### Fenêtre de convergence actuelle

Au moment de cette décision, les deux trains déjà engagés restent autonomes :

```text
P5 → finaliser le train P / Sharing
Q1→Q4 → finaliser le train Q / Capital d’action personnel
```

P et Q peuvent terminer en parallèle parce qu’ils ont déjà été conçus comme trains empilés et autonomes. Chaque train se réconcilie avec le `main` réel uniquement à sa fin.

### Gate avant M7

**Par défaut, M7 ne démarre qu’après l’intégration finale de P et Q dans `main`.**

Raison :

- P fixe les contrats Sharing et documents entrants qui touchent les actions externes ;
- Q fixe le capital personnel, la provenance et la réutilisation documentaire ;
- M7 introduit Connections, actions externes, providers et extensions et doit donc partir d’un contrat interne stabilisé plutôt que d’inventer ses propres variantes.

Cette règle est un choix de coordination pour réduire les collisions, pas une dépendance technique artificielle entre tous les modèles P/Q et M7.

### Après M7 : capacités qui doivent façonner le web Mature

M8 est un **gate d’assemblage UX**, pas nécessairement la branche chronologiquement ouverte le lendemain de M7.

Avant de figer M8, terminer les capacités structurantes que nous voulons réellement voir dans le premier web Mature :

```text
R — Préparation intelligente
D — Dossiers, Projets & Collaboration
T-core — Occurrence Operations backend/web
```

Ordre de référence :

```text
P + Q intégrés
      ↓
M7
      ↓
R
      ↓
D
      ↓
T-core
      ↓
M8
      ↓
M9
      ↓
M10
      ↓
A — Mobile
```

Des branches peuvent exceptionnellement se chevaucher lorsqu’un audit de collision montre qu’elles sont réellement indépendantes, mais le défaut n’est plus le parallélisme maximal.

### U n’est pas un gate mobile

`U — Intelligence cumulative` ne bloque ni M8, ni M10, ni le lancement du programme mobile.

Proven Paths et l’intelligence cumulative doivent disposer d’assez de données réelles avant de tirer des conclusions crédibles. U peut donc mûrir après la Release Candidate Mature et continuer pendant la vie du produit.

## 5. M7 — Interoperability, Connections & Extension Platform

M7 est le dernier grand chantier architectural de plateforme avant l’assemblage UX Mature.

Question :

> **Comment Makolo coopère-t-il avec des applications, comptes, providers et extensions externes sans perdre la propriété de ses domaines canoniques ?**

### Provider Registry

Le cœur demande une capability stable, pas un fournisseur codé partout :

```text
Capability → Provider → Adapter
```

Exemples de familles possibles lorsque le besoin réel existe : navigation, routing, traffic, weather, calendar, email, source-control, export et external actions.

M7 n’invente aucun fournisseur commercial, compte ou secret qui n’existe pas dans une décision réelle du projet.

### Connections

Une `Connection` représente l’autorisation explicite donnée par un Profile ou un Space à Makolo pour coopérer avec un service externe.

Installed/available ne signifie jamais authorized :

```text
capability disponible
+ Connection
+ scopes
+ Permission/Mandate
+ contexte autorisé
= action exécutable
```

Les credentials externes ne doivent pas apparaître dans logs, templates, API publique ou configuration d’extension visible.

### Action Registry

Les actions externes passent par un catalogue contrôlé : validation, autorisation, exécution et audit utile.

Une extension/provider n’obtient jamais l’ORM Makolo, les credentials DB, le raw SQL ou le filesystem interne.

### Event subscriptions et webhooks

Les intégrations peuvent consommer des Domain Events autorisés et échanger par webhook lorsque pertinent, avec scopes, authentification/signature, idempotence, retry borné et observabilité.

Un webhook entrant ne modifie jamais directement une vérité métier : il passe par le service du domaine propriétaire.

### Extension Platform

Makolo doit rester un produit complet sans plugin.

Une extension ajoute une capacité ; elle ne déplace pas le cœur Makolo hors de Makolo Base.

Le contrat d’exécution reste :

```text
extension installée
+ active
+ entitlement éventuel
+ permission utilisateur
+ Connection éventuelle
+ contexte autorisé
= capacité exécutable
```

Les extensions utilisent APIs, Actions, Events, Webhooks et Scoped Data. Les UI contributions sont bornées à des slots contrôlés ; une extension ne remplace pas arbitrairement toute l’interface.

M7 ne construit pas : marketplace commerciale, billing d’extensions, revenue sharing, runtime mobile de plugins, Python/JavaScript arbitraire ou accès DB direct.

## 6. M8 — Makolo Mature Web Experience

M8 assemble le produit ; il ne crée pas un nouveau domaine métier.

### Cockpit `/me/`

Le Cockpit reste une projection, pas `Dashboard`, `DashboardItem` ou `DashboardState` comme nouvelles vérités.

Il compose notamment :

- Discovery / Recommendations / Network / Goals lorsqu’il n’y a rien d’urgent ;
- NextAction / Readiness / Forms / Resources / Requirements / Payment / Access pour une Journey active ;
- M6 Temporal/Spatial/Mobility/Hazards lorsque l’Occurrence devient imminente ;
- R pour Prepared Start et la priorisation contextuelle ;
- D pour Dossiers/Projets et responsabilités lorsqu’ils sont actifs ;
- T pour l’état opérationnel Jour J.

**R possède les règles/projections de préparation ; M8 possède leur composition web.** Le train R ne doit donc pas construire un second Cockpit concurrent.

### Journey Command Center

M8 assemble les phases BEFORE / READY / ARRIVAL / AFTER autour des domaines canoniques sans posséder leurs faits.

### Explorer, Réseau et Space Consoles

M8 harmonise Activities, Services, Transport, Events, Groups, Opportunities, Recommendations et surfaces M5 sans transformer Discovery en liste de bounded contexts.

Les Space Consoles composent Team, Mandates, Forms, Resources, Presentation, Capacity, Commerce, Payments, Access, Operations, Trust, CRM, Automation, Analytics, Connections et Extensions avec les permissions serveur existantes.

### Responsive web

Le web desktop, tablette et navigateur mobile doit rester sérieusement utilisable même sans application native.

## 7. R, D et T avant M8

### R — Préparation intelligente

R construit :

- Prepared Start ;
- Proactive Preparation ;
- contrats de priorité/NextAction nécessaires à l’Accueil contextuel.

R réutilise M1 Readiness, M6, Domain Events, Notifications et Autopilot. Il ne recrée ni scheduler, ni `ReadinessState`, ni Cockpit persistant.

### D — Dossiers, Projets & Collaboration

D livre Dossier, Projet et leurs mécanismes de collaboration/relations, en conservant :

- Journey comme démarche individuelle ;
- Assignment comme responsabilité ;
- Mandate comme autorité ;
- Payment, Access, Capacity, Artifact dans leurs domaines canoniques.

D doit être stabilisé avant M8 si Dossiers/Projets doivent façonner la navigation Mature ; sinon M8 serait immédiatement à refaire.

### T-core — Occurrence Operations

Avant M8, T-core couvre les vérités/projections backend et web nécessaires à :

- Operational Readiness ;
- Occurrence Live ;
- Placement ;
- Checkpoints/Flow ;
- Live Queue lorsque les données permettent une estimation légitime.

M6 reste propriétaire du contexte spatio-temporel et des Hazards. Access reste le droit. AccessUse reste l’observation du passage. Capacity reste le nombre. Placement répond à « où ? ».

## 8. Frontière T / mobile offline

La capacité stratégique `Offline Action Pack` doit être séparée en deux responsabilités :

### Avant mobile

Le backend peut définir :

- quelles données sont nécessaires ;
- leur provenance ;
- sensibilité ;
- expiration ;
- politique de révocation ;
- contrat de synchronisation/lecture lorsque nécessaire.

Le web peut éventuellement exploiter les mécanismes standards du navigateur si cela reste sûr et utile.

### A4 mobile

Restent explicitement au programme mobile :

- secure local storage natif ;
- background sync OS ;
- vrai scanner offline ;
- réconciliation multi-device ;
- replay/double-use ;
- clock skew ;
- conflits ;
- protocole offline Access.

Aucun train T ne doit improviser ces garanties dans Django ou le navigateur uniquement pour « cocher offline ».

## 9. M9 — Mature Hardening & Quality Gate

M9 prouve que l’ensemble effectivement intégré avant M8 fonctionne comme un système cohérent.

Le gate doit couvrir, selon les domaines présents dans `main` :

- E2E utilisateur : Discovery → Journey → Preparation → READY → Commerce/Payment éventuel → Access → Occurrence → Scan → Feedback/Proof/History ;
- E2E social ;
- E2E opérateur ;
- E2E Sharing P ;
- E2E Q/R/D/T si ces trains sont intégrés ;
- E2E interoperability M7 : Connection/scopes/action/revocation et Extension install/permission/action-event-UI/disable ;
- IDOR, permissions serveur, Mandates, uploads privés, credentials, tokens provider, scopes extensions, webhooks, CSP/XSS/cache privacy ;
- performance des projections critiques ;
- migrations base fraîche et historique, PostgreSQL, absence de migrations manquantes ;
- accessibilité des parcours critiques ;
- résilience providers/extensions/email/routing/signaux stale/retries/webhooks dupliqués.

M9 ne doit pas devenir un chantier de features opportunistes.

## 10. M10 — Closure, Production Readiness & Mobile Handoff

M10 produit la **Makolo Mature Core/Web Release Candidate**.

La vraie cible de production doit être lue dans les décisions/configurations réelles du projet. PythonAnywhere reste un environnement temporaire de développement/bêta.

M10 vérifie ce qui est réellement nécessaire autour de : deployment, environment configuration, static/media, database, workers/jobs, notifications, providers, observabilité, backups/restores, secrets et rollback.

Le handoff mobile documente les contrats backend/API réellement disponibles. Il inclut les capacités qui ont effectivement été intégrées avant le gate, notamment : authentication/session, Profile, Cockpit, Discovery, Social, Sharing, Activities, Journeys, Readiness, Forms, Resources, Presentation, Trust, Goals/Loyalty, Spatiotemporal, Access, Commerce/Payment, Connections et, lorsqu’ils sont intégrés, Q/R/D/T.

Principe de parity : aucune règle critique destinée au mobile ne doit n’exister que dans JavaScript ou un template web.

Après M10, la phrase suivante doit être vraie :

> **Makolo Mature est un produit complet backend + web + API même si aucune application mobile native n’existait jamais.**

## 11. Programme A — mobile natif

Le programme A commence seulement après M10.

### A1 — Application Makolo

Nouveau client natif : architecture, navigation, auth, API client, state management, secure storage, design system, deep links, erreurs et cache de base. La technologie mobile n’est pas fixée sans décision réelle.

A1 consomme les contrats Makolo ; il ne réimplémente pas Readiness, Trust, ranking, permissions, goal progress, Hazards, Payment state ou Access validity.

### A2 — Native Capabilities

Device registration/push, biométrie locale, caméra/scanner natif, share sheet, contacts consentis, localisation native, geofencing et intents/voice lorsque justifiés.

Biométrie et capacités device ne remplacent jamais l’autorisation serveur.

### A3 — Ambient Makolo

Widgets, lock screen, Live Activities/équivalents et notifications ambiantes affichent les projections Makolo — par exemple Readiness et M6 recommended departure — sans recalculer la vérité métier sur le téléphone.

### A4 — Operations & Offline R&D

Scanner offline, participant offline, background sync et résolution de conflits. Le backend reste source de vérité ; aucun `last write wins` aveugle pour Access ou Payment.

## 12. Capacités réservées au mobile

Restent hors M1–M10 lorsqu’elles dépendent réellement du device :

- application native iOS/Android ;
- push natif ;
- biométrie ;
- caméra/scanner natif optimisé ;
- contacts système ;
- share sheet native ;
- GPS background / geofencing natif ;
- Siri/App Intents/équivalents ;
- widgets home/lock screen ;
- Live Activities ;
- background tasks natifs ;
- secure offline storage mobile ;
- protocole scanner offline ;
- autres capabilities OS spécifiques.

Les décisions métier nécessaires doivent cependant exister côté backend avant le client qui les consomme.

## 13. Discipline de branches

Pour les grands streams :

```text
main vert
→ branche/train dédié
→ préflight ciblé
→ changements bornés
→ tests ciblés
→ PR/CI
→ correction cause racine
→ réconciliation main réel
→ merge vert
→ vérification post-merge
```

Les trains empilés comme P et Q ne mergent pas leurs checkpoints intermédiaires dans `main` : le checkpoint suivant part du précédent et le train complet est intégré une seule fois après réconciliation.

Pas de merge rouge, pas de test affaibli pour obtenir du vert, pas de duplication métier pour gagner du temps à court terme.

## 14. Sources canoniques associées

- [`makolo-domain-blueprint.md`](makolo-domain-blueprint.md) — frontières et invariants globaux ;
- [`strategic-action-roadmap.md`](strategic-action-roadmap.md) — 18 capacités et trains P→U ;
- [`readiness.md`](readiness.md) — Readiness dérivé ;
- [`forms-resources.md`](forms-resources.md) — Forms, Resources et frontière JourneyArtifact ;
- [`spatiotemporal-intelligence.md`](spatiotemporal-intelligence.md) — M6 et contrats provider-neutral existants ;
- [`domain-events-automation.md`](domain-events-automation.md) — Domain Events/Automation ;
- [`authorization-boundaries.md`](authorization-boundaries.md) — autorisation runtime ;
- `docs/operations-runbook.md` — exploitation réelle.