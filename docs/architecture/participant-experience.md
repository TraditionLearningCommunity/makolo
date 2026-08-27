# Participant Experience — canonical personal hub

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
4. Les pages de détail sont filtrées par bénéficiaire ; la visibilité supplémentaire du buyer pour un Access acheté pour autrui reste explicitement limitée au contrat Commerce T25.
5. L’Event reste une verticale de vocabulaire. Une Activity non-Event avec Occurrence → Journey registration → Access fonctionne sans Event, Ticket ni TicketOrder.
6. Les bridges historiques ne sont pas utilisés par la nouvelle surface participant.
7. Les actions métier continuent d’appeler les services propriétaires ; la surface participant ne mute jamais directement Journey, Access, Capacity ou Payment.

## Hub personnel T29

`/me/` est une projection d’attention, pas un feed ni une table de dashboard. Aucune entité `PersonalTask`, `History`, `FeedItem` ou équivalent n’est persistée.

L’ordre produit est :

1. **À faire** — Journeys réellement actionnables, priorisées par besoin participant ;
2. **À venir** — Access actifs ayant une Occurrence temporelle pertinente, triés par engagement ;
3. **Mes accès** — résumé compact du nombre de droits actifs + lien vers la surface canonique ;
4. raccourcis personnels vers **Mes Groupes**, **Mes favoris** et **Mes Espaces** ;
5. Activities personnellement organisées (`owner_profile`, jamais `created_by`) ;
6. **Historique récent**, uniquement à partir d’objets déjà historiques.

Une même carte Access n’est donc plus répétée dans « À venir » et « Mes accès ». Une Journey encore actionnable n’est jamais utilisée pour remplir « Historique récent ».

Chaque section du hub est bornée. Les selectors filtrent d’abord par Profile en base ; seule la fusion finale de petits ensembles historiques est effectuée en Python.

## Historique personnel

`/me/history/` unifie la mémoire participant depuis les objets canoniques, sans nouvelle table.

Sources principales :

- Access `used`, `expired`, `revoked`, `cancelled`, `transferred` ;
- Access encore `valid` mais dont la période/Occurrence est passée ;
- Journey `fulfilled`, `rejected`, `cancelled`, `expired` lorsqu’aucun Access ne représente déjà la même expérience.

### Déduplication Journey / Access

`Access.journey` est la relation explicite de déduplication. Lorsqu’un Access historique pointe vers une Journey, l’Access devient la représentation principale de cette expérience et la carte garde des liens vers les deux détails. Aucune déduplication n’est faite seulement sur `activity_id` : deux Occurrences ou deux droits distincts restent deux engagements distincts.

Un Access manuel sans Journey reste visible. Une Journey historique sans Access reste visible. Les `AccessUse` ne deviennent pas chacun une entrée de timeline ; le détail Access conserve l’historique de contrôle.

Le tri utilise le moment métier le plus pertinent disponible : usage accepté pour un Access utilisé, fin d’Occurrence ou de validité lorsqu’elle explique le passage en historique, puis timestamps canoniques. La surface est recherchable localement, filtrable entre accès/participations et démarches, et paginée.

### Confidentialité buyer / beneficiary

L’historique de participation commence toujours depuis `beneficiary=profile`. Un billet que Sarah a acheté pour Jacques peut rester visible dans la section « Pour d’autres personnes » de `Mes accès`, mais ne devient jamais une participation personnelle de Sarah dans l’Historique.

## Notifications et attention

La cloche de navbar reste le point d’entrée Notifications et conserve le compteur de non-lus. `/notifications/` et les deep-links T23 restent inchangés et protégés côté serveur.

T29 retire l’entrée Notifications de la sidebar personnelle pour éviter deux points d’entrée permanents. Rendre `/me/` ne marque aucune Notification comme lue et le hub ne crée pas une deuxième tâche parce qu’une Notification existe : l’actionnabilité vient des domaines, principalement Journey.

La navigation personnelle de premier niveau cible désormais :

```text
Accueil
Mes démarches
Mes accès
Historique
```

## Réseau personnel

Le hub compose uniquement des liens vers les domaines existants :

- **Mes Groupes** → surface Groups T27 ;
- **Mes favoris** → ActivityBookmark / Discovery T26 ;
- **Mes Espaces** → contextes Space T24/T28.

Un Bookmark reste une mémoire volontaire, pas une tâche. GroupMembership ne donne aucune autorité. La Console Space reste le lieu des responsabilités opérationnelles collectives.

## Compatibilité Event encore conservée

Les modèles et routes historiques `Ticket` / `TicketOrder` ne sont pas réintroduits dans la nouvelle surface personnelle, mais ils ne sont pas supprimés tant que des consommateurs actuels les utilisent encore :

- la verticale Event utilise encore ses routes de choix de billet, waitlist et transfert ;
- la billetterie professionnelle expose encore `tickets:list` aux rôles autorisés ;
- le scanner Event garde un lien de présentation vers `Ticket` autour de l'`Access` canonique ;
- les tests de continuation d’authentification exercent encore l’ancienne URL `/tickets/` comme destination `next=`.

Ces bridges restent des projections Event : `Journey`, `CommerceOrder`, `Access` et `AccessCredential` demeurent les autorités canoniques.
