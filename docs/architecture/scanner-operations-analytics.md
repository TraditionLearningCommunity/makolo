# Scanner, Operations et Analytics — généralisation canonique 8C

Cette note décrit la Tâche 8C. Elle complète le blueprint canonique sans supprimer la verticale Events ni son vocabulaire.

## Vue d’ensemble

```text
Activity / Occurrence
      │
      ├── Access / AccessCredential
      │          │
      │          ▼
      │       Scanner
      │          │
      │          ▼
      │       AccessUse
      │
      ├── Operations
      │      └── OperationsIncident
      │
      └── Domain Events
               │
               ▼
            Analytics
```

Les invariants sont :

- Scanner valide un `Access`, jamais un Ticket comme source de décision ;
- `Ticket` et `ScanLog` restent des projections Events pendant la transition ;
- `ScannerAssignment` est désormais scoped par `Activity` et éventuellement `Occurrence` ;
- Operations peut contextualiser un incident par Space / Activity / Occurrence sans Event ;
- Analytics préfère Journey, Access, CommerceOrder, Payment et Capacity ;
- une représentation legacy et son objet canonique ne sont comptés qu’une fois ;
- valeur commerciale confirmée et paiement réellement encaissé sont deux métriques différentes ;
- une inscription gratuite produit de l’engagement sans créer de faux revenu ;
- le backend reste générique, l’UI Event continue à parler d’événements, billets et contrôle d’accès.

## Scanner

### Moteur canonique

Le point d’entrée transversal est `scanner.canonical_services.scan_access_credential()` :

```text
AccessCredential
      ↓
validate_access_credential()
      ↓
Access
      ↓
AccessUse
```

Scanner ne réimplémente ni signature, ni expiration, ni révocation, ni single-use. Le service Access reçoit toujours le `expected_activity` et, lorsqu’il existe, le `expected_occurrence`. Une tentative cryptographiquement valide mais présentée dans un autre contexte est donc refusée par le moteur Access.

Une validation acceptée produit `AccessUse`. Une tentative refusée produit le résultat Access approprié sans émettre `access.used`. `ScanLog` n’est jamais consulté pour décider de l’autorisation.

### ScannerAssignment

`ScannerAssignment` conserve `event` comme projection historique nullable mais ajoute les relations explicites :

- `activity` ;
- `occurrence` nullable.

Une affectation sans Occurrence est Activity-wide. Une affectation avec Occurrence est locale à cette occurrence. Les nouvelles écritures Event dérivent automatiquement l’Activity et l’Occurrence bridgées sans exposer ces concepts techniques dans le formulaire Events.

La migration suit `expand → backfill → bridge` : les anciennes affectations Event reçoivent `event.activity` et l’Occurrence correspondante lorsqu’elle est déterminable par Activity + fenêtre temporelle. Aucun objet canonique n’est inventé lorsqu’une correspondance n’est pas sûre.

### Autorité

Deux formes d’autorité permettent de scanner :

- un Mandat Activity contenant `activity.access.scan` ;
- une `ScannerAssignment` active sur Activity/Occurrence.

La permission `activity.access.scan` est distincte de `activity.access.manage`. Le rôle système `activity-scanner` ne reçoit ni gestion Activity, ni Commerce, ni Finance, ni administration des Access.

Le rôle Space historique `access.manage` continue à autoriser les responsables d’accès existants. Dans Events, l’autorité historique de l’organisateur/access manager est conservée comme bridge UX.

### Compatibilité Events

Le chemin Event reste disponible :

```text
legacy QR Ticket
      ↓
Ticket
      ↓
Access bridge
      ↓
validate_access_credential()
      ↓
AccessUse
      ↓
ScanLog projection Event
```

Les nouveaux credentials canoniques peuvent suivre directement `QR → AccessCredential → Access`, sans Ticket ni Event.

`ScanLog` reste utile pour l’historique Event, les portes Event et le reporting legacy. Il n’est plus une source d’autorité transversale.

## Operations

### Scope canonique des incidents

`OperationsIncident` conserve son nom et ses liens historiques, mais accepte désormais :

- `organization` / Space ;
- `activity` nullable ;
- `occurrence` nullable ;
- `event` nullable comme projection legacy.

Si une Occurrence existe, elle doit appartenir à l’Activity. Si l’Activity porte un Space, le Space de l’incident doit être le même. Un Event historique peut fournir son Activity et son Space ; son Occurrence est backfillée lorsqu’elle est déterminable.

Les liens Payment et ScanLog historiques conservent leurs contrôles d’isolation Event/Space. Un Payment Commerce-only est validé via `payment.commerce_order.journey.activity/occurrence` sans nécessiter TicketOrder.

### Services et permissions

`create_incident()` et `update_incident()` centralisent les écritures importantes. La mise à jour verrouille uniquement l’incident concerné et conserve l’audit existant.

Le Operations Center global reste plateforme-only. Les nouvelles capacités Activity sont :

- `activity.operations.view` ;
- `activity.operations.manage`.

Le rôle `activity-operations-manager` est local à une Activity. Une ScannerAssignment ne confère aucune autorité Operations. Marketing et Finance ne reçoivent pas Operations automatiquement.

