# Contrat API — MVP mobile Flutter

Ce document fixe le contrat HTTP utilisé par le futur client Flutter Android/iOS de Makolo. Il ne décrit pas le back-office organisateur. Le mobile MVP cible les participants, acheteurs et détenteurs de billets, avec un mode Scanner séparé et strictement autorisé côté serveur.

## Base et principes

Base API : `/api/v1/`.

Le serveur reste la source de vérité pour les prix, stock, capacité, fenêtres de vente, devise, promotions, état des commandes, paiements et validation QR. Le client Flutter ne doit jamais envoyer ou faire confiance à un total calculé localement.

Toutes les dates/heures sont des valeurs ISO-8601 DRF avec timezone. Les identifiants métier sont majoritairement des UUID.

Les endpoints de découverte participant sont séparés des endpoints génériques/de gestion. Un utilisateur qui est aussi organisateur ne voit donc pas ses brouillons ou événements privés dans le feed participant.

## Health et bootstrap

`GET /api/v1/health/`

Public :

```json
{
  "status": "ok",
  "api_version": "v1"
}
```

Aucune donnée d'infrastructure, version de framework, secret ou état de base de données détaillé n'est exposé.

## Authentification JWT

### Inscription

`POST /api/v1/accounts/auth/register/`

Exemple :

```json
{
  "email": "amina@example.com",
  "username": "amina",
  "password": "mot-de-passe-fort",
  "password_confirm": "mot-de-passe-fort",
  "first_name": "Amina",
  "last_name": "K."
}
```

### Connexion

`POST /api/v1/accounts/auth/login/`

```json
{
  "email": "amina@example.com",
  "password": "mot-de-passe-fort"
}
```

Réponse : `access` + `refresh`. L'access token dure 15 minutes et le refresh 7 jours avec rotation/blacklist. Le client doit stocker les tokens dans un stockage sécurisé du système (Keychain/Keystore), jamais en préférence non chiffrée.

Les appels authentifiés utilisent :

```text
Authorization: Bearer <access-token>
```

### Refresh

`POST /api/v1/accounts/auth/refresh/`

```json
{"refresh": "..."}
```

La rotation renvoie un nouvel `access` et un nouveau `refresh`. Le client remplace atomiquement l'ancien refresh.

### Logout

`POST /api/v1/accounts/auth/logout/`

Authentifié, avec :

```json
{"refresh": "..."}
```

Le refresh est blacklisté.

### Utilisateur courant et profil

`GET /api/v1/accounts/auth/me/`

`PATCH /api/v1/accounts/auth/profile/update/`

Le PATCH accepte JSON pour les mises à jour normales et multipart/form-data lorsqu'un avatar est envoyé.

## Cycle de mot de passe

### Mot de passe oublié

`POST /api/v1/accounts/auth/password/forgot/`

```json
{"email": "amina@example.com"}
```

La réponse est volontairement identique que l'e-mail existe ou non. Le serveur ne révèle jamais l'existence d'un compte.

Le backend envoie un UID et un token Django signé/expirable par e-mail. En développement/test, le backend e-mail local est utilisé. Le futur Flutter présentera un écran de réinitialisation ; ce lot ne met pas encore en place les universal links/app links.

### Reset

`POST /api/v1/accounts/auth/password/reset/`

```json
{
  "uid": "...",
  "token": "...",
  "new_password": "...",
  "new_password_confirm": "..."
}
```

Le token est à usage effectif unique : le changement du hash de mot de passe invalide le token. Les refresh tokens existants de l'utilisateur sont blacklistés et les JWT émis avec l'ancien mot de passe ne restent pas valides.

### Changement authentifié

`POST /api/v1/accounts/auth/password/change/`

```json
{
  "current_password": "...",
  "new_password": "...",
  "new_password_confirm": "..."
}
```

Le mot de passe actuel est vérifié, les validateurs Django s'appliquent, puis les refresh existants sont révoqués.

## Pagination

