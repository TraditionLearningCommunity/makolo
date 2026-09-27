# A2 — Personal Makolo mobile program

> **Statut : A2-P0 préparé — P1 bloqué tant que A1 n'est pas fusionné sur main**
>
> **Audit runtime : 27 septembre 2026**
>
> **Base documentaire P0 : main@98618746d2d4c0ae1b3e1a4ce3da0c6bdfbca527**
>
> Le code, les migrations, les tests et le main courant restent prioritaires sur ce document. Les identifiants GitHub ci-dessous sont un snapshot d'audit et doivent être revérifiés avant A2-P1.

## 1. Objet

A2 transforme le moteur mobile installé par A1 en expérience personnelle Makolo réellement utilisable :

~~~text
Maintenant | Découvrir | [Makolo Mark] | En cours | Moi
                                      +
                                   Avatar
~~~

A2 ne reconstruit pas le moteur A1. Il consomme les projections et owner APIs déjà exposées par le serveur, les lit via le store local quand elles sont déjà disponibles, et suit les links/capabilities fournis par le backend.

Promesse :

> **Makolo marche pour vous.**

Principe d'expérience :

> **Pas le plaisir de rester. Le plaisir d'avancer.**

Une session peut légitimement se terminer par :

> **Tout est en ordre. ✓**

## 2. État vérifié avant A2

### 2.1 main

Au moment de l'audit :

