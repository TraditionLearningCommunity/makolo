# Makolo — Product Language

> Référence produit pour le vocabulaire visible. Les bounded contexts canoniques restent en anglais dans le code ; cette couche choisit des mots métier selon la verticale, le workflow réel, l’état réel et la surface.

## Promesse fonctionnelle

Makolo permet de faire à distance les démarches nécessaires avant un déplacement, afin de ne se déplacer que lorsque c’est réellement nécessaire.

## Principes

1. **L’utilisateur n’a jamais à apprendre l’architecture Makolo.**
2. Le backend reste canonique : `Activity`, `Occurrence`, `Journey`, `JourneyRequest`, `Offer`, `CapacityPool`, `CommerceOrder`, `Payment`, `Access`, `AccessCredential`, `AccessUse`.
3. Le produit parle métier : activité, événement, trajet, départ, inscription, réservation, invitation, demande, tarif, commande, paiement, billet, confirmation, participant, voyageur, embarquement.
4. Le contexte choisit le mot ; il ne change jamais la source de vérité.
5. Product Language ne décide jamais de l’éligibilité, de la capacité, du paiement, de l’autorisation ou de l’émission d’un accès.
6. Une Journey peut exister sans CommerceOrder ni Payment. Un Access peut être issu d’une inscription gratuite, d’une invitation ou d’une décision administrative.
7. Aucun second système de wording legacy n’est maintenu.

Le resolver partagé est `core/product_language.py`. Les surfaces peuvent enrichir une phrase ou un CTA, mais les noms contextuels transversaux doivent provenir de ce contrat.

## Matrice canonique

| Backend | Générique | Events | Transport |
| --- | --- | --- | --- |
| Space | Espace | Organisateur / Espace | Opérateur / Espace |
| Activity | Activité | Événement | Trajet |
| Occurrence | Date / créneau | Date / séance selon contexte | Départ |
| Journey | Démarche | Inscription / achat / réservation / invitation | Réservation / achat de billet |
| JourneyRequest | Demande | Demande d’inscription | Demande |
| Offer | Tarif | Type de billet / Tarif | Tarif |
| CapacityPool | Capacité / places | Places | Places |
| CommerceOrder | Commande | Commande | Réservation ou Commande selon surface |
| Payment | Paiement | Paiement | Paiement |
| Access | Accès / Confirmation | Billet / Invitation / Confirmation | Billet |
| AccessCredential | Invisible par défaut | QR du billet | QR du billet |
| AccessUse | Utilisation / contrôle | Entrée / Scan | Embarquement |
| Place | Lieu | Lieu | Origine / Destination / Arrêt |
| Profile concerné | Participant | Participant | Voyageur |

## Matrice surface × concept

| Concept | Navigation générique | Participant Event | Participant Transport | Space Console |
| --- | --- | --- | --- | --- |
| Journey | Mes démarches | Inscription / Achat de billet / Invitation | Réservation | Demandes / Commandes selon vue |
| Access | Mes accès | Billet / Invitation / Confirmation | Billet | Accès |
| Offer | Tarif | Type de billet / Tarif | Tarif | Tarifs |
| Occurrence | implicite | Date / séance | Départ | Dates / Départs |
| Space | Espace | Organisé par… | Opéré par… | Espace |

## Résolution par workflow

### Générique

- `registration` → **Inscription** ; résultat **Confirmation**.
- `reservation` → **Réservation**.
- `invitation` → **Invitation**.
- `order_approval` → **Demande**.
- fallback → **Démarche** / **Accès**.

### Event

- inscription gratuite → **Inscription**, CTA **S’inscrire** ; aucune commande gratuite artificielle.
- achat → **Achat de billet**, CTA **Acheter le billet** ; résultat **Billet**.
- réservation → **Réservation**, CTA **Réserver** ; résultat **Billet** lorsque le workflow émet ce droit.
- invitation → **Invitation**, CTA **Accepter l’invitation** ; jamais Commande.
- demande avec validation → **Demande d’inscription**.

### Transport

- Activity → **Trajet**.
- Occurrence → **Départ**.
- réservation → **Réservation**, CTA **Réserver**.
- achat → **Achat de billet**.
- Access → **Billet**.
- bénéficiaire → **Voyageur**.
- AccessUse → **Embarquement**.

Transport ne dépend jamais d’un Event pour déterminer son vocabulaire.

## États Journey

| État | Label produit |
| --- | --- |
| draft | À terminer |
| submitted | Envoyée |
| pending_approval | En attente de validation |
| approved | Approuvée |
| pending_payment | Paiement requis |
| confirmed | Confirmée |
| fulfilled | Terminée |
| rejected | Refusée |
| cancelled | Annulée |
| expired | Expirée |

Contextualiser lorsque cela améliore la compréhension : **Réservation confirmée**, **Inscription confirmée**, **Invitation acceptée**.

## États Access

- Valide
- Utilisé
- Annulé
- Révoqué
- Expiré
- Transféré

Les valeurs d’enum brutes ne sont jamais affichées sur les surfaces utilisateur.

## Modes de paiement

| Mode | Présentation |
| --- | --- |
| none | rien si inutile |
| upfront | Paiement en ligne requis |
| after_approval | Paiement requis après validation |
| on_site | À payer sur place |
| later | Paiement ultérieur |

`on_site` n’est jamais présenté comme « impayé » au participant.

## Participant

Navigation de référence : **Accueil**, **Mes démarches**, **Mes accès**, **Notifications**, **Profil**.

