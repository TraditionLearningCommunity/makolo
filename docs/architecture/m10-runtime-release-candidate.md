# M10.1 — Runtime & Release Candidate

> Statut : gate de fermeture runtime de M10.
> Base auditée : `main@27996f016bc2eb4d9cec4bcca158f52a32cf0abf`.
> Le runtime courant reste prioritaire si ce document vieillit.

## 1. Objet

M10.1 ferme ce qui doit être reproductible, vérifiable et récupérable avant de déclarer Makolo Mature Core/Web Release Candidate.

Il ne crée aucun nouveau domaine métier, aucun namespace mobile, aucune application Flutter et aucune cible de production inventée.

PythonAnywhere reste l'environnement bêta/test courant. La cible de production finale reste une décision externe tant qu'aucune configuration canonique ne la fixe.

## 2. Runtime actuel

Le dépôt supporte les profils `development`, `test`, `e2e` et `production`.

En production, le runtime refuse notamment :

- une `DJANGO_SECRET_KEY` absente ;
- des `DJANGO_ALLOWED_HOSTS` absents ;
- une `MAKOLO_PUBLIC_BASE_URL` absente ou non HTTPS ;
- `DJANGO_DEBUG=True` ;
- un backend SMTP sans host ;
- le sandbox Payment sans secret webhook.

Les cookies session/CSRF sont Secure en production. Les secrets restent fournis par environnement et ne sont jamais versionnés.

## 3. Base de données

Le déploiement PythonAnywhere bêta documenté reste SQLite.

PostgreSQL est supporté par la configuration et validé par les workflows PostgreSQL du dépôt. Le passage de la bêta courante à PostgreSQL n'est pas une étape implicite de M10.1.

Les gates de release restent :

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --check
```

Aucune migration métier n'est introduite par M10.1.

## 4. Autopilot

Autopilot est le propriétaire du travail différé récurrent nécessaire au produit.

Les deux modes d'exécution utilisent maintenant le même cycle canonique :

```text
scheduler cycle
  -> Capacity expirations
  -> Journey expirations
  -> Domain Event recovery + processing
  -> event/order/waitlist/notification runtime
  -> Service reminders
  -> Subscription deadlines
  -> Spatiotemporal
  -> Proactive preparation
  -> Conversation points
  -> Recognition periodic runtime
  -> inbound capture expiration
  -> CRM workflows
