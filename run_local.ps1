$ErrorActionPreference = "Stop"

$env:DJANGO_DEBUG = "True"
$env:DJANGO_SECRET_KEY = "django-insecure-local-development-only-change-me"
$env:DJANGO_ALLOWED_HOSTS = "127.0.0.1,localhost"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Environnement absent. Exécutez : python -m venv .venv"
}

& $python "$PSScriptRoot\manage.py" migrate
& $python "$PSScriptRoot\manage.py" runserver 127.0.0.1:8765
