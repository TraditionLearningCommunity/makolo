# Makolo Platform — Architecture & expérience opérateur consolidées
## Contrat UX, autorité, surfaces, opérations, gouvernance et système

**Date :** 2026-10-08  
**Statut :** contrat consolidé de référence pour la cible Makolo Platform  
**Base runtime vérifiée :** `main@52eced16a35d779f98eb8d43bbea405fd7f7b4b0`  
**État GitHub vérifié :** PR ouverte `#501 — feat: close Moi and Nous mature surfaces` au moment de l’étude  
**Portée :** expérience opérateur interne Makolo, principalement Web/desktop responsive  
**Hors portée :** redesign de l’application Makolo Profile/Space, remplacement complet de Django Admin, nouvelle application mobile Platform  
**Promesse opérateur :** **Faire fonctionner Makolo sans contourner Makolo.**

---

# 0. Décision structurante

Makolo possède trois niveaux distincts :

```text
MAKOLO
→ expérience Profile / Space
→ vivre, découvrir, préparer, accomplir, opérer une réalité métier

MAKOLO PLATFORM
→ expérience opérateur interne
→ superviser, investiguer, gouverner, modérer et maintenir Makolo

DJANGO ADMIN
→ outil technique profond
→ inspecter / maintenir directement des objets Django lorsque cela reste justifié
```

Ils utilisent le même backend canonique.

Ils ne doivent pas devenir trois sources de vérité.

---

# 1. Platform n’est pas un Space

Invariant :

```text
Platform
≠ Space
```

Platform ne possède pas :

- Activity ;
- Occurrence ;
- Journey ;
- Access ;
- Payment ;
- Capacity ;
- Profile ;
- Space ;
- Trust ;
- Subscription ;
- Recognition ;
- Opportunity.

Ces domaines restent propriétaires de leurs vérités.

---

# 2. Platform n’est pas un acteur métier global

L’opérateur reste un Profile humain authentifié.

Conceptuellement :

```text
VIEWER / ACTOR OF PLATFORM ACTION
→ Profile humain

OPERATING CONTEXT
→ Platform

TARGET
→ Profile / Space / Activity / Payment / etc.
```

Exemple :

```text
Jean suspend Mulykap via Makolo Platform
```

La vérité d’audit doit rester :

```text
actor = Jean
target = Mulykap
action = suspend
reason = ...
```

et non :

```text
actor = Platform
```

---

# 3. Platform Context ≠ Actor Context Space

Dans Makolo utilisateur :

```text
Agir comme
→ Moi / Space
```

Dans Platform :

```text
opérateur
→ agit avec autorité platform.*
→ sur une cible explicite
```

Platform ne doit jamais utiliser un Space comme masque pour une action globale.

---

# 4. Autorité Platform existante

Le runtime courant possède déjà des Permissions globales :

```text
platform.manage
platform.trust.review

platform.subscriptions.catalog.view
platform.subscriptions.catalog.manage
platform.subscriptions.view
platform.subscriptions.manage
platform.subscriptions.grants.manage
platform.subscriptions.reviews.manage

platform.recognition.view
platform.recognition.policy.manage
platform.recognition.policy.publish
platform.recognition.economy.manage
platform.recognition.achievements.manage
platform.recognition.audit.view

opportunities.manage
opportunities.review_submissions
opportunities.sources_verify
opportunities.merge
```

Ces permissions sont une base réelle.

Platform doit les consommer.

Elle ne doit pas recréer un deuxième système RBAC.

---

# 5. Rôles existants

Le runtime possède notamment :

```text
makolo-platform-admin
opportunity-curator
```

Les personas UX sont des projections de Permission sets.

Ils ne justifient pas automatiquement de nouveaux modèles Role.

---

# 6. `is_staff` ≠ autorité Platform

Invariant majeur :

```text
Django is_staff
≠ Platform Permission
```

Les domaines Makolo doivent continuer à utiliser les contrats d’autorisation canoniques.

Django Admin peut exiger `is_staff` pour son accès technique.

Platform doit exiger les Permissions Platform appropriées.

---

# 7. `is_superuser` ≠ design produit

Un superuser peut conserver un rôle de maintenance exceptionnelle.

Mais Platform ne doit pas être conçue en supposant :

```text
tous les opérateurs = superusers
```

Les permissions fines existantes doivent rester visibles dans l’architecture.

---

# 8. Pourquoi Platform existe

Platform répond à des questions qu’un utilisateur Makolo ne doit pas avoir à traiter :

> **Est-ce que Makolo fonctionne correctement ?**

> **Quelle situation nécessite une intervention opérateur ?**

> **Pourquoi cette personne / ce Space rencontre-t-il ce problème ?**

> **Quelle vérité propriétaire dois-je inspecter ?**

> **Ai-je l’autorité d’intervenir ?**

> **Quelle action est sûre et auditée ?**

> **Le système s’est-il réellement rétabli ?**

---

# 9. Platform ≠ application utilisateur

Les objectifs diffèrent.

Makolo Profile/Space optimise :

```text
accomplissement humain
+
réduction de friction
+
action réelle
```

Platform optimise :

```text
diagnostic
+
gouvernance
+
intégrité
+
récupération
+
contrôle explicable
```

---

# 10. Platform ≠ Django Admin

Django Admin pense naturellement :

```text
App
→ Model
→ Row
→ Field
→ CRUD
```

Platform pense :

```text
Situation opérateur
→ comprendre
→ relier les réalités
→ vérifier authority
→ agir via owner
→ vérifier la conséquence
→ audit
```

---

# 11. Platform ≠ ERP interne générique

Platform ne doit pas devenir :

- task manager ;
- Jira clone ;
- CRM interne ;
- BI générique ;
- SIEM complet ;
- observability SaaS clone ;
- CMS ;
- data warehouse UI ;
- shell de tous les modèles Django.

---

# 12. Platform est capability-driven

Le runtime possède déjà :

```text
GET platform/capabilities
```

avec des modules calculés selon Permissions.

Cette idée doit devenir le socle du shell :

```text
permission
→ capability
→ module visible
```

et non :

```text
menu complet
→ 403 après clic
```

---

# 13. Modules réellement démontrés dans le runtime

La projection Platform courante expose ou relie déjà :

```text
operations
trust_review
subscriptions
recognition_governance
opportunity_curation
interoperability
```

Ce sont les premières briques de la Platform cible.

---

# 14. Frontière de portée

Le payload courant affirme :

```text
space_modules_included = false
personal_modules_included = false
```

Cet invariant est important :

```text
Platform
≠ agrégation de tous les menus Space + Personal
```

---

# 15. Shell cible

Makolo Platform doit avoir un shell distinct.

Candidate :