```

Le mode persistant et le fallback one-shot ne diffèrent donc plus par leur couverture métier ; ils diffèrent uniquement par leur cadence et leur heartbeat.

PythonAnywhere :

- mode préféré si disponible : `autopilot_worker` persistant ;
- fallback : `run_autopilot` horaire avec heartbeat scheduled ;
- ne jamais activer les deux simultanément ;
- ne pas ajouter `process_notifications` en parallèle.

Un fallback horaire peut retarder le travail jusqu'au prochain cycle. Cette dégradation doit être assumée explicitement par l'opérateur.

Les erreurs du worker destinées aux logs/heartbeats passent par la redaction applicative avant persistance ou affichage.

## 5. Observer

Observer reste distinct d'Autopilot.

Un déploiement de code n'active jamais implicitement :

- Internet ;
- HTTP direct ;
- Chromium ;
- Adaptive HTTP -> Browser.

Le mode Browser exige une capacité d'hébergement réelle et un Chromium compatible. Le dépôt ne suppose pas que PythonAnywhere convient à un worker Chromium persistant. En l'absence de décision opérateur, cette capacité reste désactivée.

Le coeur Makolo Mature ne dépend pas d'Observer Browser pour fonctionner.

## 6. Notifications et e-mail

Le chemin fonctionnel est :

```text
fait métier
-> Notification
-> NotificationDelivery
-> Autopilot / dispatcher
-> backend e-mail configuré
```

Les livraisons queued, retries et recovery des livraisons interrompues sont traités par Autopilot.

SMS et Push ne sont pas présentés comme fonctionnels : ils restent hors runtime livré.

Le dépôt n'impose aucun fournisseur e-mail commercial. Le backend est choisi par environnement ; console/locmem/file restent des choix de développement/bêta, SMTP est disponible lorsqu'il est réellement configuré.

## 7. Static, media et fichiers privés

`STATIC_ROOT` et `MEDIA_ROOT` sont séparés.

Les artifacts privés ne sont pas servis comme media public. Journey artifacts, PersonalAssets, Trust evidence et Conversation attachments utilisent le storage privé commun hors `MEDIA_ROOT`, sans URL publique. Leur téléchargement traverse une vue autorisée et applique les protections HTTP de confidentialité.

Les artifacts Observer possèdent également un storage opérationnel distinct.

## 8. Backup et restore

SQLite bêta utilise `backup_database`, qui :

- utilise l'API de backup SQLite ;
- écrit dans un fichier temporaire ;
- exécute `PRAGMA integrity_check` ;
- renomme atomiquement la copie validée ;
- refuse l'écrasement silencieux.

M10.1 ajoute une preuve automatisée de recoverability :

```text
backup
-> copie vers une cible SQLite isolée
-> migrate --noinput
-> migrate --check
-> django check
-> /api/v1/readiness/ == 200
-> PRAGMA integrity_check == ok
```

Cette preuve n'écrase jamais la base bêta réelle.

Les médias privés/publics doivent être sauvegardés séparément de la DB selon la procédure opérateur. Une copie DB située uniquement sur le même disque que l'application n'est pas considérée comme protection contre une perte de l'hébergement.

## 9. Rollback

Un rollback code peut revenir temporairement sur un SHA connu bon, mais il n'est pas assimilé à un rollback de données.

Avant rollback :

1. noter le SHA ;
2. sauvegarder DB + médias ;
3. évaluer les migrations écrites depuis le SHA cible ;
4. ne jamais inverser une migration destructive à l'aveugle ;
5. redéployer le SHA retenu ;
6. revalider health/readiness et un parcours critique.

Si du code N+1 a déjà écrit une forme de données incompatible avec N, le retour au code N exige une stratégie de données explicite ou un restore validé.

## 10. Observabilité

Le socle livré fournit :

- `/api/v1/health/` pour la liveness Django ;
- `/api/v1/readiness/` pour Django + DB minimale ;
- logs applicatifs tournants ;
- filtre de redaction best-effort ;
- WorkerHeartbeat Operations ;
- état/cycle Autopilot ;
- heartbeat Observer lorsqu'il est activé ;
- signaux Operations pour queues et échecs.

Une plateforme SaaS d'observabilité n'est pas ajoutée pour fermer M10.

## 11. Inventaire providers

| Capability | Provider/runtime connu | Configuration | Criticité | Fallback / comportement sans provider | Signal |
| --- | --- | --- | --- | --- | --- |
| E-mail | backend Django ; SMTP possible | environnement | optionnel tant qu'aucun parcours ne promet un e-mail externe | console/test backend ou échec contrôlé selon environnement | delivery status + logs |
| Payment | `sandbox`, `manual` | runtime owner | sandbox/manual uniquement | aucun provider final inventé | Payment/events/Operations |
| Cartographie | MapLibre + tile URL configurable | environnement | non critique au coeur transactionnel | surface cartographique dégradée selon disponibilité | logs/UX |
| Intelligence | registry provider du domaine Intelligence | environnement/capability | non critique à M10 | noop ou capacité non configurée selon owner | health/provider tests |
| Observer HTTP/Browser | adapters Observer explicites | flags opérateur | optionnel | désactivé | heartbeat Observer |

Ce tableau décrit les capacités du dépôt. Il ne prétend pas connaître les credentials ou l'activation effective d'un environnement live.

## 12. Données de démonstration

Le seed canonique existant est conservé.

Les workflows Beta seed valident :

- base SQLite fraîche ;
- base PostgreSQL fraîche ;
- migrations ;
- seed synthétique ;
- validation ;
- idempotence pour paramètres identiques.

Le seed n'est pas une étape de déploiement normal.

## 13. Contrat Release Candidate

Chaque release bêta candidate doit pouvoir être identifiée sans nouvelle table :

```text
commit                = git rev-parse HEAD
migrations            = migrate --check + showmigrations --plan
settings profile      = DJANGO_ENV + moteur DB, sans secrets
demo/seed             = commande/version/as-of seulement si environnement démo
deployment timestamp  = horodatage opérateur
smoke result          = résultat daté du smoke post-déploiement
autopilot mode        = persistent OU scheduled, jamais les deux
observer mode         = disabled/control-plane/http/browser/adaptive explicitement
```

Le SHA, le résultat des checks et le mode runtime sont des preuves de release. Ils ne sont pas une nouvelle vérité métier persistante.

## 14. PythonAnywhere bêta

Le runbook reste la procédure canonique.

Le dépôt connaît les chemins de référence documentés, mais l'onglet Web PythonAnywhere reste la source de vérité pour le WSGI et les mappings réellement actifs. M10.1 ne prétend pas avoir observé l'interface live PythonAnywhere depuis la CI GitHub.

Un déploiement bêta réel doit encore enregistrer :

- SHA effectivement déployé ;
- résultat `check --deploy` ;
- état migrations ;
- health/readiness ;
- mode Autopilot ;
- résultat du smoke fonctionnel ;
- backup récent ;
- état du quota disque/logs.

## 15. Branch protection

Au moment de l'audit d'entrée M10.1, `main` est visible comme non protégé sur GitHub.

Le compte d'automatisation utilisé pour cette passe possède un accès `push`, pas `admin/maintain`. M10.1 ne fabrique donc pas un ruleset fictif.

L'action administrateur finale devra sélectionner uniquement les checks qui se déclenchent réellement pour les changements visés. Le check agrégé de CI est un bon candidat lorsqu'il est garanti sur chaque PR concernée ; les workflows path-filtered ne doivent pas devenir des requirements créant un deadlock.

## 16. Gate M10.1

M10.1 est fermé lorsque :

- le cycle Autopilot est unique et équivalent entre worker et fallback ;
- les erreurs worker sont redacted ;
- backup + restore isolé sont exercés automatiquement ;
- settings/deployment/runbook restent alignés ;
- aucun modèle ni migration surprise n'est ajouté ;
- CI applicable est verte ;
- la PR est mergée sur `main` puis `main` redevient vert.

Le déploiement et le smoke de l'environnement bêta réel restent une preuve opérateur externe au dépôt et devront être enregistrés avant la fermeture globale M10.
