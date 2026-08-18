# Events vertical — Task 9

Events is a Makolo product vertical composed on the canonical domain core. `Event` is not a universal technical root and does not own generic scheduling, commerce, capacity, payment or access state.

## Composition

| Event vocabulary | Canonical owner |
| --- | --- |
| Event | `Activity` + Event-specific configuration |
| Date / planning | `Occurrence` |
| Physical venue | `OccurrencePlace → Place` |
| Ticket type | `TicketType → Offer + CapacityPool` |
| Registration / purchase process | `Journey` |
| Order | `TicketOrder → CommerceOrder` |
| Payment | `Payment → CommerceOrder` |
| Ticket | `Ticket → Access` |
| QR | `AccessCredential` |
| Access control | `AccessUse` |

The Event UI and API keep the Event vocabulary. Callers still see Événement, Date, Lieu, Type de billet, Tarif, Commande, Billet and Contrôle d’accès; the backend representation is composed.

## Event

`events.Event` is a required one-to-one configuration over `activities.Activity`.

Activity is authoritative for Space, title, short description, description, generic status and visibility. Occurrence is authoritative for start, end, timezone and schedule status. `Event.primary_occurrence` is the current single-occurrence vertical projection; Activity itself remains multi-occurrence capable.

Task 9 removes stored Event columns for `organization`, `organizer`, `title`, `short_description`, `description`, `status`, `visibility`, `start_at`, `end_at`, `timezone` and `capacity`. Compatibility properties expose the old Event vocabulary by reading Activity, Occurrence and CapacityPool; they are not storage.

Event keeps Event-specific category, cover/presentation data, stable Event route slug, publication/cancellation timestamps, metadata and the current global registration policy. `registration_start_at` / `registration_end_at` bound Offer availability; they do not create a second sale window that can make an Offer available outside the Event policy.

## EventVenue

`EventVenue` remains an Event presentation/configuration object for its label, physical/online/hybrid kind and online URL. `Place` is authoritative for physical address, locality, country and coordinates; `OccurrencePlace` connects the primary Event occurrence to that Place.

The old geographic columns on EventVenue are retained temporarily only for imported historical rows and are readonly in admin. New physical/hybrid configuration requires `EventVenue.place`; no new Event flow writes legacy address/coordinate fields.

## TicketType

`TicketType` remains because “Type de billet” is legitimate Event language. It stores the Event label/description/public presentation and required links to one Offer and one CapacityPool.

Offer is authoritative for unit price, currency, payment mode, sale availability window, per-order bounds and active commercial state. CapacityPool is authoritative for total capacity and held/committed availability. Task 9 removes TicketType storage for `price`, `currency`, `quantity_total`, `reserved_quantity`, `issued_quantity`, `sales_start_at`, `sales_end_at`, `min_per_order`, `max_per_order` and `is_active`.

`configure_ticket_type` is the vertical service that routes Event form/API values to Offer and CapacityPool. TicketType counters never decide availability.

## TicketOrder and TicketOrderItem

`TicketOrder` remains an Event projection because its Event reference, Event-facing reference number, guest/history compatibility and provider-facing historical endpoints are still consumed. New checkout creates `Journey → CommerceOrder → CommerceOrderItem/CapacityReservation` first and then links the Event projections.

`CommerceOrder` is authoritative for commercial state, totals, discounts, currency and confirmation. `TicketOrder.status`, `total_amount` and `currency` remain stored compatibility projections for historical callbacks/templates and are updated only after canonical transitions. They must not be used to calculate availability, price, fulfillment or Payment amount when CommerceOrder exists.

`TicketOrderItem.quantity` and `unit_price` remain historical Event snapshots. `CommerceOrderItem` is authoritative for commercial line decisions.

## Ticket

Ticket is the Event representation of an Access. New Tickets receive `Access`; their displayed status comes from Access, their QR comes from an active AccessCredential and successful control is recorded as AccessUse.

Legacy `Ticket.code`, `Ticket.status`, holder fields and timestamps remain for historical guest/unconverted tickets and stable Event endpoints. A legacy signed Ticket QR is accepted only for explicitly historical Tickets without a replacement canonical credential. No new flow generates a legacy QR as the primary credential.

Transfer changes the Access beneficiary and rotates the credential before updating Event presentation fields.

## Waitlist

`TicketWaitlistEntry` remains Event-specific. Eligibility and sold-out decisions read CapacityPool. Promotion from the queue creates the same Journey/CapacityReservation/CommerceOrder path as normal Event checkout. A free waitlist offer can fulfill without Payment; a paid offer remains pending until provider payment succeeds.

## Payments bridge

`Payment.commerce_order` is the canonical commercial relation and Payment remains financial truth. `Payment.ticket_order` is retained temporarily because provider callbacks, refund UX and historical Event payment endpoints still use the Event projection. New Event payment amount/currency/state checks read CommerceOrder.

Removal condition: migrate the remaining provider/refund/legacy endpoint consumers so Event callbacks can resolve the projection from CommerceOrder rather than requiring the legacy FK.

## Scanner and Operations

Events supplies Activity and its primary Occurrence as context. Scanner validates AccessCredential/Access and records AccessUse; it does not make Ticket status authoritative. ScanLog remains an Event operational audit/presentation record.

Operations owns incidents. Event surfaces may link an incident to Event while canonical operational scope remains Activity/Occurrence/Space.

## Analytics

Event detail analytics uses the canonical 8C selectors: Journey for process, CommerceOrder for commercial value, Payment for collected money, CapacityPool/Reservation for capacity, Access for rights and AccessUse for attendance. It never adds TicketOrder to CommerceOrder, Ticket to Access, or ScanLog to AccessUse as separate facts.

The distinction remains explicit: commercial value is not provider cash collected.

## Authorization

Event management is Activity management. Creation/navigation uses Space Activities permissions; object management uses Activity mandates. Finance, access control/scanner and analytics keep their separate canonical permission codes. `OrganizationRole.EVENT_MANAGER` may still exist as an old vocabulary mapping in authorization data, but Task 9 Event code does not read it as an independent authority.

## Compatibility bridges retained

- `events.activity_bridge`: import-compatible accessor and EventVenue.place → OccurrencePlace projection only; it no longer syncs generic Event fields into Activity/Occurrence.
- `tickets.commerce_capacity_bridge`: backfill path only for historical TicketOrder/TicketOrderItem rows missing Commerce objects; existing canonical objects are never overwritten.
- `tickets.journey_access_bridge`: backfill path only for identifiable historical rows missing Journey/Access; it never invents a Profile and never overwrites existing Access/Journey state.
- `Payment.ticket_order`: historical provider/refund/Event endpoint compatibility as described above.
- EventVenue legacy geography and Ticket/TicketOrder stored compatibility fields: historical data/UI compatibility until their remaining consumers are migrated.

These bridges are debt-reduction boundaries, not bidirectional synchronization.

## New write path

Creating an Event is transactional: Activity → Occurrence → optional OccurrencePlace → Event configuration. A unified Event form routes each field to its owner.

Paid Event checkout: Event UI → TicketType → Offer/Capacity → Journey → CommerceOrder/CapacityReservation → Payment when required → Access → Ticket representation.

Free Event checkout: Event UI → TicketType/registration → Offer/Capacity → Journey → CommerceOrder confirmation where the checkout representation requires it → Access → Ticket representation, with **no Payment**.

An Event may exist without TicketType/Offer; commerce is not required by the Event definition.
