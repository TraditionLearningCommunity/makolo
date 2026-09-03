# Makolo — Mature Program Roadmap

> **Statut : canonique pour le séquencement de clôture Makolo Mature et le handoff mobile.** Ce document complète [`makolo-domain-blueprint.md`](makolo-domain-blueprint.md), [`strategic-action-roadmap.md`](strategic-action-roadmap.md) et [`mature-experience-principles.md`](mature-experience-principles.md). Le code, les migrations, les tests et l'état GitHub du `main` courant restent la vérité sur ce qui est effectivement livré.

## 1. Rôle de cette roadmap

Makolo possède désormais trois lectures complémentaires de sa suite :

- **stream M** : colonne vertébrale de maturité du produit, jusqu'au backend/web/API prêt pour le mobile ;
- **trains stratégiques P/Q/R/D/O/U** : capacités produit qui enrichissent le produit par composition ;
- **M8-PRE** : piste d'audit et de contrats d'expérience qui prépare M8 sans devenir un nouveau bounded context.

Ces lectures ne sont pas des files de tâches équivalentes ni un ordre alphabétique obligatoire.

Le stream M fixe les gates de maturité et le handoff vers le mobile. Les trains stratégiques stabilisent les capacités internes que ces gates doivent assembler. M8-PRE prépare les contrats d'expérience nécessaires à l'assemblage web.

Principe général :

> **Le backend Makolo décide. Le web présente et orchestre. Le mobile présente, orchestre et utilise les capacités du téléphone. Les providers externes exécutent leurs capacités spécialisées. Les extensions ajoutent des capacités sans prendre possession des domaines canoniques.**

## 2. État du stream M

Les responsabilités suivantes sont considérées comme déjà livrées et ne doivent pas être recréées dans les trains futurs :

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
- M5 porte le réseau social d'action et ses projections contextualisées ;
- M6 porte les projections spatio-temporelles, `Hazard` et `ActionAdvice` sans persister ETA, météo, trafic ou position utilisateur comme vérités métier.

## 3. Nommage des trains stratégiques

Les désignations canoniques sont :

```text
P — Sharing
Q — Capital d'action personnel
R — Préparation intelligente
D — Dossiers, Projets & Collaboration
O — Occurrence Operations
U — Intelligence cumulative
```

`S` n'est plus utilisé pour Dossier/Projet : le dépôt possède déjà le programme Subscription **S1→S6**.

`T` n'est plus utilisé pour Occurrence Operations : le projet possède déjà un historique de tâches Services en série T.

Les anciennes mentions documentaires `P→U`, `S — Objectifs & collaboration` ou `T — Occurrence Operations` sont des désignations historiques. Elles ne doivent pas conduire à créer un nouveau train S ou T concurrent des programmes existants.

## 4. Structure de clôture Mature

La fermeture finale reste :

```text
M7 — Interoperability, Connections & Extension Platform
M8 — Makolo Mature Web Experience
M9 — Mature Hardening & Quality Gate
M10 — Mature Closure, Production Readiness & Mobile Handoff
A — Mobile natif
```

Mais **M7 n'est plus le prochain chantier obligatoire immédiatement après M6**.

M7 doit venir à la convergence, lorsque les grandes capacités internes que Makolo veut exposer sont suffisamment stables.

La structure de référence devient :

```text
M1–M6 + P
     │
     ├───────────────┐
     ▼               ▼
Q — Capital        D — Dossiers /
personnel          Projets / Collaboration
     │               │
     ▼               ▼
R — Préparation    O — Occurrence
intelligente       Operations
     │               │
     └───────┬───────┘
             │
      M8-PRE │ audit/contrats d'expérience en parallèle
             │
             ▼
            M7
             ↓
            M8
             ↓
            M9
             ↓
           M10
             ↓
         A1 → A4

U — Intelligence cumulative : hors chemin critique.
```

Cette structure autorise un **vrai parallélisme de deux lignes métier**, comme deux développeurs travaillant sur des responsabilités distinctes :

- ligne A : `Q → R` ;
- ligne B : `D → O`.