Une Activity/Occurrence sans `events.Event` peut créer et gérer un incident, ce qui prépare une future verticale Transport sans introduire de modèle Transport dans cette PR.

## Analytics

### Sources de vérité

Les métriques transactionnelles courantes lisent directement les modèles canoniques :

- Journey / JourneyRequest pour le funnel ;
- Access / AccessUse pour émission et usage ;
- CommerceOrder pour la valeur commerciale ;
- Payment / Refund pour l’argent réellement traité ;
- CapacityPool / CapacityReservation pour capacité et utilisation.

Les modèles TicketOrder, Ticket et ScanLog ne sont pas additionnés en parallèle lorsque leur projection canonique existe. Un achat Event bridgé reste donc une seule commande analytique, et un Ticket bridgé reste un seul droit analytique.

### Journey et engagement

Le funnel distingue les workflows `purchase`, `order_approval`, `reservation`, `registration` et `invitation`. Il ne suppose pas que tous les parcours nécessitent un paiement.

Une registration gratuite confirmée et ses Access apparaissent dans Journey/Access. Elle ne crée pas de ligne financière artificielle à zéro.

### Access

Les résumés Activity/Occurrence exposent :

- Access issued ;
- Access actifs ;
- Access utilisés ;
- Access révoqués ;
- taux d’usage ;
- tentatives refusées lorsque `AccessUse` les porte.

Ces métriques fonctionnent sans Event et sans Ticket.

### Commerce et Payment

`CommerceOrder` fournit : nombre de commandes, subtotal, remises et total commercial par devise.

`Payment` et `Refund` fournissent séparément les paiements réellement réussis, échecs, brut, remboursements et net par devise.

Une commande `on_site` ou `later` de montant positif peut donc contribuer à la **valeur commerciale confirmée** sans contribuer au **paiement encaissé via Makolo** tant qu’aucun Payment réussi ne le prouve.

USD, CDF et toute autre devise restent dans des agrégats séparés. Aucun FX n’est introduit.

### Capacity

Les indicateurs Capacity lisent les pools et réservations canoniques : total, held non expiré, committed, available et utilization. Ils ne reposent pas sur `TicketType.issued_quantity`.

### AnalyticsFact et Domain Events

`AnalyticsFact` est une projection légère des faits historiques utiles. Il stocke uniquement le type de fait, ses dimensions Space/Activity/Occurrence/Profile légitimes, une valeur numérique/devise facultative et le timestamp. Il ne recopie pas le payload complet d’un Domain Event.

Le consumer local `analytics.system` consomme les événements canoniques utiles, notamment :

- Journey submitted/approved/rejected/confirmed/fulfilled/cancelled ;
- Request approved/rejected ;
- Commerce order confirmed/cancelled ;
- Payment succeeded/refunded ;
- Access issued/used/revoked ;
- Occurrence cancelled/rescheduled.

L’unicité `domain_event + fact_type`, en plus de la consommation système at-least-once, garantit l’idempotence.

Aucun faux DomainEvent historique n’est créé. Les données historiques déjà backfillées sont lues directement depuis Journey/Access/Commerce/Payment/Capacity. Le seed de démonstration ne fait que matérialiser le consumer Analytics sur un Domain Event canonique existant afin de couvrir le modèle.

## Adaptateur Event Analytics

Les dashboards Events gardent leur vocabulaire : Billets, Commandes, Paiement, Présence, Revenus, Contrôle d’accès.

Lorsque `event.activity` existe, leurs KPIs communs viennent en priorité du cœur :

- « Billets actifs » ← Access ;
- « Présence » ← AccessUse accepté ;
- « Commandes » ← CommerceOrder ;
- « Revenus nets observés » ← Payment/Refund ;
- remplissage ← Capacity.

Les dimensions strictement Event encore non généralisées, telles que Waitlist et certains détails par TicketType, restent sur leur projection verticale jusqu’au cutover Events.

## Confidentialité et sécurité

Analytics ne stocke aucun token QR, signature ou credential secret. Les dashboards privilégient les agrégats et ne deviennent pas un export CRM nominatif.

Les permissions Analytics existantes restent séparées : les données financières demeurent derrière les permissions financières prévues. Un agent scanner n’obtient pas les revenus, et Finance ne reçoit pas Operations par effet de bord.

Toutes les résolutions Scanner/Operations/Analytics restent isolées par Space et, pour les délégations locales, par Activity/Occurrence.

## Compatibilités conservées

Après 8C restent volontairement :

- `Event`, `Ticket`, `TicketOrder` et leurs écrans ;
- `ScannerAssignment.event` nullable ;
- `ScanLog` et `EventAccessGate` ;
- `OperationsIncident.event`, Payment et ScanLog historiques ;
- les métriques Event verticales Waitlist/TicketType encore nécessaires ;
- le Operations Center plateforme existant ;
- les permissions Space historiques servant de bridge.

Le cutover final Events viendra dans une tâche ultérieure, après cette base verte.

## Hors scope

8C n’introduit ni Transport, Vehicle, Seat, manifest d’embarquement transport, PostGIS/MapLibre, BI externe, data warehouse, Kafka, prédictions, refonte CRM/Promotions/Notifications/Automation, grande Console Espace, grande UX Participant, ni suppression immédiate d’Event/Ticket/ScanLog.