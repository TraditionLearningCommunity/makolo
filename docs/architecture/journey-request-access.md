# Démarche, Demande et Accès

## Statut

Cette note décrit l’implémentation de l’étape **Démarche / Demande / Accès** du blueprint Makolo. Le noyau canonique est porté par `journeys` et `access`; `TicketOrder`, `Ticket`, `TicketType`, `Event`, `Payment` et `ScannerAssignment` restent des objets historiques ou verticaux conservés par compatibilité.

La Tâche 25 étend ce noyau pour distinguer un **Profil Makolo authentifiable** d’un **bénéficiaire externe** qui reçoit légitimement un droit sans posséder de compte. Cette extension ne transforme ni CRM Contact ni Ticket holder legacy en identité canonique universelle.

## Démarche

`Journey` représente une instance concrète du processus orchestré. Elle référence explicitement un `initiated_by`, une `Activity` et, lorsque le processus vise une exécution précise, une `Occurrence`.

L’initiateur est toujours un Profil Makolo authentifié lorsque l’action est déclenchée par un utilisateur. Le bénéficiaire logique est distinct et prend exactement une des deux formes suivantes pour les nouvelles écritures :

- `beneficiary` → Profil Makolo existant ;
- `external_beneficiary` → identité minimale d’une personne extérieure.

Une Démarche ne remplace jamais un bénéficiaire externe par son acheteur uniquement pour satisfaire une FK. Exemple : Sarah peut initier une Journey pour Jacques sans compte ; `initiated_by=Sarah` et `external_beneficiary=Jacques` restent deux faits différents.

Les workflows supportés sont contrôlés dans le code :

- `purchase` ;
- `order_approval` ;
- `reservation` ;
- `registration` ;
- `invitation`.

Les états communs sont `draft`, `submitted`, `pending_approval`, `approved`, `pending_payment`, `confirmed`, `fulfilled`, `rejected`, `cancelled` et `expired`. Ils ne forment pas un automate administrable arbitrairement : les changements passent par les services de domaine et produisent un `JourneyTransition` auditable.

Une Journey peut exister et aller jusqu’à confirmation/fulfillment sans `TicketOrder` ni `Payment`. Le paiement reste une capacité optionnelle, jamais un invariant de la Démarche.

Si `occurrence` est renseignée, elle doit appartenir exactement à `journey.activity`. Cette règle est appliquée par validation métier et par les services ; elle n’est pas exprimable proprement par une simple contrainte SQL inter-table portable SQLite/PostgreSQL.

## Bénéficiaire externe

`ExternalBeneficiary` est une identité de titulaire minimale, **pas un compte Makolo**. Il peut conserver le nom d’affichage et, lorsqu’ils sont utiles à la transaction, un email ou un téléphone, ainsi que le Profil qui a créé cette identité transactionnelle.

Invariants :

- aucun `User` fictif n’est créé ;
- aucune authentification n’est attachée à l’objet ;
- un email identique à celui d’un Profil ne déclenche jamais un claim automatique ;
- l’objet ne donne aucun accès au Profil, aux Journeys, Groupes, Payments ou autres Access d’une personne ;
- les Domain Events évitent d’embarquer email/téléphone et préfèrent des IDs et états ;
- CRM Contact reste une relation CRM et n’est pas détourné comme titulaire canonique de tous les Access.

Un rattachement futur à un Profil devra être explicite et disposer d’une preuve suffisante. T25 prépare la structure de données mais n’introduit aucun claim automatique par correspondance d’email.

## Demande

`JourneyRequest` représente une décision attendue dans une Démarche, et non la Démarche elle-même. Une Journey peut avoir plusieurs Requests mais l’implémentation reste volontairement simple et n’introduit aucun moteur de chaîne de décisions.

Les états sont `pending`, `approved`, `rejected`, `cancelled` et `expired`. Les décisions passent par `approve_request`, `reject_request`, `cancel_request` ou `expire_request`; les services vérifient l’état, l’Activity et l’autorité du décideur puis synchronisent la Journey lorsque la décision modifie son étape.

## Accès

`Access` est le droit individuel canonique. Il vise une `Activity`, éventuellement une `Occurrence`, et peut conserver sa provenance via une `Journey`. Une création administrative sans Journey reste possible.

Pour les nouvelles écritures, le titulaire est exactement un des deux suivants :

- `beneficiary` → Profil Makolo ;
- `external_beneficiary` → bénéficiaire externe.

