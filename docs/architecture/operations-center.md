# Makolo Operations Center

Le **Makolo Operations Center** est le cockpit interne de la plateforme. Il est réservé au staff Makolo (`is_staff`) et ne fait pas partie des espaces organisateur. Un `Owner` ou `Admin` d'organisation n'obtient jamais ces droits par son rôle métier.

## Objectifs

Le domaine `operations` couvre quatre responsabilités :

1. modération et vérification des organisations / événements ;
2. gestion explicite des incidents ;
3. détection agrégée de signaux opérationnels sur Payments, Scanner, Notifications et Automation ;
4. supervision des heartbeats du worker Autopilot.

Le cockpit ne remplace pas une solution d'observabilité externe. Il donne une vue métier exploitable depuis les sources de vérité déjà présentes dans Makolo et crée une piste d'audit des décisions staff.

## Modèles

### `OperationsIncident`

Registre d'incidents avec : domaine, sévérité, statut, organisation/événement/paiement/scan optionnels, responsable staff, timestamps de détection/prise en charge/résolution et résolution finale.

États : `open`, `investigating`, `monitoring`, `resolved`, `dismissed`.

Une clôture `resolved` exige une résolution textuelle. L'assignation est limitée aux comptes `is_staff`.

### `ModerationCase`

Dossier de modération organisation ou événement. Les actions de vérification/suspension ou de modération événement créent automatiquement un dossier `actioned` contenant la justification et le résultat appliqué.

### `OperationsAuditLog`

Journal append-only des actions Operations : acteur, action, cible, résumé, snapshots `before`/`after` et métadonnées. L'admin Django interdit l'ajout, la modification et la suppression manuelle de ces lignes.

### `WorkerHeartbeat`

État déclaré des workers Makolo. Le worker `autopilot_worker` enregistre : démarrage de cycle, fin de cycle, dernier résultat, erreur éventuelle et arrêt propre. Un worker actif sans heartbeat depuis plus de deux minutes est signalé critique.

## Frontière d'autorisation

Toutes les vues web et API du domaine sont staff-only. Les rôles `Owner`, `Admin`, `Event Manager`, `Finance`, `Marketing` et `Scanner Manager` restent des rôles d'organisation et n'accordent aucun accès au Operations Center.

Routes web :

- `/operations/`
- `/operations/organizations/`
- `/operations/events/`
- `/operations/incidents/`
- `/operations/moderation/`

API :

- `GET /api/v1/operations/overview/`
- `GET /api/v1/operations/organizations/`
- `POST /api/v1/operations/organizations/<uuid>/review/`
- `GET /api/v1/operations/events/`
- `POST /api/v1/operations/events/<uuid>/moderate/`
- `GET|POST /api/v1/operations/incidents/`
- `GET|PATCH /api/v1/operations/incidents/<uuid>/`
- `GET /api/v1/operations/moderation/`
- `GET /api/v1/operations/workers/`

## Modération des organisations

Le staff peut définir `new`, `pending`, `verified` ou `suspended`. Une justification est obligatoire et chaque décision crée un `ModerationCase` et un `OperationsAuditLog`.

La suspension s'appuie sur la frontière existante de `events.selectors` : les événements d'une organisation suspendue ne sont plus exposés dans les sélecteurs publics. La suspension **ne supprime pas** les données et **n'annule pas automatiquement** les événements. Une annulation événement doit être une décision Operations séparée et auditée.

## Modération des événements

Actions staff explicites :

- `unlist` : retire l'événement de la découverte mais garde le détail accessible selon les règles existantes ;
- `private` : rend l'événement privé ;
- `cancel` : passe le statut à `cancelled` et renseigne `cancelled_at` ;
- `restore_public` : restaure uniquement la visibilité `public`, sans modifier le statut métier.

Aucune action automatique n'est appliquée à partir d'un simple signal. Un signal aide à décider ; la mutation reste humaine et auditée.

## Signaux déterministes

Le moteur `build_operations_overview` lit les sources existantes. Il ne crée pas de score opaque et ne prétend pas faire de détection IA.

### Payments

- signatures webhook invalides sur 24 h : critique ;
- webhook non traité après 10 minutes : élevé ;
- taux d'échec paiement >= 30 % avec au moins 5 tentatives sur 24 h : élevé ;
- paiement `pending/processing` après 15 minutes : moyen ;
- remboursement en échec sur 24 h : élevé.

Le cockpit ne renvoie jamais le payload brut `PaymentEvent.payload`, les coordonnées du payeur, PAN/CVV ou secrets de provider.

### Scanner / Smart Access

Sur une fenêtre de 15 minutes :

- taux de refus >= 30 % avec au moins 10 scans : élevé ;
- au moins 5 scans `invalid_token`, `unknown_ticket` ou `wrong_event` : élevé.

Le cockpit travaille sur des compteurs. Il n'expose pas le QR brut ; `ScanLog` ne conserve déjà qu'une empreinte SHA-256.

### Automation / CRM Workflows

- `AutomationRun` ou action CRM en échec sur 24 h : élevé ;
- action CRM `queued/processing` encore en attente 15 minutes après son échéance : moyen.

### Notifications

- livraison `failed` sur 24 h : élevé ;
- livraison `queued/processing` en retard de plus de 15 minutes : moyen.

### Workers

Un heartbeat déclaré actif devient `stale` après deux minutes. L'arrêt propre passe le worker à `stopped` et n'est pas considéré comme une panne.

Ces seuils sont des garde-fous V1 explicites. Ils pourront devenir configurables plus tard, mais toute évolution doit rester expliquable et testable.

## Données et confidentialité

Le résumé Operations est volontairement agrégé. Les signaux n'incluent pas :

- e-mail, téléphone ou nom de payeur ;
- payload webhook brut ;
- QR brut ;
- secret PSP ;
- PAN/CVV ;
- données CRM participant.

Les incidents possèdent des champs de texte libre parce qu'un opérateur peut devoir documenter un cas. La consigne produit est de ne copier que le minimum nécessaire et de ne jamais coller un secret ou un payload complet.

## Heartbeat Autopilot

`python manage.py autopilot_worker` enregistre son hostname comme `instance_id`. Les erreurs de heartbeat sont capturées et ne doivent pas interrompre le cycle Autopilot : l'observabilité ne doit pas devenir une dépendance qui arrête le moteur métier.

## Limites assumées avant la transition production finale

Le Lot 7 donne un cockpit applicatif, mais les sujets d'infrastructure restent séparés : PostgreSQL, monitoring externe, centralisation des logs, object storage, PSP réel, process manager pour les workers, health/readiness de plateforme et alerting hors application restent à traiter lors de la transition production finale.

Le Operations Center est donc la couche **métier d'exploitation** de Makolo, pas le remplacement d'une stack SRE.
