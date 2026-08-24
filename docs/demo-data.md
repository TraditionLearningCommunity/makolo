# Données de démonstration Makolo

Le seed Makolo est un environnement de démonstration et de test manuel reproductible. Pour la bêta canonique, il ne cherche pas à peupler chaque modèle Django : il construit des scénarios produit cohérents à partir des domaines canoniques `Activity`, `Occurrence`, `Place`, `Journey`, `Offer`, `Capacity`, `CommerceOrder`, `Payment` et `Access`.

Aucune donnée réelle ne doit être utilisée. Les comptes, contacts, lieux métier et historiques du profil bêta sont fictifs ; les adresses e-mail utilisent le domaine réservé `.test`.

## Profil recommandé

Le profil de référence pour la bêta est `beta` :

```bash
python manage.py seed_makolo_demo --scale beta --as-of YYYY-MM-DD
```

Le mot de passe doit venir de `MAKOLO_DEMO_PASSWORD` ou de l'argument explicite `--demo-password`. Pour un reseed opérateur, préférer une saisie qui n'écrit pas le secret dans l'historique du shell :

```bash
read -s -p "Mot de passe bêta: " MAKOLO_DEMO_PASSWORD; echo
export MAKOLO_DEMO_PASSWORD
python manage.py seed_makolo_demo --scale beta --as-of YYYY-MM-DD
unset MAKOLO_DEMO_PASSWORD
```

`--as-of` est obligatoire. Il n'existe plus de date métier historique implicite. En déploiement réel, utiliser la date du reseed dans la timezone `Africa/Lubumbashi`. Les tests emploient une date fixe afin de rester déterministes.

Les profils `small`, `medium` et `large` restent disponibles pour des besoins de volume en développement ; ils ne définissent pas le contrat de la bêta canonique.

## Horizon temporel

Le profil `beta` contient de l'historique utile ainsi que des Occurrences autour de la date `as-of` et jusqu'à environ 30 jours : aujourd'hui lorsque pertinent, demain, week-end proche, +7, +14, +21 et +30 jours. L'objectif est que Discovery, Participant et les consoles restent intéressants plusieurs semaines après le reseed.

## Personas

Tous les comptes utilisent le mot de passe temporaire fourni séparément lors du reseed.

| Persona | Email | Autorité démontrée |
| --- | --- | --- |
| Makolo staff/admin | `beta.admin@makolo.test` | plateforme / Operations globale, sans Mandate Espace artificiel |
| Owner | `beta.owner@makolo.test` | propriété et administration complètes des Espaces bêta |
| Space admin | `beta.spaceadmin@makolo.test` | administration Espace sans `space.ownership.manage` |
| Event manager | `beta.eventmanager@makolo.test` | portefeuille d'activités de l'Espace Event |
| Transport operator | `beta.transport@makolo.test` | portefeuille d'activités de l'Espace Transport |
| Finance | `beta.finance@makolo.test` | commandes, paiements et analyses financières, sans CRM/Access/ownership |
| Marketing | `beta.marketing@makolo.test` | contacts, audiences et promotions, sans finances/Access/ownership |
| Access Manager | `beta.access@makolo.test` | gestion Access Espace, sans Finance/ownership |
| Activity-local manager | `beta.activitylocal@makolo.test` | Mandate limité à une Activity Transport |
| Scanner | `beta.scanner@makolo.test` | contrôle d'accès limité à des Activities assignées |
| Team-only | `beta.teamonly@makolo.test` | membre d'équipe sans Mandate, donc sans autorité métier |
| Participant | `beta.participant@makolo.test` | Discovery, démarches et accès personnels |

L'autorité professionnelle est seedée via `Mandate` / `Role` / `Permission` / scope. `TeamMembership` représente uniquement l'appartenance opérationnelle : elle ne donne aucun droit à elle seule. Le compte staff plateforme reste distinct des responsabilités Espace.

## Scénarios Event

Le seed fournit notamment :

- un Événement gratuit avec `Offer` à zéro, capacité et inscription, sans `Payment` fictif ;
- un Événement public payant avec `Offer`, `CapacityPool`, `Journey`, `CommerceOrder`, paiement sandbox confirmé et `Access` ;
- un scénario invitation avec `JourneyRequest` ;
- un Événement réellement complet via la capacité canonique ;
- un Événement public sans commerce ;
- quelques cas privé, non répertorié, annulé et historique sans polluer Discovery.