Un Access externe reste individuel et reçoit son propre credential. Acheter trois places pour Sarah, Jacques et Enfant X produit trois Access et trois credentials lorsque le métier délivre trois droits ; aucune `Access.quantity` n’est introduite et aucun QR collectif n’est créé.

Les états sont `pending`, `valid`, `used`, `cancelled`, `revoked`, `expired` et `transferred`. La politique initiale conserve le comportement single-use historique des Tickets, tout en laissant le modèle prêt à porter ultérieurement une autre politique d’utilisation.

Un Access respecte notamment ces invariants :

- exactement un titulaire Profile ou externe pour les nouvelles écritures ;
- son `occurrence`, lorsqu’elle existe, appartient à son `activity` ;
- sa `journey`, lorsqu’elle existe, concerne la même `activity` ;
- son titulaire est cohérent avec le résultat métier porté par la Journey ;
- `valid_until > valid_from` lorsque les deux bornes existent.

`issue_access` et le service d’émission par titulaire centralisent l’émission et l’idempotence. L’unicité n’est pas définie globalement sur bénéficiaire + occurrence : une `source_key` liée à la Journey identifie le résultat métier lorsque la provenance fournit une clé stable, par exemple `ticket:<uuid>` ou `transport-ticket`. Cette idempotence empêche un retry d’émettre deux fois le même droit sans interdire un nouvel achat volontaire.

## Credential et représentation du billet

Le QR n’est pas l’Access. `AccessCredential` est une représentation révocable et versionnée du droit. Le credential QR contient un identifiant public aléatoire et une version, puis est authentifié avec le mécanisme de signature Django sous un salt dédié. Le token brut n’est pas stocké comme secret réutilisable et le même credential peut être re-rendu à partir de ses données persistées.

`rotate_access_credential` révoque les credentials actifs avant d’émettre la version suivante. L’ancien QR devient donc inutilisable. Une révocation, annulation ou expiration de l’Access invalide également ses credentials actifs.

T25 enrichit la page Access participant comme représentation imprimable du billet au lieu de créer un `TicketV2`. Elle peut afficher le titulaire, l’opérateur de l’Activity, la référence, le contexte temporel/géographique ou Transport et le QR lorsque l’état l’autorise. L’impression ou l’enregistrement navigateur en PDF partage une représentation du credential ; cela ne change pas `Access.status` vers `transferred` et ne constitue pas à lui seul un transfert juridique du droit.

## Validation et anti-double-use

`validate_access_credential` puis `validate_access` constituent la source de décision canonique. Ils contrôlent : authenticité et type du credential, statut du credential, existence et état du droit, fenêtre de validité, Activity/Occurrence attendue, usage antérieur et autorité du contrôleur lorsqu’elle est fournie.

Pour un droit single-use, la validation verrouille la ligne `Access` avec `select_for_update(of=("self",))`, sans nullable outer join et avec ordering vidé avant le lock. Une validation acceptée change l’Access en `used` et écrit un `AccessUse` dans la même transaction. Le gate PostgreSQL exécute un test avec deux connexions concurrentes : une seule peut obtenir `accepted`; l’autre obtient `already_used`.

`AccessUse` conserve le résultat, l’Access, le credential éventuel, le contrôleur éventuel, l’Occurrence et une source courte. Aucun secret QR brut n’est journalisé.

## Visibilité participant et acheteur

Les projections personnelles continuent de considérer comme **Mes accès** uniquement les Access dont le Profil connecté est réellement bénéficiaire.

Lorsqu’un acheteur a financé ou réservé un droit pour un autre titulaire, il peut retrouver l’Access issu de **sa propre CommerceOrder** afin d’afficher, imprimer ou transmettre le billet. Cette visibilité transactionnelle ne fait pas de l’acheteur le bénéficiaire et n’autorise aucun accès aux autres ressources du titulaire.

La présentation distingue donc les droits personnels des « billets achetés pour d’autres personnes ». Les selectors serveur restent la frontière anti-IDOR : un tiers qui n’est ni titulaire ni acheteur de la transaction ne peut pas ouvrir ce billet.

## Bridge Events

### TicketOrder → Journey

`TicketOrder.journey` est une OneToOne nullable pendant la migration. Le commercial reste projeté dans Tickets pour la compatibilité Event tandis que Commerce reste le noyau transversal.

Le backfill historique utilise :

- `Event.activity` comme Activity ;
- l’Occurrence Event correspondante ;
- `buyer` comme bénéficiaire/initiator lorsque ce Profil est déterminable ;
- résolution par e-mail seulement pour reconnaître un Profil actif dans le bridge legacy, jamais pour fabriquer un User ;
- workflow `purchase` ;
- `pending → pending_payment` ;
- `confirmed → fulfilled` si des Tickets ont déjà été produits, sinon `confirmed` ;
- `cancelled → cancelled` ;
- `expired → expired`.

