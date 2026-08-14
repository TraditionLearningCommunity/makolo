# Domain Events, Notifications et Automation

Cette note décrit le socle introduit par la Tâche 8A. Il complète le blueprint canonique sans généraliser CRM, Promotions, Scanner/Operations ou Analytics.

```text
Domain service
    │
    ├─ mutate business state
    └─ write DomainEventOutbox
             │
           commit
             │
      process_domain_events
        ├─ system consumers
        │    └─ Notifications
        └─ Automation rules
```

## Contrat de fait métier

Un Domain Event décrit un fait passé avec un nom stable `<domain>.<fact>`. Il n'est pas un `events.Event` historique et ne porte aucune FK vers ce modèle. Les payloads sont versionnés, minimaux et composés principalement d'identifiants canoniques ; mots de passe, secrets, bearer credentials, QR secrets, tokens et données KYC y sont refusés.

Le socle ne publie que les faits utilisés aujourd'hui : transitions Journey/Request, émission/usage/révocation/transfert d'Access, transitions CommerceOrder, succès/échec/remboursement Payment, publication Activity et annulation/replanification Occurrence.

## Transactional outbox

`core.DomainEventOutbox` est écrit par `emit_domain_event()` dans la transaction métier courante. Une mutation annulée par rollback annule donc aussi le fait. La clé `idempotency_key` est unique et une collision avec un contenu différent est refusée.

Le traitement immédiat éventuel est enregistré avec `transaction.on_commit`; il ne remplace jamais l'outbox. Un événement resté `pending` peut être retraité par :

```text
python manage.py process_domain_events --once --batch-size 100
```

Autopilot appelle également le processor pendant ses cycles périodiques.

## Delivery et concurrence

Le processor revendique de petits lots dans une transaction courte. PostgreSQL verrouille uniquement la table Outbox avec `select_for_update(of=("self",), skip_locked=True)` lorsque la fonctionnalité est disponible. SQLite suit une stratégie compatible sans `skip_locked`.

Le lock n'est pas conservé pendant un envoi e-mail ou un autre consumer. Le delivery est donc volontairement **at-least-once** : un crash exactement après un effet mais avant l'enregistrement du succès peut provoquer une relivraison. `DomainEventConsumption` mémorise l'état par `(event, consumer)`, et chaque effet final doit lui-même être dédupliqué.

Les erreurs stockées et loggées contiennent l'id de l'événement, son type et le consumer, jamais le payload complet.

## Notifications système

`notifications.system` est un consumer garanti par Makolo, distinct des règles configurables. Une Notification reste centrée sur un Profil : recipient, titre, message, catégorie, statut lu/non lu, URL et deliveries. Les nouveaux messages peuvent en plus référencer de façon nullable DomainEvent, Activity, Journey, Access et CommerceOrder.

La déduplication système utilise au minimum `domain_event + recipient + template`. Lorsque deux faits représentent une seule expérience utilisateur, une clé partagée est volontairement utilisée : par exemple `journey.confirmed` puis `access.issued` pour une inscription générique ne créent pas deux confirmations.

La couche de présentation conserve le vocabulaire vertical :

- un Access projeté en Ticket Event produit « billets » et utilise les URLs Ticket existantes ;
- une Journey `registration` sans Ticket produit « inscription » ;
- une Journey `invitation` produit « invitation » ;
- une CommerceOrder `on_site` confirmée précise que le paiement est prévu sur place et ne prétend jamais qu'un Payment a réussi.

Les préférences e-mail, quiet hours et catégories existantes sont appliquées par `create_notification`. Une notification in-app reste créée même lorsque l'e-mail est désactivé. Aucun consentement marketing n'est déduit d'un fait transactionnel.

L'e-mail est mis en file après consommation du Domain Event, jamais pendant les locks métier. La file `NotificationDelivery` possède déjà sa propre déduplication/retry. Comme avec tout SMTP classique, il n'est pas possible de garantir l'absence absolue de doublon si le serveur a accepté le message mais que le processus meurt avant de persister `sent`; Makolo empêche en revanche toutes les duplications contrôlables avant l'appel SMTP.

## Automation configurable

`AutomationRule` réagit à `trigger_event_type` et appartient toujours à un Espace, avec Activity optionnelle. Un événement ne peut déclencher que les règles du même Espace ; une règle Activity-scoped ne voit que cette Activity.

La Tâche 8A limite volontairement les conditions aux champs whitelistés suivants : `workflow`, `payment_mode`, `status`, `currency`, `amount_gte`. Il n'existe ni `eval`, ni Python/SQL stocké, ni requête arbitraire de base de données depuis une règle.

L'unique action générique nouvelle de 8A est une notification contrôlée. Les destinataires sont choisis parmi des identifiants explicitement présents dans le fait (`beneficiary`, `initiated_by`, `buyer`, `requester`). Les actions arbitraires sur Journey, Payment ou Access restent interdites.

`AutomationExecution` est unique par `(rule, domain_event)`, conserve attempts/status/error safe et est retentable jusqu'à une limite finie. Une règle défectueuse n'annule pas les exécutions déjà réussies des autres règles ; lors d'une relivraison, celles-ci sont ignorées comme déjà terminées.

## Scheduler vs événements

Autopilot reste le mécanisme des travaux temporels. Il appelle les services canoniques `expire_stale_capacity_reservations()` et `expire_due_journeys()` puis traite l'outbox. Il ne réimplémente ni Capacity ni Journey.

Les politiques Event périodiques et le moteur `CRMWorkflow*` existants sont conservés comme compatibilité. Leur généralisation appartient à 8B ; les supprimer ou les convertir implicitement dans 8A créerait un changement de portée et des effets marketing non souhaités.

## Rétention et inspection

Les Domain Events traités ne sont pas supprimés automatiquement pendant la bêta. L'admin staff permet l'inspection en lecture seule et la remise en attente d'un événement échoué sans autoriser la réécriture de son type ou de son payload historique. Une politique de purge pourra être ajoutée lorsque les besoins de rétention seront stabilisés.

## Hors scope 8A

CRM/audiences, Promotions, Scanner/Operations, Analytics, Transport, GroupEligibility, grande UX Participant/Console, infrastructure Kafka/RabbitMQ/Redis/Celery obligatoire, SMS provider et workflow builder no-code restent explicitement hors de cette étape.
