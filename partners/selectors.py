from django.db.models import Q

from organizations.models import OrganizationMembership

from .models import AffiliateCampaign, Partner, PartnerCommission, PartnerPayout, ReferralAttribution, ReferralCode
from .permissions import PARTNER_FINANCE_ROLES, PARTNER_MANAGEMENT_ROLES


def _organization_ids_for_roles(user, roles):
    if not getattr(user, "is_authenticated", False):
        return []
    if user.is_staff:
        return None
    return list(
        OrganizationMembership.objects.filter(
            user=user,
            is_active=True,
            role__in=roles,
        ).values_list("organization_id", flat=True)
    )


def get_partners_visible_to(user):
    queryset = Partner.objects.select_related("organization", "user")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_staff:
        return queryset
    org_ids = _organization_ids_for_roles(user, PARTNER_MANAGEMENT_ROLES | PARTNER_FINANCE_ROLES)
    return queryset.filter(Q(organization_id__in=org_ids) | Q(user=user)).distinct()


def get_campaigns_visible_to(user):
    queryset = AffiliateCampaign.objects.select_related("organization", "event")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_staff:
        return queryset
    org_ids = _organization_ids_for_roles(user, PARTNER_MANAGEMENT_ROLES | PARTNER_FINANCE_ROLES)
    partner_campaign_ids = ReferralCode.objects.filter(partner__user=user).values_list("campaign_id", flat=True)
    return queryset.filter(Q(organization_id__in=org_ids) | Q(id__in=partner_campaign_ids)).distinct()


def get_referral_codes_visible_to(user):
    queryset = ReferralCode.objects.select_related("campaign", "campaign__event", "campaign__organization", "partner")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_staff:
        return queryset
    org_ids = _organization_ids_for_roles(user, PARTNER_MANAGEMENT_ROLES | PARTNER_FINANCE_ROLES)
    return queryset.filter(Q(campaign__organization_id__in=org_ids) | Q(partner__user=user)).distinct()


def get_attributions_visible_to(user):
    queryset = ReferralAttribution.objects.select_related("order", "campaign", "campaign__event", "partner", "referral_code")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_staff:
        return queryset
    org_ids = _organization_ids_for_roles(user, PARTNER_MANAGEMENT_ROLES | PARTNER_FINANCE_ROLES)
    return queryset.filter(Q(campaign__organization_id__in=org_ids) | Q(partner__user=user)).distinct()


def get_commissions_visible_to(user):
    queryset = PartnerCommission.objects.select_related("partner", "campaign", "campaign__event", "order", "payout")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_staff:
        return queryset
    org_ids = _organization_ids_for_roles(user, PARTNER_FINANCE_ROLES)
    return queryset.filter(Q(campaign__organization_id__in=org_ids) | Q(partner__user=user)).distinct()


def get_payouts_visible_to(user):
    queryset = PartnerPayout.objects.select_related("organization", "partner", "created_by", "paid_by")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_staff:
        return queryset
    org_ids = _organization_ids_for_roles(user, PARTNER_FINANCE_ROLES)
    return queryset.filter(Q(organization_id__in=org_ids) | Q(partner__user=user)).distinct()
