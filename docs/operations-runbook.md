# Makolo — Operations Runbook

Ce document est la procédure de référence pour exploiter Makolo pendant la bêta et préparer un futur hébergement plus robuste. Il remplace les anciennes habitudes de déploiement implicites.

## 1. Architecture opérationnelle actuelle

### 1.1 Travail synchrone

Les opérations suivantes sont exécutées dans la requête Django qui les déclenche :

- inscription, login et gestion du compte ;
- demande de réinitialisation de mot de passe et tentative d'envoi de son e-mail ;
- création/annulation de commande ;
- confirmation du paiement sandbox ou manuel ;
- émission des billets lors de la confirmation de commande/paiement ;
- remboursement et annulation cohérente des billets ;
- scan QR et création du `ScanLog` ;
- validation des uploads ;
- vues Operations et dashboards.

Les parcours paiement → commande → billet et scan → billet utilisé → `ScanLog` sont protégés par des transactions métier. Sur SQLite, `select_for_update()` ne fournit pas le même verrouillage ligne-à-ligne que PostgreSQL : garder un seul scheduler Autopilot et éviter les écritures concurrentes inutiles.

### 1.2 Travail différé

Les `NotificationDelivery` e-mail en état `queued` sont réellement envoyées par le dispatcher de notifications, normalement appelé par Autopilot. Une notification en file n'est **pas** envoyée par magie.

Si Autopilot ne tourne jamais :

- les livraisons e-mail `queued` restent en attente ;
- les retries e-mail ne sont pas traités ;
- les rappels événement ne sont pas créés à temps ;
- les expirations de commandes/transferts et promotions de waitlist sont retardées ;
- les campagnes/workflows CRM planifiés sont retardés ;
- les règles de capacité, stock, fermeture des ventes et complétion d'événement sont retardées.

SMS et Push restent visibles dans les préférences mais ne sont pas implémentés ; ces canaux sont volontairement `skipped` par le socle actuel.

### 1.3 Travail récurrent réel

Le job fonctionnel à planifier est **Autopilot**. Il agrège les opérations récurrentes déjà existantes :

| Commande | Usage | Fréquence recommandée | Idempotence | Si absente |
|---|---|---|---|---|
| `python manage.py autopilot_worker --poll-seconds 30 --delivery-limit 100` | mode persistant préféré | continu, Always-on task | oui via états/dedup keys | files et automations prennent du retard |
| `python manage.py run_autopilot --delivery-limit 100 --record-scheduled-heartbeat --instance-id pythonanywhere-hourly` | fallback one-shot PythonAnywhere | toutes les heures | oui | retard pouvant aller jusqu'au prochain cycle |
| `python manage.py process_notifications` | diagnostic/manual seulement | non planifiée si Autopilot tourne | oui | n/a |
| commandes de rappel spécialisées | diagnostic/manual seulement | non planifiées si Autopilot tourne | dédupliquées selon leur contrat | n/a |

Ne pas lancer simultanément un worker persistant et un `run_autopilot` horaire : sur SQLite cela augmente inutilement la concurrence d'écriture. Ne pas ajouter `process_notifications` ou une commande de reminders en parallèle juste « par sécurité » : Autopilot les couvre déjà.

Le cycle Autopilot est conçu pour être court sur la taille bêta. Il borne les livraisons par `--delivery-limit` et ne reparcourt plus tout l'historique des événements terminés : le rattrapage post-événement est borné aux 30 derniers jours. Surveiller le temps réel dans les logs ; il n'existe pas de SLA de durée garanti.

### 1.4 Dépendances spécifiques à PythonAnywhere

Le cœur métier ne dépend pas de PythonAnywhere. Les éléments spécifiques à l'hébergement courant sont :

- le WSGI configuré dans l'onglet **Web** ;
- le virtualenv `/home/makolo/.virtualenvs/makolo` ;
- le checkout courant `/home/makolo/makolo` ;
- les mappings de fichiers statiques/médias de l'onglet Web si utilisés ;
- Always-on Tasks ou Scheduled Tasks dans l'onglet **Tasks** ;
- les logs et quotas disque PythonAnywhere ;
- le bouton **Reload** de l'application Web.

