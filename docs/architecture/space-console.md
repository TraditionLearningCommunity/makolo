# Space Console — Tâche 11

## Rôle

La Space Console est la couche d’application et de présentation professionnelle de Makolo. Elle ne constitue pas un nouveau bounded context et ne possède aucune règle métier parallèle.

```text
Profile
   │
 Mandate
   │
   ▼
Space Console
   │
   ├── Activities / Occurrences
   ├── Journeys / Requests
   ├── Access / AccessUse
   ├── Commerce / Payments / Capacity
   ├── Groups / CRM / Audiences / Promotions
   ├── Places
   ├── Operations / Scanner
   ├── Analytics
   └── Automation
```

Le principe UX est explicite : une même personne peut **agir en son nom** dans l’expérience participant ou **agir au nom d’un Espace** lorsqu’un Mandat lui donne l’autorité nécessaire.

Un Espace n’a ni mot de passe, ni session, ni compte utilisateur autonome. La vérité d’autorisation reste `Profile + Mandate + Scope`.

## Routes canoniques

Le point d’entrée professionnel est :

```text
/spaces/<space_slug>/
```

Les sections de Console sont sous ce contexte : overview, activities, requests, access, offers, orders, payments, groups, crm, audiences, promotions, places, control, operations, analytics, automation, team et settings.

`/dashboard/` n’est plus un dashboard professionnel autonome ; il conduit vers le contexte professionnel autorisé ou vers l’espace personnel.

## Switcher et sécurité

Le sélecteur « Agir au nom de » n’affiche jamais tous les Espaces Makolo. Il est construit à partir :

- des Mandats actifs de scope Espace ;
- des Mandats actifs de scope Activity et de leur Espace parent ;
- des affectations scanner actives lorsqu’elles donnent un accès opérationnel limité.

Le switcher est une aide de navigation, jamais une source d’autorisation. Chaque route reconstruit le contexte depuis le slug de route et vérifie le serveur.

Un Mandat Activity-only permet d’entrer dans l’Espace parent mais limite strictement les Activities et modules à la portée autorisée. Une URL directe vers une autre Activity ou un autre Espace est refusée.

`TeamMembership` et `GroupMembership` ne donnent aucune autorité Console.

## Navigation permission-aware

La sidebar est dérivée d’une matrice centralisée dans `SpaceConsoleContext`. Un module n’est présenté que lorsqu’une capacité réelle le justifie. Le masquage UI ne remplace pas les contrôles serveur.

Exemples :

- Finance : commandes, paiements et analyses autorisées, sans CRM, scanner ou édition d’Activity automatique ;
- Marketing : CRM, Audiences et Promotions, sans Payment ni Access ;
- Scanner : contrôle d’accès sur les Activities explicitement autorisées ;
- Activity Manager : Activities, Requests, Access, Commerce/Capacity et opérations selon ses permissions ;
- Owner/Admin : responsabilités globales de l’Espace via les rôles système.

## Sources canoniques

La Console lit directement :

- `Activity.space` et `Occurrence` pour l’offre d’activité et le calendrier ;
- `JourneyRequest` pour la boîte de Demandes ;
- `Access` / `AccessUse` pour les droits et leur utilisation ;
- `Offer` / `CapacityPool` pour les tarifs et la disponibilité ;
- `CommerceOrder` pour les commandes ;
- `Payment` pour les paiements réellement enregistrés ;
- `Group`, `CRMContact`, `AudienceSegment`, `Promotion` pour les publics ;
- `SpacePlace → Place` pour les lieux ;
- `OperationsIncident` pour l’exploitation ;
- les sources canoniques Journey / Access / CommerceOrder / Payment pour la synthèse Analytics ;
- `AutomationRule` / `AutomationExecution` pour les automatisations contrôlées.

Aucun compteur Console ne doit additionner simultanément Ticket + Access, TicketOrder + CommerceOrder ou ScanLog + AccessUse.

## Event comme verticale

Event reste une verticale concrète d’Activity. La Console générique peut ouvrir une Activity sans Event associé. Pour une Activity Event, le vocabulaire métier peut parler d’événement, billet ou participant lorsque cette contextualisation est utile.

La création « Événement » compose la verticale Event existante ; elle ne réintroduit pas Event comme propriétaire de l’Activity, de l’Occurrence, de la capacité, de la commande, du paiement ou de l’accès.

Cette propriété est le prérequis pour ajouter Transport comme nouvelle verticale en Tâche 12 sans créer une deuxième console.

## Mutations

La Console n’écrit pas directement les statuts métier :