Les collections DRF paginées utilisent la pagination par page, taille serveur par défaut 20 :

```json
{
  "count": 42,
  "next": "http://.../?page=2",
  "previous": null,
  "results": []
}
```

Le client doit lire `results`, ne pas supposer que toutes les ressources tiennent sur une page, et traiter `next` comme optionnel.

## Format global des erreurs

Les erreurs attendues DRF/Django sont normalisées :

```json
{
  "error": {
    "code": "validation_error",
    "message": "Les données fournies sont invalides.",
    "fields": {
      "quantity": ["Stock insuffisant."]
    }
  }
}
```

Codes génériques stables :

- `validation_error` ;
- `authentication_required` ;
- `permission_denied` ;
- `not_found` ;
- `throttled` ;
- `method_not_allowed` ;
- `api_error` pour les erreurs HTTP attendues ne rentrant pas dans les catégories précédentes.

`fields` est toujours un objet. Le client doit utiliser `code` pour la logique générale et `message`/`fields` pour l'affichage. Les exceptions internes et stack traces ne sont jamais sérialisées par ce contrat.

Les résultats métier valides qui ne sont pas des erreurs HTTP, notamment un scan refusé, gardent leur propre contrat métier et peuvent répondre HTTP 200 avec `accepted=false`.

## Découverte participant

### Feed

`GET /api/v1/events/discover/`

Retourne exclusivement les événements :

- `published` ;
- `public` ;
- dont l'organisation n'est pas suspendue ;
- encore à venir/non terminés par défaut.

Filtres MVP :

- `search=<texte>` ;
- `category=<slug>` ;
- `city=<ville>` ;
- `date_min=YYYY-MM-DD` ;
- `date_max=YYYY-MM-DD` ;
- `ordering=start_at` ou `ordering=-start_at`.

Aucun brouillon/privé n'est ajouté parce que l'utilisateur connecté serait aussi organisateur.

Chaque ligne fournit : id, slug, titre, description courte, URL d'image absolue, catégorie, dates, timezone, état d'inscription, lieu public, organisation publique minimale et synthèse de disponibilité.

### Détail

`GET /api/v1/events/discover/<slug>/`

Même frontière strictement publique. Le détail ajoute la description complète et les fenêtres d'inscription.

Structure utile :

```json
{
  "id": "uuid",
  "slug": "makolo-night",
  "title": "Makolo Night",
  "short_description": "...",
  "description": "...",
  "image_url": "http://.../media/...",
  "category": {"id": "uuid", "name": "Concerts", "slug": "concerts"},
  "start_at": "...",
  "end_at": "...",
  "registration_start_at": null,
  "registration_end_at": null,
  "timezone": "Africa/Lubumbashi",
  "registration_status": "open",
  "venue": {
    "id": "uuid",
    "name": "Grand Hall",
    "kind": "physical",
    "address": "...",
    "city": "Lubumbashi",
    "country": "CD",
    "latitude": "-11.664700",
    "longitude": "27.479400"
  },
  "organization": {
    "id": "uuid",
    "name": "Makolo Live",
    "slug": "makolo-live",
    "is_verified": true
  },
  "ticket_availability": {
    "registration_open": true,
    "has_public_ticket_types": true,
    "has_tickets_on_sale": true,
    "can_purchase": true,
    "sold_out": false
  }
}
```

Aucune donnée de gestion, membership, finance, CRM ou analytics n'est exposée ici.

## Types de billets participant

`GET /api/v1/events/<slug>/ticket-types/`

La route utilise la frontière participant, pas le ViewSet générique de gestion. Elle retourne uniquement les types `is_active=true` d'un événement public admissible.

Un type comprend :

```json
{
  "id": "uuid",
  "name": "Standard",
  "description": "...",
  "price": "25.00",
  "currency": "USD",
  "is_free": false,
  "available_quantity": 42,
  "min_per_order": 1,
  "max_per_order": 5,
  "sales_start_at": null,
  "sales_end_at": null,
  "is_on_sale": true
}
```