M8-PRE peut être audité en parallèle. Les gros changements frontend globaux restent cependant réservés à M8.

## 5. Fenêtre de coordination actuelle

Au moment de la décision qui a produit cette version de la roadmap :

- P est intégré dans `main` ;
- Q poursuit sa fin de train autonome ;
- D a commencé depuis le `main` sans dépendre de Q ;
- R peut être audité et conçu pendant Q, mais son implémentation finale attend les contrats Q stabilisés ;
- O peut être audité tôt, mais son implémentation doit bénéficier des contrats D suffisamment stabilisés autour d'acteur, contexte d'autorité, bénéficiaire et collaboration ;
- M8-PRE peut démarrer par audit sans ouvrir un chantier média autonome.

Cet état est un instantané de coordination : GitHub actuel reste la vérité pour savoir ce qui est réellement ouvert, mergé ou validé.

### Pourquoi Q et D peuvent avancer en parallèle

Q possède principalement :

- Bibliothèque / Personal Assets ;
- reuse vers/depuis JourneyArtifact ;
- Action Memory ;
- fondation Trusted Reuse.

D possède principalement :

- Dossier ;
- relations inter-Journeys ;
- collaboration d'objectif ;
- Collective Readiness ;
- Projet et sa frontière avec Goals.

D ne doit pas dépendre d'une branche Q non mergée et Q ne doit pas importer D.

Les deux lignes doivent éviter de refaire simultanément `/me/`, la navigation globale ou une large couche de templates Journey. M8 possède l'assemblage transversal.

### Pourquoi R attend Q pour son implémentation finale

Prepared Start doit pouvoir distinguer :

```text
je possède quelque chose
        ≠
Makolo le retrouve
        ≠
ce Requirement l'accepte
```

R dépend donc matériellement de Bibliothèque, Action Memory et Trusted Reuse stabilisés par Q.

L'audit R peut avancer en parallèle pour définir contracts, selectors, read models, events, permissions et critères d'acceptation.

### Pourquoi O suit D par défaut

O dépend principalement d'Activity/Occurrence, Access/AccessUse, Capacity, Scanner, Assignments/Mandates, Analytics et M6 ; il n'a pas de dépendance forte sur Q/R.

Mais D doit clarifier suffisamment le contexte transversal :

- acteur ;
- autorité personnelle ou d'Espace ;
- bénéficiaire ;
- responsabilités/collaboration.

O peut ensuite projeter Occurrence Live et les opérations sans inventer un second modèle mental des rôles.

## 6. R — Préparation intelligente

R construit :

- Prepared Start ;
- Proactive Preparation ;
- contrats de priorité/NextAction nécessaires à l'Accueil contextuel.

R réutilise :

- M1 Readiness ;
- Q pour le capital personnel et Trusted Reuse ;
- Requirements ;
- Trust/Proof ;
- Domain Events ;
- Automation/Autopilot ;
- Notifications ;
- M6 lorsqu'un fait temporel/spatial change la prochaine action.

R ne recrée ni scheduler, ni `ReadinessState`, ni Requirement engine, ni Cockpit persistant.

**R possède les règles/projections de préparation ; M8 possède leur composition web.**

## 7. D — Dossiers, Projets & Collaboration

D construit la capacité de comprendre ce que plusieurs personnes essaient d'accomplir ensemble sans écraser les frontières Journey.

Dossier est un objectif actif pouvant composer plusieurs Journeys, personnes et bénéficiaires.

Projet est un horizon plus durable pouvant regrouper plusieurs Dossiers ; il ne doit pas devenir un Trello/Notion bis et sa frontière avec `goals.PersonalGoal` doit être auditée avant création de modèle.

D conserve :

- Journey comme démarche individuelle ;
- JourneyStep comme action de cette démarche ;
- Assignment comme responsabilité ;
- Mandate comme autorité ;
- Payment, Access, Capacity, Artifact et Requirement dans leurs domaines propriétaires ;
- Readiness comme projection dérivée.