```text
┌──────────────────────────────────────────────────────────────┐
│ Makolo Platform     Recherche opérateur        [Operator]    │
├───────────────┬──────────────────────────────────────────────┤
│ Vue d’ensemble│                                              │
│ Investiguer   │                 CONTENT                      │
│ Opérations    │                                              │
│ Confiance     │                                              │
│ Curation      │                                              │
│ Gouvernance   │                                              │
│ Système       │                                              │
└───────────────┴──────────────────────────────────────────────┘
```

Les items invisibles par Permission disparaissent.

---

# 16. Navigation candidate

## Vue d’ensemble

Question :

> **Qu’est-ce qui mérite l’attention de la plateforme ?**

## Investiguer

Question :

> **Que se passe-t-il réellement pour cette personne, ce Space ou cette opération ?**

## Opérations

Question :

> **Quel incident, backlog, worker ou problème opérationnel faut-il traiter ?**

## Confiance

Question :

> **Quelle vérification, plainte, preuve ou dispute doit être revue ?**

## Curation

Question :

> **Quelle connaissance ou possibilité doit être revue, sourcée ou réconciliée ?**

## Gouvernance

Question :

> **Quelles politiques, abonnements, droits contractuels ou économies doivent être administrés ?**

## Système

Question :

> **Les mécanismes techniques de Makolo fonctionnent-ils et sont-ils correctement connectés ?**

Ces catégories sont Presentation.

Elles ne créent aucun bounded context.

---

# 17. Pourquoi pas `Maintenant`

Platform peut avoir une vue d’attention actuelle.

Mais elle ne doit pas réutiliser automatiquement le mot `Maintenant` comme si l’opérateur se trouvait dans le shell Makolo utilisateur.

La distinction cognitive doit être visible.

---

# 18. Pourquoi pas Makolo Mark central

Le Makolo Mark appartient à l’expérience d’intake/orchestration Profile/Space.

Platform peut avoir :

- recherche ;
- commande opérateur ;
- assistance ;
- outils contextualisés.

Mais il ne doit pas avoir un Mark central uniquement pour conserver la symétrie visuelle.

---

# 19. Identité visuelle

Décision :

> **Platform doit être immédiatement identifiable comme hors de l’expérience Makolo utilisateur.**

Base :

```text
#0F172A
→ fond principal sombre

#2B176E
→ surfaces / profondeur violette

#5232DB
→ action / focus

#FF704D
→ attention forte lorsque sémantiquement correcte

#FAF7F5
→ texte / surfaces claires ponctuelles
```

---

# 20. Noir + violet

L’idée noir + violet est retenue comme direction cognitive.

Mais :

```text
dark
≠ cyberpunk
≠ terminal hacker
≠ décor technologique
```

Le but est :

```text
institutionnel
+
concentré
+
opérationnel
+
distinct
```

---

# 21. Continuité de marque

Platform reste Makolo.

Conserver :

- Makolo Mark officiel ;
- typographie / langage Makolo ;
- violet canonique ;
- qualité de motion ;
- accessibilité.

Mais afficher explicitement :

```text
Makolo Platform
```

pour éviter la confusion.

---

# 22. Le Mark devient marque, pas action

Dans Platform :

```text
Makolo Mark
→ identité de marque
```

Dans Makolo utilisateur :

```text
Makolo Mark
→ identité + action centrale
```

Ne pas confondre ces rôles.

---

# 23. Densité

Platform peut être plus dense que Makolo.

Mais :

```text
professionnel
≠ tout afficher
```

Densité candidate :

```text
Vue d’ensemble   moyenne-élevée
Investiguer      élevée structurée
Opérations       élevée
Confiance        moyenne-élevée
Curation         élevée structurée
Gouvernance      élevée structurée
Système          élevée / technique
```

---

# 24. Progressive disclosure

N1 explique :

- état ;
- queue ;
- problème ;
- cible ;
- prochaine action.

N2 explique :

- contexte ;
- owners ;
- relations ;
- preuves ;
- historique.

N3 peut exposer :

- IDs ;
- payloads sûrs ;
- before/after ;
- logs ;
- détails techniques.

---

# 25. Vue d’ensemble

La Vue d’ensemble est le point d’entrée Platform.

Elle ne doit pas être un dashboard vanity.

Elle doit répondre :

```text
CRITIQUE
→ qu’est-ce qui peut casser l’action réelle ?

À TRAITER
→ quelles files attendent une décision ?

SYSTÈME
→ quels mécanismes sont dégradés ?

RÉCEMMENT
→ quelles interventions significatives ont eu lieu ?
```

---

# 26. Runtime Operations Overview

Le runtime actuel possède déjà :

```text
health
metrics
signals
organization_queue
incidents
workers
recent_audit
```

C’est une excellente fondation de Vue d’ensemble.

---

# 27. Signals-first

Préférer :

> **Un worker déclaré actif n’émet plus de heartbeat.**

à :

```text
stale_workers = 1
```

La métrique reste en support.

---

# 28. Health

Le runtime dérive actuellement :

```text
healthy
degraded
critical
```

Platform peut utiliser cette synthèse.

Elle ne doit pas devenir un score opaque.

---

# 29. Santé globale ≠ vérité de tous les domaines

`healthy` signifie seulement :

```text
aucun signal critique/haut selon la couverture actuelle
```

Pas :

```text
tout Makolo fonctionne parfaitement
```

Coverage doit rester compréhensible.

---

# 30. Files opératoires actuelles

Le runtime sait déjà signaler notamment :

- incidents critiques ;
- webhooks de paiement invalides ;
- webhooks bloqués ;
- taux d’échec paiement ;
- paiements bloqués ;
- remboursements échoués ;
- scans rejetés / invalides ;
- automation failures ;
- CRM actions en retard ;
- notification deliveries en échec ;
- backlog notifications ;
- workers sans heartbeat ;
- organisations à vérifier.

Ces signaux doivent être réutilisés.

---

# 31. Investiguer

`Investiguer` est la surface qui manque le plus aujourd’hui comme expérience unifiée.

Elle répond :

> **Je connais une personne, un Space, une référence ou un problème : montre-moi la réalité reliée sans me faire naviguer modèle par modèle.**

---

# 32. Investiguer ≠ nouveau domaine

L’unité UX est une **Investigation operator projection**.

Pas de modèle `Investigation` obligatoire.

Elle peut être éphémère.

---

# 33. Search Platform

Recherche globale opérateur candidate :

```text
Profile
Space
Activity
Occurrence
Journey
Dossier
Order
Payment
Access
Trust case
Subscription
Opportunity
Incident
...
```

uniquement si les owners possèdent un selector sûr.

---

# 34. Search Platform ≠ Search Makolo

La Search Platform :

