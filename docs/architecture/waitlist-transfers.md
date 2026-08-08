# Smart Waitlist & Secure Ticket Transfer

## Smart Waitlist

La liste d'attente est attachée à un `TicketType` et à un compte Makolo authentifié.

Principes :

- l'inscription n'est autorisée que lorsque la fenêtre de vente est ouverte mais qu'aucune place n'est disponible à cause du stock du type ou de la capacité globale de l'événement ;
- une seule entrée active (`waiting` ou `offered`) est autorisée par utilisateur et type de billet ;
- la promotion suit un FIFO strict par type de billet ;
- Makolo ne saute pas une demande plus ancienne si la quantité disponible ne suffit pas à la satisfaire ;
- une promotion crée une vraie `TicketOrder` temporaire et augmente `reserved_quantity`, ce qui empêche une vente concurrente de prendre la place ;
- l'offre expire comme toute commande en attente et libère alors automatiquement le stock ;
- un billet gratuit issu de la waitlist n'est émis qu'après acceptation explicite de l'utilisateur ;
- une offre payante utilise le flux de paiement existant ; la confirmation de la commande convertit l'entrée de waitlist ;
- annulation, expiration et Autopilot déclenchent ou rattrapent les promotions suivantes.

Autopilot exécute `promote_open_waitlists()` à chaque cycle, après l'expiration des commandes dues.

## Secure Ticket Transfer

Un transfert est une proposition entre deux comptes Makolo existants.

Principes :

- seul le propriétaire actuel d'un billet `valid` peut initier un transfert ;
- un billet utilisé, annulé, remboursé ou expiré n'est jamais transférable ;
- le destinataire doit posséder un compte actif correspondant à l'adresse e-mail saisie ;
- un seul transfert `pending` est permis par billet ;
- le billet reste au propriétaire initial tant que le destinataire n'a pas accepté ;
- l'acceptation est autorisée uniquement au compte destinataire ;
- l'acceptation verrouille la ligne du transfert et la ligne du billet dans une transaction ;
- Makolo remplace `Ticket.code` par un nouvel UUID avant de changer le propriétaire ;
- l'ancien QR signé ne correspond alors plus à aucun `Ticket.code` et devient définitivement invalide ;
- le nouveau propriétaire obtient le même billet métier avec un nouveau QR, ce qui conserve l'historique et évite une double émission ;
- les transferts non acceptés expirent automatiquement via Makolo Autopilot.

## Sécurité et concurrence

Les opérations critiques utilisent `transaction.atomic()` et `select_for_update()` sur les événements, stocks, commandes, billets, entrées de waitlist et transferts concernés. PostgreSQL reste recommandé en production pour fournir les garanties de verrouillage attendues sous concurrence réelle.

Les notifications sont créées après commit de la transaction métier afin qu'un e-mail ou une notification ne puisse pas annoncer une opération finalement annulée par rollback.