`available_quantity` peut être `null` pour un stock illimité. Cette lecture est informative. La création de commande revérifie atomiquement l'événement, le type, la période, la quantité, le stock, la capacité, les prix, la devise et une éventuelle promotion.

## Commandes et idempotence

`POST /api/v1/tickets/orders/`

Pour Flutter, `idempotency_key` est obligatoire au niveau du protocole client, même si l'API garde sa présence facultative pour compatibilité avec les anciens clients Makolo.

Le client génère un UUID une seule fois par intention de checkout et conserve la même clé lors d'un retry réseau :

```json
{
  "idempotency_key": "8120c67c-b13f-4cda-b9c5-b29db2a71d7f",
  "event_id": "uuid",
  "customer_name": "Amina K.",
  "customer_email": "amina@example.com",
  "promotion_code": "SUMMER20",
  "items": [
    {"ticket_type_id": "uuid", "quantity": 2}
  ]
}
```

La clé est UNIQUE en base et liée à une empreinte SHA-256 déterministe de l'intention (acheteur, événement, identité de commande, billets/quantités, promotion et sources d'attribution). Une répétition compatible retourne la commande existante avec HTTP 200 ; la première création retourne HTTP 201. Une même clé avec une intention différente retourne une erreur de validation.

La contrainte DB protège les races. L'enveloppe transactionnelle extérieure garantit qu'une deuxième transaction concurrente qui perd la course sur la clé annule aussi sa réservation de stock avant de retourner la commande gagnante. Les verrous métier existants dans Ticketing restent la source de vérité pour stock/capacité.

L'ancienne création sans `idempotency_key` reste supportée pour compatibilité, mais le Flutter MVP ne doit jamais l'utiliser.

Réponse de commande : référence, statut, sous-total, remise, code promotionnel appliqué, total final, devise, expiration, items et billets déjà émis le cas échéant.

## Promotions côté participant

Flutter ne gère pas les promotions. Il peut seulement transmettre un `promotion_code` saisi par l'utilisateur lors de la création de commande.

Le serveur :

- normalise et valide le code ;
- verrouille offre/code lorsque nécessaire ;
- applique quotas et éligibilité ;
- recalcule le prix depuis les TicketType ;
- conserve le snapshot de remise ;
- peut ramener le total à zéro.

Le client n'envoie jamais `discount_amount` ni `total_amount`.

## Parcours gratuit

Si le total final serveur vaut `0.00`, y compris après promotion :

- la commande est immédiatement `confirmed` ;
- les billets sont émis dans la même transaction ;
- aucun Payment n'est nécessaire ;
- le POST de commande contient déjà `tickets` avec `qr_token` ;
- une notification Makolo de disponibilité des billets est créée.

Flutter peut donc passer directement à l'écran de confirmation/wallet.

## Paiement sandbox

Configuration : `GET /api/v1/payments/configuration/`.

Pour un participant normal en développement, le provider visible est `sandbox`. Le provider `manual` n'est pas proposé ; il reste un outil contrôlé par les rôles Finance/staff existants et ne doit pas apparaître comme parcours mobile normal.

### Créer la tentative

`POST /api/v1/payments/payments/`

```json
{
  "order_id": "uuid",
  "provider": "sandbox",
  "method": "card",
  "idempotency_key": "mobile-payment-uuid"
}
```

Le montant et la devise viennent exclusivement de la commande. L'idempotence paiement existante est conservée et une clé ne peut pas être rejouée avec une autre commande/provider/méthode.

### Finaliser en développement

`POST /api/v1/payments/payments/<payment-id>/sandbox-complete/`

Transition attendue :

```text
order pending
  -> Payment sandbox pending
  -> sandbox-complete
  -> Payment succeeded
  -> TicketOrder confirmed
  -> émission unique des billets
```

Un retry de confirmation d'un paiement déjà réussi est sans effet secondaire : pas de double billet. Une commande expirée ne peut pas être payée. Le endpoint `manual-complete` n'est pas un parcours participant Flutter.