- est interne ;
- peut utiliser des identifiants techniques en profondeur ;
- a des permissions globales spécifiques ;
- peut diagnostiquer.

Elle ne doit pas être réutilisée directement comme Search utilisateur.

---

# 35. PII dans Search

Rechercher par PII ne doit être possible que si :

- cas réel ;
- permission adaptée ;
- journalisation appropriée ;
- affichage minimal.

Ne jamais exposer des listes de PII par défaut.

---

# 36. Investigation bundle

Une investigation peut composer :

```text
TARGET
→ Profile / Space / Activity / ...

RELATIONS
→ owners liés

CURRENT STATE
→ état owner-backed

RECENT SIGNIFICANT EVENTS
→ audit / domain history

RISKS
→ incidents / trust / payment / sync

AVAILABLE ACTIONS
→ owner services only
```

---

# 37. No giant JSON first

Le détail opérateur commence par le sens.

Le raw payload est profondeur technique.

---

# 38. No arbitrary edit

Depuis Investiguer :

```text
modifier directement status = X
```

est interdit si un service métier existe.

Toujours préférer :

```text
action nommée
→ validation
→ service owner
→ audit
```

---

# 39. Profile investigation

Peut permettre de comprendre :

- identité minimale nécessaire ;
- subscriptions ;
- Journeys visibles selon authority Platform réelle ;
- Trust cases ;
- Access concernés ;
- incidents ;
- relations utiles au cas.

Il ne devient pas une page “voir toute la vie de cette personne”.

---

# 40. Space investigation

Peut composer :

- identité ;
- lifecycle ;
- Trust ;
- Subscription ;
- Activities ;
- incidents ;
- moderation ;
- platform interoperability ;
- permissions pertinentes ;
- recent operator actions.

---

# 41. Activity investigation

Peut composer :

- owner Space ;
- Occurrences ;
- Access/Capacity ;
- Payments/Commerce ;
- Operations incidents ;
- visibility/moderation ;
- related Journey counts si autorisés.

---

# 42. Payment investigation

Doit préserver :

```text
Payment
≠ Order
≠ fulfillment
```

Ne pas afficher un paiement réussi comme succès métier final.

---

# 43. Access investigation

Préserver :

```text
Access
≠ AccessCredential
≠ AccessUse
```

Ne jamais exposer un secret credential complet dans une vue générale.

---

# 44. Opérations

Le runtime possède déjà un vrai Operations Center backend.

Il couvre notamment :

```text
overview
organizations
organization lifecycle decisions
events
event moderation
incidents
moderation cases
worker health
audit
```

Platform doit l’absorber visuellement.

---

# 45. Operations ne devient pas tout Platform

`platform.manage` est actuellement large.

Mais conceptuellement :

```text
Operations
≠ Trust Review
≠ Subscription Governance
≠ Recognition Governance
≠ Opportunity Curation
```

La Platform les compose sans les fusionner.

---

# 46. Incidents

Incident N1 :

- titre ;
- sévérité ;
- état ;
- owner/context ;
- âge ;
- assignee ;
- prochain geste.

N2 :

- symptômes ;
- impacts ;
- timeline ;
- relations ;
- resolution ;
- audit.

---

# 47. Incident ≠ ticket support générique

`OperationsIncident` est un owner technique/opérationnel.

Il ne doit pas devenir automatiquement un modèle SupportCase universel.

---

# 48. Organisation lifecycle

Actions réelles déjà présentes :

```text
suspend
archive
restore
```

via services owner.

Platform doit exiger :

- cible ;
- conséquence ;
- reason ;
- confirmation ;
- audit.

---

# 49. Modération Event

Actions actuelles :

```text
unlist
private
cancel
restore_public
```

Le contrat Platform doit les présenter avec leur conséquence réelle.

---

# 50. Reason obligatoire

Le runtime exige déjà une justification pour plusieurs actions Operations.

Cette règle devient un invariant Platform :

```text
action opérateur à forte conséquence
→ reason obligatoire
```

---

# 51. Before / After

Les mutations critiques doivent présenter, lorsque utile :

```text
AVANT
→ état connu

ACTION
→ conséquence

APRÈS
→ résultat confirmé
```

Le backend audit existe déjà pour certaines actions.

---

# 52. Worker Health

Worker health est une surface technique légitime de Platform.

Afficher :

- worker ;
- instance ;
- state ;
- last seen ;
- last cycle ;
- erreur bornée ;
- stale.

Pas de log infini en racine.

---

# 53. Payments health

Operations peut synthétiser :

- failure rate ;
- stale pending ;
- invalid webhooks ;
- stuck webhooks ;
- failed refunds.

Mais Payment reste owner des opérations financières spécifiques.

---

# 54. Scanner health

Operations peut montrer des tendances :

- rejected ;
- duplicate ;
- invalid ;
- wrong context.

Un Scan rejeté n’est pas automatiquement fraude.

---

# 55. Automation health

Operations peut montrer :

- failed runs ;
- overdue runs ;
- backlog.

La configuration métier Automation reste son owner.

---

# 56. Notification delivery health

Platform peut montrer :

- failed deliveries ;
- overdue deliveries ;
- provider/config state safe.

Ne jamais afficher secrets/provider credentials.

---

# 57. Confiance

Le runtime possède déjà une file Platform Trust.

Elle compose :

```text
verification claims
reports
disputes
proof review / revoke
evidence access
```

---

# 58. Trust Review ≠ Space Trust

Space Trust console :

```text
acteur Space
→ gérer sa propre Trust
```

Platform Trust :

```text
opérateur global
→ revoir / décider selon platform.trust.review
```

Ne pas fusionner.

---

# 59. Verification queue

N1 :

- sujet ;
- claim type ;
- requested_at ;
- status ;
- risk/context minimal.

N2 :

- evidence protégée ;
- historique ;
- requester ;
- subject ;
- décisions possibles.

---

# 60. Evidence

Le runtime protège déjà Evidence par Permission et `private, no-store`.

Platform doit conserver :

```text
Evidence
→ ouverture explicite
→ no-store
→ aucun preview public
```

---

# 61. Reports

Report N1 :

- category ;
- subject/context ;
- age ;
- status ;
- assignment.

N2 :

- description ;
- evidence ;
- parties ;
- owner facts ;
- resolution actions.

---

# 62. Disputes

Une dispute doit rendre visibles :

- parties ;
- sujet ;
- état ;
- demandes d’information ;
- décision ;
- remedy ;
- audit.

Sans score automatique de culpabilité.

---

# 63. Trust decision

Les actions actuelles incluent :

```text
review
verify
reject
revoke
triage
investigate
resolve
dismiss
open dispute
request info
decide
close
```

Le langage Platform doit rester humain et conséquence-first.

---

# 64. Curation

Le runtime possède déjà une expérience staff Opportunity.