Invariant sécurité majeur : appartenir au même Dossier ne donne pas automatiquement le droit de lire toutes les Journeys qui le composent.

D doit être stabilisé avant M8 si Dossiers/Projets doivent façonner la navigation Mature.

## 8. O — Occurrence Operations

O couvre les vérités/projections backend et web nécessaires à :

- Operational Readiness ;
- Occurrence Live ;
- Placement ;
- Checkpoints/Flow ;
- Live Queue lorsque les données permettent une estimation légitime ;
- contrat Offline Action Pack côté backend/web.

M6 reste propriétaire du contexte spatio-temporel et des Hazards. Access reste le droit. AccessUse reste l'observation du passage. Capacity reste le nombre. Placement répond à « où ? ».

Occurrence Live compose les domaines existants ; il ne devient pas une seconde base opérationnelle.

### Frontière O / mobile offline

Avant mobile, O peut définir :

- quelles données sont nécessaires ;
- leur provenance ;
- sensibilité ;
- expiration ;
- politique de révocation ;
- contrat de synchronisation/lecture lorsque nécessaire.

Restent explicitement au programme mobile A4 :

- secure local storage natif ;
- background sync OS ;
- vrai scanner offline ;
- réconciliation multi-device ;
- replay/double-use ;
- clock skew ;
- conflits ;
- protocole offline Access.

O ne doit pas improviser ces garanties dans Django ou le navigateur uniquement pour « cocher offline ».

## 9. M8-PRE — préparation des contrats d'expérience

M8-PRE est une piste de préparation, **pas un nouveau train métier** et pas un bounded context.

Sa doctrine complète est dans [`mature-experience-principles.md`](mature-experience-principles.md).

### M8-P0 — Experience contracts & audit

Auditer M3 Presentation, Discovery, Event `cover_image`, Activity/Occurrence, ActivityResource, storage, uploads/validators, M5 Contribution, Sharing, M6 et le frontend actuel.

### M8-P1 — Activity-first representation / media foundation si gap confirmé

Le code sait déjà afficher une image de découverte via la verticale Event. Cela ne fait pas d'Event le propriétaire générique de la représentation Makolo.

La direction est Activity-first. Un mécanisme média transversal n'est créé que si l'audit démontre qu'une relation/projection M3 ne suffit pas.

Principe : **No Orphan Media**.

### M8-P2 — Bounded Exploration

Discovery peut offrir un scroll naturel sans créer un corpus artificiellement infini.

Les candidats et reasons restent explicables. Lorsqu'un cercle pertinent est épuisé, Makolo peut dire qu'il est terminé et proposer explicitement d'élargir zone, période ou contexte.

### M8-P3 — Action Rituals

Les situations humaines suivantes deviennent des scénarios d'acceptation transversaux :

- Aujourd'hui ;
- On fait quoi ? ;
- Est-ce que tout est prêt ? ;
- Il est temps d'y aller ;
- Autour de moi maintenant ;
- On fait ça ? ;
- Une possibilité vient d'apparaître ;
- J'ai accompli quelque chose.

M8-PRE peut être audité pendant Q/D/R. Une petite fondation technique réellement isolée peut être livrée avant M8 si l'audit la justifie, mais les gros redesigns Accueil/Discover restent dans M8.

## 10. M7 — Interoperability, Connections & Extension Platform

M7 est le dernier grand chantier architectural de plateforme **après stabilisation des grandes capacités internes R et O** et avant l'assemblage UX Mature.

Question :

> **Comment Makolo coopère-t-il avec des applications, comptes, providers et extensions externes sans perdre la propriété de ses domaines canoniques ?**

Le déplacement de M7 après R/O est intentionnel : il vaut mieux exposer des capabilities, Actions et Events internes déjà mûrs que figer trop tôt une plateforme d'interopérabilité pendant que Prepared Start, Dossier ou Occurrence Operations changent encore le modèle mental du produit.

### Provider Registry

Le cœur demande une capability stable, pas un fournisseur codé partout :

```text
Capability → Provider → Adapter
```

