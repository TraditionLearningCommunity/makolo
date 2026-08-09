# Makolo

Makolo est une plateforme événementielle multi-organisateurs : événements, équipes, billetterie numérique, paiements, notifications, automatisations, intelligence événementielle, acquisition par partenaires, CRM événementiel, promotions, communauté d'organisateurs et contrôle d’accès par QR code.

## Vision

Makolo n'est pas le back-office d'une seule société. Un utilisateur peut être participant, suivre des organisateurs, créer une organisation, rejoindre l'équipe d'un autre organisateur ou exercer un rôle limité (événements, finance, communication, accès) sans devenir administrateur de la plateforme.

La chaîne fonctionnelle couvre maintenant :

- organisations et équipes organisatrices ;
- profils publics et abonnements/followers d'organisateurs avec préférences propres à chaque organisation ;
- création et publication d’événements ;
- catégories de billets, stock et capacité ;
- commandes gratuites ou payantes ;
- promotions/codes avec périodes, quotas, billets éligibles, minimums, limites client et attribution campagne ;
- paiements sandbox/manuels et remboursements contrôlés ;
- génération de tickets et QR uniques ;
- listes d'attente FIFO avec offres temporaires et promotion automatique ;
- transferts sécurisés de billets avec rotation du QR à l'acceptation ;
- contrôle d’accès anti-double-scan ;
- notifications transactionnelles ;
- Makolo Autopilot pour les tâches temporelles et réactives ;
- CRM Automation : déclencheurs métier, conditions, délais, actions multi-étapes, retries et audit ;
- Analytics & Event Intelligence : ventes, remplissage, présence, waitlist, flux d'entrée, finances autorisées et signaux explicables ;
- Partners / Ambassadeurs / Affiliation : campagnes, liens de recommandation, attribution, commissions et paiements partenaires ;
- CRM événementiel : contacts organisationnels, audiences dynamiques, tags, champs personnalisés, consentements, modèles réutilisables et campagnes ;
- attribution CRM campagne → clic → commande → vente confirmée, avec revenus séparés par devise.

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
- `crm`
- `promotions`
- `analytics_app`

## Organisations, équipes et followers

`is_staff` et `is_superuser` sont des privilèges de **plateforme Makolo**. Ils ne sont pas nécessaires pour organiser un événement.

Une `Organization` possède sa propre équipe :

- Owner : propriété de l'espace organisateur ;
- Admin : équipe et paramètres de l'organisation ;
- Event manager : événements et billetterie ;
- Finance : commandes, paiements et remboursements ;
- Marketing : communication, acquisition, partenaires, promotions et CRM ;
- Scanner manager : contrôle d'accès et agents scanner.

Une appartenance à l'organisation ne donne pas accès à toutes ses données. Les lectures des commandes, paiements, billets, journaux de scan, commissions, promotions financières, CRM et métriques sont limitées par capacité métier. Voir `docs/architecture/authorization-boundaries.md`.

`OrganizationFollow` est une relation sociale différente de `OrganizationMembership`. Suivre un organisateur ne donne aucun droit d'équipe et ne vaut jamais consentement e-mail automatique. Le participant choisit séparément les notifications Makolo et les e-mails pour les nouveaux événements et annonces de chaque organisateur. Un désabonnement de l'organisation A ne modifie ni ses préférences globales Makolo ni celles de l'organisation B.

Les événements existants sont automatiquement rattachés à une organisation personnelle lors de la migration vers ce modèle.

## Makolo Autopilot

Les opérations récurrentes ne doivent pas dépendre d'un développeur. En production, un worker persistant tourne à côté du serveur web :

```text
python manage.py autopilot_worker --poll-seconds 30 --delivery-limit 100
```

Il exécute automatiquement :

