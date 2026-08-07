# Makolo

Makolo est une plateforme intelligente de gestion événementielle, de billetterie numérique et de contrôle d’accès par QR code.

## Vision

Makolo couvre progressivement le cycle de vie d’un événement :

- création et publication d’événements ;
- gestion des catégories de billets ;
- inscriptions et ventes ;
- génération de tickets numériques ;
- QR codes uniques ;
- contrôle d’accès ;
- prévention du double scan ;
- paiements ;
- notifications ;
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

## Applications Django

- `core`
- `accounts`
- `events`
- `tickets`
- `scanner`
- `partners`
- `analytics_app`
- `payments`
- `notifications`

## État fonctionnel

Le socle comptes/authentification est actif et le premier module métier `events` est implémenté avec catégories, lieux, cycle de vie, permissions organisateur, API v1, administration Django, pages de gestion et tests.

Les modules `tickets`, `scanner`, `payments`, `notifications` et `analytics_app` restent les prochains chantiers métier.

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

## Environnement

En développement, Makolo utilise `DJANGO_ENV=development` par défaut. Les vraies clés et informations d'hébergement ne doivent jamais être versionnées.

Le fichier `.env.example` documente les variables de base. Le fichier `.env` réel est ignoré par Git.

## API

Les endpoints principaux de la v1 sont :

```text
/api/v1/accounts/
/api/v1/events/
/api/v1/events/categories/
/api/v1/events/venues/
```

L'inscription crée un compte sans émettre immédiatement de JWT. Les jetons sont obtenus explicitement via l'endpoint de connexion.

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
- domaine événementiel : `docs/architecture/events.md`.

Consultez également `AUDIT_LOCAL.md` pour l'état initial du projet avant la phase de durcissement du dépôt.
