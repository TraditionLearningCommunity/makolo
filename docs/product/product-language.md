# Makolo — Product Language

> Référence produit pour le vocabulaire visible. Les bounded contexts canoniques restent en anglais dans le code ; cette couche choisit des mots métier selon la verticale, le workflow réel, l’état réel et la surface.

## Promesse fonctionnelle

Makolo permet de préparer et d’orchestrer ce qui peut l’être avant que la présence ou la décision de la personne devienne réellement nécessaire.

## Principes

1. **L’utilisateur n’a jamais à apprendre l’architecture Makolo.**
2. Le backend reste canonique : `Activity`, `Occurrence`, `Journey`, `JourneyRequest`, `Offer`, `CapacityPool`, `CommerceOrder`, `Payment`, `Access`, `AccessCredential`, `AccessUse`.
3. Le produit parle métier : activité, événement, trajet, départ, inscription, réservation, invitation, demande, tarif, commande, paiement, billet, confirmation, participant, voyageur, embarquement.
4. Le contexte choisit le mot ; il ne change jamais la source de vérité.
5. Product Language ne décide jamais de l’éligibilité, de la capacité, du paiement, de l’autorisation ou de l’émission d’un accès.
6. Une Journey peut exister sans CommerceOrder ni Payment. Un Access peut être issu d’une inscription gratuite, d’une invitation ou d’une décision administrative.
7. Aucun second système de wording legacy n’est maintenu.
8. **L’interface décrit la situation de la personne ; elle n’explique pas sa propre conception.** Les principes UX, le ranking, les projections, les garde-fous et les choix d’architecture restent dans la documentation et les tests.
9. **Une phrase n’est ajoutée que si elle aide à comprendre, décider ou agir.** Le silence et les espaces calmes sont légitimes.

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

| Concept | Surface générique | Participant Event | Participant Transport | Space Console |
| --- | --- | --- | --- | --- |
| Journey | En cours / profondeur Démarche | Inscription / Achat de billet / Invitation | Réservation | Demandes / Commandes selon vue |
| Access | En cours / Mes ressources selon conséquence | Billet / Invitation / Confirmation | Billet | Accès |
| Offer | Tarif | Type de billet / Tarif | Tarif | Tarifs |
| Occurrence | implicite | Date / séance | Départ | Dates / Départs |
| Space | Collectif / contexte d’action | Organisé par… | Opéré par… | Espace |

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

## Expérience personnelle

La navigation primaire mobile de référence est :

> **Maintenant | Découvrir | Makolo | En cours | Moi**

Le desktop adapte ces mêmes repères ; il ne réintroduit pas un index de domaines.

### Maintenant

Parler du prochain pas réel. Ne pas expliquer pourquoi Makolo classe ou ne classe pas quelque chose ici.

Préférer :

- **Tout est en ordre. ✓**
- **Rien à faire pour le moment.**
- **Votre demande est envoyée.**
- **Il reste une action de votre côté.**
- **C’est votre tour.**

Éviter :

- « Makolo n’invente pas une urgence pour remplir cet espace. »
- « dans l’ordre canonique de priorité » ;
- « sans transformer l’Accueil en catalogue » ;
- toute phrase qui commente le design du produit.

### En cours

Parler de la continuité humaine :

- **Vous avez fait votre part. Ça suit son cours.**
- **Tout est prêt pour la suite.**
- **Un point doit être réglé avant de continuer.**

Ne pas exposer les états techniques `Readiness.WAITING`, `JourneyStatus.PENDING_APPROVAL`, etc.

### Moi

Employer les territoires humains : **Passeport Makolo**, **Ce qui compte pour moi**, **Mes collectifs**, **Mes ressources**.

Compte et Paramètres restent sous l’Avatar. `Moi` n’est ni « Mon profil » ni une copie de tous les modèles rattachés au Profile.

### Makolo Mark

Le premier geste est une entrée naturelle, pas une taxonomie de fonctionnalités.

Préférer : **Qu’est-ce que vous avez en tête ?**

Une clarification n’apparaît que lorsqu’elle débloque réellement l’interprétation suivante. Les capacités internes `Comprendre`, `Retrouver`, `Réutiliser`, `Conserver`, `Faire avancer`, `Faire exister`, `Continuer pour moi` ne deviennent pas sept boutons.

CTA privilégiés dans les profondeurs métier : **S’inscrire**, **Réserver**, **Payer**, **Voir mon billet**, **Accepter**, **Refuser**, **Continuer** lorsque l’action exacte ne peut pas être nommée plus précisément.

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

Question : **Qu’est-ce que je pourrais avoir envie de vivre, faire ou obtenir ?**

La recherche peut partir d’une intention naturelle. Les filtres précisent le contexte sans devenir l’architecture visible.

Filtres temporels : **Aujourd’hui**, **Demain**, **Ce week-end**, **Cette semaine**, **À venir**. Géolocalisation : **Autour de moi**.

Prix : **Gratuit** ou **À partir de 20 USD**. Disponibilité : **Disponible**, **Quelques places**, **Complet**, ou une quantité lisible.

Liste et carte partagent la même sémantique. Une raison de pertinence, lorsqu’elle aide, reste courte et humaine : **Près de vous**, **Pendant votre séjour**, **Avec votre pass**, **Correspond à votre veille**.

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

Un état vide peut simplement constater la situation. Il ne doit pas inventer une action pour remplir l’écran.

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

Le texte visible ne doit pas ressembler à une note de conception ou à une justification générée : pas de phrase méta sur ce que Makolo « cherche à éviter », pas de rappel du contrat UX dans le corps de l’interface, pas de remplissage éditorial lorsque le titre, l’état et l’action suffisent.

Capitalisation en style phrase français : **Mes démarches**, **Contrôle d’accès**, **Paiements encaissés**.

Les boutons n’ont pas de point final. Éviter les fragments concaténés qui compliqueraient une future i18n.

## Gate anti-jargon

Avant chaque livraison Product Language, rechercher dans les surfaces produit : `Activity`, `Occurrence`, `Journey`, `JourneyRequest`, `Offer`, `CapacityPool`, `CommerceOrder`, `AccessCredential`, `AccessUse`, `Mandate`, `PermissionDenied`, `TicketOrder`. Chaque occurrence restante doit être technique/admin/documentation, ou être corrigée.

Rechercher également `Event`, `Ticket` et `Organizer` dans les surfaces génériques et Transport pour détecter les restes Event-centric.

Enfin, auditer les phrases visibles contenant des formulations de documentation telles que `canonique`, `projection`, `sans transformer`, `Makolo ne doit pas`, `moteur`, `baseline`, `ranking`, `score` ou `algorithme`. Elles sont légitimes dans les docs, rarement dans une interface destinée à la personne.