Les commandes invitées historiques qui ne peuvent pas être attribuées de façon sûre restent sur le chemin legacy. T25 n’effectue pas de rattachement automatique de ces lignes à partir d’un email.

### Ticket → Access

`Ticket.access` est une OneToOne nullable. Pour le bridge historique, le titulaire Profile déterminable reste choisi selon les données legacy disponibles. Les nouveaux flows génériques peuvent en revanche utiliser explicitement `ExternalBeneficiary` sans créer de compte.

Le backfill mappe :

- `valid → valid` avec la fenêtre Event comme limite de validité ;
- `used → used` ;
- `cancelled → cancelled` ;
- `refunded → revoked`.

Ticket reste une représentation/compatibilité Event ; Access reste l’autorité du droit.

## Compatibilité QR historique

La stratégie retenue est le **resolver legacy contrôlé**. Les Tickets historiques backfillés ne reçoivent pas artificiellement un nouveau credential lors de la data migration ; leur QR signé `Ticket.code` peut encore être résolu vers `Ticket → Access` tant qu’il n’a pas été remplacé par une représentation canonique.

Pour les nouveaux Tickets, `ticket.qr_token` préfère le credential Access actif. Le validateur Tickets accepte à la fois cette représentation canonique et l’ancien QR signé afin de préserver les surfaces existantes.

Après rotation ou réémission, un ancien credential Access est révoqué. Le QR Ticket legacy d’un droit encore actif n’est pas accepté comme chemin de contournement lorsqu’un credential canonique existe. Pour les droits historiques déjà terminaux, le resolver conserve la sémantique métier (`used`, `cancelled`, `revoked`, `expired`) plutôt que de transformer un ancien QR authentique en « faux token ».

## Scanner

L’interface Scanner conserve les adaptations de vocabulaire Event/Transport nécessaires. La décision critique vient du service Access :

1. le scanner vérifie son autorité contextuelle ;
2. le token canonique est résolu vers `AccessCredential → Access` ;
3. la validation Access décide accepté/refusé et écrit `AccessUse` ;
4. un bridge met à jour le `Ticket` historique lorsqu’il existe ;
5. les journaux historiques restent compatibles sans conserver le token brut.

## Transfert, annulation et remboursement

Lorsqu’un transfert Ticket legacy est accepté, le titulaire du Ticket et `Access.beneficiary` sont alignés, les credentials actifs sont révoqués et un nouveau credential est émis pour un droit encore actif. T25 ne généralise pas ce mécanisme en transfert complet entre bénéficiaire externe et Profile.

Une annulation Ticket synchronise Access vers `cancelled`; un Ticket remboursé synchronise Access vers `revoked`. Les credentials actifs deviennent inutilisables. Le domaine Access ne décide pas si le remboursement lui-même est autorisé : Payments conserve cette responsabilité.

Partager ou imprimer un billet ne provoque aucune transition de transfert.

## Autorité

Les permissions Activity-scoped du domaine Journey/Access comprennent notamment :

- `activity.requests.view` ;
- `activity.requests.decide` ;
- `activity.access.view` ;
- `activity.access.manage`.

Le rôle local `activity-manager` reçoit les responsabilités prévues par ces contrats. Les responsabilités Espace héritent explicitement vers les Activities de cet Espace lorsqu’une règle d’héritage existe. Cette règle n’accorde ni Finance ni CRM.

Un gestionnaire Activity A ne peut pas décider ou administrer un Access de l’Activity B. Les selectors participant filtrent par bénéficiaire ou par transaction d’achat explicitement autorisée ; ils ne retournent jamais un `Access.objects.all()` brut à une surface utilisateur.

## Compatibilités conservées et suite

Cette étape conserve volontairement :

- `TicketOrder`, `TicketType` et `Ticket` comme projections/vocabulaire Event ;
- `Payment` et `Refund` dans leur bounded context ;
- les bridges Scanner/Ticket nécessaires à la bêta ;
- le resolver QR Ticket legacy ;
- les bénéficiaires Profile historiques sans conversion destructive.

T25 ajoute la compatibilité bénéficiaire externe de façon additive : nouvelle relation nullable, services compatibles et contraintes empêchant les nouvelles écritures ambiguës. Les anciens Access/Journey liés à un Profil continuent donc à fonctionner sans conversion en chaînes de texte.