Le fichier `passenger_wsgi.py` du dépôt est désormais portable et ne contient aucun username PythonAnywhere. Sur PythonAnywhere, le **fichier WSGI affiché par l'onglet Web est la source de vérité**.

Références officielles :

- Environment variables : https://help.pythonanywhere.com/pages/EnvironmentVariables/
- Scheduled Tasks : https://help.pythonanywhere.com/pages/ScheduledTasks
- Always-on Tasks : https://help.pythonanywhere.com/pages/AlwaysOnTasks/
- Timezone : https://help.pythonanywhere.com/pages/SettingTheTimezone/

## 2. Variables d'environnement

`.env.example` est la référence exhaustive et ne contient que des valeurs fictives. Le vrai `.env` est ignoré par Git.

### Obligatoires en `production`

- `DJANGO_ENV=production`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `MAKOLO_PUBLIC_BASE_URL` : URL HTTPS absolue
- `PAYMENTS_WEBHOOK_SECRET` si `PAYMENTS_SANDBOX_ENABLED=True`

`DJANGO_CSRF_TRUSTED_ORIGINS` est recommandé ; si absent en production il reprend `MAKOLO_PUBLIC_BASE_URL`.

### Base de données

Actuel :

```text
DJANGO_DATABASE_ENGINE=sqlite
DJANGO_DB_PATH=/home/makolo/makolo/db.sqlite3
DJANGO_SQLITE_TIMEOUT_SECONDS=20
```

Futur PostgreSQL : `DJANGO_DATABASE_ENGINE=postgresql` et variables `DJANGO_DATABASE_NAME`, `USER`, `PASSWORD`, `HOST`, `PORT`. Le passage à PostgreSQL n'est **pas** une étape du déploiement PythonAnywhere actuel.

### E-mail

En développement/test, Console/locmem/file backend est normal. Pour la bêta PythonAnywhere sans provider réel, définir explicitement :

```text
DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

Pour une production e-mail réelle, configurer par environnement le backend SMTP (ou futur provider) et `DJANGO_EMAIL_HOST`, `PORT`, TLS/SSL, utilisateur, mot de passe et `DJANGO_DEFAULT_FROM_EMAIL`. Aucun provider externe n'est imposé par le code.

Toutes les URLs Makolo générées par les e-mails utilisent `MAKOLO_PUBLIC_BASE_URL`. Aucun ancien domaine n'est un fallback de production.

### Fichiers, logs et sessions

Les variables facultatives sont documentées dans `.env.example`, notamment `DJANGO_MEDIA_ROOT`, `DJANGO_STATIC_ROOT`, `MAKOLO_BACKUP_DIR`, limites d'upload, rotation logs et durée de session.

## 3. Configuration PythonAnywhere unique

### 3.1 Fichier `.env`

Créer `/home/makolo/makolo/.env`, ne jamais le commiter, et limiter ses permissions :

```bash
cd /home/makolo/makolo
cp .env.example .env
chmod 600 .env
```

Remplacer les valeurs fictives par les vraies valeurs du déploiement.

### 3.2 Chargement `.env` dans le WSGI Web

Dans **PythonAnywhere > Web > WSGI configuration file**, avant l'import/application Django :

```python
import os
import sys
from dotenv import load_dotenv

project_folder = "/home/makolo/makolo"
if project_folder not in sys.path:
    sys.path.insert(0, project_folder)

load_dotenv(os.path.join(project_folder, ".env"), override=False)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

Le package `python-dotenv` est épinglé dans `requirements.txt`.

Pour les consoles et tâches, charger le même fichier :

```bash
set -a; source /home/makolo/makolo/.env; set +a
```

On peut ajouter cette ligne au `postactivate` du virtualenv si souhaité.

### 3.3 Static et media

Makolo sépare :

- `STATIC_ROOT` : `/home/makolo/makolo/staticfiles` par défaut ;
- `MEDIA_ROOT` : `/home/makolo/makolo/media` par défaut.

`collectstatic` n'écrit jamais dans `MEDIA_ROOT`.