- décisions de Demandes via les services Journey ;
- révocation d’accès via le service Access ;
- validation scanner via `AccessCredential → Access → AccessUse` ;
- création Event via le service de composition Event ;
- mutations Geography via les services Place/SpacePlace existants.

Les domaines ne doivent jamais importer la Space Console.

## Base de données et données de démonstration

> Makolo étant encore en construction et sans données de production à préserver, la Tâche 11 privilégie le schéma et l’expérience cibles plutôt que des couches de compatibilité destinées à conserver d’anciennes données de démonstration.

Une base de développement ou bêta peut être supprimée, recréée, migrée puis reseedée. Aucun backfill complexe ne doit être ajouté uniquement pour préserver de faux utilisateurs, commandes, billets ou événements.

L’historique Git et les migrations Django ne sont toutefois pas réécrits massivement sans nécessité : la suppression du legacy reste ciblée et explicite.

## Legacy professionnel supprimé

La Tâche 11 retire comme surfaces professionnelles centrales :

- l’ancien dashboard Event/Ticket/TicketOrder ;
- le détail privé Organization centré sur Events ;
- la liste Lieux professionnelle parallèle à la Console ;
- la navigation globale composée de modules techniques Events.

Les éventuels modèles de projection encore consommés par des verticales existantes ne doivent jamais redevenir une autorité de la Console. Lorsqu’un consommateur réel disparaît, la projection doit être supprimée plutôt que conservée par prudence.

## Tâche 28 — Teams et opérations mobiles

T28 rend exploitable le modèle Team déjà présent sans créer de nouveau modèle d’autorité.

- Une `Team` appartient à un seul `Space`.
- Un Space possède une **Équipe principale** (`is_default=True`) et peut posséder plusieurs Teams secondaires.
- `TeamMembership` signifie uniquement « cette personne collabore dans cette Team ».
- `TeamMembership` n’accorde aucune Permission et ne contient aucun rôle métier parallèle.
- Les responsabilités Space et Activity restent exclusivement des `Mandate`.
- Retirer une personne d’une Team secondaire ne touche ni ses autres Teams ni ses Mandates.
- **Retirer de l’Espace** est une opération distincte : elle désactive toutes les TeamMemberships de cet Espace et révoque les Mandates Space ainsi que les Mandates Activity des Activities de cet Espace, sans toucher les autres Espaces.
- L’Équipe principale ne peut pas être archivée comme une Team secondaire et la protection du dernier Owner repose sur les Mandates canoniques.

La section Team de la Console affiche séparément la Team principale, les Teams secondaires et les responsabilités. Un Profile peut appartenir à plusieurs Teams sans duplication de User ni duplication automatique de Mandate.

`Group` reste la communauté/population de T27 ; `Team` reste la collaboration interne d’un Space. Un Groupe cross-owner utilisé par une Activity n’est jamais converti en Team ni en Groupe possédé par le Space.

### Scope Activity-local

`SpaceConsoleContext` reste l’unique matrice de navigation. Un Profile `activity-finance` peut atteindre la surface Paiements parce que son rôle possède `activity.finance.view`, mais les selectors filtrent les paiements sur les Activities pour lesquelles cette Permission est réellement accordée. Une autre Activity visible pour une responsabilité différente ne fuit pas dans les paiements.

Les Mandates expirés, futurs ou révoqués ne doivent pas ouvrir la Console ou ses modules. `TeamMembership` seule et `GroupMembership` seule ne suffisent jamais.

### Contrat mobile opérationnel

La Console doit rester utilisable sur petits écrans sans créer une seconde navigation. Les titres Space/Activity peuvent se replier sur plusieurs lignes, la navigation mobile expose son état d’ouverture aux technologies d’assistance et les actions terrain gardent des cibles tactiles utilisables.

Le Scanner reste générique `Activity/Occurrence` et conserve la vérité `Access → AccessCredential → AccessUse`. T28 améliore uniquement l’expérience terrain : caméra arrière préférée lorsque disponible, picker existant, torch conditionnel, fallback image et manuel, résultat textuel accessible, `Scanner le suivant` dominant et feedback tactile facultatif lorsque `navigator.vibrate` est disponible. Le succès reste figé jusqu’à l’action explicite suivante et les tracks caméra sont arrêtés lors de la sortie de page.

## Hors scope

Transport, Vehicle, Seat, Route, Stop, découverte spatio-temporelle globale, PostGIS, Product Language global, nouveau CRM, nouveau moteur Analytics, nouveau provider Payment et workflow builder avancé restent hors Tâche 11.

Pour T28 spécifiquement, restent hors scope : Team Activity dédiée, hiérarchie récursive de Teams, invitation externe d’identité non existante, scanner offline/PWA, refonte des moteurs T23/T25/T26/T27 et hub personnel T29.