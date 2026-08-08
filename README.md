# Makolo

Makolo est une plateforme événementielle multi-organisateurs : événements, équipes, billetterie numérique, paiements, notifications, automatisations et contrôle d’accès par QR code.

## Vision

Makolo n'est pas le back-office d'une seule société. Un utilisateur peut être participant, créer une organisation, rejoindre l'équipe d'un autre organisateur ou exercer un rôle limité (événements, finance, communication, accès) sans devenir administrateur de la plateforme.

La chaîne fonctionnelle couvre maintenant :

- organisations et équipes organisatrices ;
- création et publication d’événements ;
- catégories de billets, stock et capacité ;
- commandes gratuites ou payantes ;
- paiements sandbox/manuels et remboursements contrôlés ;
- génération de tickets et QR uniques ;
- contrôle d’accès anti-double-scan ;
- notifications transactionnelles ;
- Makolo Autopilot pour les tâches temporelles et réactives.

## Stack actuelle

- Python 3.10
- Django 5.2
- Django REST Framework
- Django Templates
- HTMX
- Alpine.js
- Tailwind CSS
- SQLite pour le développement initial
- PostgreSQL recommandé en production, notamment pour les opérations concurrentes

## Applications Django

- `core`
- `accounts`
- `organizations`
- `events`
- `tickets`
- `scanner`
- `payments`
- `notifications`
- `automation`
- `partners`
- `analytics_app`

## Organisations et droits

`is_staff` et `is_superuser` sont des privilèges de **plateforme Makolo**. Ils ne sont pas nécessaires pour organiser un événement.

Une `Organization` possède sa propre équipe :

- Owner : propriété de l'espace organisateur ;
- Admin : équipe et paramètres de l'organisation ;
- Event manager : événements et billetterie ;
- Finance : commandes, paiements et remboursements ;
- Marketing : communication et futures fonctions CRM ;
- Scanner manager : contrôle d'accès et agents scanner.

Les événements existants sont automatiquement rattachés à une organisation personnelle lors de la migration vers ce modèle.

## Makolo Autopilot

Les opérations récurrentes ne doivent pas dépendre d'un développeur. En production, un worker persistant tourne à côté du serveur web :

```text
python manage.py autopilot_worker --poll-seconds 30 --delivery-limit 100
```

Il exécute automatiquement :

- expiration des commandes non payées et libération du stock ;
- traitement/retry de la file de notifications ;
- rappels configurables à J-7, H-24 et H-2 ;
- alertes de remplissage ;
- alertes de stock faible ;
- fermeture automatique des ventes au démarrage ;
- passage automatique de l'événement à `completed` après sa fin ;
- suivi post-événement.

L'organisateur configure ses règles dans l'interface :

```text
/autopilot/events/<event-slug>/
```

Le moteur décide ensuite quand les exécuter. `run_autopilot` reste disponible pour un cron ou le diagnostic, mais ce n'est pas une action quotidienne d'un développeur.

Des exemples de déploiement sont fournis dans :

```text
deploy/systemd/makolo-autopilot.service.example
deploy/cron/makolo-autopilot.cron.example
```

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

L'application est disponible sur <http://127.0.0.1:8000/>.

Pour observer Autopilot en développement, lancer **dans un second terminal** :

```powershell
python manage.py autopilot_worker --poll-seconds 10
```

Ce second processus simule le worker qui sera géré automatiquement par le système de déploiement en production.

## Vérifications avant commit

```powershell
python -m pip check
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

## Environnement

En développement, Makolo utilise `DJANGO_ENV=development` par défaut. Les vraies clés et informations d'hébergement ne doivent jamais être versionnées.

`.env.example` documente notamment :

- URL publique Makolo ;
- sandbox et secret webhook Payments ;
- paramètres SMTP de production.

Le fournisseur de paiement `sandbox` reste réservé au développement/test sauf activation explicite. Aucun PAN, CVV ou secret bancaire n'est stocké par Makolo.

## API

Les endpoints principaux de la v1 sont :

```text
/api/v1/accounts/
/api/v1/events/
/api/v1/events/categories/
/api/v1/events/venues/
/api/v1/tickets/types/
/api/v1/tickets/orders/
/api/v1/tickets/tickets/
/api/v1/scanner/events/
/api/v1/scanner/assignments/
/api/v1/scanner/logs/
/api/v1/scanner/scan/
/api/v1/payments/configuration/
/api/v1/payments/payments/
/api/v1/payments/events/
/api/v1/payments/webhooks/sandbox/
/api/v1/notifications/
/api/v1/notifications/unread-count/
```

## Notifications

Le centre de notifications est disponible sous `/notifications/`. Les e-mails passent par une outbox persistante `NotificationDelivery` avec retry et respect des préférences/heures silencieuses. Autopilot consomme cette file automatiquement en production. SMS et push sont préparés mais aucun fournisseur externe n'est simulé.

## Contrôle d’accès

Le QR est validé côté serveur. Le premier scan valide marque le billet `used`; les scans suivants sont rejetés et journalisés. Un `Scanner manager` d'organisation peut administrer l'accès sans obtenir les droits finance ou plateforme.

## Prochains axes produit

La nouvelle frontière `Organization -> Events` et Autopilot préparent :

- listes d'attente automatiques ;
- transfert sécurisé de billets ;
- CRM événementiel ;
- abonnements/followers d'organisateurs ;
- codes ambassadeurs et affiliation ;
- intelligence des flux d'entrée ;
- analytics et prévisions de remplissage ;
- recommandations et découverte sociale d'événements.

## CI

GitHub Actions vérifie automatiquement chaque Pull Request vers `main` : dépendances, contrôles Django, cohérence des migrations, application des migrations et tests.

## Architecture

- rôles historiques : `docs/architecture/accounts-rbac.md` ;
- domaine événementiel : `docs/architecture/events.md` ;
- billetterie et QR : `docs/architecture/tickets.md` ;
- contrôle d’accès : `docs/architecture/scanner.md` ;
- paiements : `docs/architecture/payments.md` ;
- notifications : `docs/architecture/notifications.md` ;
- organisations, équipes et Autopilot : `docs/architecture/platform-autopilot-organizations.md`.