En `DEBUG=False`, Django ne sert pas automatiquement `/media/`. Sur PythonAnywhere, configurer dans **Web > Static files** :

```text
URL       Directory
/media/   /home/makolo/makolo/media
```

Les statiques applicatifs sont compatibles WhiteNoise après `collectstatic`; si un mapping PythonAnywhere `/static/` existe déjà, il doit pointer vers `/home/makolo/makolo/staticfiles` et rester cohérent avec le déploiement.

Les médias utilisateurs doivent être sauvegardés séparément de la base. Plus tard, `MEDIA_ROOT`/storage pourra être remplacé par un object storage sans transformer les médias en statiques versionnés.

## 4. Déploiement PythonAnywhere

Après un merge validé :

```bash
cd ~/makolo
source ~/.virtualenvs/makolo/bin/activate
set -a; source .env; set +a

git checkout main
git pull origin main
python -m pip install -r requirements.txt
python -m pip check
python manage.py check
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

Puis **PythonAnywhere > Web > Reload**.

Vérifier ensuite :

```bash
python manage.py check --deploy
python manage.py showmigrations --plan
```

Et appeler :

```text
/api/v1/health/       # liveness Django
/api/v1/readiness/    # Django + requête DB minimale
```

Ne pas exécuter npm, Playwright, Chromium ou le seed démo pendant ce déploiement.

## 5. Scheduler PythonAnywhere

### Option A — compte payant : Always-on Task, recommandé

Dans **Tasks > Always-on**, utiliser une commande unique :

```bash
bash -lc 'set -a; source /home/makolo/makolo/.env; set +a; exec /home/makolo/.virtualenvs/makolo/bin/python -u /home/makolo/makolo/manage.py autopilot_worker --poll-seconds 30 --delivery-limit 100'
```

PythonAnywhere redémarre une Always-on Task en cas de crash/maintenance. Surveiller son état et son log.

### Option B — fallback : Scheduled Task horaire

Sur un compte qui permet les tâches horaires, créer **une** tâche toutes les heures, par exemple à `:05` :

```bash
bash -lc 'cd /home/makolo/makolo && set -a; source .env; set +a; /home/makolo/.virtualenvs/makolo/bin/python manage.py run_autopilot --delivery-limit 100 --record-scheduled-heartbeat --instance-id pythonanywhere-hourly'
```

Le rappel H-2 tolère ce rythme horaire. Le `WorkerHeartbeat` enregistré est un heartbeat de job one-shot et revient à `stopped` après un cycle sain ; il ne prétend pas qu'un worker persistant existe.

Les comptes PythonAnywhere gratuits récents n'ont pas de Scheduled Tasks ; les anciens comptes gratuits n'ont qu'une tâche quotidienne. Un rythme quotidien n'est pas suffisant pour garantir les rappels H-2 et les délais de queue attendus. Pour une bêta avec fonctionnalités temporelles, utiliser une offre donnant accès à Always-on ou au scheduling horaire, ou accepter explicitement la dégradation.

PythonAnywhere utilise UTC côté serveur par défaut. Makolo stocke des datetimes timezone-aware et Django utilise `Africa/Lubumbashi` par défaut pour l'affichage. Les règles métier ne doivent pas dépendre de l'heure locale du shell.

## 6. Sauvegarde SQLite

### Sauvegarde cohérente

Ne pas documenter `cp db.sqlite3 backup.sqlite3` comme stratégie de sauvegarde à chaud. Utiliser :

```bash
cd /home/makolo/makolo
source /home/makolo/.virtualenvs/makolo/bin/activate
set -a; source .env; set +a
python manage.py backup_database
```

La commande :

- utilise l'API de backup SQLite sur la connexion vivante ;
- écrit d'abord un fichier temporaire ;
- exécute `PRAGMA integrity_check` sur la copie ;
- renomme atomiquement le fichier vérifié ;
- n'écrase pas silencieusement une sauvegarde portant le même timestamp ;
- affiche le chemin final.

Le répertoire par défaut est `MAKOLO_BACKUP_DIR` (`backups/`). Il est ignoré par Git.

### Fréquence

Pour des données bêta réelles : au minimum une sauvegarde DB quotidienne **et** une sauvegarde avant une opération à risque/déploiement important. Une copie présente uniquement sur le même disque PythonAnywhere ne protège pas contre la perte du compte/disque : exporter régulièrement une copie hors PythonAnywhere selon le processus opérateur.

Les fichiers `media/` doivent être sauvegardés dans la même politique de rétention, mais séparément de SQLite.

### Restauration testable

1. Désactiver temporairement le worker/scheduler pour stopper les écritures de fond.
2. Noter le SHA déployé et faire une sauvegarde de sécurité de l'état courant.
3. Vérifier le backup choisi avec SQLite si nécessaire.
4. Remplacer `DJANGO_DB_PATH` par une copie du backup restauré, ou restaurer le fichier à l'emplacement configuré **application arrêtée**.
5. Exécuter :

```bash
python manage.py check
python manage.py migrate --plan
python manage.py migrate --noinput
```

6. Vérifier `/api/v1/readiness/`, quelques données attendues et l'admin.
7. Reload Web puis réactiver exactement un scheduler Autopilot.

La CI teste qu'un backup produit est une base SQLite lisible, intègre et contenant le schéma Makolo.

## 7. Médias et uploads

Uploads actuellement protégés :

- avatar : 5 Mo, JPEG/PNG/WebP, image réellement décodable ;
- couverture événement : 8 Mo, JPEG/PNG/WebP, image réellement décodable ;
- document de vérification : 10 Mo, PDF/JPEG/PNG ; signature PDF minimale vérifiée et images décodées ;
- noms contenant des séparateurs de chemin rejetés.

Django/storage normalise aussi les noms de fichiers ; aucun QR utilisateur n'est accepté comme upload. Les QR billets sont générés à la demande à partir du token et ne sont pas des médias versionnés.

Surveiller `media/` et le quota disque ; l'object storage est une étape future, pas une exigence de cette bêta.

## 8. E-mail et notifications

Le reset password est synchrone et ne révèle pas l'existence du compte. Une panne backend e-mail est journalisée sans token ni adresse et ne transforme pas la page publique en fuite d'information.

Les autres notifications peuvent créer une `NotificationDelivery` e-mail `queued`. Autopilot les prend par lots, marque `processing`, retente avec délai croissant puis passe `failed` quand `max_attempts` est atteint. Une livraison restée `processing` après interruption est récupérée par Autopilot.

À surveiller :

- nombre de deliveries `queued/processing` en retard ;
- `failed` sur 24 h ;
- dernière exécution Autopilot ;
- backend e-mail réellement configuré avant d'ouvrir une fonctionnalité qui promet un e-mail externe.

## 9. Health et readiness

- `/api/v1/health/` : liveness uniquement. Aucun accès DB, aucun secret.
- `/api/v1/readiness/` : `SELECT 1` minimal. Répond 503 avec un corps générique si la DB n'est pas accessible.

Une panne d'un service facultatif (par exemple un futur SMTP) ne met pas la readiness à down.

## 10. Logs et diagnostic d'un 500

Logs applicatifs locaux par défaut :

- `logs/django.log` ;
- `logs/security.log`.

Ils tournent par défaut à 5 MiB avec 5 archives, réglables par env. PythonAnywhere possède en plus ses propres server/error/access logs ; utiliser les deux sources.

Un 500 web affiche un identifiant `MKL-XXXXXX`. Pour le diagnostiquer :

1. noter l'heure, URL et identifiant MKL affiché ;
2. chercher l'identifiant dans `logs/django.log` et le log erreur PythonAnywhere ;
3. corréler avec les opérations paiement/scanner/automation proches ;
4. ne jamais coller dans un ticket un header Authorization, cookie, token QR, token reset ou secret webhook.

Un filtre de redaction best-effort masque dans les logs applicatifs les tokens reset dans leurs URLs, Bearer tokens, passwords, secrets, signatures et cookies usuels. Il ne remplace pas la règle « ne jamais logger un secret » dans le code.

## 11. Données sensibles

Ne jamais journaliser :

- mot de passe ;
- header `Authorization`/JWT ;
- cookie ou session id ;
- token password reset ;
- QR token brut ;
- secret/signature webhook ;
- données carte/paiement sensibles.

Le scanner conserve une empreinte SHA-256 du token présenté dans le `ScanLog`, pas le token QR brut.

Les payloads webhook sauvegardés sont réduits à une liste blanche de champs métier ; le secret de signature n'est jamais stocké dans l'événement.

## 12. Rate limiting et abus

DRF conserve ses throttles existants. Les formulaires web publics sensibles disposent aussi d'une protection légère :

- login : 10 tentatives/minute par IP **et** identité de compte ;
- inscription : 5/heure par IP ;
- password forgot : 5/heure par IP **et** cible e-mail.

Cette protection web utilise le cache Django local : c'est une défense **best-effort mono-instance**, pas un mécanisme distribué absolu. Lors d'un futur déploiement multi-instance, déplacer ce quota vers un cache partagé/proxy/WAF adapté au lieu d'introduire Redis uniquement pour la bêta actuelle.

## 13. Sessions et cookies

En production :

- cookies session et CSRF `Secure` ;
- session `HttpOnly` ;
- `SameSite=Lax` ;
- HTTPS redirect et HSTS selon settings/env ;
- durée session configurable, 14 jours par défaut ;
- password reset timeout 1 heure par défaut.

Les environnements test/E2E gardent les cookies non-Secure afin de ne pas casser localhost.

## 14. Paiement sandbox / webhooks

Le sandbox reste le provider actuel. Le webhook :

- exige une signature HMAC valide ;
- compare la signature en temps constant ;
- conserve un hash SHA-256 du payload ;
- impose l'unicité de `event_id` ;
- accepte un replay seulement s'il est signé et que le payload est exactement identique ;
- refuse la réutilisation d'un `event_id` avec un autre payload ;
- verrouille le paiement pendant le traitement ;
- reste idempotent ;
- ne loggue/stocke pas le secret webhook.

Aucun vrai provider externe n'est ajouté par ce runbook.

## 15. SQLite aujourd'hui, PostgreSQL demain

### SQLite bêta

SQLite reste officiellement le moteur PythonAnywhere actuel. Mesures de prudence :

- timeout de verrou configurable (20 s par défaut) ;
- transactions critiques courtes ;
- un seul Autopilot actif ;
- listes importantes paginées ou explicitement bornées ;
- historique Autopilot terminé borné à 30 jours ;
- backup online par API SQLite ;
- surveiller quota, taille DB et durée des requêtes Operations/Discovery.

`select_for_update()` n'apporte pas les mêmes garanties de verrouillage sous SQLite que sous PostgreSQL. Les contraintes/idempotency DB et transactions restent donc essentielles.

### Portabilité PostgreSQL

La configuration accepte PostgreSQL mais PythonAnywhere reste SQLite. La CI lance un service PostgreSQL 16 en parallèle, applique toutes les migrations et exécute un smoke ciblé sur les domaines opérationnels/transactionnels.

Au futur basculement :

1. provisionner PostgreSQL et sauvegardes natives ;
2. tester migration/copie de données hors production ;
3. définir les variables `DJANGO_DATABASE_*` ;
4. utiliser `pg_dump`/outil provider au lieu de `backup_database` ;
5. relancer toute la suite CI et un E2E de validation ;
6. revalider les zones `select_for_update`, transactions et JSON/datetime.

Aucun SQL métier SQLite-only n'est volontairement ajouté dans cette passe. Les `PRAGMA` restent confinés au backup/test SQLite.

## 16. Volumes et performance

Les surfaces principales commandes/paiements/tickets/scans/notifications utilisent déjà pagination ou limites. Operations borne les queues de revue à 100 lignes avec recherche/filtres. L'API DRF utilise une pagination globale de 20.

Cette passe ne micro-optimise pas toutes les queries. Le correctif volume principal concerne Autopilot : plus de scan infini de tout l'historique `completed`, et déduplication participant côté DB plutôt qu'une requête/charge complète de tous les billets.

Si une page devient lente, mesurer le queryset et son nombre de requêtes avant d'ajouter des caches ou de nouveaux services.

## 17. Temps, devise et cohérence transactionnelle

- Django stocke les datetimes timezone-aware (`USE_TZ=True`).
- `TIME_ZONE` par défaut est `Africa/Lubumbashi` ; les affichages utilisent la timezone Django/utilisateur quand prévu.
- expiration commande, paiement, scan et automation utilisent `timezone.now()`.
- montants monétaires restent en `DecimalField`/`Decimal`, jamais en float pour la logique métier.
- paiement réussi et émission ticket partagent la transaction critique ; une exception provoque rollback.
- scan ticket + passage USED + `ScanLog` sont transactionnels.
- remboursements et annulations sont transactionnels/idempotents selon leur contrat.

## 18. Commandes sensibles et démo

`seed_makolo_demo` est un outil de démonstration et **n'est jamais une étape de déploiement production**. Ne pas l'ajouter au WSGI, au scheduler ou à un script de release. Lancer le seed uniquement dans un environnement explicitement choisi pour la démo selon son `--help` et son contrat de ré-exécution.

Les données démo restent distinguées des indicateurs live Operations. Ne pas supprimer la démo et ne pas inventer un `DEMO MODE` global.

Django Admin reste un outil opérateur : `DEBUG=False`, accès staff authentifié, pas une surface utilisateur publique.

## 19. Surveillance quotidienne

Au minimum :

- `/api/v1/readiness/` répond 200 ;
- Web/Always-on task en état attendu ;
- dernière exécution Autopilot récente ;
- pas d'accumulation anormale de notifications/CRM en queue ;
- pas de hausse de paiements/webhooks/scans en échec ;
- incidents Operations ouverts ;
- taille `db.sqlite3`, `media/`, `logs/`, `backups/`, `staticfiles/` ;
- quota disque PythonAnywhere ;
- sauvegarde récente présente **et** copie off-host selon politique.

Commande de taille utile :

```bash
cd /home/makolo/makolo
du -sh db.sqlite3 media logs backups staticfiles 2>/dev/null
df -h .
```

## 20. Avant un événement réel

- readiness verte ;
- backup DB récent + médias sauvegardés ;
- un et un seul Autopilot actif ;
- backend e-mail testé si les participants dépendent des mails ;
- événement/timezone/heures vérifiés ;
- stock/capacité/types de billets vérifiés ;
- comptes agents scanner et portes d'accès vérifiés ;
- un scan test accepté puis duplicate conforme ;
- téléphone/scanner chargé et réseau testé ;
- Operations Center ouvert par le staff ;
- quota disque et logs contrôlés ;
- aucun déploiement non essentiel pendant la fenêtre d'entrée.

## 21. Rollback simple

Pour un rollback **code** urgent sans réécrire `origin/main` :

1. noter le SHA actuellement déployé ;
2. sauvegarder DB + média ;
3. identifier un SHA connu bon ;
4. sur PythonAnywhere, checkout temporaire en detached HEAD ;
5. installer les requirements de ce SHA si nécessaire, collectstatic, check ;
6. Reload Web ;
7. revalider health/readiness et parcours critique.

Exemple :

```bash
cd /home/makolo/makolo
source /home/makolo/.virtualenvs/makolo/bin/activate
set -a; source .env; set +a

