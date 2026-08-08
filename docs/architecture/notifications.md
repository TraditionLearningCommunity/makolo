# Module Notifications

## Responsabilité

`notifications` centralise les messages visibles par l’utilisateur et leur livraison asynchrone. Le domaine métier qui déclenche une notification ne doit pas envoyer directement un e-mail : il produit un événement transactionnel, puis `notifications` crée une notification interne et une livraison à traiter.

Le socle livré prend en charge :

- centre de notifications dans l’application ;
- compteur de non-lus dans la barre de navigation ;
- e-mails transactionnels ;
- préférences utilisateur ;
- heures silencieuses ;
- file de livraison persistante avec retry ;
- confirmations de billets gratuits ;
- paiement réussi, échoué et remboursé ;
- rappels avant événement ;
- API v1 ;
- journal d’audit dans l’administration Django.

SMS et push sont modélisés comme canaux futurs mais ne sont pas encore envoyés par ce socle.

## Modèles

### Notification

Une `Notification` est le message fonctionnel affiché dans Makolo. Elle appartient toujours à un utilisateur et contient : catégorie, type, titre, message, URL d’action locale, métadonnées minimales, clé de déduplication et date de lecture.

La clé `dedup_key` rend les notifications métier idempotentes : un retry de webhook ou un second signal identique ne crée pas plusieurs messages.

### NotificationDelivery

Une `NotificationDelivery` représente une tentative de livraison externe. États :

```text
queued -> processing -> sent
   |          |
   |          +-> queued (retry)
   |          +-> failed (tentatives épuisées)
   +-> skipped (préférence/canal indisponible)
```

La récupération d’une livraison est transactionnelle. Le worker la passe d’abord en `processing`, libère le verrou, effectue l’I/O e-mail, puis écrit le résultat. Cela évite qu’un envoi SMTP lent maintienne une transaction métier ouverte.

## Déclencheurs métier

Les signaux Django sont utilisés uniquement comme pont après commit :

- commande gratuite `confirmed` -> billets disponibles ;
- paiement `succeeded` -> confirmation de paiement + billets disponibles ;
- paiement `failed` -> paiement non abouti ;
- paiement `refunded` -> remboursement confirmé et billets annulés.

Chaque signal utilise `transaction.on_commit()`. Aucun e-mail n’est donc envoyé avant la validation définitive de la transaction qui a changé l’état métier.

## Préférences

Les préférences existantes dans `accounts.NotificationPreference` sont réutilisées. Le centre de notifications interne reste la source de vérité. Les options contrôlent les livraisons externes :

- e-mail global ;
- billets/événements ;
- sécurité ;
- marketing ;
- heures silencieuses.

Pendant les heures silencieuses, la livraison reste en file et son `scheduled_for` est déplacé à la fin de la période.

## Worker e-mail

Commande :

```text
python manage.py process_notifications --limit 100
```

En production cette commande doit être lancée périodiquement par cron/systemd/superviseur (par exemple chaque minute) tant qu’un vrai système de tâches asynchrones n’a pas été introduit.

En développement, le backend e-mail Django écrit les e-mails dans la console. En test, le backend mémoire est utilisé.

## Rappels d’événement

Commande :

```text
python manage.py schedule_event_reminders --hours-before 24 --window-minutes 60
```

Elle recherche les détenteurs de billets `valid` dont l’événement commence dans la fenêtre ciblée et crée un rappel idempotent par événement/utilisateur. Une exécution répétée ne duplique pas les rappels.

Pour un rappel à 24 h et un autre à 2 h, planifier séparément les deux commandes.

## Interface web

```text
/notifications/
/notifications/preferences/
```

La cloche de la navbar mène au centre de notifications et affiche le nombre de non-lus.

## API v1

```text
GET  /api/v1/notifications/
GET  /api/v1/notifications/?filter=unread
GET  /api/v1/notifications/unread-count/
GET  /api/v1/notifications/<id>/
POST /api/v1/notifications/<id>/read/
POST /api/v1/notifications/read-all/
```

Toutes les requêtes sont isolées au compte authentifié.

## Sécurité et données

- aucun secret fournisseur ni donnée bancaire dans les notifications ;
- pas de QR brut dans les e-mails : l’utilisateur ouvre son billet dans Makolo ;
- aucune redirection vers une URL externe depuis le centre de notifications ;
- métadonnées limitées à des identifiants fonctionnels ;
- destinations et erreurs de livraison visibles uniquement dans l’administration ;
- préférences vérifiées avant mise en file ;
- déduplication des événements métier ;
- envoi après commit uniquement.

## Extension future

Un adaptateur SMS ou push doit implémenter le traitement du canal correspondant sans déplacer la logique métier hors de `notifications.services`. Un futur Celery/RQ peut remplacer l’exécution cron tout en conservant `NotificationDelivery` comme outbox/audit durable.