- expiration des commandes non payées et libération du stock ;
- traitement/retry de la file de notifications ;
- traitement des campagnes CRM planifiées et retries de livraison ;
- traitement des scénarios CRM multi-étapes et reprise des actions interrompues ;
- déclencheurs CRM temporels avant/après événement, no-show et anniversaires ;
- rappels configurables à J-7, H-24 et H-2 ;
- alertes de remplissage ;
- alertes de stock faible ;
- fermeture automatique des ventes au démarrage ;
- passage automatique de l'événement à `completed` après sa fin ;
- promotion des listes d'attente lorsqu'une place se libère ;
- expiration des offres waitlist et transferts non acceptés ;
- suivi post-événement.

L'organisateur configure les règles d'exploitation d'un événement dans :

```text
/autopilot/events/<event-slug>/
```

et les parcours CRM d'une organisation dans :

```text
/autopilot/crm/<organization-slug>/
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

## Promotions, codes et offres avancées

L'espace Promotions est disponible sous `/promotions/`. Owner/Admin/Marketing peuvent créer une offre en pourcentage ou montant fixe, la limiter à un événement et à certains types de billets, définir un minimum de commande, une période, un quota global et une limite par client. Chaque offre peut porter plusieurs codes, chacun avec sa propre période, son quota, son état public/privé et une campagne CRM associée facultative.

Le participant transmet seulement le code. Makolo recalcule toujours la remise côté serveur à partir des prix réels et verrouille l'offre/code pendant la création de commande. Une redemption `reserved` consomme temporairement le quota ; elle devient `confirmed` lorsque la commande est réellement confirmée et `reversed` en cas d'annulation ou expiration. Les snapshots sous-total, montant éligible, remise et total final restent attachés à la commande même si l'offre est modifiée plus tard.

Une remise qui ramène un total payant exactement à zéro confirme immédiatement la commande et émet les billets. Une commande waitlist encore `pending` peut recevoir un code avant tout paiement. Payments, affiliation et CRM voient ensuite le vrai `TicketOrder.total_amount` après remise.

Les mécanismes d'attribution restent indépendants et peuvent coexister : partenaire pour l'acquisition, campagne CRM signée pour le clic, et promotion pour le prix. Une campagne CRM peut aussi être liée explicitement à un code ; Makolo mesure alors séparément campagne → code → vente sans inventer un clic.

Finance/Owner/Admin peuvent consulter les lignes financières de redemption ; Marketing gère la stratégie et les codes sans obtenir cette liste monétaire détaillée ; Event Manager conserve une lecture opérationnelle.

## CRM, audiences et conversion

Le CRM est disponible sous `/crm/`. Chaque organisation possède son propre espace de contacts, alimenté par ses commandes, billets, waitlists et followers. Les segments sont dynamiques et peuvent cibler : tous les contacts, followers, acheteurs confirmés, détenteurs de billets, participants présents, no-shows, waitlist ou acquisition partenaire.

Les segments peuvent combiner événement, type de billet, ville/pays, consentement, plusieurs tags avec logique ET et filtres exacts sur les champs personnalisés de l'organisation. Les champs disponibles sont texte, nombre, oui/non, date ou liste de choix.

Un achat ne vaut jamais consentement marketing. Le consentement CRM est propre à l'organisation. Les préférences globales Makolo restent prioritaires, mais un membre Marketing ne peut plus changer les préférences globales d'un participant en modifiant un contact local. Les campagnes marketing vérifient encore le consentement et les préférences au moment de la livraison.

Les équipes peuvent créer des `CampaignTemplate` réutilisables. Le contenu est copié dans chaque campagne afin de préserver l'historique même si le modèle évolue ensuite.

Lorsqu'une campagne active le suivi de conversion, son CTA passe par un jeton signé Makolo. Le clic est compté et une commande compatible peut être attribuée à la campagne. Une commande payante reste `pending` jusqu'à confirmation réelle ; l'attribution devient alors `confirmed`. Une annulation ou expiration la passe à `reversed`. Les revenus attribués sont toujours groupés par devise. Aucun pixel d'ouverture invisible n'est installé.

L'attribution CRM et l'attribution partenaire peuvent coexister sur une même commande sans s'écraser : l'une mesure la campagne de communication, l'autre le partenaire commercial.

### CRM Automation

Les rôles Owner/Admin/Marketing peuvent créer des scénarios sous `/autopilot/crm/<organization-slug>/`. Event Manager peut les consulter, mais pas les modifier. Finance et Scanner Manager n'obtiennent aucun accès CRM implicite.

Les déclencheurs disponibles couvrent : nouvel abonné, commande confirmée, commande expirée, entrée en waitlist, check-in, délai avant événement, fin d'événement, no-show et anniversaire. Un scénario peut ensuite enchaîner des actions avec délais : e-mail depuis un `CampaignTemplate`, notification Makolo, ajout/retrait de tag et notification de l'équipe.

Les conditions optionnelles portent sur l'événement, le segment dynamique, le type de billet, le montant minimum et la devise. Les segments sont revalidés au déclenchement ; les no-shows sont calculés uniquement parmi les détenteurs de billets.

Chaque parcours et chaque étape sont persistés, dédupliqués et audités. Les actions e-mail ont retries/backoff, les actions `processing` abandonnées sont reprises par Autopilot, et un workflow mis en pause ne consomme pas ses étapes en attente. Les contenus utilisent uniquement un petit ensemble de variables sûres, sans exécuter de template arbitraire fourni par un organisateur.

Une automatisation ne contourne jamais le consentement : les modèles marketing exigent le consentement CRM et les préférences globales/organisationnelles au moment exact de l'envoi. Une notification Makolo promotionnelle doit être explicitement déclarée comme telle et passe par les mêmes garde-fous.

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
/api/v1/organizations/follows/
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
/api/v1/crm/contacts/
/api/v1/crm/tags/
/api/v1/crm/custom-fields/
/api/v1/crm/templates/
/api/v1/crm/segments/
/api/v1/crm/segments/<segment-id>/preview/
/api/v1/crm/campaigns/
/api/v1/crm/campaigns/<campaign-id>/metrics/
/api/v1/automation/workflows/
/api/v1/automation/workflows/<workflow-id>/
/api/v1/automation/workflows/<workflow-id>/actions/
/api/v1/automation/workflows/<workflow-id>/runs/
/api/v1/promotions/promotions/
/api/v1/promotions/promotions/<promotion-id>/metrics/
/api/v1/promotions/codes/
/api/v1/promotions/redemptions/
```