git fetch origin
git checkout --detach <KNOWN_GOOD_SHA>
python -m pip install -r requirements.txt
python manage.py check
python manage.py collectstatic --noinput
```

Ne pas inverser une migration de données ou de schéma à l'aveugle. Restaurer une DB uniquement avec une procédure explicitement validée. Pour revenir ensuite au flux normal : `git checkout main && git pull origin main` puis redéployer.

## 22. Checklist « Avant ouverture à des bêta-testeurs »

- [ ] `DJANGO_ENV=production`, `DJANGO_DEBUG=False`
- [ ] secret, hosts, CSRF et public base URL définis
- [ ] aucun ancien domaine/path dans la config active
- [ ] `.env` non versionné et permissions restreintes
- [ ] migrations + collectstatic verts
- [ ] `/health/` et `/readiness/` verts
- [ ] `/media/` PythonAnywhere configuré
- [ ] backup DB testé et politique média/off-host définie
- [ ] exactly one Autopilot mode configuré
- [ ] e-mail backend explicitement choisi
- [ ] webhook secret sandbox configuré si sandbox actif
- [ ] logs tournants et logs PythonAnywhere accessibles
- [ ] quota disque vérifié
- [ ] compte staff/admin fonctionnel
- [ ] seed démo non inclus dans le déploiement
- [ ] CI Django/frontend/collectstatic/E2E/PostgreSQL smoke verte

## 23. Checklist « Avant un événement réel »

- [ ] backup récent
- [ ] readiness verte
- [ ] Autopilot récent
- [ ] queues notifications/CRM sans retard anormal
- [ ] horaire et timezone événement validés
- [ ] billets/stock/capacité validés
- [ ] webhook/paiement sandbox testé si utilisé pour la répétition générale
- [ ] scanner test : accepté puis duplicate
- [ ] agents scanner autorisés
- [ ] Operations Center surveillé
- [ ] e-mail réel testé si nécessaire
- [ ] quota disque et logs contrôlés
- [ ] fenêtre de déploiement gelée pendant l'entrée

## 24. Éléments volontairement non activés

Cette passe ne met pas en place :

- SMS ;
- Push ;
- PWA ;
- service worker ;
- Kubernetes/Docker comme prérequis ;
- nouveau serveur ;
- nouveau provider de paiement ;
- object storage ;
- Redis ;
- PostgreSQL sur le PythonAnywhere actuel.

Risques restant volontairement ouverts : plafond de concurrence SQLite, rate limiting web local-cache non distribué, médias sur filesystem local, dépendance à l'offre PythonAnywhere pour Always-on/scheduling, backend e-mail réel à choisir, sauvegarde off-host à opérer, migration PostgreSQL future à planifier.

## 25. Reseed bêta canonique exceptionnel

Cette procédure est **distincte du déploiement normal** de la section 4. Elle sert uniquement lorsqu'un opérateur autorisé décide de reconstruire explicitement la base de démonstration/bêta. Elle ne doit jamais être appelée depuis le WSGI, un scheduler, Autopilot ou un script de release.

Avant toute opération, récupérer la configuration réelle depuis PythonAnywhere : URL publique/`MAKOLO_PUBLIC_BASE_URL`, fichier WSGI de l'onglet Web, chemin `DJANGO_DB_PATH`, SHA actuellement déployé, état du worktree, mode Autopilot réellement actif et espace disque. Ne pas supposer qu'un ancien hostname ou chemin est encore correct.

### 25.1 Préparer la fenêtre

1. Choisir une courte fenêtre sans écritures de testeurs.
2. Stopper temporairement **l'unique** mode Autopilot actif (Always-on ou Scheduled Task).
3. Noter le SHA et l'état Git avant déploiement :

```bash
cd /home/makolo/makolo
git rev-parse HEAD
git status --short
```

Si le worktree contient des modifications locales inconnues, les identifier avant de poursuivre ; ne pas les écraser aveuglément.

4. Charger l'environnement puis produire le backup technique de rollback :

```bash
source /home/makolo/.virtualenvs/makolo/bin/activate
set -a; source .env; set +a
python manage.py backup_database
```

Noter le chemin affiché sans publier de secret. Vérifier également le quota :

```bash
du -sh db.sqlite3 media logs backups staticfiles 2>/dev/null
df -h .
```

### 25.2 Charger exactement le `main` validé

Le reseed live doit être fait uniquement après merge et CI verte sur `main` :

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
git rev-parse HEAD
python -m pip install -r requirements.txt
python -m pip check
python manage.py check
```

