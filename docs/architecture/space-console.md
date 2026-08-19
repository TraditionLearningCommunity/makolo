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

## Hors scope

Transport, Vehicle, Seat, Route, Stop, découverte spatio-temporelle globale, PostGIS, Product Language global, nouveau CRM, nouveau moteur Analytics, nouveau provider Payment et workflow builder avancé restent hors Tâche 11.
