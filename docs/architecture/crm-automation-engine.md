# Makolo CRM Automation Engine

## Objectif

Le moteur CRM Automation transforme les données transactionnelles et sociales déjà présentes dans Makolo en parcours multi-étapes exécutés automatiquement par Makolo Autopilot. Un organisateur configure un scénario ; aucun développeur n'intervient ensuite pour déclencher les actions quotidiennes.

Le moteur reste organisationnel : un scénario appartient à une `Organization`, utilise ses contacts, segments, tags et modèles, et respecte les mêmes frontières de rôles que le CRM.

## Modèle

Un `CRMWorkflow` décrit :

- un déclencheur ;
- un événement optionnel ;
- un segment dynamique optionnel, réévalué au moment du déclenchement ;
- un type de billet optionnel ;
- un montant minimum et une devise optionnels ;
- pour les déclencheurs temporels, un offset et une fenêtre de grâce ;
- un état actif / pause.

Un workflow contient des `CRMWorkflowAction` ordonnées. Chaque étape possède un délai **après la fin de l'étape précédente**. Cela permet par exemple :

```text
commande confirmée
    ↓ immédiat
ajouter tag VIP
    ↓ + 24 h
notification de bienvenue
    ↓ + 6 jours
e-mail d'upsell
```

`CRMWorkflowRun` constitue l'audit du parcours pour un contact et une source métier. `CRMWorkflowActionRun` est l'outbox persistante de chaque étape : état, échéance, tentatives, erreur et résultat sont conservés.

## Déclencheurs disponibles

- `followed_organizer` — nouvel abonnement à un organisateur ;
- `order_confirmed` — commande réellement confirmée ;
- `order_expired` — réservation non payée expirée ;
- `waitlist_joined` — entrée en liste d'attente ;
- `checked_in` — billet passé à `used` lors d'un scan accepté ;
- `before_event` — temps configurable avant le début d'un événement ;
- `event_ended` — après la fin d'un événement ;
- `no_show` — détenteur de billet n'ayant aucun billet utilisé pour l'événement ;
- `birthday` — anniversaire d'un contact Makolo disposant d'une date de naissance.

Les déclencheurs métier sont raccordés par signaux puis exécutés après commit transactionnel. Les déclencheurs temporels et anniversaires sont évalués par Autopilot.

### Fenêtre de grâce

Un workflow temporel ne doit pas envoyer un rappel J-3 devenu absurde si le worker a été arrêté plusieurs jours. `trigger_grace_minutes` borne donc la période pendant laquelle le déclencheur reste valable après son échéance.

Deux workflows temporels du même événement sont évalués **indépendamment**. Un scénario J-3 ne déclenche pas prématurément un scénario H-24.

## Actions disponibles

- envoyer un `CampaignTemplate` par e-mail ;
- créer une notification Makolo pour le contact ;
- ajouter un tag CRM ;
- retirer un tag CRM ;
- notifier l'équipe organisatrice.

Les actions désactivées sont ignorées proprement et le parcours passe à l'étape active suivante.

## Variables sûres

Les contenus de workflow supportent une interpolation volontairement limitée, par remplacement de jetons connus et sans exécution de template arbitraire :

- `{{ contact.name }}`
- `{{ contact.email }}`
- `{{ organization.name }}`
- `{{ event.title }}`
- `{{ event.start_at }}`
- `{{ order.reference }}`
- `{{ order.amount }}`
- `{{ order.currency }}`

Cette première version n'autorise pas l'exécution de code, de filtres Django ou d'expressions fournies par un organisateur.

## Consentement et préférences

Le moteur ne transforme jamais un événement métier en consentement marketing implicite.

Pour un modèle e-mail `marketing` :

1. le contact CRM doit être `subscribed` ;
2. les préférences globales du compte Makolo doivent autoriser e-mail + marketing ;
3. si le contact suit l'organisateur, ses préférences propres à cette organisation doivent autoriser les annonces e-mail ;
4. l'e-mail inclut un lien signé de désabonnement organisationnel.

Pour une notification Makolo promotionnelle, l'action doit être explicitement marquée `marketing_action`. Le moteur revalide alors le consentement CRM, la préférence marketing globale et `notify_announcements` du follow.

Les communications `event_update` restent distinctes du marketing et exigent un contexte événement adapté.

## Idempotence et anti-doublons

Chaque exécution possède un `dedup_key` unique composé du workflow, de la source métier et du contact. Réexécuter un signal, un webhook ou un cycle Autopilot ne crée donc pas un second parcours pour le même événement source.

Chaque étape possède aussi une contrainte unique `(run, action)`.

## Retries et reprise après crash

Avant I/O, une étape passe atomiquement de `queued` à `processing`. En cas d'erreur :

- l'étape est replanifiée avec backoff ;
- après `max_attempts`, elle devient `failed` et le parcours devient `failed` ;
- un `processing` abandonné depuis plus de 15 minutes est remis en file par Autopilot.

Le worker ne dépend donc pas d'un terminal humain restant ouvert.

## No-show

Le déclencheur no-show part uniquement des détenteurs de billets de l'événement. Un simple contact CRM ou membre d'un segment sans billet n'est jamais classé absent. Si une adresse possède au moins un billet `used` pour l'événement, elle est exclue du no-show.

## Permissions

Les automatisations CRM reprennent les droits CRM :

- Owner / Admin : lecture et gestion ;
- Marketing : lecture et gestion ;
- Event Manager : lecture via les frontières CRM existantes, sans droit de création/modification ;
- Finance / Scanner Manager : aucun accès implicite ;
- Staff Makolo : supervision plateforme.

## Web et API

Interface :

```text
/autopilot/crm/<organization-slug>/
/autopilot/crm/<organization-slug>/new/
/autopilot/crm/workflows/<workflow-id>/
```

API :

```text
GET/POST /api/v1/automation/workflows/
GET/PATCH /api/v1/automation/workflows/<workflow-id>/
POST      /api/v1/automation/workflows/<workflow-id>/toggle/
POST      /api/v1/automation/workflows/<workflow-id>/actions/
GET       /api/v1/automation/workflows/<workflow-id>/runs/
```

## Exploitation

Le même processus Autopilot existant traite les scénarios CRM :

```bash
python manage.py autopilot_worker --poll-seconds 30 --delivery-limit 100
```

Le fallback cron continue d'utiliser :

```bash
python manage.py run_autopilot
```

Les deux commandes exécutent le moteur CRM en plus des expirations, rappels, campagnes et notifications déjà gérés par Autopilot.