Le SHA retourné doit être exactement celui du `main` validé. Aucun patch manuel du code sur PythonAnywhere n'est autorisé.

### 25.3 Construire une DB candidate à côté de la DB active

Vérifier d'abord le vrai `DJANGO_DB_PATH`. Pour le layout SQLite habituel, construire une candidate séparée :

```bash
BETA_NEXT_DB=/home/makolo/makolo/db.beta-next.sqlite3
rm -f "$BETA_NEXT_DB"
DJANGO_DB_PATH="$BETA_NEXT_DB" python manage.py migrate --noinput
```

Choisir `AS_OF` comme la date réelle du reseed en `Africa/Lubumbashi`. Saisir le mot de passe sans le placer dans l'historique :

```bash
read -s -p "Mot de passe bêta: " MAKOLO_DEMO_PASSWORD; echo
export MAKOLO_DEMO_PASSWORD
DJANGO_DB_PATH="$BETA_NEXT_DB" python manage.py seed_makolo_demo --scale beta --as-of "$AS_OF"
DJANGO_DB_PATH="$BETA_NEXT_DB" python manage.py validate_makolo_demo --as-of "$AS_OF"
unset MAKOLO_DEMO_PASSWORD
```

Puis valider la candidate :

```bash
DJANGO_DB_PATH="$BETA_NEXT_DB" python manage.py check
DJANGO_DB_PATH="$BETA_NEXT_DB" python manage.py showmigrations --plan
sqlite3 "$BETA_NEXT_DB" 'PRAGMA integrity_check;'
```

