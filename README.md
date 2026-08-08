# Makolo

Makolo est une plateforme événementielle multi-organisateurs : événements, équipes, billetterie numérique, paiements, notifications, automatisations, intelligence événementielle, acquisition par partenaires et contrôle d’accès par QR code.

## Vision

Makolo n'est pas le back-office d'une seule société. Un utilisateur peut être participant, créer une organisation, rejoindre l'équipe d'un autre organisateur ou exercer un rôle limité (événements, finance, communication, accès) sans devenir administrateur de la plateforme.

La chaîne fonctionnelle couvre maintenant :

- organisations et équipes organisatrices ;
- création et publication d’événements ;
- catégories de billets, stock et capacité ;
- commandes gratuites ou payantes ;
- paiements sandbox/manuels et remboursements contrôlés ;
- génération de tickets et QR uniques ;
- listes d'attente FIFO avec offres temporaires et promotion automatique ;
- transferts sécurisés de billets avec rotation du QR à l'acceptation ;
- contrôle d’accès anti-double-scan ;
- notifications transactionnelles ;
- Makolo Autopilot pour les tâches temporelles et réactives ;
- Analytics & Event Intelligence : ventes, remplissage, présence, waitlist, flux d'entrée, finances autorisées et signaux explicables ;
- Partners / Ambassadeurs / Affiliation : campagnes, liens de recommandation, attribution, commissions et paiements partenaires.

## Stack actuelle

- Python 3.10
- Django 5.2
- Django REST Framework
- Django Templates
- HTMX
- Alpine.js
- Tailwind CSS
- SQLite pour le développement initial
- PostgreSQL prévu pour la production, notamment pour les opérations concurrentes

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
- Marketing : communication, acquisition et partenaires ;
- Scanner manager : contrôle d'accès et agents scanner.

Une appartenance à l'organisation ne donne pas accès à toutes ses données. Les lectures des commandes, paiements, billets, journaux de scan, commissions et métriques financières sont limitées par capacité métier. Voir `docs/architecture/authorization-boundaries.md`.

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
- promotion des listes d'attente lorsqu'une place se libère ;
- expiration des offres waitlist et transferts non acceptés ;
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

## Analytics & Event Intelligence

Le tableau de bord Analytics est disponible sous :

```text
/analytics/
/analytics/events/<event-slug>/
```

Il calcule directement depuis les sources de vérité Makolo : billets actifs, capacité, commandes, conversions, waitlist, transferts, scans, vitesse des ventes et projection simple de sold-out. Les rôles Finance/Owner/Admin peuvent aussi voir les revenus brut, remboursé et net ; les autres rôles reçoivent uniquement les agrégats opérationnels compatibles avec leurs droits.

Les devises ne sont jamais additionnées entre elles. Les réponses Analytics n'exposent aucun nom, e-mail, téléphone, QR ou référence de paiement client. Les insights sont des règles déterministes et explicables, pas des décisions automatiques opaques.

## Partners / Ambassadeurs / Affiliation

L'espace acquisition est disponible sous `/partners/`. Une organisation peut enregistrer des ambassadeurs, influenceurs, médias, agences, communautés ou partenaires commerciaux, puis créer une campagne liée à un événement.

Chaque couple campagne/partenaire reçoit un `ReferralCode` unique et un lien public du type :

```text
/partners/r/ALICE10/
```

Makolo enregistre une visite avec un UUID anonyme, le chemin de destination et uniquement le domaine référent. L'adresse IP et l'URL référente complète ne sont pas conservées. Le dernier code valide est mémorisé dans la session pendant la fenêtre d'attribution de la campagne, jusqu'à 90 jours.

Une réservation n'acquiert aucune commission. La commission devient `earned` uniquement lorsque la commande est réellement confirmée. Un remboursement ou une annulation inverse automatiquement une commission non payée. Une commission déjà payée bloque une inversion silencieuse : l'équipe Finance doit d'abord traiter l'ajustement comptable.

Les commissions peuvent être un pourcentage du montant de la commande ou un montant fixe. Les paiements de commissions sont groupés par devise ; Makolo ne mélange jamais USD, CDF ou d'autres monnaies dans un même solde. Les rôles Marketing gèrent partenaires/campagnes sans voir les montants financiers ; Finance gère commissions et paiements sans obtenir de droits marketing implicites. Un partenaire relié à un compte Makolo dispose de son propre portail de performance agrégé.

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

La CI exécute aussi `python manage.py check --deploy --fail-level WARNING` avec un environnement de production synthétique afin de détecter les régressions de configuration de sécurité avant fusion.

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
/api/v1/tickets/waitlist/
/api/v1/tickets/transfers/
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
/api/v1/analytics/overview/
/api/v1/analytics/events/<event-slug>/
/api/v1/partners/partners/
/api/v1/partners/campaigns/
/api/v1/partners/codes/
/api/v1/partners/commissions/
/api/v1/partners/payouts/
/api/v1/partners/partners/<partner-id>/metrics/
```

`POST /api/v1/tickets/orders/` accepte aussi `referral_code` afin que les clients API/mobile puissent préserver l'attribution sans dépendre d'une session navigateur.

## Notifications

Le centre de notifications est disponible sous `/notifications/`. Les e-mails passent par une outbox persistante `NotificationDelivery` avec retry et respect des préférences/heures silencieuses. Autopilot consomme cette file automatiquement en production. SMS et push sont préparés mais aucun fournisseur externe n'est simulé.

## Contrôle d’accès

Le QR est validé côté serveur. Le premier scan valide marque le billet `used`; les scans suivants sont rejetés et journalisés. Un `Scanner manager` d'organisation peut administrer l'accès sans obtenir les droits finance ou plateforme.

## Prochains axes produit

Le socle actuel prépare désormais les fonctionnalités majeures suivantes :

- CRM événementiel ;
- abonnements/followers d'organisateurs ;
- intelligence avancée des flux d'entrée ;
- recommandations et découverte sociale d'événements ;
- opérations et modération de plateforme avancées ;
- cohortes, attribution multi-touch et prévisions analytiques plus avancées.

## CI

GitHub Actions vérifie automatiquement chaque Pull Request vers `main` : dépendances, contrôles Django, configuration de sécurité production, cohérence des migrations, application des migrations et tests.

## Architecture

- rôles historiques : `docs/architecture/accounts-rbac.md` ;
- domaine événementiel : `docs/architecture/events.md` ;
- billetterie et QR : `docs/architecture/tickets.md` ;
- waitlist et transferts : `docs/architecture/waitlist-transfers.md` ;
- contrôle d’accès : `docs/architecture/scanner.md` ;
- paiements : `docs/architecture/payments.md` ;
- notifications : `docs/architecture/notifications.md` ;
- organisations, équipes et Autopilot : `docs/architecture/platform-autopilot-organizations.md` ;
- frontières d'autorisation : `docs/architecture/authorization-boundaries.md` ;
- Analytics & Event Intelligence : `docs/architecture/analytics-event-intelligence.md` ;
- Partners / Ambassadeurs / Affiliation : `docs/architecture/partners-affiliation.md`.
