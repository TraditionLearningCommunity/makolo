from django.db.models import Q

from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission

from .models import AffiliateCampaign, Partner, PartnerCommission, PartnerPayout, ReferralAttribution, ReferralCode


def _merge_space_ids(*sets):
    if any(items is None for items in sets):
        return None
    merged = set()
    for items in sets:
        merged.update(items)
    return list(merged)


def _partner_workspace_space_ids(user):
    return _merge_space_ids(
        space_ids_with_permission(user, PermissionCode.PARTNERS_MANAGE),
        space_ids_with_permission(user, PermissionCode.PARTNERS_FINANCE),
    )


def get_partners_visible_to(user):
    queryset = Partner.objects.select_related("organization", "user")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    org_ids = _partner_workspace_space_ids(user)
    if org_ids is None:
        return queryset
    return queryset.filter(Q(organization_id__in=org_ids) | Q(user=user)).distinct()


def get_campaigns_visible_to(user):
    queryset = AffiliateCampaign.objects.select_related("organization", "event")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    org_ids = _partner_workspace_space_ids(user)
    if org_ids is None:
        return queryset
    partner_campaign_ids = ReferralCode.objects.filter(partner__user=user).values_list("campaign_id", flat=True)
    return queryset.filter(Q(organization_id__in=org_ids) | Q(id__in=partner_campaign_ids)).distinct()


def get_referral_codes_visible_to(user):
    queryset = ReferralCode.objects.select_related("campaign", "campaign__event", "campaign__organization", "partner")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    org_ids = _partner_workspace_space_ids(user)
    if org_ids is None:
        return queryset
    return queryset.filter(Q(campaign__organization_id__in=org_ids) | Q(partner__user=user)).distinct()


def get_attributions_visible_to(user):
    queryset = ReferralAttribution.objects.select_related("order", "campaign", "campaign__event", "partner", "referral_code")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    org_ids = _partner_workspace_space_ids(user)
    if org_ids is None:
        return queryset
    return queryset.filter(Q(campaign__organization_id__in=org_ids) | Q(partner__user=user)).distinct()


def get_commissions_visible_to(user):
    queryset = PartnerCommission.objects.select_related("partner", "campaign", "campaign__event", "order", "payout")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    org_ids = space_ids_with_permission(user, PermissionCode.PARTNERS_FINANCE)
    if org_ids is None:
        return queryset
    return queryset.filter(Q(campaign__organization_id__in=org_ids) | Q(partner__user=user)).distinct()


def get_payouts_visible_to(user):
    queryset = PartnerPayout.objects.select_related("organization", "partner", "created_by", "paid_by")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    org_ids = space_ids_with_permission(user, PermissionCode.PARTNERS_FINANCE)
    if org_ids is None:
        return queryset
    return queryset.filter(Q(organization_id__in=org_ids) | Q(partner__user=user)).distinct()