Elle couvre :

```text
dashboard
create
submission review
detail
revision
publish revision
source create
source check
lifecycle
merge
```

---

# 65. Opportunity Curation

Question :

> **Quelle possibilité mérite d’être admise, corrigée, sourcée, fusionnée ou publiée ?**

---

# 66. Curation ≠ Discover

Discover montre des Possibilités aux utilisateurs.

Curation gouverne ce qui peut devenir une possibilité fiable.

---

# 67. Source ≠ vérité

Une source vérifiée reste une source.

La curation doit conserver :

```text
source
observation
interpretation
admission
```

comme concepts distincts.

---

# 68. Merge

Fusionner deux Opportunities est une action à forte conséquence.

Platform doit présenter :

- survivant ;
- doublon ;
- données affectées ;
- redirections/handoffs si owner ;
- confirmation.

---

# 69. Mayele et curation

Mayele possède sa propre architecture de connaissance.

Platform pourra éventuellement exposer des opérations Mayele lorsque le runtime les démontre.

Ne pas inventer aujourd’hui :

```text
Knowledge Admin
AI Control Center
Agent Fleet
```

sans owner actuel.

---

# 70. Gouvernance

Gouvernance regroupe des politiques et capacités globales existantes.

Premiers domaines démontrés :

```text
Subscriptions
Recognition
```

---

# 71. Subscriptions

Le runtime distingue déjà :

```text
catalog view/manage
subscription view/manage
grants manage
reviews manage
```

Platform doit préserver cette granularité.

---

# 72. Subscription ≠ Payment

Une Subscription peut avoir une dimension billing.

Mais :

```text
Subscription
≠ Payment
```

Platform doit conserver la séparation.

---

# 73. Entitlement ≠ Permission

Invariant :

```text
Entitlement
→ capacité contractuelle

Permission
→ autorité d’action
```

Platform ne doit jamais les fusionner.

---

# 74. Entitlement Grant

Le runtime précise que Grant detail est une préoccupation interne Platform.

C’est un excellent candidat Platform.

Pas un écran utilisateur Makolo générique.

---

# 75. Subscription reviews

Les transitions et Requirement assessments doivent être présentés comme workflow owner.

Pas comme édition brute de lignes.

---

# 76. Recognition Governance

Une partie importante de Recognition est actuellement administrée via Django Admin.

Elle utilise déjà les Permissions Platform.

C’est le principal candidat de migration progressive vers Platform.

---

# 77. Recognition policy workflow

Le runtime a déjà :

```text
DRAFT
SIMULATED
SCHEDULED
ACTIVE
SUPERSEDED
```

et des actions :

```text
simulate
publish / schedule
```

Platform doit représenter ce workflow explicitement.

---

# 78. Recognition simulation

Simulation N2 :

- policy ;
- fenêtre ;
- projected credits ;
- signals ;
- matches ;
- comparaison ;
- warnings.

La simulation ne doit pas être confondue avec publication.

---

# 79. Recognition publish

Publication est à haute conséquence.

Elle doit présenter :

- policy/version ;
- effective boundary ;
- policy actuellement active ;
- impact simulé ;
- confirmation ;
- audit.

---

# 80. Recognition audit

Les Signals, Ledgers, Evaluations et Grants sont plutôt des profondeurs audit.

Pas des objets de navigation primaire.

---

# 81. Achievements

AchievementDefinition est Platform governance.

Mais :

```text
Achievement
≠ credit balance
```

Le runtime le teste déjà.

---

# 82. Rewards / economy

RewardDefinition et économie Recognition doivent rester séparées des Payments.

Une récompense n’est pas un remboursement ou une monnaie bancaire.

---

# 83. Interopérabilité

Le runtime possède :

```text
PlatformInteroperabilityAPIView
```

avec connections Platform `manageable=true`.

---

# 84. Interop Platform ≠ Space Interop

Les contexts sont séparés :

```text
personal
space
platform
```

La Platform doit préserver cette frontière.

---

# 85. Connections

Une connexion Platform peut représenter un provider/connecteur global.

Afficher :

- identité ;
- état ;
- capabilities ;
- configuration status ;
- dernière vérification utile.

Ne jamais exposer :

- secret ;
- token ;
- clé complète.

---

# 86. Système

Système regroupe les capacités techniques qui ne sont pas un workflow métier utilisateur.

Candidate :

```text
Health / Readiness
Workers
Domain Events
Background queues
Interop
Runtime capability states
Audit technique
```

---

# 87. Health / Readiness

Les endpoints `/health` et `/readiness` peuvent nourrir Platform.

Ils ne doivent pas être confondus avec Readiness métier.

---

# 88. Runtime Readiness ≠ domain Readiness

Invariant :

```text
server readiness
≠ Journey Readiness
```

Le mot visible peut être :

```text
État du runtime
```

pour éviter l’ambiguïté.

---

# 89. Domain Events

Django Admin expose aujourd’hui :

```text
DomainEventOutbox
DomainEventConsumption
```

en lecture, avec requeue ciblé des failed events.

Platform peut à terme fournir une surface système mieux contextualisée.

---

# 90. Requeue Domain Event

Cette action est technique et risquée.

Si déplacée dans Platform :

- montrer idempotency key ;
- consumer ;
- attempts ;
- dernière erreur ;
- cible owner ;
- raison opérateur ;
- confirmation.

Sinon, elle peut rester Django Admin.

---

# 91. Système ≠ secrets

Platform ne doit jamais être un viewer `.env`.

Elle peut afficher :

```text
configured
missing
healthy
degraded
```

Pas la valeur sensible.

---

# 92. Système ≠ hébergeur

PythonAnywhere reste actuellement un environnement bêta.

Platform ne doit pas hardcoder un provider d’hébergement.

---

# 93. Configuration

Une configuration Platform n’est exposée que si :

- owner clair ;
- mutation sûre ;
- validation ;
- Permission ;
- audit.

Sinon :

→ Django Admin ou environnement opérateur.

---

# 94. Recherche opérateur globale

Le header peut fournir une recherche globale.

Elle doit être permission-first.

Résultats possibles :

```text
Spaces
Profiles
Activities
Occurrences
Journeys
Payments
Incidents
Trust cases
Subscriptions
Opportunities
```

selon owners démontrés.

---

# 95. Pas de Search brute DB

La Search ne doit pas :

```text
SELECT * across all models
```

ou indexer des secrets.

---

# 96. Raccourcis clavier

Platform desktop peut privilégier :

- `/` ou raccourci Search ;
- navigation results ;
- shortcuts de queue ;
- retour focus.

Le mapping exact reste à valider.

---

# 97. Actions bulk

Bulk est permis seulement quand :