`POST /api/v1/tickets/orders/` accepte `referral_code` pour l'affiliation, `campaign_token` pour préserver une attribution CRM signée et `promotion_code` pour demander une remise validée côté serveur.

## Notifications

Le centre de notifications est disponible sous `/notifications/`. Les e-mails transactionnels passent par une outbox persistante `NotificationDelivery` avec retry et respect des préférences/heures silencieuses. Autopilot consomme cette file automatiquement en production. Les campagnes CRM disposent d'une outbox séparée afin de conserver leur audit de destinataires et leur politique de consentement. SMS et push sont préparés mais aucun fournisseur externe n'est simulé.

## Contrôle d’accès

Le QR est validé côté serveur. Le premier scan valide marque le billet `used`; les scans suivants sont rejetés et journalisés. Un `Scanner manager` d'organisation peut administrer l'accès sans obtenir les droits finance ou plateforme.

## Prochains axes produit

Le socle actuel prépare désormais les fonctionnalités majeures suivantes :

- découverte sociale et feed personnalisé d'événements ;
- intelligence avancée des flux d'entrée ;
- recommandations selon préférences, localisation et organisateurs suivis ;
- opérations et modération de plateforme avancées ;
- cohortes, attribution multi-touch et prévisions analytiques plus avancées ;
- Customer 360, scoring comportemental et fidélisation.

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
- Partners / Ambassadeurs / Affiliation : `docs/architecture/partners-affiliation.md` ;
- CRM événementiel, audiences et campagnes : `docs/architecture/event-crm-audiences-campaigns.md` ;
- followers, tags/champs, modèles et attribution campagne → vente : `docs/architecture/followers-crm-growth-attribution.md` ;
- CRM Automation, déclencheurs, parcours et reprise : `docs/architecture/crm-automation-engine.md` ;
- promotions, codes, quotas et attribution : `docs/architecture/promotions-coupons-offers.md`.
