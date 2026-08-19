# Participant Experience — Task 10

La surface participant Makolo est **canonical-first**. Elle ne prend ni `Event`, ni `Ticket`, ni `TicketOrder` comme racine universelle.

## Flux de présentation

```text
Occurrence
    ↓
Journey
    ↓
next participant action
    ↓
optional Commerce / Payment
    ↓
Access
    ↓
Credential
```

- **Occurrence** répond à « quand ? » et porte les relations `OccurrencePlace → Place` pour « où ? ».
- **Journey** est présentée comme une **démarche** (inscription, réservation, invitation, achat selon le workflow).
- La **prochaine action** est un resolver de présentation ; elle n’est jamais stockée comme état métier.
- **Commerce / Payment** n’apparaissent que lorsqu’un workflow les exige. `on_site` signifie « À payer sur place » et un parcours gratuit n’invente aucun paiement.
- **Access** est le droit obtenu. Son vocabulaire est contextualisé : billet pour Event, confirmation pour registration, invitation pour invitation, réservation pour reservation.
- Le QR est rendu à partir de l’`AccessCredential` actif avec le service canonique de signature ; son secret et son payload technique ne sont jamais affichés.

## Principes produit

1. Actionnable avant historique : l’accueil répond d’abord à « Que dois-je faire maintenant ? ».
2. `Mes démarches` lit `Journey`, avec selectors dédiés et préchargements pour éviter les N+1.
3. `Mes accès` lit `Access`, jamais `Ticket.objects...`.
4. Les pages de détail sont filtrées par bénéficiaire : changer l’UUID vers celui d’un autre participant retourne 404.
5. L’Event reste une verticale de vocabulaire. Une Activity non-Event avec Occurrence → Journey registration → Access doit fonctionner sans Event, Ticket ni TicketOrder.
6. Les bridges historiques ne sont pas utilisés par la nouvelle surface participant ; ils restent uniquement pour leurs consommateurs Event historiques documentés dans `events-vertical.md`.
7. Les actions métier continuent d’appeler les services propriétaires ; la surface participant ne mute jamais directement Journey, Access, Capacity ou Payment.

## Navigation

La navigation personnelle cible : Accueil, Mes démarches, Mes accès, Notifications, Profil. Les outils professionnels restent conditionnés aux capacités et un utilisateur mandaté peut toujours revenir à son espace personnel.