- owner possède une opération bulk sûre ;
- prévisualisation ;
- count exact ;
- scope clair ;
- confirmation ;
- audit.

---

# 98. Bulk delete

Pas de bulk delete générique Platform.

---

# 99. Actions destructives

Doivent être :

- nommées ;
- ciblées ;
- motivées ;
- confirmées ;
- auditables ;
- réversibles lorsque le domaine le permet.

---

# 100. Undo

Ne pas inventer un Undo si le domaine ne peut pas annuler réellement.

---

# 101. Feedback

Exemples :

```text
Space suspendu.
Raison enregistrée.

Policy planifiée pour la prochaine frontière Recognition.

Signalement passé en investigation.

Connexion revalidée.
```

Pas :

```text
Success
```

---

# 102. Erreurs

Une erreur opérateur doit répondre :

1. qu’est-ce qui a échoué ?
2. l’action a-t-elle été appliquée ?
3. l’état connu actuel ?
4. que faire ensuite ?
5. existe-t-il un audit / incident ?

---

# 103. Concurrence

Les mutations à forte conséquence doivent anticiper :

- stale form ;
- state changed ;
- double decision ;
- double publish ;
- double refund ;
- concurrent moderator.

Le owner décide du verrouillage/idempotence.

---

# 104. Freshness

Platform doit montrer la fraîcheur quand elle compte.

Particulièrement :

- worker health ;
- payment state ;
- incident ;
- queue ;
- connection ;
- runtime health.

---

# 105. Offline

Platform est **online-authoritative**.

Elle ne doit pas promettre un mode offline opérationnel comparable à Flutter Makolo.

---

# 106. Cached read

Un snapshot de lecture peut être conservé techniquement.

Mais :

```text
stale cached Platform data
≠ autorité actuelle
```

Toutes les mutations sont revalidées à distance.

---

# 107. Local-first Makolo ≠ Platform offline

L’architecture local-first de l’application installée ne doit pas être appliquée aveuglément à Platform.

Platform peut être web-first et connectée.

---

# 108. Web-first

Recommandation :

```text
Platform v1
→ Web/desktop responsive
```

Pourquoi :

- opérations denses ;
- tables ;
- preuves ;
- comparaison ;
- audit ;
- multi-pane ;
- clavier.

---

# 109. Pas d’app Flutter Platform maintenant

Le runtime mobile contient des répertoires `platform/*` pour des **device platform capabilities** :

- Location ;
- Camera ;
- Scanner ;
- Files ;
- Sharing ;
- Biometrics.

Cela n’a rien à voir avec Makolo Platform opérateur.

Invariant de vocabulaire :

```text
mobile platform capability layer
≠ Makolo Platform product
```

---

# 110. Responsive

Platform doit fonctionner sur :

```text
Medium
Wide
Very Wide
```

Compact peut supporter :

- consultation ;
- triage ;
- actions simples sûres.

Il ne doit pas forcer toutes les opérations denses sur téléphone.

---

# 111. Layout Wide

Candidate :

```text
RAIL       220–260
LIST       360–440
FOCUS      flex
```

3 panes seulement si les trois rôles cognitifs existent.

---

# 112. Compact

Candidate :

```text
top app bar
drawer / compact rail
single pane
sticky contextual actions
```

---

# 113. No dashboard drift

Wide ne doit pas devenir une mosaïque de 24 widgets.

---

# 114. Tables

Platform peut utiliser davantage de tables que Makolo utilisateur.

Mais une table doit répondre à un travail réel :

- comparer ;
- trier ;
- filtrer ;
- décider.

---

# 115. Inspector

Un Inspector technique peut exister en N3.

Il peut montrer :

- ID ;
- owner ;
- timestamps ;
- before/after ;
- safe metadata ;
- links.

Pas secrets.

---

# 116. Environment indicator

Platform devrait pouvoir rendre visible l’environnement **lorsque le runtime le sait de manière sûre**.

But :

éviter une action opérateur dans le mauvais environnement.

Ne pas hardcoder de nom d’environnement.

---

# 117. Production protection

Lorsqu’une vraie production existera, les actions sensibles peuvent avoir une friction visuelle plus forte.

Le contrat n’invente pas aujourd’hui de production finale.

PythonAnywhere reste bêta/test selon le runbook courant.

---

# 118. Audit

Platform doit considérer l’audit comme une conséquence native des actions à risque.

---

# 119. Audit ≠ Historique utilisateur

Audit Platform répond :

```text
qui a fait quoi
sur quelle cible
quand
pourquoi
avant/après
```

Historique Makolo répond à une expérience humaine passée.

---

# 120. OperationsAuditLog

Le runtime possède déjà :

```text
actor
action
target_type
target_id
summary
before
after
metadata
created_at
```

C’est une bonne base pour les actions Operations.

---

# 121. Audit cross-domain

Les domaines possèdent aussi leurs traces.

Platform ne doit pas recopier tout dans `OperationsAuditLog`.

Une vue d’audit peut fédérer.

---

# 122. Private notes

Les notes opérateur privées doivent rester :

- permissionnées ;
- non publiques ;
- non renvoyées aux utilisateurs sauf contrat explicite ;
- minimales.

---

# 123. Support

Le besoin de Support est réel.

Mais le runtime inspecté ne démontre pas un bounded context `SupportCase` universel.

Donc Platform v1 doit supporter :

```text
investigation
+
handoff owner
+
incident si besoin
```

sans inventer un nouveau ticketing système.

---

# 124. Future SupportCase

Créer un SupportCase seulement si un besoin irréductible apparaît :

- assignation ;
- SLA ;
- conversation support ;
- statut ;
- escalade ;
- historique propre.

Pas uniquement parce que Platform a une page Support.

---

# 125. Sécurité

MUST :

- canonical Permissions ;
- CSRF ;
- sessions sûres ;
- no-store pour données sensibles appropriées ;
- IDOR tests ;
- audit ;
- reason sur actions fortes ;
- revalidation avant mutation ;
- aucune exposition de secrets ;
- PII minimale.

---

# 126. Impersonation

Platform ne doit pas permettre une impersonation silencieuse.

Si une capacité future d’assistance “voir comme” devient nécessaire :

- explicitement séparée ;
- read-only par défaut ;
- très auditée ;
- bannière persistante ;
- aucune mutation comme l’utilisateur sans contrat fort.

Elle n’est pas requise par le runtime actuel.

---

# 127. Passwords

Platform ne doit jamais permettre de lire un mot de passe.

Les opérations compte utilisent les services d’auth adaptés.

---

# 128. AccessCredential

Ne jamais afficher un token/QR complet en vue générale.

---

# 129. Provider secrets

Ne jamais afficher :

- OAuth secret ;
- webhook secret ;
- API key ;
- private key ;
- token complet.

