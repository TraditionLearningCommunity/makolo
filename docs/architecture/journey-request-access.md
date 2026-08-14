# Démarche, Demande et Accès

## Statut

Cette note décrit l’implémentation de l’étape **Démarche / Demande / Accès** du blueprint Makolo. Le noyau canonique est désormais porté par `journeys` et `access`; `TicketOrder`, `Ticket`, `TicketType`, `Event`, `Payment` et `ScannerAssignment` restent des objets historiques ou verticaux conservés par compatibilité.

## Démarche

`Journey` représente une instance concrète du processus orchestré pour un bénéficiaire. Elle référence explicitement un `initiated_by`, un `beneficiary`, une `Activity` et, lorsque le processus vise une exécution précise, une `Occurrence`.

Les workflows supportés sont contrôlés dans le code :

- `purchase` ;
- `order_approval` ;
- `reservation` ;
- `registration` ;
- `invitation`.

Les états communs sont `draft`, `submitted`, `pending_approval`, `approved`, `pending_payment`, `confirmed`, `fulfilled`, `rejected`, `cancelled` et `expired`. Ils ne forment pas un automate administrable arbitrairement : les changements passent par les services de domaine et produisent un `JourneyTransition` auditable.

Une Journey peut exister et aller jusqu’à confirmation/fulfillment sans `TicketOrder` ni `Payment`. Le paiement reste une capacité optionnelle, jamais un invariant de la Démarche.

Si `occurrence` est renseignée, elle doit appartenir exactement à `journey.activity`. Cette règle est appliquée par validation métier et par les services ; elle n’est pas exprimable proprement par une simple contrainte SQL inter-table portable SQLite/PostgreSQL.

## Demande

`JourneyRequest` représente une décision attendue dans une Démarche, et non la Démarche elle-même. Une Journey peut avoir plusieurs Requests mais la première implémentation reste volontairement simple et n’introduit aucun moteur de chaîne de décisions.

Les états sont `pending`, `approved`, `rejected`, `cancelled` et `expired`. Les décisions passent par `approve_request`, `reject_request`, `cancel_request` ou `expire_request`; les services vérifient l’état, l’Activity et l’autorité du décideur puis synchronisent la Journey lorsque la décision modifie son étape.

## Accès

`Access` est le droit individuel canonique. Il appartient toujours à un Profil bénéficiaire, vise une `Activity`, éventuellement une `Occurrence`, et peut conserver sa provenance via une `Journey`. Une création administrative sans Journey reste possible.

Les états sont `pending`, `valid`, `used`, `cancelled`, `revoked`, `expired` et `transferred`. La politique initiale conserve le comportement single-use historique des Tickets, tout en laissant le modèle prêt à porter ultérieurement une autre politique d’utilisation.

Une Access respecte trois invariants :

- son `occurrence`, lorsqu’elle existe, appartient à son `activity` ;
- sa `journey`, lorsqu’elle existe, concerne la même `activity` ;
- `valid_until > valid_from` lorsque les deux bornes existent.

`issue_access` centralise l’émission et l’idempotence. L’unicité n’est pas définie globalement sur bénéficiaire + occurrence : une `source_key` liée à la Journey identifie le résultat métier lorsque la provenance fournit une clé stable, par exemple `ticket:<uuid>`.

## Credential

Le QR n’est pas l’Access. `AccessCredential` est une représentation révocable et versionnée du droit. Le credential QR contient un identifiant public aléatoire et une version, puis est authentifié avec le mécanisme de signature Django sous un salt dédié. Le token brut n’est pas stocké comme secret réutilisable et le même credential peut être re-rendu à partir de ses données persistées.

`rotate_access_credential` révoque les credentials actifs avant d’émettre la version suivante. L’ancien QR devient donc inutilisable. Une révocation, annulation ou expiration de l’Access invalide également ses credentials actifs.

## Validation et anti-double-use

`validate_access_credential` puis `validate_access` constituent la source de décision canonique. Ils contrôlent : authenticité et type du credential, statut du credential, existence et état du droit, fenêtre de validité, Activity/Occurrence attendue, usage antérieur et autorité du contrôleur lorsqu’elle est fournie.

Pour un droit single-use, la validation verrouille la ligne `Access` avec `select_for_update(of=("self",))`, sans nullable outer join et avec ordering vidé avant le lock. Une validation acceptée change l’Access en `used` et écrit un `AccessUse` dans la même transaction. Le gate PostgreSQL exécute un test avec deux connexions concurrentes : une seule peut obtenir `accepted`; l’autre obtient `already_used`.

`AccessUse` conserve le résultat, l’Access, le credential éventuel, le contrôleur éventuel, l’Occurrence et une source courte. Aucun secret QR brut n’est journalisé.

## Bridge Events

### TicketOrder → Journey

`TicketOrder.journey` est une OneToOne nullable pendant la migration. Le commercial reste dans Tickets : prix, lignes, réservations de stock, devise et paiement ne sont pas déplacés dans Journey.

Le backfill utilise :

