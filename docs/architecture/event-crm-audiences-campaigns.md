# CRM événementiel, audiences, segmentation et campagnes

## Responsabilité

`crm` transforme les interactions déjà connues de Makolo en un espace relationnel **par organisation** : contacts, segments dynamiques et campagnes de communication. Le domaine ne devient pas une nouvelle source de vérité pour les commandes, billets, présences, waitlists ou affiliations : il lit ces domaines et reconstruit les audiences au moment du preview ou de l’envoi.

## Contacts

`CRMContact` est propre à une organisation. La même personne peut donc apparaître dans plusieurs CRM sans que les équipes puissent croiser leurs données.

Les contacts sont synchronisés depuis :

- `TicketOrder` ;
- `Ticket` ;
- `TicketWaitlistEntry`.

Le signal métier et une resynchronisation avant preview/envoi rendent le système tolérant aux données historiques. Le contact conserve une identité de communication minimale : e-mail, nom, téléphone éventuel, compte Makolo lié, source, première/dernière activité connue et consentement marketing.

Le CRM n’importe pas les QR, références de paiement, secrets PSP ou journaux de scan bruts.

## Consentement

Un achat **n’est jamais interprété comme un opt-in marketing**.

États :

```text
unknown
subscribed
unsubscribed
```

Un compte Makolo dont `NotificationPreference.marketing_notifications=True` peut alimenter un consentement `subscribed`. Sinon le contact reste `unknown` jusqu’à un consentement explicite. Un abonnement manuel exige une source de consentement documentée.

Chaque e-mail marketing contient un lien signé de désabonnement. Le désabonnement met aussi `NotificationPreference.marketing_notifications=False` lorsque le contact est lié à un compte Makolo.

Les communications `event_update` sont séparées du marketing : elles ciblent une audience événementielle et respectent `event_notifications` pour les comptes Makolo. Elles peuvent joindre un détenteur de billet invité/guest même si son consentement marketing est inconnu, car il s’agit d’une information liée à l’événement et non d’une prospection.

## Segments dynamiques

`AudienceSegment` combine :

- organisation ;
- événement éventuel ;
- type de billet éventuel ;
- catégorie d’audience ;
- filtre de consentement marketing ;
- ville/pays pour les contacts liés à un profil Makolo.

Catégories supportées :

```text
all
confirmed_buyers
ticket_holders
attendees
no_shows
waitlist
partner_referred
```

Les audiences sont recalculées depuis `tickets` et `partners`. Il n’existe donc pas de table de membres de segment susceptible de devenir silencieusement obsolète.

`no_shows` ne retourne rien avant la fin de l’événement et correspond aux billets encore valides/non utilisés après cette fin.

## Campagnes

`CommunicationCampaign` possède deux natures :

- `marketing` ;
- `event_update`.

Cycle :

```text
draft -> scheduled -> sending -> sent
   \-----------------> sending

draft/scheduled/sending -> cancelled
```

Au lancement, Makolo crée un snapshot `CampaignRecipient` afin que l’audit de livraison reste stable même si le segment évolue ensuite. Le consentement est **revalidé au moment exact de la livraison** ; un désabonnement effectué après le snapshot entraîne `skipped` et aucun e-mail n’est envoyé.

Chaque destinataire possède une machine d’état `queued / processing / sent / failed / skipped`, un compteur de tentatives, un maximum d’essais, un backoff simple et une reprise des lignes restées `processing` après interruption du worker.

## Autopilot

`run_autopilot_cycle()` traite désormais :

1. les campagnes planifiées arrivées à échéance ;
2. les destinataires CRM en file ;
3. les retries et récupérations de workers interrompus ;
4. la finalisation automatique des campagnes ;
5. puis l’outbox générale de notifications Makolo.

Commande de diagnostic/fallback :

```text
python manage.py process_crm_campaigns --campaign-limit 20 --recipient-limit 100
```

En production, `autopilot_worker` suffit normalement.

## Permissions

- Owner / Admin : lecture et gestion CRM ;
- Marketing : lecture et gestion CRM ;
- Event manager : lecture du CRM et des audiences, sans modification ni envoi ;
- Finance : aucun accès implicite au CRM ;
- Scanner manager : aucun accès implicite au CRM ;
- staff Makolo : supervision plateforme.

Cette frontière évite qu’un droit financier ou de contrôle d’accès donne automatiquement accès aux coordonnées et notes relationnelles.

## Interfaces

Web :

```text
/crm/
/crm/org/<organization-slug>/
/crm/contacts/<uuid>/
/crm/segments/<uuid>/
/crm/campaigns/<uuid>/
/crm/unsubscribe/<signed-token>/
```

API :

```text
GET        /api/v1/crm/contacts/
POST       /api/v1/crm/contacts/<uuid>/consent/
GET/POST   /api/v1/crm/segments/
GET        /api/v1/crm/segments/<uuid>/preview/
GET/POST   /api/v1/crm/campaigns/
GET        /api/v1/crm/campaigns/<uuid>/metrics/
POST       /api/v1/crm/campaigns/<uuid>/send/
POST       /api/v1/crm/campaigns/<uuid>/cancel/
```

## Mesure et vie privée

Cette version mesure la livraison (`sent`, `failed`, `skipped`) mais **n’ajoute pas de pixel d’ouverture ni de tracking de clic invisible**. Les futures métriques d’engagement devront être introduites avec une politique de confidentialité explicite et des signaux techniquement fiables.

Les conversions billetterie après une campagne peuvent être analysées comme évolution d’audience, mais ne doivent pas être présentées comme causalité sans mécanisme d’attribution dédié.

## Évolutions prévues

- tags CRM et champs personnalisés contrôlés ;
- préférences par organisation/catégorie ;
- templates réutilisables et variantes ;
- import/export avec journal de consentement ;
- suppression/anonymisation guidée ;
- providers SMS/push réels ;
- bounce/complaint webhooks lorsque le provider e-mail est choisi ;
- cohortes et attribution campagne -> vente avec règles explicites ;
- fréquence maximale et politiques anti-fatigue par destinataire.
