# Loyalty, memberships and rewards

## Purpose

Lot 5 adds organization-scoped retention mechanics without turning Makolo points into money. Each organizer can run one loyalty program with deterministic earning rules, levels, memberships and redeemable rewards.

## Source of truth

`LoyaltyLedgerEntry` is the immutable points audit trail. `LoyaltyAccount.points_balance`, `lifetime_earned` and `lifetime_redeemed` are operational aggregates updated transactionally by the service layer. Every automatic business event uses a unique idempotency key.

Points are not a currency and are never converted between USD, CDF or another money currency. Purchase points are based on order/ticket counts rather than aggregating monetary amounts across currencies.

## Automatic earning

A confirmed ticket order earns `points_per_order + points_per_ticket × quantity`. A successful check-in earns `points_per_checkin`. Active tier and membership multipliers are applied at earning time. Repeated signals are idempotent. Cancelling a confirmed order reverses available points from that order and never creates a negative balance.

## Levels

Levels are based on lifetime earned points. The highest active threshold reached becomes the current level. Redemptions do not erase lifetime relationship history. An order cancellation may reduce lifetime earned points and therefore recalculate the level.

## Memberships

A membership plan snapshots price and currency into each subscription, has a bounded duration, a points multiplier, an optional join bonus and an optional Promotion benefit. Free plans self-activate. Paid plans stay `pending` until Owner/Admin/Finance validates the external/manual payment.

This is deliberate: Makolo does not claim recurring-card or Mobile Money billing before a real PSP exists. When a future recurring PSP is integrated, it should activate the same `MembershipSubscription` service after verified payment rather than bypassing it.

A membership Promotion benefit generates a private, single-use PromotionCode valid only for the subscription period. Expired/cancelled memberships no longer apply points multipliers; their benefit code is disabled on explicit expiration/cancellation and also carries its own `ends_at` guard.

## Rewards

A reward costs points and may optionally link to an existing Promotion. Redemption locks the account and reward, checks availability, member quota and points balance, then creates an immutable debit. When a Promotion is linked, Makolo generates a private single-use code. The normal Promotions checkout engine remains the source of truth for discount eligibility and quota enforcement.

## Permissions

Owner/Admin/Marketing manage loyalty strategy, levels, plans, rewards and audited point adjustments. Owner/Admin/Finance can inspect memberships and manually activate paid subscriptions. Finance cannot silently change marketing/retention strategy. Participants can only view their own accounts, request/cancel their own memberships and redeem their own rewards. Staff retains platform supervision.

Public loyalty endpoints expose program configuration only; they never enumerate other members or their balances.

## Interfaces

Web:

- `/loyalty/`
- `/loyalty/o/<organization-slug>/`
- `/loyalty/manage/<organization-slug>/`

API:

- `GET /api/v1/loyalty/me/`
- `GET /api/v1/loyalty/organizations/<slug>/`
- `POST /api/v1/loyalty/memberships/join/`
- `POST /api/v1/loyalty/memberships/<id>/activate/`
- `POST /api/v1/loyalty/memberships/<id>/cancel/`
- `POST /api/v1/loyalty/rewards/<id>/redeem/`
- management endpoints for programs, tiers, plans, rewards and audited account adjustments.

## Autopilot

`expire_due_memberships()` is idempotent and designed for the Makolo Autopilot cycle. Even before status cleanup, benefit enforcement checks the membership time window and generated Promotion codes have their own validity window, so stale status cannot extend a benefit beyond `ends_at`.