- `Event.activity` comme Activity ;
- l’Occurrence Event correspondante ;
- `buyer` comme bénéficiaire/initiator, avec résolution par e-mail uniquement lorsqu’un Profil actif correspondant existe ;
- workflow `purchase` ;
- `pending → pending_payment` ;
- `confirmed → fulfilled` si des Tickets ont déjà été produits, sinon `confirmed` ;
- `cancelled → cancelled` ;
- `expired → expired`.

Les commandes invitées historiques sans Profil déterministe sont laissées au modèle legacy plutôt que de fabriquer un bénéficiaire fictif.

### Ticket → Access

`Ticket.access` est une OneToOne nullable. Le titulaire est choisi dans cet ordre : `Ticket.owner`, Profil correspondant à `holder_email`, puis bénéficiaire déterministe de la commande. Le backfill mappe :

- `valid → valid` avec la fenêtre Event comme limite de validité ;
- `used → used` ;
- `cancelled → cancelled` ;
- `refunded → revoked`.

Les nouveaux Tickets rattachables à un Profil obtiennent transactionnellement leur Access et un credential. Les Tickets invités historiques sans Profil déterministe conservent temporairement le comportement legacy ; aucune Access collective ou sans bénéficiaire n’est créée.

## Compatibilité QR historique

La stratégie retenue est le **resolver legacy contrôlé**. Les Tickets historiques backfillés ne reçoivent pas artificiellement un nouveau credential lors de la data migration ; leur QR signé `Ticket.code` peut encore être résolu vers `Ticket → Access` tant qu’il n’a pas été remplacé par une représentation canonique.

Pour les nouveaux Tickets, `ticket.qr_token` préfère le credential Access actif. Le validateur Tickets accepte à la fois cette représentation canonique et l’ancien QR signé afin de préserver les surfaces existantes.

Après rotation ou réémission, un ancien credential Access est révoqué. Le QR Ticket legacy d’un droit encore actif n’est pas accepté comme chemin de contournement lorsqu’un credential canonique existe. Pour les droits historiques déjà terminaux, le resolver conserve la sémantique métier (`used`, `cancelled`, `revoked`, `expired`) plutôt que de transformer un ancien QR authentique en « faux token ».

## Scanner

L’interface Scanner reste Event/Ticket. `ScannerAssignment`, `EventAccessGate` et `ScanLog` ne sont pas remplacés dans cette étape.

La décision critique vient désormais du service Access :

1. le scanner vérifie son autorité Event comme auparavant ;
2. le token canonique est résolu vers `AccessCredential → Access` ;
3. la validation Access décide accepté/refusé et écrit `AccessUse` ;
4. le bridge met à jour le `Ticket` historique lorsqu’un scan est accepté ;
5. le `ScanLog` historique est conservé comme journal Event-facing, avec seulement un fingerprint du token.

Les anciens QR Ticket passent par un resolver compatible puis la même décision Access lorsqu’une Access déterministe existe. Les rares Tickets bêta sans Profil/Access restent sur le dernier fallback legacy afin de ne pas casser les billets déjà émis.

## Transfert, annulation et remboursement

Lorsqu’un transfert Ticket est accepté, le titulaire du Ticket et `Access.beneficiary` sont alignés, les credentials actifs sont révoqués et un nouveau credential est émis pour un droit encore actif. Un droit historique déjà terminal peut voir son propriétaire aligné pour cohérence d’historique, sans réémission d’un droit actif.

Une annulation Ticket synchronise Access vers `cancelled`; un Ticket remboursé synchronise Access vers `revoked`. Les credentials actifs deviennent inutilisables. Le domaine Access ne décide pas si le remboursement lui-même est autorisé : Payments conserve cette responsabilité et continue à passer par le workflow Order/Ticket existant.

## Autorité

Les permissions Activity-scoped ajoutées sont :

- `activity.requests.view` ;
- `activity.requests.decide` ;
- `activity.access.view` ;
- `activity.access.manage`.

Le rôle local `activity-manager` reçoit ces permissions. Les responsabilités Espace héritent explicitement vers les Activities de cet Espace : les permissions de lecture héritent de `space.activities.view`, les décisions/gestions de `space.activities.manage`. Cette règle n’accorde ni Finance ni CRM.

Un gestionnaire Activity A ne peut pas décider ou administrer une Access de l’Activity B. Les selectors participant filtrent toujours par bénéficiaire et ne retournent jamais un `Access.objects.all()` brut à une surface utilisateur.

## Compatibilités conservées et suite

Cette étape conserve volontairement :

- `TicketOrder` comme objet commercial Event ;
- `TicketType` comme prix/quota/disponibilité Event ;
- `Ticket` comme représentation et vocabulaire Event ;
- `Payment` et `Refund` dans leur bounded context actuel ;
- `ScannerAssignment` et l’UX Scanner Event ;
- `ScanLog` historique ;
- le resolver QR Ticket legacy nécessaire à la bêta.

La prochaine étape **Commerce / Capacity** pourra introduire Offer, Order/OrderLine génériques et Capacity sans retransformer Journey en commande commerciale. `GroupEligibility`, Transport et la grande UX « Mes démarches / Mes accès » restent également hors de cette PR.