Accueil : **À faire**, **À venir**, **Mes accès**. Un état vide d’accès dit qu’aucun billet, pass ou confirmation n’est encore disponible et propose **Découvrir**.

CTA privilégiés : **S’inscrire**, **Réserver**, **Payer**, **Voir mon billet**, **Accepter l’invitation**, **Refuser**. Utiliser **Continuer** uniquement lorsque l’action exacte ne peut pas être nommée.

## Space Console

Contexte stable : **Agir en mon nom** / agir dans l’Espace sélectionné.

Navigation métier :

- Activité : **Activités**, **Demandes**, **Accès** ;
- Transport : **Routes · Départs · Véhicules** lorsque le module est accessible ;
- Commercial : **Tarifs**, **Commandes**, **Paiements**, **Promotions** ;
- Publics : **Groupes**, **Contacts**, **Audiences** ;
- Exploitation : **Lieux**, **Contrôle d’accès**, **Opérations** ;
- Pilotage : **Analyses**, **Automatisations** ;
- Espace : **Équipe**, **Paramètres**.

La visibilité de navigation ne remplace jamais les permissions serveur.

## Events

Employer : **Événement**, **Organisé par**, **Date**, **Heure**, **Lieu**, **Type de billet**, **Tarif**, **Billet**, **Participant**, **Inscription**, **Commande**, **Promotion**, **Contrôle d’accès**.

Ne pas exposer `Activity`, `Occurrence`, `Offer`, `CommerceOrder` ou `AccessCredential` sur les surfaces Event.

## Transport

Employer : **Transport**, **Trajet**, **Départ**, **Origine**, **Destination**, **Arrêt**, **Véhicule**, **Tarif**, **Places disponibles**, **Réserver**, **Billet**, **Voyageur**, **Liste des voyageurs**, **Embarquement**.

Exemple : **Trajet Lubumbashi → Kolwezi — Départ vendredi à 08:00**.

## Discovery

Surface : **Découvrir**.

Questions : **Que voulez-vous faire ?**, **Où ?**, **Quand ?**.

Filtres temporels : **Aujourd’hui**, **Demain**, **Ce week-end**, **Cette semaine**, **À venir**. Géolocalisation : **Autour de moi**.

Prix : **Gratuit** ou **À partir de 20 USD**. Disponibilité : **Disponible**, **Quelques places**, **Complet**, ou une quantité lisible.

Liste et carte doivent partager la même sémantique.

## Notifications et emails

Toute communication répond à : que s’est-il passé, dois-je agir, où cliquer ?

Exemples :

- **Inscription confirmée** ;
- **Votre billet est disponible** ;
- **Votre billet de voyage est disponible** ;
- **Paiement requis** — « Votre demande est approuvée. Vous pouvez maintenant effectuer le paiement. » ;
- Event reprogrammé → **L’horaire de l’événement a changé** ;
- Transport reprogrammé → **L’horaire de votre départ a changé** ;
- paiement échoué → **Le paiement n’a pas pu être confirmé**.

Les sujets d’emails suivent le même vocabulaire. Ne jamais employer `Journey confirmed`, `Access issued` ou `Occurrence rescheduled` dans une communication utilisateur.

## Erreurs et états vides

Les erreurs décrivent une action ou une situation compréhensible :

- capacité insuffisante → **Il n’y a plus assez de places disponibles.**
- 403 → **Vous n’avez pas l’autorisation d’accéder à cette page.**
- promotion invalide → **Ce code promotionnel n’est pas valide pour cette réservation.**
- credential trop tôt → **Ce billet n’est pas encore valable.**
- déjà utilisé → **Ce billet a déjà été utilisé.**
- sold out → **Complet**.

Un état vide explique la situation puis propose une action utile lorsque possible.

## Scanner

Event : **Billet valide**, **Entrée autorisée**, **Billet déjà utilisé**, **Billet expiré**, **Billet annulé**, **Billet non encore valide**.

Transport : **Billet valide**, **Voyageur autorisé à embarquer**, **Mauvais départ** et les mêmes états de validité pertinents.

Texte QR : **Présentez ce QR au contrôle.**

## Dates, devises et quantités

- Long : **vendredi 21 août 2026 à 14:00**.
- Compact : **ven. 21 août · 14:00**.
- Devise : **20 USD**, **50 000 CDF** ; ne pas afficher des décimales inutiles.
- Quantité : **1 place disponible**, **2 places disponibles**.
- La timezone n’est affichée que lorsqu’elle apporte une information utile.

## Ton et typographie

Makolo est clair, direct, professionnel et simple. Éviter jargon administratif, jargon startup, infantilisation et exclamations inutiles.

Capitalisation en style phrase français : **Mes démarches**, **Contrôle d’accès**, **Paiements encaissés**.

Les boutons n’ont pas de point final. Éviter les fragments concaténés qui compliqueraient une future i18n.

## Gate anti-jargon

Avant chaque livraison Product Language, rechercher dans les surfaces produit : `Activity`, `Occurrence`, `Journey`, `JourneyRequest`, `Offer`, `CapacityPool`, `CommerceOrder`, `AccessCredential`, `AccessUse`, `Mandate`, `PermissionDenied`, `TicketOrder`. Chaque occurrence restante doit être technique/admin/documentation, ou être corrigée.

Rechercher également `Event`, `Ticket` et `Organizer` dans les surfaces génériques et Transport pour détecter les restes Event-centric.