Aucun provider réel n'est intégré dans ce lot.

## Wallet et billets

`GET /api/v1/tickets/tickets/`

`GET /api/v1/tickets/tickets/<ticket-id>/`

Le selector Ticketing existant limite un participant à ses billets, tout en conservant les capacités serveur nécessaires aux rôles d'accès/événement sur les endpoints historiques.

Contrat mobile d'un billet :

- `id` ;
- `code` ;
- `event` ;
- `ticket_type` ;
- `order_reference` ;
- `holder` (`user_id`, `name`, `email`) ;
- champs historiques `holder_name` / `holder_email` conservés pour compatibilité ;
- `status` ;
- `issued_at` ;
- `used_at` ;
- `cancelled_at` ;
- `qr_token` ;
- `is_valid` ;
- `updated_at`.

Le QR affiché par Flutter est `qr_token`. Flutter ne valide jamais localement l'authenticité ou la consommation d'un QR ; seul `/scanner/scan/` fait foi.

`updated_at` permet une synchronisation incrémentale côté wallet, même si le MVP peut commencer par rafraîchir la liste complète.

## Notifications Makolo

Pas de FCM/APNs dans ce MVP. Flutter interroge les notifications internes :

- `GET /api/v1/notifications/` ;
- `GET /api/v1/notifications/unread-count/` ;
- `GET /api/v1/notifications/<id>/` ;
- `POST /api/v1/notifications/<id>/read/` ;
- `POST /api/v1/notifications/read-all/`.

Les confirmations de commande/billets sont émises aussi bien pour les commandes gratuites que pour les commandes payantes après succès du paiement. Les notifications de paiement réussi, échoué et remboursé existantes restent actives.

En plus de `action_url`, le serializer fournit `navigation`, construit à partir des métadonnées structurées déjà présentes :

```json
{
  "target": "payment",
  "event_id": "uuid éventuel",
  "order_id": "uuid",
  "payment_id": "uuid",
  "ticket_id": "uuid éventuel"
}
```

Flutter doit préférer ces identifiants structurés et ne doit pas dépendre uniquement d'une URL HTML.

## Préférences de notification personnelles

`GET /api/v1/accounts/notification-preferences/`

`PATCH /api/v1/accounts/notification-preferences/`

Toujours le compte authentifié courant ; aucun identifiant utilisateur n'est accepté. Le modèle complet est conservé : e-mail, SMS, push, marketing, sécurité, événements et heures calmes. Le MVP Flutter peut n'afficher qu'un sous-ensemble.

Lorsque `quiet_hours_enabled=true`, début et fin doivent être fournis.

## Suppression de compte

`POST /api/v1/accounts/account/delete/`

```json
{"password": "mot-de-passe-actuel"}
```

Le mot de passe courant protège cette mutation destructive.

Le service est transactionnel et ne fait pas `user.delete()`. Il :

- désactive immédiatement le compte et retire ses privilèges/roles ;
- rend son mot de passe inutilisable et blackliste ses refresh tokens ;
- remplace e-mail/username et identité personnelle par des valeurs non réversibles ;
- efface profil public, appareils, documents de vérification, followers, préférences et notifications personnelles ;
- anonymise les contacts CRM liés au compte et force leur consentement local à `unsubscribed` ;
- anonymise les snapshots acheteur/détenteur/payer dans commandes, billets, promotions et paiements ;
- conserve les références, montants, devises, statuts et relations nécessaires à l'audit financier/accès ;
- conserve la ligne User inactive/anonymisée lorsque des FK historiques PROTECT doivent rester auditables ;
- ne modifie pas silencieusement les montants financiers historiques.

Des enregistrements métiers historiques tels que scans, transferts, subscriptions ou objets créés peuvent donc encore référencer l'UUID interne du compte anonymisé sans conserver son identité de connexion.

## Mode Scanner mobile

