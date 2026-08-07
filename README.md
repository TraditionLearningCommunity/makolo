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

## Installation locale

Créer un environnement virtuel :

```bash
python -m venv .venv

## Lancement local sous PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run_local.ps1
```

L'application est ensuite disponible sur <http://127.0.0.1:8765/>.

## Vérifications

```powershell
$env:DJANGO_DEBUG = "True"
$env:DJANGO_SECRET_KEY = "django-insecure-local-development-only-change-me"
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

Consultez `AUDIT_LOCAL.md` pour l'état fonctionnel, les corrections et les risques restants.