Le résultat du contrôle SQLite doit être exactement `ok`. Si migration, seed, validation ou intégrité échoue, **ne pas toucher à la DB active** : corriger dans Git puis recommencer avec une candidate fraîche.

### 25.4 Préparer les statiques et effectuer le swap contrôlé

Avec les settings live :

```bash
python manage.py collectstatic --noinput
```

Pendant que Web et Autopilot ne produisent aucune écriture, conserver le backup et l'ancienne DB, puis remplacer de façon contrôlée le fichier réellement référencé par `DJANGO_DB_PATH` avec la candidate validée. Ne pas utiliser une copie artisanale de l'ancienne DB comme nouveau seed.

Après remplacement, utiliser immédiatement **PythonAnywhere > Web > Reload** afin qu'aucun worker Web ne conserve une connexion vers l'ancien inode SQLite.

### 25.5 Validation live avant réouverture

Après Reload :

```bash
git rev-parse HEAD
python manage.py check --deploy
python manage.py showmigrations --plan
```

Puis vérifier sur l'URL HTTPS réelle :

- `/api/v1/health/` = 200 ;
- `/api/v1/readiness/` = 200 ;
- landing, login, Discovery Event + Transport, carte/liste ;
- Event gratuit sans paiement fictif ;
- Event payant sandbox ;
- Transport, dont un cas `À payer sur place` si exposé ;
- Participant : démarches, à venir, accès/billets, notifications ;
- Space Console avec les personas autorisés ;
- frontières Event manager / Finance / Scanner ;
- scan du credential dédié : accepté puis duplicate/déjà utilisé selon le contrat courant ;
- statiques, MapLibre/tuiles/attribution et logs autour du déploiement.

Le guide `docs/beta-testing.md` donne la matrice persona-based. Ne jamais inclure mot de passe, cookie/session, token QR ou secret dans le rapport de smoke test.

### 25.6 Réactiver exactement un Autopilot

Une fois les smoke tests initiaux réussis, réactiver le mode qui était réellement choisi pour cet environnement : **Always-on worker ou Scheduled hourly, jamais les deux**. Vérifier ensuite une exécution/heartbeat récente et l'absence d'erreur immédiate ou de queue anormale.

Si aucun scheduler horaire/persistant correct n'est disponible, documenter explicitement la dégradation plutôt que créer un hack.

### 25.7 Rollback

Conserver dans le rapport opérateur : ancien SHA, nouveau SHA, backup pré-déploiement et état média pertinent. Si la candidate ou le code live présente un blocage, revenir au SHA connu bon selon la section 21 et restaurer la DB sauvegardée uniquement si nécessaire pour rétablir le service. La vieille DB reste un mécanisme de rollback opérationnel, jamais une source de vérité fonctionnelle à réintroduire dans le seed canonique.