Exemples de familles possibles lorsque le besoin réel existe : navigation, routing, traffic, weather, calendar, email, source-control, export et external actions.

M7 n'invente aucun fournisseur commercial, compte ou secret qui n'existe pas dans une décision réelle du projet.

### Connections

Une `Connection` représente l'autorisation explicite donnée par un Profile ou un Space à Makolo pour coopérer avec un service externe.

Installed/available ne signifie jamais authorized :

```text
capability disponible
+ Connection
+ scopes
+ Permission/Mandate
+ contexte autorisé
= action exécutable
```

Les credentials externes ne doivent pas apparaître dans logs, templates, API publique ou configuration d'extension visible.

### Action Registry

Les actions externes passent par un catalogue contrôlé : validation, autorisation, exécution et audit utile.

Une extension/provider n'obtient jamais l'ORM Makolo, les credentials DB, le raw SQL ou le filesystem interne.

### Event subscriptions et webhooks

Les intégrations peuvent consommer des Domain Events autorisés et échanger par webhook lorsque pertinent, avec scopes, authentification/signature, idempotence, retry borné et observabilité.

Un webhook entrant ne modifie jamais directement une vérité métier : il passe par le service du domaine propriétaire.

### Extension Platform

Makolo doit rester un produit complet sans plugin.

Une extension ajoute une capacité ; elle ne déplace pas le cœur Makolo hors de Makolo Base.

Le contrat d'exécution reste :

```text
extension installée
+ active
+ entitlement éventuel
+ permission utilisateur
+ Connection éventuelle
+ contexte autorisé
= capacité exécutable
```

Les extensions utilisent APIs, Actions, Events, Webhooks et Scoped Data. Les UI contributions sont bornées à des slots contrôlés ; une extension ne remplace pas arbitrairement toute l'interface.

M7 ne construit pas : marketplace commerciale, billing d'extensions, revenue sharing, runtime mobile de plugins, Python/JavaScript arbitraire ou accès DB direct.

## 11. M8 — Makolo Mature Web Experience

M8 assemble le produit ; il ne crée pas un nouveau domaine métier.

Son principe d'expérience est :

> **Makolo Mature doit pouvoir être utile sans ressembler à un outil qu'il faut se forcer à utiliser.**

M8 doit rendre Makolo aussi naturel à explorer que rassurant à préparer et évident à utiliser lorsque l'action commence.

### Accueil `/me/`

Question :

> **Qu'est-ce qui compte maintenant ?**

L'Accueil reste une projection privée, pas `Dashboard`, `DashboardItem`, `DashboardState` ou `HomeFeedItem` comme nouvelles vérités.

Il compose notamment :

- NextAction / Readiness / Forms / Resources / Requirements / Payment / Access pour une Journey active ;
- Q/R pour Prepared Start et la préparation intelligente ;
- D pour Dossiers/Projets et responsabilités ;
- M6 Temporal/Spatial/Mobility/Hazards lorsque l'Occurrence devient imminente ;
- O pour l'état opérationnel Jour J ;
- Notifications utiles et facts déjà autorisés.

L'Accueil doit pouvoir conclure : **Tout est en ordre. ✓**

Il n'est pas le feed d'exploration Makolo.

### Discover

Question :

> **Qu'est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?**

Discover est l'espace volontaire d'exploration : visuel, multimédia lorsque légitime, cartographique, sensoriel et social sans économie autonome du contenu.

M8 applique :

- Sensory Discovery ;
- représentation Activity-first ;
- No Orphan Media ;
- Bounded Exploration ;
- reasons explicables ;
- pas d'infini artificiel.

M5 reste la source des contrats sociaux/action existants ; M8 ne crée pas un second réseau social ni un nouveau `FeedItem` persistant.

### Activity

Activity reste le noyau. Event, Service, Transport et autres verticales peuvent proposer des représentations adaptées sans faire d'Event le propriétaire générique de l'image/vidéo/audio.

Les médias représentent les faits ; ils ne deviennent pas propriétaires de date, capacité, prix, Access ou disponibilité.

### Journey Command Center