Event reste une verticale composée : le temps vient d'`Occurrence`, le prix d'`Offer`, la capacité de `CapacityPool`, le commerce de `CommerceOrder`/`Payment` et le billet d'`Access`.

## Scénarios Transport / Activity sans Event

Transport est seedé indépendamment d'Events. Ses `TransportService` composent de vraies `Activity` qui n'ont aucun `Event` associé. Le profil contient des trajets cohérents Lubumbashi ↔ Kolwezi, plusieurs départs sur l'horizon bêta, des Places avec coordonnées plausibles, des offres actives, de la capacité disponible et complète, un paiement en ligne et un paiement sur place.

Le parcours de preuve T22 réutilise directement le noyau canonique : `Activity → Occurrence → Journey → Capacity → CommerceOrder → Payment → Access → AccessUse`. Le contrôle de l'Access Transport passe par le service canonique de validation et par la permission Activity de scan ; aucun Ticket parallèle n'est créé.

Le paiement sur place reste une `CommerceOrder` en mode `on_site`; aucun faux `Payment` encaissé n'est créé pour la remplir. Le scénario Transport ne crée pas de `JourneyRequest` artificielle lorsque le workflow de réservation n'en a pas besoin.

## Participant

`beta.participant@makolo.test` contient un mélange de scénarios multi-verticaux : démarche à continuer, démarche confirmée, Event, Transport, billet valide, historique d'accès utilisé et notifications. Cela permet de tester `/me/`, Mes démarches, À venir, Mes accès et Notifications sans connaître les noms des modèles internes.

## Space Console

Les données bêta alimentent les surfaces utiles de la Console : activités, demandes, accès, tarifs, commandes, paiements, groupes, contacts, audience, promotions, lieux, contrôle d'accès, opérations, analyses, automation et équipe. Les personas Owner, Admin, Finance, Marketing, Access Manager et Activity-local ont volontairement des frontières d'autorisation différentes.

## Discovery

Les données publiques couvrent Event et Transport, plusieurs jours et localités, gratuit/payant, disponible/complet, carte et liste. Les objets privés, non répertoriés ou annulés ne sont pas créés pour artificiellement remplir les résultats publics.

## Scanner

Deux `Access` dédiés au smoke test historique sont produits, un pour Event et un pour Transport. T22 ajoute une preuve d'usage canonique hors Event en émettant un Access supplémentaire idempotent sur le Journey Transport puis en le contrôlant via `validate_access`. Les credentials proviennent du chemin canonique `AccessCredential`; aucun token QR brut n'est versionné dans Git.

## Validation

La commande read-only suivante vérifie le contrat de scénarios bêta :

```bash
python manage.py validate_makolo_demo --as-of YYYY-MM-DD
```

Elle contrôle notamment la matrice de personas et de Permissions, l'horizon Event/Transport, le gratuit/payant/on-site, la capacité complète, le Participant, le scanner, `TeamMembership != autorité`, l'isolation Activity-local, l'absence de dépendance Transport→Event, les flux canoniques hors Event et l'absence de deliveries externes en attente.

La CI prouve deux chemins indépendants sur bases fraîches :

- SQLite fraîche → `check` → `makemigrations --check --dry-run` → `migrate --plan` → migrations → seed → validation → second seed identique → validation → `PRAGMA integrity_check` ;
- PostgreSQL 16 fraîche → `check` → `makemigrations --check --dry-run` → `migrate --plan` → migrations → seed → validation → second seed identique → validation.

Les snapshots d'idempotence incluent notamment Activities, Occurrences, Capacity, Journeys, CommerceOrders, Payments, Access, AccessUse, Mandates et TeamMemberships.

## Idempotence, atomicité et side effects

Pour les mêmes paramètres (`scale`, `as-of`, mot de passe), les objets déterministes sont réutilisés et les volumes canoniques ne doivent pas dériver au second passage. Le seed s'exécute dans une transaction atomique : une erreur ne doit pas laisser une base partiellement construite.

Le profil bêta désactive les préférences de deliveries externes et ne laisse pas de `NotificationDelivery` queued/processing. Il ne doit envoyer ni e-mail réel, ni SMS, ni push, ni appel paiement ou webhook externe.

Le seed est une opération explicite de démonstration. Il ne doit jamais être ajouté au WSGI, à Autopilot, à un scheduler ou à chaque déploiement normal.