Le Flutter MVP ne doit afficher le mode Scanner qu'après interrogation serveur.

### Événements scannables

`GET /api/v1/scanner/events/`

Un participant ordinaire reçoit une liste vide. Un scanner-agent doit avoir une affectation active et actuellement valide. Les rôles serveur déjà autorisés à gérer l'accès conservent leurs capacités.

### Affectations courantes

`GET /api/v1/scanner/assignments/current/`

Cette lecture mobile exclut les affectations inactives, futures ou expirées et inclut la porte (`access_gate`) lorsque l'affectation y est fixée.

### Scan

`POST /api/v1/scanner/scan/`

```json
{
  "event_id": "uuid",
  "access_gate_id": "uuid",
  "token": "qr_token",
  "client_reference": "uuid-généré-par-le-terminal"
}
```

Réponse métier stable :

```json
{
  "accepted": true,
  "result": "accepted",
  "message": "Accès autorisé.",
  "scan": {}
}
```

Résultats refusés possibles notamment : `duplicate`, `invalid_token`, `unknown_ticket`, `wrong_event`, `invalid_status`, `event_unavailable`, `gate_unavailable`. Une porte explicitement incompatible avec l'affectation est une erreur de permission HTTP.

`client_reference` rend le scan idempotent pour un terminal : rejouer la même mutation réseau retourne le même log. Présenter de nouveau le même QR comme une nouvelle tentative produit `duplicate` après la première acceptation.

Le throttle actuel est 180 scans/minute/utilisateur, adapté au MVP connecté. Aucun scan offline n'est implémenté.

## Parcours participant complet recommandé

```text
GET  health
POST register
POST login
GET  auth/me
GET  events/discover
GET  events/discover/<slug>
GET  events/<slug>/ticket-types
POST tickets/orders avec idempotency_key
  -> si total == 0 : confirmed + tickets immédiatement
  -> sinon : pending
POST payments/payments provider=sandbox + idempotency_key
POST payments/payments/<id>/sandbox-complete  (développement)
GET  tickets/tickets
GET  tickets/tickets/<id> -> qr_token
GET  notifications
GET/PATCH notification-preferences
```

Lors d'une perte réseau après `POST tickets/orders`, Flutter ne génère pas une nouvelle clé : il rejoue exactement la même intention avec la clé d'origine et récupère la commande déjà créée.

## Réseau local Flutter

Django reste sur le port 8000. Pour accepter un émulateur ou téléphone sur le LAN :

```text
python manage.py runserver 0.0.0.0:8000
```

Bases URL de développement usuelles :

- navigateur sur la machine : `http://127.0.0.1:8000` ;
- iOS Simulator : `http://127.0.0.1:8000` ;
- Android Emulator AVD : `http://10.0.2.2:8000` ;
- téléphone physique : `http://<IP-LAN-DE-LA-MACHINE>:8000`.

Pour le téléphone physique, ajouter explicitement l'IP LAN de la machine à `DJANGO_ALLOWED_HOSTS`, par exemple :

```text
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,192.168.1.42
```

Ne pas utiliser `*` en production et ne pas désactiver CSRF/SSL/HSTS de production pour simplifier le développement mobile.

CORS n'est pas ajouté : une application Flutter Android/iOS native n'est pas soumise à la politique CORS d'un navigateur. Une future cible Flutter Web devra être traitée séparément si elle existe.

Sur Android, l'HTTP clair local peut nécessiter une configuration **debug** côté application Flutter/Android ; cela ne justifie aucune réduction de sécurité côté Django production.

## Hors périmètre Flutter MVP

Le backend continue à faire fonctionner CRM, Customer 360, Analytics, Autopilot, promotions de gestion, partenaires, finance organisateur, création d'événements, équipes, fidélité, waitlist et transferts. Le Flutter MVP ne doit pas consommer ces surfaces de back-office.

Sont également différés : push FCM/APNs, scanner offline, recommandations/trending complexes et dashboard organisateur.
