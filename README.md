# Makolo

Makolo est une plateforme intelligente de gestion événementielle, de billetterie numérique, de paiements, de notifications et de contrôle d’accès par QR code.

## Vision

Makolo couvre progressivement le cycle de vie d’un événement :

- création et publication d’événements ;
- gestion des catégories de billets ;
- inscriptions et ventes ;
- génération de tickets numériques ;
- QR codes uniques ;
- paiements ;
- notifications transactionnelles et rappels ;
- contrôle d’accès ;
- prévention du double scan ;
- tableaux de bord et analytics.

## Stack actuelle

- Python 3.10
- Django 5.2
- Django REST Framework
- Django Templates
- HTMX
- Alpine.js
- Tailwind CSS
- SQLite pour le développement initial
- PostgreSQL recommandé pour la production et les opérations concurrentes

## Applications Django

- `core`
- `accounts`
- `events`
- `tickets`
- `scanner`
- `payments`
- `notifications`
- `partners`
- `analytics_app`

## État fonctionnel

Les domaines `accounts`, `events`, `tickets`, `scanner`, `payments` et `notifications` sont actifs. La chaîne principale couvre maintenant la création d’un événement, la réservation de billets, les commandes gratuites ou payantes, l’émission de QR, le paiement sandbox ou manuel, les remboursements complets contrôlés, les notifications transactionnelles, les rappels d’événements et le contrôle d’accès anti-double-scan.

Les prochains chantiers métier sont `analytics_app` et `partners`, puis les adaptateurs de paiement externes réels et les canaux SMS/push.

## Installation locale sous PowerShell

Créer et activer un environnement Python dédié, puis installer les dépendances :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Préparer la base de données et démarrer le serveur :

```powershell
python manage.py migrate
python manage.py runserver
```

L'application est disponible sur <http://127.0.0.1:8000/>.

Le script `run_local.ps1` reste disponible pour le flux local historique sur le port `8765`.

## Vérifications avant commit

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python -m pip check
```

Pour libérer le stock des commandes payantes arrivées à expiration :

```powershell
python manage.py expire_ticket_orders
```

Pour envoyer les notifications en attente :

```powershell
python manage.py process_notifications --limit 100
```

Pour créer les rappels d’événements à 24 h :

```powershell
python manage.py schedule_event_reminders --hours-before 24 --window-minutes 60
python manage.py process_notifications --limit 100
```

## Environnement

En développement, Makolo utilise `DJANGO_ENV=development` par défaut. Les vraies clés et informations d'hébergement ne doivent jamais être versionnées.

Le fichier `.env.example` documente les variables de base. Le fichier `.env` réel est ignoré par Git.

Le fournisseur de paiement `sandbox` est actif par défaut uniquement lorsque `DEBUG=True`. Le webhook sandbox peut être signé avec la variable d’environnement :

```text
PAYMENTS_WEBHOOK_SECRET
```

Aucun numéro de carte, CVV ou secret bancaire n’est stocké par Makolo.

En développement, les e-mails sont écrits dans la console par le backend Django. En production, configurez le SMTP via les variables `DJANGO_EMAIL_*` déjà prévues dans `config/settings.py`.

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

L'inscription crée un compte sans émettre immédiatement de JWT. Les jetons sont obtenus explicitement via l'endpoint de connexion.

## Paiements

Une commande payante reste `pending` et réserve son stock jusqu’au paiement ou à son expiration. Une transaction réussie confirme la commande et émet les billets. Les confirmations directes de commandes payantes ont été retirées de l’API `tickets` afin que ce changement d’état passe par le domaine `payments`.

Le sandbox permet de tester le cycle complet sans argent réel. Le mode `manual` est réservé aux organisateurs/staff pour les encaissements vérifiés hors plateforme.

## Notifications

Le centre de notifications est disponible sous `/notifications/`. La cloche de la navbar affiche le nombre de messages non lus. Les confirmations de billets gratuits, paiements réussis/échoués/remboursés et rappels d’événements sont dédupliqués et créés après commit de la transaction métier.

Les e-mails passent par une file persistante `NotificationDelivery` avec retry et respect des préférences/heures silencieuses. SMS et push sont prévus dans le modèle mais pas encore branchés à un fournisseur réel.

## Contrôle d’accès

La console web est disponible sous `/scanner/`. Un agent doit avoir le rôle `scanner-agent` et une affectation active pour l’événement. Les organisateurs peuvent contrôler leurs propres événements et le staff dispose du périmètre global.

Le QR est toujours validé côté serveur. Le premier scan valide marque le billet `used`; les scans suivants sont rejetés et journalisés comme doublons.

## CI

GitHub Actions exécute automatiquement sur les Pull Requests vers `main` :

- installation des dépendances ;
- `pip check` ;
- contrôles Django ;
- vérification des migrations ;
- migrations ;
- tests Django.

## Architecture

- rôles et permissions : `docs/architecture/accounts-rbac.md` ;
- domaine événementiel : `docs/architecture/events.md` ;
- billetterie et QR : `docs/architecture/tickets.md` ;
- contrôle d’accès et anti-double-scan : `docs/architecture/scanner.md` ;
- paiements, webhooks et remboursements : `docs/architecture/payments.md` ;
- notifications, outbox, e-mails et rappels : `docs/architecture/notifications.md`.

Consultez également `AUDIT_LOCAL.md` pour l'état initial du projet avant la phase de durcissement du dépôt.