---

# 130. Evidence Trust

Evidence est sensible.

Accès explicite, tracé et permissionné.

---

# 131. Logs

Les logs Platform doivent être filtrés de PII inutile.

Le runbook impose déjà cette direction.

---

# 132. Observability

Platform peut représenter l’état d’observabilité.

Elle ne doit pas devenir le stockage primaire des logs.

---

# 133. External observability provider

Aucun SaaS n’est imposé.

Platform doit rester provider-neutral.

---

# 134. Navigation capability-driven

Exemple :

```text
User A
platform.manage
→ Vue d’ensemble
→ Investiguer
→ Opérations
→ Système
→ Interop

User B
platform.trust.review
→ Confiance

User C
Opportunity curator
→ Curation
```

Pas de pages interdites visibles inutilement.

---

# 135. Cross-capability operator

Une personne avec plusieurs permissions peut voir plusieurs modules dans le même shell.

Pas plusieurs apps.

---

# 136. Platform Admin

`makolo-platform-admin` est le rôle global actuel.

Il ne doit pas devenir un raccourci vers `is_superuser`.

---

# 137. Opportunity Curator

`opportunity-curator` est spécialisé.

Il doit pouvoir utiliser Platform sans accéder aux Operations globales.

---

# 138. Subscription operators

Les Permissions existantes permettent de créer des responsabilités Platform plus fines sans changer le modèle d’autorité.

---

# 139. Recognition operators

Même principe :

- view ;
- policy manage ;
- publish ;
- economy ;
- achievements ;
- audit.

---

# 140. Trust reviewer

`platform.trust.review` reste séparé du platform admin général.

---

# 141. Capabilities endpoint

La Platform Web doit pouvoir s’amorcer à partir de la projection de capabilities.

Le client ne hardcode pas tous les modules comme disponibles.

---

# 142. Current gap — capabilities

`PlatformCapabilitiesAPIView` ne donne actuellement des liens explicites qu’à certains modules.

La cible devrait progressivement fournir des handoffs cohérents, sans transformer l’API en route registry universelle.

---

# 143. Current gap — shell

Il n’existe pas de shell Platform Web consolidé démontré.

Les expériences sont dispersées :

- `/operations/...`
- `/trust/staff/...`
- `/opportunities/staff/...`
- Django Admin ;
- API Platform.

Le chantier doit d’abord les unifier visuellement et cognitivement.

---

# 144. Current gap — Recognition

Recognition Governance dépend encore fortement du Django Admin.

C’est acceptable comme runtime actuel.

C’est une dette UX Platform à réduire.

---

# 145. Current gap — Subscriptions

Les Permissions et owners sont riches.

L’expérience Platform doit composer catalogue, subscriptions, reviews et grants sans exposer les modèles bruts.

---

# 146. Current gap — Investigation

Aucune surface transverse d’investigation complète n’a été démontrée.

C’est une capacité Platform importante.

---

# 147. Current gap — Search

La Search opérateur globale n’est pas démontrée.

Elle doit être owner-federated et permission-safe.

---

# 148. Current gap — Audit federation

Operations possède son Audit Log.

Recognition / Subscription / Trust possèdent d’autres vérités.

Une vue fédérée peut être utile sans créer un nouveau propriétaire.

---

# 149. Current gap — UX consistency

Les staff views actuelles sont des expériences domain-locales.

Platform doit fournir :

- shell ;
- breadcrumbs ;
- global search ;
- permissions ;
- tables ;
- confirmations ;
- audit ;
- deep links ;
- visual language.

---

# 150. Current gap — Django Admin dependence

Certains workflows réels sont encore portés par Django Admin.

Ils doivent être classés :

```text
KEEP IN ADMIN
MIGRATE TO PLATFORM
DUAL DURING TRANSITION
REMOVE / DISALLOW
```

Le document frontière associé fixe cette matrice.

---

# 151. Surface Golden — Platform Overview

```text
Makolo Platform

État
Dégradé

À traiter
Worker Observer sans heartbeat          CRITIQUE
3 webhooks paiement non traités         ÉLEVÉ
2 organisations en attente              MOYEN

Incidents
2 ouverts

Système
Observer       Dégradé
Automation     Stable
Notifications  Stable

Récent
Jean a suspendu Space X · motif…
```

---

# 152. Golden — Investigation Space

```text
Mulykap

État
Actif

Confiance
Vérifié

Subscription
Active

Activités
8

Incidents
1 ouvert

Interventions Platform
Suspension levée · 4 oct.

[Ouvrir Trust] [Ouvrir Operations]
```

---

# 153. Golden — Trust Queue

```text
Confiance

Vérifications
12 à revoir

Signalements
4 ouverts

Disputes
2 actives

Sélection
Space X
Vérification identité
Demandée il y a 2 h
```

---

# 154. Golden — Recognition Publish

```text
Policy network-utility v3

État
Simulée

Simulation 30 jours
Signals: ...
Projected credits: ...

Activation prévue
Prochaine frontière Recognition

[Planifier la publication]
```

---

# 155. Golden — Opportunity merge

```text
Fusionner

Conserver
Opportunity A

Fusionner depuis
Opportunity B

Sources
...

Conséquences
...

[Confirmer la fusion]
```

---

# 156. Golden — Worker Health

```text
Workers

Observer
instance default
Dernier heartbeat · 37 s
Healthy

Resolver
instance default
Dernier heartbeat · 4 min
Stale
```

---

# 157. Golden — Platform limited role

Opportunity curator voit :

```text
Makolo Platform
Curation
```

et ne voit pas :

```text
Operations
Trust
Recognition
Subscriptions
```

sans Permission.

---

# 158. Golden — High consequence

```text
Suspendre Mulykap

Conséquence
Le Space ne pourra plus opérer normalement.

Raison *
[____________________________]

[Annuler] [Suspendre le Space]
```

---

# 159. États UX Platform

```text
loading
content
empty
no_permission
partial
stale
degraded
critical
action_pending
action_failed
action_confirmed
conflict
```

---

# 160. Empty

Une queue vide doit être calme :

```text
Aucune vérification en attente.
```

Pas de métrique marketing.

---

# 161. No permission

```text
Vous n’avez pas l’autorité Platform requise pour cette surface.
```

Ne pas révéler counts/détails.

---

# 162. Conflict

Si l’objet a changé :

```text
Cette réalité a changé depuis son ouverture.
Actualisez avant de décider.
```

---

# 163. Stale

Affichage explicite de la dernière actualisation lorsque nécessaire.

---

# 164. Degrade locally

Une panne Trust n’empêche pas Operations si indépendante.

---

# 165. Accessibility

MUST :