- main HEAD : **98618746d2d4c0ae1b3e1a4ce3da0c6bdfbca527** ;
- commit : **W7 — Close orphan web capabilities (#312)** ;
- Z15 est déjà fusionné sur main via #304 ;
- les workflows principaux du HEAD main audités sont verts ;
- main ne contient pas encore le répertoire mobile/ ;
- main ne contient donc pas encore le socle Flutter A1.

### 2.2 A1

A1 n'est pas encore canoniquement fermé :

- PR #306 — **A1 — Installed Makolo Core** : ouverte vers main ;
- branche : **mobile/a1-installed-makolo-core** ;
- HEAD audité : **7e233118c207578ac4da65221a30009474ba75c8** ;
- PR #319 — **A1 — close Android native identity and APK checkpoint** : ouverte vers la branche A1 ;
- HEAD #319 audité : **e001aaeca85cdcc57da6db31b08f25aca97345e2** ;
- les nouveaux runs CI/Android/APK de #319 étaient encore en cours lors du dernier contrôle ;
- le head précédent de #319 avait Mobile CI verte mais Android Build et APK rouges.

Conclusion :

> **A1 n'est pas encore fusionné sur main. A2-P1 et les deux lanes fonctionnelles restent interdits.**

A2-P0 peut produire les contrats et le collision plan, mais aucun A2_BASE_SHA ne doit être fixé avant le merge réel d'A1.

### 2.3 Migrations

Audit du périmètre récent :

- Z15 (#304) : aucune migration Django ;
- W7 (#312) : aucune migration Django ;
- A1 (#306) : aucune migration Django ; une migration locale Drift est testée dans mobile/test/migration_test.dart ;
- A1 documente actuellement un schéma local v2, avec isolation par Profile.

A2 ne doit normalement introduire aucune migration Django. Une éventuelle évolution Drift pour Discovery ou une projection secondaire doit être centralisée par l'orchestrateur, forward-safe, non destructive et couverte par migration_test.

## 3. Sources canoniques A2

Ordre d'utilisation :

1. code, tests, migrations et APIs du main courant ;
2. docs/architecture/makolo-domain-blueprint.md ;
3. docs d'expérience, projection et mobile ci-dessous ;
4. contrats transversaux Behavior et Local-first du Project Makolo ;
5. état GitHub courant.

Sources obligatoires :

- docs/architecture/mobile-a0-architecture-reconciliation.md
- docs/architecture/mobile-a1-installed-core.md — à reprendre depuis main uniquement après merge A1
- docs/architecture/mobile-api-contract.md
- docs/architecture/z13-mobile-api-handoff.md
- docs/architecture/z14-program-closeout.md
- docs/architecture/m10-final-production-mobile-handoff.md
- docs/architecture/backend-ux-projection-api.md
- docs/architecture/m8-ux-shell-contract.md
- docs/architecture/mature-experience-principles.md
- docs/architecture/makolo-domain-blueprint.md
- docs/product/product-language.md
- docs/product/brand-system.md
- docs/architecture/brand-visual-system-v1.md
- docs/architecture/z7-makolo-mark-orchestration.md
- Makolo_Application_Behavior_Interaction_System_v1.1.md
- Makolo_Local_First_Synchronization_Offline_Execution_Architecture.md

Le document brand-visual-system-v1 contient encore une formulation historique de marque temporaire. Elle ne prévaut pas sur le Makolo Mark officiel, sur docs/product/brand-system.md, ni sur les assets A1 courants.

## 4. Contrats backend vérifiés

Les cinq surfaces principales utilisent les contrats existants :

| Surface | Contrat serveur |
|---|---|
| Maintenant | GET /api/v1/me/now/ |
| Découvrir | GET /api/v1/discovery/items/ |
| Makolo Mark | POST /api/v1/me/mark/ |
| En cours | GET /api/v1/me/ongoing/ |
| Moi | GET /api/v1/me/ |
| Identité auth | GET /api/v1/accounts/auth/me/ |

Le runtime main confirme que ces routes résolvent vers leurs vues canoniques. Il n'existe pas de namespace mobile parallèle.

Contrat de projection :

~~~text
meta:
  projection
  schema_version
  generated_at
  scope

data:
  projection composée par le serveur
~~~

Le serveur reste propriétaire de Readiness, Permission, Mandate, Access validity, Capacity, Payment, inclusion dans Maintenant, composition En cours et autorité.

Le client consomme notamment :

~~~text
projection
links
capabilities
states
reasons/context lorsque présents
~~~

et n'en reconstruit pas la vérité métier.

## 5. Scope A2

A2 porte les surfaces personnelles principales :

- Maintenant ;
- Découvrir ;
- Makolo Mark ;
- En cours ;
- Moi ;
- Avatar ;
- navigation/header nécessaires à ces surfaces ;
- lecture locale, fraîcheur, refresh, recovery et états dégradés de ces surfaces ;
- éventuelles surfaces secondaires Notifications/Conversations uniquement si elles peuvent être raccordées proprement sans élargir A2.

A2 ferme les placeholders A1 présents sur ces surfaces.

## 6. Non-scope A2

A2 ne construit pas la profondeur métier complète :

- Journey détaillée ;
- Forms complexes ;
- Requirement/Readiness profonde ;
- Access détaillé ;
- Resources détaillées ;
- Dossier/Project détaillés ;
- Jour J complet ;
- owner workspaces complets ;
- push FCM/APNs ;
- caméra/GPS/uploads profonds ;
- autorité offline déléguée ;
- scanner terrain autonome ;
- identité iOS si elle n'est toujours pas canoniquement décidée.

Ces sujets appartiennent à A3+ ou à leur train propriétaire.

Une action visible ne doit cependant jamais être morte. Si la profondeur n'existe pas encore en Flutter, A2 conserve le link/capability pour A3 et n'affiche un CTA que s'il mène à une destination utile réellement supportée.

## 7. Dépendances A1 à préserver

A2 réutilise, sans architecture parallèle :

- Riverpod ;
- go_router ;
- client HTTP Makolo ;
- JWT + refresh single-flight ;
- secure storage ;
- Drift ;
- DB locale isolée par Profile ;
- migration locale ;
- ProfileStore ;
- repository layer ;
- sync owner-scoped ;
- outbox durable ;
- lifecycle launch/resume/retour réseau ;
- SessionRecovery ;
- AppShell ;
- MakoloTheme ;
- Behavior primitives/states ;
- Makolo Mark canonique ;
- CI mobile ;
- Android host com.makolo.

Si une fondation A1 est réellement insuffisante, l'orchestrateur corrige le minimum sur la branche d'intégration après démonstration du problème. Une lane ne crée jamais une seconde architecture.

## 8. Architecture des phases

~~~text
A2-P0  Audit + contrats
A2-P1  Shared checkpoint
A2-P2A Action lane       ┐
                         ├── parallèles
A2-P2B Explore/Self lane ┘
A2-P3  Integration
A2-P4  Cross-surface behavior & visual QA
A2-P5  Closure / handoff A3
~~~

### A2-P0 — présent chantier

Livrables :

- ce programme ;
- contrat visual/behavior ;
- matrice local-first ;
- contrats de surfaces ;
- work package Action ;
- work package Explore/Self ;
- matrice d'acceptation ;
- template d'intégration/handoff.

Gate P0 :

> deux développeurs peuvent comprendre le produit et leur périmètre sans décider eux-mêmes l'architecture métier, locale, visuelle ou de navigation.

P0 ne crée aucun écran métier.

### A2-P1 — seulement après A1 merge

Conditions d'entrée obligatoires :

1. #319 ou son remplacement est fermé proprement ;
2. #306 est fusionnée sur main ;
3. main contient mobile/ et mobile-a1-installed-core.md ;
4. CI requise du commit A1 final est verte ;
5. Android build/APK checkpoint attendu par A1 est vert ;
6. docs A1 finales sont relues depuis main ;
7. main HEAD et PR concurrentes sont réaudités ;
8. migrations et API contracts sont revérifiés.

Alors seulement :

- créer **mobile/a2-integration** depuis ce main ;
- intégrer/réconcilier les documents P0 ;
- faire les corrections communes minimales ;
- ne créer aucun écran métier complet ;
- fixer **A2_BASE_SHA**.

### A2-P2

Créer depuis A2_BASE_SHA :

- **mobile/a2-action-orchestration**
- **mobile/a2-explore-self**

Cibles :

~~~text
mobile/a2-action-orchestration -> mobile/a2-integration
mobile/a2-explore-self         -> mobile/a2-integration
~~~

### A2-P3 à P5

L'orchestrateur possède l'intégration, le shell final, les routes, les headers, les composants réellement transversaux, la suppression des placeholders A1, la CI, le build et le handoff A3.

## 9. Stratégie deux développeurs

### Lane Action

Responsable de :

- Maintenant ;
- En cours ;
- Makolo Mark.

Ownership par défaut :

- mobile/lib/features/now/**
- mobile/lib/features/ongoing/**
- mobile/lib/features/mark/**
- repositories/adapters spécialisés nouveaux et tests propres à ces features.

### Lane Explore/Self

Responsable de :

- Découvrir ;
- Moi ;
- Avatar.

Ownership par défaut :

- mobile/lib/features/discovery/**
- mobile/lib/features/me/**
- mobile/lib/features/avatar/**
- repositories/adapters spécialisés nouveaux et tests propres à ces features.

Les deux lanes ne s'intègrent pas mutuellement. Elles remontent les besoins partagés à l'orchestrateur.

## 10. Shared/frozen après A2_BASE_SHA

Par défaut, les deux lanes ne modifient pas indépendamment :

- mobile/lib/app/**
- mobile/lib/navigation/**
- mobile/lib/design/makolo_theme.dart
- mobile/lib/design/behavior_primitives.dart
- mobile/lib/design/behavior_states.dart
- mobile/lib/auth/**
- mobile/lib/network/**
- mobile/lib/sync/**
- mobile/lib/data/local/**
- mobile/pubspec.yaml
- mobile/pubspec.lock

Sont également orchestrator-owned :

- AppShell final ;
- router final ;
- bottom navigation ;
- headers contextuels communs ;
- Avatar trigger commun ;
- suppression des placeholders A1 ;
- nettoyage/réconciliation de PersonalRepository ;
- shared primitives ;
- deep-link wiring transversal ;
- migration Drift éventuelle ;
- sync root Discovery/Notifications/Conversations éventuel.

Règle de shared component :

> créer un composant partagé seulement s'il sert réellement au moins deux surfaces ; sinon le garder dans la feature.

## 11. Collision audit P0

| Source | Risque A2 | Décision |
|---|---|---|
| #306 A1 Installed Core | direct, tout mobile/ | bloque P1 ; ne jamais brancher A2 fonctionnel avant merge |
| #319 A1 native identity | direct Android/build | bloque fermeture A1 ; surveiller CI/build/APK |
| #308 Personal UX closure | vocabulaire/navigation/profondeurs web | relire si merge avant P1 ; pas de collision mobile actuelle |
| #307 Product copy polish | Product Language, templates web ; CI non fiable lors de l'audit | ne pas copier ses chaînes tant qu'elles ne sont pas canoniques |
| #320 W7 status docs | docs statut programme | faible collision ; réconcilier current-program-status si nécessaire |
| W7/#312 | déjà sur main, web | pas de blocage mobile ; respecter owner links |
| Z15/#304 | déjà sur main, authorization/workspaces | important pour Avatar/contextes autorisés ; ne pas dériver l'autorité localement |

Avant chaque intégration de lane, refaire :

~~~text
main HEAD
PR ouvertes
fichiers touchés
API contracts
Product Language
brand
migrations
~~~

## 12. Gaps connus à l'entrée A2

### Discovery local-first

A1 synchronise aujourd'hui surtout personal.now, personal.ongoing et personal.me. A2 doit installer un cache/pack Discovery borné à partir de l'API propriétaire existante sans créer /sync/ ni moteur de ranking local. Toute modification de Drift/sync nécessaire est orchestrator-owned.

### Avatar / Agir comme

Le runtime expose désormais l'inventaire permissionné :

- GET /api/v1/organizations/workspaces/
- GET /api/v1/organizations/workspaces/<slug>/

Mais le runtime personnel interdit qu'un paramètre client act_as_space, space_id ou équivalent crée de l'autorité. L'inventaire d'Espaces autorisés n'est donc pas, à lui seul, un contrat de changement d'acteur.

A2 n'invente pas un mode act_as_space. Tant qu'un handoff mobile réel vers un contexte Espace n'est pas démontré, l'Avatar n'affiche pas un faux sélecteur opérationnel.

### Notifications / Conversations

Les collections serveur existent :

- /api/v1/notifications/
- /api/v1/conversations/

A1 n'installe pas encore une projection locale dédiée à ces listes. A2 ne montre leurs icônes dans un header que si l'orchestrateur ferme un slice secondaire utilisable, local-first ou honnêtement network-required. Sinon les icônes restent absentes plutôt que mortes.

## 13. Gates de lane

Une lane peut entrer dans mobile/a2-integration seulement si :

- scope respecté ;
- fichiers partagés non modifiés hors checkpoint orchestrateur ;
- lecture locale prioritaire pour les données acquises ;
- aucune vérité métier recalculée ;
- Product Language respecté ;
- états content + sync couverts ;
- tests ciblés verts ;
- captures revues ;
- accessibilité ciblée ;
- aucun faux contenu ;
- aucun CTA mort ;
- aucun backend métier dupliqué.

## 14. Gate final A2

A2 est fermé lorsque l'installation permet d'utiliser réellement :

~~~text
Maintenant
Découvrir
Makolo Mark
En cours
Moi
Avatar
~~~

sans placeholder A1 sur ces surfaces, avec :

- réponse locale immédiate lorsque le snapshot existe ;
- refresh discret ;
- offline utile ;
- stale honnête ;
- resume sans perte de contexte ;
- back naturel ;
- isolation Profile ;
- session recovery ;
- Product Language ;
- Reduce Motion ;
- text scaling ;
- Semantics ;
- qualité visuelle Makolo ;
- build Android et smoke réel.

Le verdict final est exactement :

~~~text
A2 TERMINÉ — A3 READY
~~~

uniquement si tous les gates sont fermés. Sinon :

~~~text
A2 NON TERMINÉ

Blockers :
- ...
~~~

## 15. Prochain checkpoint

**A2-P0 peut être revu et fusionné comme documentation.**

**A2-P1 reste bloqué.**

A2_BASE_SHA :

~~~text
NON DÉFINI — attendre A1 fusionné sur main et réaudit.
~~~
