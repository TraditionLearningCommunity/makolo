from __future__ import annotations

from datetime import timedelta

from loyalty.models import (
    LedgerKind,
    LoyaltyAccount,
    LoyaltyLedgerEntry,
    LoyaltyProgram,
    LoyaltyReward,
    LoyaltyRewardRedemption,
    LoyaltyTier,
    MembershipPlan,
    MembershipStatus,
    MembershipSubscription,
)
from tickets.models import TicketOrderStatus

from .common import SeedContext, backdate, choose, money, upsert


def _seed_loyalty(ctx: SeedContext) -> None:
    ctx.loyalty_programs.clear()
    for org_index, org in enumerate(ctx.organizations[:6]):
        owner = org.memberships.filter(role="owner", is_active=True).first().user
        program = upsert(LoyaltyProgram, f"org-{org_index}-loyalty", defaults={
            "organization": org,
            "name": f"Club {org.name}",
            "description": "Programme de fidélité de démonstration : achats, check-ins, statuts et récompenses.",
            "points_name": "Makolo Points",
            "points_per_order": 20,
            "points_per_ticket": 10,
            "points_per_checkin": 30,
            "is_active": org_index != 5,
            "created_by": owner,
        })
        backdate(program, created_at=ctx.as_of - timedelta(days=500-org_index*25), updated_at=ctx.as_of - timedelta(days=30))
        ctx.loyalty_programs.append(program)

        tiers = []
        for j, (name, code, threshold, mult) in enumerate([
            ("Explorer", "EXPLORER", 0, money("1.00")),
            ("Insider", "INSIDER", 250, money("1.15")),
            ("Ambassadeur", "AMBASSADOR", 800, money("1.35")),
        ]):
            tier = upsert(LoyaltyTier, f"org-{org_index}-tier-{j}", defaults={
                "program": program, "name": name, "code": code, "threshold_points": threshold,
                "points_multiplier": mult,
                "benefits": choose([
                    "Accès aux annonces en avant-première.",
                    "Bonus points et files prioritaires sur certains événements.",
                    "Avantages premium et invitations communautaires.",
                ], j),
                "is_active": True,
            })
            backdate(tier, created_at=program.created_at + timedelta(days=1+j), updated_at=program.updated_at)
            tiers.append(tier)

        benefit_promo = next((p for p in ctx.promotions if p.organization_id == org.id), None)
        plans = []
        for j, (name, code, price, mult, bonus) in enumerate([
            ("Communauté", "COMMUNITY", money("0"), money("1.00"), 50),
            ("Plus annuel", "PLUS", money("25"), money("1.25"), 150),
        ]):
            plan = upsert(MembershipPlan, f"org-{org_index}-plan-{j}", defaults={
                "program": program, "name": name, "code": code,
                "description": f"Plan {name.lower()} du programme fidélité.",
                "price": price, "currency": "USD", "duration_days": 365,
                "points_multiplier": mult, "join_bonus_points": bonus,
                "benefit_promotion": benefit_promo,
                "benefits": "Avantages membres, bonus de points et accès à certaines offres.",
                "is_active": True, "created_by": owner,
            })
            backdate(plan, created_at=program.created_at + timedelta(days=4+j), updated_at=program.updated_at)
            plans.append(plan)

        rewards = []
        for j, (name, cost) in enumerate([
            ("Boisson offerte sur événement partenaire", 180),
            ("Réduction membre", 350),
            ("Pass upgrade sous réserve", 700),
        ]):
            reward = upsert(LoyaltyReward, f"org-{org_index}-reward-{j}", defaults={
                "program": program, "name": name,
                "description": "Récompense de démonstration basée sur les points accumulés.",
                "points_cost": cost, "promotion": benefit_promo if j == 1 else None,
                "fulfillment_instructions": "Présenter la confirmation dans l'espace Makolo.",
                "max_redemptions_per_member": 2,
                "starts_at": ctx.as_of - timedelta(days=120), "ends_at": ctx.as_of + timedelta(days=365),
                "is_active": True, "created_by": owner,
            })
            backdate(reward, created_at=ctx.as_of - timedelta(days=120-j), updated_at=ctx.as_of - timedelta(days=20))
            rewards.append(reward)

        pivot = (org_index * 13) % len(ctx.users)
        program_users = ctx.users[pivot:] + ctx.users[:pivot]
        for j, user in enumerate(program_users[:min(24, len(program_users))]):
            points = 80 + (j * 83) % 1100
            tier = tiers[2] if points >= 800 else (tiers[1] if points >= 250 else tiers[0])
            account = upsert(LoyaltyAccount, f"org-{org_index}-account-{j}", defaults={
                "program": program, "user": user, "points_balance": points,
                "lifetime_earned": points + (120 if j % 5 == 0 else 0),
                "lifetime_redeemed": 120 if j % 5 == 0 else 0, "current_tier": tier,
            })
            joined = ctx.as_of - timedelta(days=300-j*4)
            backdate(account, joined_at=joined, updated_at=ctx.as_of - timedelta(days=j % 12))

            subscription_status = choose([MembershipStatus.ACTIVE, MembershipStatus.ACTIVE, MembershipStatus.EXPIRED, MembershipStatus.CANCELLED, MembershipStatus.PENDING], j)
            plan = plans[j % len(plans)]
            if subscription_status == MembershipStatus.PENDING:
                starts, ends = None, None
            elif subscription_status == MembershipStatus.EXPIRED:
                starts = ctx.as_of - timedelta(days=plan.duration_days + 90 + j); ends = starts + timedelta(days=plan.duration_days)
            elif subscription_status == MembershipStatus.CANCELLED:
                starts = ctx.as_of - timedelta(days=220 + j); ends = starts + timedelta(days=plan.duration_days)
            else:
                starts = ctx.as_of - timedelta(days=120 + j); ends = starts + timedelta(days=plan.duration_days)
            benefit_code = benefit_promo.codes.first() if benefit_promo else None
            sub = upsert(MembershipSubscription, f"org-{org_index}-subscription-{j}", defaults={
                "program": program, "plan": plan, "user": user, "status": subscription_status,
                "price_amount": plan.price, "currency": plan.currency, "starts_at": starts, "ends_at": ends,
                "activation_source": "manual" if plan.price > 0 else "free",
                "activated_by": owner if subscription_status == MembershipStatus.ACTIVE else None,
                "benefit_code": benefit_code,
                "activated_at": starts if subscription_status == MembershipStatus.ACTIVE else None,
                "cancelled_at": ctx.as_of - timedelta(days=15) if subscription_status == MembershipStatus.CANCELLED else None,
                "expired_at": ends if subscription_status == MembershipStatus.EXPIRED else None,
            })
            backdate(sub, requested_at=joined, updated_at=ctx.as_of - timedelta(days=j % 9))

            order = next((o for o in ctx.orders if o.buyer_id == user.id and o.event.organization_id == org.id and o.status == TicketOrderStatus.CONFIRMED), None)
            ledger_specs = [
                (LedgerKind.MEMBERSHIP_BONUS, plan.join_bonus_points, "Bonus d'adhésion", sub, None, None),
                (LedgerKind.ORDER, 20, "Points achat confirmé", None, order, None),
            ]
            if order and order.tickets.exists():
                ledger_specs.append((LedgerKind.CHECKIN, 30, "Bonus présence événement", None, order, order.tickets.first()))
            for k, (kind, value, desc, subscription, ledger_order, ticket) in enumerate(ledger_specs):
                if value == 0 or (kind == LedgerKind.ORDER and ledger_order is None):
                    continue
                entry = upsert(LoyaltyLedgerEntry, f"org-{org_index}-account-{j}-ledger-{k}", defaults={
                    "account": account, "kind": kind, "points": value, "description": desc,
                    "idempotency_key": f"demo-loyalty-{org_index}-{j}-{k}", "order": ledger_order,
                    "ticket": ticket, "subscription": subscription, "reward_redemption": None,
                    "created_by": owner, "metadata": {"seed": "makolo-demo"},
                })
                backdate(entry, created_at=joined + timedelta(days=10+k*12))

            if j % 7 == 0 and points >= rewards[0].points_cost:
                reward = rewards[j % len(rewards)]
                redemption = upsert(LoyaltyRewardRedemption, f"org-{org_index}-reward-redemption-{j}", defaults={
                    "account": account, "reward": reward, "user": user, "status": "redeemed",
                    "points_cost": reward.points_cost,
                    "promotion_code": benefit_code if reward.promotion_id else None, "cancelled_at": None,
                })
                backdate(redemption, redeemed_at=ctx.as_of - timedelta(days=20+j))
                ledger = upsert(LoyaltyLedgerEntry, f"org-{org_index}-reward-ledger-{j}", defaults={
                    "account": account, "kind": LedgerKind.REWARD, "points": -reward.points_cost,
                    "description": f"Récompense : {reward.name}", "idempotency_key": f"demo-reward-{org_index}-{j}",
                    "order": None, "ticket": None, "subscription": None, "reward_redemption": redemption,
                    "created_by": owner, "metadata": {"seed": "makolo-demo"},
                })
                backdate(ledger, created_at=redemption.redeemed_at)