- clavier complet ;
- focus visible ;
- tables accessibles ;
- headings structurés ;
- modals/confirmations correctement annoncés ;
- contrastes élevés ;
- couleurs non exclusives ;
- text scale ;
- Reduce Motion ;
- densité configurable si nécessaire.

---

# 166. Data density

L’utilisateur opérateur peut préférer une densité élevée.

Mais le produit doit conserver :

- lisibilité ;
- hiérarchie ;
- erreurs locales ;
- no accidental click.

---

# 167. Destructive action affordance

Les actions destructives ne doivent pas être icon-only.

---

# 168. Mobile narrow screen

Sur petit écran :

- consultation ;
- triage ;
- acknowledgement ;
- petites actions sûres.

Pour workflows denses :

- préserver possibilité ;
- ne pas tronquer irréversiblement ;
- guider vers un viewport plus adapté si nécessaire.

---

# 169. Visual distinction from Makolo

Recognition test :

en 500 ms, un utilisateur doit savoir :

```text
je suis dans Makolo Platform
≠ Makolo Profile
≠ Makolo Space
```

---

# 170. Visual distinction from Django Admin

Platform doit être reconnaissable comme un produit Makolo :

- navigation par travail opérateur ;
- contexte humain ;
- actions owner-backed ;
- design system Makolo.

Django Admin garde son apparence technique ou une customisation minimale.

---

# 171. Pas besoin de rethémer Django Admin en Platform

Retoucher l’Admin pour le faire ressembler à Platform serait dangereux :

- confusion de responsabilité ;
- faux sentiment de workflow sûr ;
- CRUD direct restant derrière le thème.

---

# 172. Entrée vers Django Admin

Platform peut fournir un lien `Administration technique` seulement aux personnes autorisées.

Il doit être explicitement séparé.

---

# 173. Sortie vers Makolo

Un opérateur qui possède aussi un compte Makolo peut avoir :

```text
Retour à Makolo
```

sans transporter automatiquement une cible Platform dans le contexte utilisateur.

---

# 174. Deep links

Un deep link Platform doit :

- exiger authentification ;
- exiger Platform Permission ;
- résoudre la cible ;
- ne pas fuiter par 403 différencié si cela est sensible.

---

# 175. Session

Platform peut partager l’auth de Makolo.

Elle ne doit pas partager implicitement l’Actor Context Space courant comme autorité Platform.

---

# 176. CSRF / mutations

Toutes les mutations Web suivent les protections Django appropriées.

---

# 177. No hidden GET mutation

Aucune action sensible via GET.

---

# 178. POST / PATCH owner-backed

Les mutations passent par services/serializers owner.

---

# 179. Tests d’autorité

Minimum :

```text
anonymous
authenticated no platform permission
opportunity curator
trust reviewer
subscription viewer
subscription manager
recognition viewer
recognition publisher
platform admin
superuser technical admin
```

---

# 180. Tests IDOR

Chaque détail Platform doit être testé avec un opérateur :

- sans permission ;
- permission partielle ;
- bonne permission.

---

# 181. Tests destructive flows

Tester :

- stale state ;
- double submit ;
- concurrent decision ;
- missing reason ;
- invalid transition ;
- rollback transaction.

---

# 182. Tests audit

Toute action forte doit laisser la trace owner attendue.

---

# 183. Tests privacy

Vérifier absence de :

- secrets ;
- credential complet ;
- Evidence sans permission ;
- PII inutile ;
- données privées Space/Profile non liées au cas.

---

# 184. Tests Platform/Django Admin divergence

Une action métier importante ne doit pas avoir :

```text
Platform workflow sûr
+
Admin save brut qui le contourne
```

sans justification explicite.

---

# 185. Doctrine de migration

Ne pas tout réécrire.

Ordre :

```text
1. Shell Platform
2. Capability navigation
3. Operations existant
4. Trust staff existant
5. Opportunity staff existant
6. Subscriptions owner workflows
7. Recognition governance hors Admin
8. Interop
9. Investigation/Search
10. System/Audit
11. réduction progressive de Django Admin
```

---

# 186. Étape 1 — Shell

Construire :

- layout sombre ;
- operator identity ;
- capability nav ;
- global search placeholder seulement si endpoint réel ;
- error/permission states ;
- links vers modules existants.

Aucune migration métier.

---

# 187. Étape 2 — Operations

Réutiliser :

- `build_operations_overview`;
- selectors ;
- services ;
- `OperationsAuditLog`;
- APIs existantes.

Pas de second Operations engine.

---

# 188. Étape 3 — Trust

Réutiliser :

- current staff queue ;
- decision services ;
- evidence permissions.

Changer shell/Presentation progressivement.

---

# 189. Étape 4 — Opportunity

Intégrer les staff views dans shell Platform.

Ne pas réécrire la curation.

---

# 190. Étape 5 — Subscriptions

Créer Presentation sur services/authorization existants.

---

# 191. Étape 6 — Recognition

Déplacer progressivement les workflows de policy/economy/achievement qui vivent dans Django Admin.

Conserver admin comme fallback temporaire.

---

# 192. Étape 7 — Investigation

Ajouter read models/selectors fédérés.

Pas de nouvelle vérité persistante.

---

# 193. Étape 8 — System

Worker health, Runtime status, Domain Events et Interop.

---

# 194. Étape 9 — Admin hardening

Réduire les modèles mutables exposés.

Passer certains admins en :

```text
read-only
deep inspection
emergency-only
```

---

# 195. Collision audit

Avant implémentation, re-check :

- `main`;
- PR #501 ou son statut final ;
- base templates ;
- authorization ;
- operations ;
- trust ;
- subscriptions ;
- recognition ;
- opportunities ;
- shared navigation.

Platform shell ne doit pas entrer en collision avec la fermeture Moi/Nous.

---

# 196. Aucune migration UX obligatoire

Le shell Platform et l’intégration des workflows existants ne nécessitent pas par principe de nouvelles tables.

---

# 197. Migration seulement si vérité irréductible

Avant un nouveau modèle Platform :

1. owner existe-t-il ?
2. audit existe-t-il ?
3. read model suffit-il ?
4. operations incident suffit-il ?
5. domain event suffit-il ?
6. relation suffit-elle ?

---

# 198. PlatformCase interdit par défaut

Ne pas créer :

```text
PlatformCase
PlatformTask
PlatformObject
PlatformAction
PlatformEntity
```

comme fourre-tout.

---

# 199. Anti-features Platform

Platform ne doit jamais devenir :

- Django Admin rethémé ;
- clone de Retool ;
- ERP universel ;
- task manager ;
- super-Space ;
- impersonation silencieuse ;
- viewer de secrets ;
- bypass Permission ;
- raw DB browser ;
- system where `is_staff` = all access ;
- collection de boutons destructifs ;
- giant dashboard ;
- AI control room décorative ;
- second Trust engine ;
- second Subscription engine ;
- second Recognition engine ;
- second Opportunity engine ;
- second Operations engine.