M8 assemble les phases BEFORE / READY / ARRIVAL / AFTER autour des domaines canoniques sans posséder leurs faits.

Le rituel **Est-ce que tout est prêt ?** doit être servi sans que l'utilisateur connaisse la terminologie interne Readiness/Requirement.

### Occurrence imminente

Le rituel **Il est temps d'y aller** compose M6 + O + Access + Placement/Flow/Queue lorsqu'ils existent.

L'Occurrence imminente ne doit plus ressembler à une fiche statique si le backend possède déjà les informations nécessaires à l'action.

### Réseau et Space Consoles

M8 harmonise Groups, Contributions M5, Sharing P, Opportunities, Recommendations et les consoles Space sans transformer Discovery en liste de bounded contexts.

Les Space Consoles composent Team, Mandates, Forms, Resources, Presentation, Capacity, Commerce, Payments, Access, Operations, Trust, CRM, Automation, Analytics, Connections et Extensions avec les permissions serveur existantes.

### Responsive web

Le web desktop, tablette et navigateur mobile doit rester sérieusement utilisable même sans application native.

### Gate produit M8

M8 échoue si :

- Discover reste essentiellement textuel ;
- Activity est riche architecturalement mais pauvre visuellement ;
- l'Accueil ressemble à un ERP/dashboard générique ;
- exploration et accomplissement sont confondus ;
- Event reste implicitement propriétaire de la représentation générique ;
- des médias orphelins deviennent le centre du produit ;
- Discovery doit inventer artificiellement du contenu pour ne jamais se terminer ;
- l'Occurrence imminente reste une fiche statique alors que les faits d'action existent.

## 12. U — Intelligence cumulative hors chemin critique

`U — Intelligence cumulative` ne bloque ni M7, ni M8, ni M10, ni le programme mobile.

Proven Paths et l'intelligence cumulative doivent disposer d'assez de données réelles avant de tirer des conclusions crédibles.

Les trains Q/R/D/O et M8 doivent toutefois instrumenter correctement les faits défendables : Domain Events, timestamps, causes, blockers, transitions, outcomes et analytics privacy-safe.

U pourra ensuite apprendre de l'action réelle plutôt que de données principalement démo.

Watch time, likes, views et profondeur de scroll ne deviennent pas les signaux défendables centraux de U.

## 13. M9 — Mature Hardening & Quality Gate

M9 prouve que l'ensemble intégré avant M8 fonctionne comme un système cohérent.

Le gate doit couvrir, selon les domaines présents dans `main` :

- E2E utilisateur : Discovery → Activity → Journey/Dossier → Preparation → READY → Commerce/Payment éventuel → Access → Occurrence → Scan → Feedback/Proof/History ;
- E2E social/Sharing ;
- E2E opérateur ;
- E2E Q/R/D/O lorsqu'ils sont intégrés ;
- E2E M7 : Connection/scopes/action/revocation et Extension install/permission/action-event-UI/disable ;
- scénarios d'expérience M8 : Aujourd'hui, On fait quoi ?, Est-ce que tout est prêt ?, Il est temps d'y aller ;
- IDOR, permissions serveur, Mandates, uploads privés, media visibility, credentials, tokens provider, scopes extensions, webhooks, CSP/XSS/cache privacy ;
- performance des projections critiques ;
- migrations base fraîche et historique, PostgreSQL, absence de migrations manquantes ;
- accessibilité des parcours critiques, images, vidéo/audio si introduits, captions/alt text selon le contrat réel ;
- résilience providers/extensions/email/routing/signaux stale/retries/webhooks dupliqués.

M9 ne doit pas devenir un chantier de features opportunistes.

## 14. M10 — Closure, Production Readiness & Mobile Handoff

M10 produit la **Makolo Mature Core/Web Release Candidate**.

La vraie cible de production doit être lue dans les décisions/configurations réelles du projet. PythonAnywhere reste un environnement temporaire de développement/bêta.

M10 vérifie ce qui est réellement nécessaire autour de : deployment, environment configuration, static/media, database, workers/jobs, notifications, providers, observabilité, backups/restores, secrets et rollback.

