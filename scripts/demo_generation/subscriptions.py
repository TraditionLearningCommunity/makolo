"""Scenarios de souscription payante sur un catalogue deja publie.

Ne fabrique pas de tarif, de benefit ou de droit de plateforme. Utilise
les versions payantes existantes, les transitions, factures et paiements sandbox
canoniques, sur une SQLite de test uniquement.
"""
import argparse
from collections import Counter


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile-username")
    p.add_argument("--profiles", type=int, default=30)
    p.add_argument("--count", type=int, default=3)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    if not 1 <= a.count <= 50 or not 1 <= a.profiles <= 100:
        p.error("--count 1..50")

    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.exceptions import ValidationError, PermissionDenied
    from django.db import connection, transaction
    from django.test.utils import override_settings
    from subscriptions.contracts import (
        SubscriptionPlanType, SubscriptionSubjectType, PlanVersionStatus,
        SubscriptionTransitionKind, SubscriptionTransitionStatus,
    )
    from subscriptions.models import PlanVersion
    from subscriptions.billing_models import PlanVersionBillingTerms, SubscriptionBillingObligation
    from subscriptions.runtime_services import ensure_subscription_for_profile
    from subscriptions.runtime_models import Subscription, SubscriptionItem
    from subscriptions.transition_models import SubscriptionTransition
    from subscriptions.transition_services import (
        request_subscription_transition, complete_subscription_transition,
    )
    from payments.models import Payment, PaymentProvider, PaymentMethod, PaymentStatus
    from payments.services import initiate_obligation_payment, complete_sandbox_payment

    if connection.vendor != "sqlite":
        p.error("Generateur de demo limite a SQLite")
    eligible = get_user_model().objects.filter(
        is_active=True, is_staff=False, is_superuser=False)
    if a.profile_username:
        eligible = eligible.filter(username=a.profile_username)
    else:
        eligible = eligible.filter(username__startswith="world_")
    users = list(eligible.order_by("username")[:a.profiles])
    if not users:
        p.error("Aucun profil eligible")

    choices = list(PlanVersionBillingTerms.objects.filter(
        amount__gt=0,
        plan_version__status=PlanVersionStatus.PUBLISHED,
        plan_version__plan__is_active=True,
        plan_version__plan__subject_type=SubscriptionSubjectType.PROFILE,
        plan_version__plan__plan_type=SubscriptionPlanType.ADDON,
        plan_version__plan__current_version_id__isnull=False,
    ).select_related("plan_version", "plan_version__plan").order_by(
        "plan_version__plan__code", "-plan_version__version")[:a.count])
    counters = Counter()
    if not choices:
        print("SUBSCRIPTIONS NO_PAID_CATALOG: aucune PlanVersion ADDON Profile publiee avec BillingTerms payants.")
        print("Creer et publier une vraie offre demo et ses entitlements dans le catalogue avant de generer des paiements.")
        return
    for user in users:
        for terms in choices:
            version = terms.plan_version
            key = "makolo-demo-subscription:" + str(user.pk) + ":" + str(version.pk)
            existing_sub = Subscription.objects.filter(profile=user).first()
            current_item = (SubscriptionItem.objects.filter(
                subscription=existing_sub, plan=version.plan,
                status="active",
            ).exists() if existing_sub is not None else False)
            existing_transition = (SubscriptionTransition.objects.filter(
                subscription=existing_sub, idempotency_key=key
            ).first() if existing_sub is not None else None)
            if current_item:
                counters["active_existing"] += 1
                continue
            if existing_transition and existing_transition.status == SubscriptionTransitionStatus.COMPLETED:
                counters["completed_existing"] += 1
                continue
            if not a.apply:
                counters["transition_planned"] += 1
                continue
            try:
                with transaction.atomic():
                    subscription = ensure_subscription_for_profile(user)
                    transition = request_subscription_transition(
                        subscription=subscription,
                        kind=SubscriptionTransitionKind.ADDON_ADD,
                        target_plan_version=version,
                        requested_by=user,
                        idempotency_key=key,
                    )
                    if transition.status == SubscriptionTransitionStatus.COMPLETED:
                        counters["completed_existing"] += 1
                        continue
                    linked = SubscriptionBillingObligation.objects.filter(
                        transition=transition).select_related("obligation").first()
                    if linked is None:
                        counters["no_billing_obligation"] += 1
                        continue
                    obligation = linked.obligation
                    with override_settings(PAYMENTS_SANDBOX_ENABLED=True):
                        paid = Payment.objects.filter(
                            obligation=obligation, status=PaymentStatus.SUCCEEDED).exists()
                        if not paid:
                            payment = initiate_obligation_payment(
                                obligation=obligation, actor=user,
                                provider=PaymentProvider.SANDBOX,
                                method=PaymentMethod.MOBILE_MONEY,
                                idempotency_key="makolo-demo-subscription-payment:" + str(transition.pk),
                            )
                            if payment.status != PaymentStatus.SUCCEEDED:
                                complete_sandbox_payment(payment=payment, actor=user)
                            counters["sandbox_payments_completed"] += 1
                    transition.refresh_from_db()
                    if transition.status == SubscriptionTransitionStatus.READY:
                        complete_subscription_transition(transition=transition)
                        counters["transitions_completed"] += 1
                    else:
                        counters["transitions_pending"] += 1
            except (ValidationError, PermissionDenied) as exc:
                counters["rejected"] += 1
                print("SUBSCRIPTION_REJECTED", version.plan.code, type(exc).__name__, str(exc)[:250])
    print("SUBSCRIPTIONS", "APPLY" if a.apply else "PREVIEW", dict(sorted(counters.items())))
    print("Paiement sandbox uniquement; aucun tarif ou entitlement invente.")


if __name__ == "__main__":
    main()