---

# 200. Invariants gelés

1. Platform est distincte de Makolo Profile/Space.
2. Platform est distincte de Django Admin.
3. Même backend canonique.
4. Même owners métier.
5. Profile humain reste actor des actions Platform.
6. Platform n’est pas un Space.
7. Platform n’est pas un acteur métier.
8. `is_staff` ≠ Platform Permission.
9. `is_superuser` ≠ rôle produit normal.
10. Navigation capability-driven.
11. Platform ne contient pas les modules Personal/Space.
12. Operations existe déjà et doit être réutilisé.
13. Trust staff existe déjà et doit être réutilisé.
14. Opportunity staff existe déjà et doit être réutilisé.
15. Subscription Platform permissions existent déjà.
16. Recognition Platform permissions existent déjà.
17. Interop Platform existe déjà.
18. Platform est Web/desktop-first.
19. Mobile `platform capability` ≠ Makolo Platform.
20. Noir + violet = identité cognitive Platform.
21. Le Mark est branding, pas action centrale Platform.
22. Progressive disclosure.
23. Reason obligatoire pour actions fortes lorsque le domaine le requiert.
24. Mutation via owner service.
25. Pas d’édition brute de lifecycle sensible.
26. Before/after lorsque pertinent.
27. Audit obligatoire pour actions critiques.
28. No secrets.
29. PII minimale.
30. Evidence protégée.
31. Cache ≠ autorité.
32. Platform online-authoritative.
33. Search opérateur permission-first.
34. Investigation est une projection, pas un nouveau domaine.
35. SupportCase non inventé.
36. Bulk seulement si owner-safe.
37. No bulk delete générique.
38. Entitlement ≠ Permission.
39. Subscription ≠ Payment.
40. Recognition ≠ Payment.
41. Trust ≠ score global.
42. Opportunity source ≠ vérité.
43. Runtime Readiness ≠ Journey Readiness.
44. Platform doit fonctionner avec plusieurs rôles spécialisés.
45. Django Admin reste disponible pour maintenance profonde.
46. La migration hors Admin est progressive.
47. Aucune nouvelle table Platform sans vérité irréductible.
48. Platform doit être reconnaissable en moins de 500 ms.
49. Platform ne doit pas refaire les surfaces Makolo utilisateur.
50. Toute capacité Platform doit pouvoir dire quel owner elle utilise.

---

# 201. Critères de sortie UX

Platform est UX-mature lorsque :

- identité distincte immédiate ;
- modules permissionnés ;
- queues compréhensibles ;
- actions conséquence-first ;
- recherche/investigation cohérentes ;
- no raw CRUD comme chemin normal ;
- audit visible ;
- erreurs récupérables ;
- desktop dense mais structuré ;
- responsive honnête.

---

# 202. Critères de sortie backend

- capability endpoint ;
- owner services ;
- granular permissions ;
- no IDOR ;
- transaction safety ;
- audit ;
- reason ;
- no secret leakage ;
- selectors dédiés ;
- no direct unsafe model writes depuis Platform.

---

# 203. Critères de sortie sécurité

- tests Permission par module ;
- CSRF ;
- session ;
- audit ;
- evidence protection ;
- secret redaction ;
- cross-account isolation ;
- no impersonation silent ;
- destructive confirmation ;
- production/environment awareness lorsque disponible.

---

# 204. Critères de sortie Operations

- overview ;
- incidents ;
- org decisions ;
- event moderation ;
- worker health ;
- moderation cases ;
- audit ;
- local failures.

---

# 205. Critères de sortie Trust

- verification ;
- report ;
- dispute ;
- evidence ;
- proof revoke ;
- private notes ;
- no leakage.

---

# 206. Critères de sortie Governance

Subscriptions :

- catalog ;
- subscriptions ;
- grants ;
- reviews.

Recognition :

- policies ;
- simulation ;
- publication ;
- economy ;
- achievements ;
- audit.

---

# 207. Critères de sortie Curation

- submissions ;
- revisions ;
- sources ;
- source checks ;
- lifecycle ;
- merge.

---

# 208. Critères de sortie System

- worker/runtime state ;
- connections ;
- Domain Event visibility adaptée ;
- safe configuration status ;
- no secrets.

---

# 209. Golden coverage candidate

```text
Platform Overview
Platform Limited Role
Investigation
Operations Incident
Organization Lifecycle Decision
Trust Verification
Trust Dispute
Opportunity Review
Opportunity Merge
Subscription Review
Recognition Simulation
Recognition Publish
Interoperability
Worker Health
System Partial Failure
```

Viewports :

```text
834×1112
1280×800
1440×900
1728×1117
```

Compact support :

```text
430×932
```

pour consultation/triage ciblé.

---

# 210. Références runtime principales

- `core/api/platform_views.py`
- `core/api/platform_urls.py`
- `authorization/constants.py`
- `operations/permissions.py`
- `operations/api/views.py`
- `operations/services.py`
- `operations/selectors.py`
- `trust/views.py`
- `trust/urls.py`
- `opportunities/staff_views.py`
- `opportunities/urls.py`
- `subscriptions/authorization.py`
- `recognition/admin.py`
- `interoperability/api_views.py`
- `core/admin.py`
- `config/urls.py`
- `docs/operations-runbook.md`

---

# 211. Références expérience

- `Makolo_Application_Behavior_Interaction_System_v1.1.md`
- `Makolo_UX_Presentation_Golden_Specification_v1.md`
- `Makolo_Space_Architecture_Experience_Mobile_Consolidee.md`
- contrats UX consolidés Profile/Space
- `Mayele_Systeme_Autonome_Intelligence_Molongo_Cadre_Consolide_V2_2026-09-30.md`

---

# 212. Formulation finale

> **Makolo Platform est l’expérience opérateur interne qui permet à des Profiles explicitement autorisés de superviser, investiguer, modérer, gouverner et maintenir Makolo à travers les domaines canoniques existants. Elle n’est ni un Space, ni un super-acteur, ni un Django Admin rethémé : l’opérateur humain reste l’acteur audité, les permissions `platform.*` déterminent les capacités, et chaque mutation retourne au service propriétaire de la vérité concernée. Platform consolide progressivement les capacités déjà présentes — Operations, Trust Review, Opportunity Curation, Subscriptions, Recognition Governance et Interoperability — sous un shell Web/desktop noir et violet immédiatement distinct de l’application Makolo. Django Admin reste une couche technique profonde pour inspection, configuration framework et maintenance exceptionnelle ; Platform devient le chemin normal pour le travail opérateur récurrent, contextualisé, sûr et auditable.**