Le handoff mobile documente les contrats backend/API réellement disponibles. Il inclut les capacités effectivement intégrées, notamment authentication/session, Profile, Accueil, Discover, Social, Sharing, Activities, Journeys, Dossiers/Projets si présents, Readiness, Forms, Resources, Presentation, Trust, Goals/Loyalty, Spatiotemporal, Access, Commerce/Payment, Connections et les contrats Q/R/D/O effectivement livrés.

Principe de parity : aucune règle critique destinée au mobile ne doit n'exister que dans JavaScript ou un template web.

Après M10, la phrase suivante doit être vraie :

> **Makolo Mature est un produit complet backend + web + API même si aucune application mobile native n'existait jamais.**

## 15. Programme A — mobile natif

Le programme A commence seulement après M10.

### A1 — Application Makolo

Nouveau client natif : architecture, navigation, auth, API client, state management, secure storage, design system, deep links, erreurs et cache de base. La technologie mobile n'est pas fixée sans décision réelle.

A1 consomme les contrats Makolo ; il ne réimplémente pas Readiness, Trust, ranking, permissions, goal progress, Hazards, Payment state ou Access validity.

### A2 — Native Capabilities

Device registration/push, biométrie locale, caméra/scanner natif, share sheet, contacts consentis, localisation native, geofencing et intents/voice lorsque justifiés.

Biométrie et capacités device ne remplacent jamais l'autorisation serveur.

### A3 — Ambient Makolo

Widgets, lock screen, Live Activities/équivalents et notifications ambiantes affichent les projections Makolo — par exemple Readiness, NextAction, départ recommandé et état d'Occurrence — sans recalculer la vérité métier sur le téléphone.

### A4 — Operations & Offline R&D

Scanner offline, participant offline, background sync et résolution de conflits. Le backend reste source de vérité ; aucun `last write wins` aveugle pour Access ou Payment.

Le mobile amplifie les rituels existants :

- Aujourd'hui → widget ;
- Il est temps d'y aller → push / Live Activity ;
- Autour de moi → localisation ponctuelle ;
- On fait ça ? → share sheet ;
- document → caméra ;
- Occurrence Live → haptique/offline/push.

## 16. Capacités réservées au mobile

Restent hors M1–M10 lorsqu'elles dépendent réellement du device :

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

## 17. Discipline de branches

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

Les trains empilés comme Q — et D si son pilote retient cette stratégie — ne mergent pas nécessairement leurs checkpoints intermédiaires dans `main` : le checkpoint suivant part du précédent et le train complet est intégré une seule fois après réconciliation.

Les trains parallèles doivent garder des surfaces propriétaires claires et éviter de reconstruire simultanément le frontend global.

Pas de merge rouge, pas de test affaibli pour obtenir du vert, pas de duplication métier pour gagner du temps à court terme.

## 18. Sources canoniques associées

- [`makolo-domain-blueprint.md`](makolo-domain-blueprint.md) — frontières et invariants globaux ;
- [`strategic-action-roadmap.md`](strategic-action-roadmap.md) — 18 capacités et trains P/Q/R/D/O/U ;
- [`mature-experience-principles.md`](mature-experience-principles.md) — M8-PRE, Accueil/Discover, Sensory Discovery, No Orphan Media, Bounded Exploration et Action Rituals ;
- [`readiness.md`](readiness.md) — Readiness dérivé ;
- [`forms-resources.md`](forms-resources.md) — Forms, Resources et frontière JourneyArtifact ;
- [`social-action-network.md`](social-action-network.md) — M5, Contribution No Orphan Content et Action Stream borné ;
- [`spatiotemporal-intelligence.md`](spatiotemporal-intelligence.md) — M6 et contrats provider-neutral existants ;
- [`domain-events-automation.md`](domain-events-automation.md) — Domain Events/Automation ;
- [`authorization-boundaries.md`](authorization-boundaries.md) — autorisation runtime ;
- `docs/operations-runbook.md` — exploitation réelle.