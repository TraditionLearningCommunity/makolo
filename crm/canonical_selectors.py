from django.db.models import Count, Q

from .canonical_models import Audience, AudienceMember, AudienceStatus, CRMInteraction
from .models import CRMContact


def contacts_for_space(organization):
    return CRMContact.objects.filter(organization=organization).select_related("user").order_by("name", "email")


def contact_for_space_profile(organization, profile):
    return CRMContact.objects.filter(organization=organization, user=profile).select_related("user").first()


def interactions_for_contact(contact):
    return CRMInteraction.objects.filter(contact=contact).select_related("activity", "domain_event").order_by("-occurred_at")


def recent_contacts_for_space(organization, *, limit=20):
    return contacts_for_space(organization).order_by("-last_seen_at")[:limit]


def audiences_for_space(organization, *, include_archived=False):
    queryset = Audience.objects.filter(organization=organization).annotate(member_count=Count("members"))
    if not include_archived:
        queryset = queryset.filter(status=AudienceStatus.ACTIVE)
    return queryset.select_related("source_group", "source_snapshot").order_by("name")


def audience_members(audience):
    return AudienceMember.objects.filter(audience=audience).select_related("profile", "source_group", "source_snapshot").order_by("profile__email")


def profile_in_audience(*, audience, profile):
    return AudienceMember.objects.filter(audience=audience, profile=profile).exists()


def audience_candidates(organization, *, query=""):
    queryset = CRMContact.objects.filter(organization=organization, user__isnull=False).select_related("user")
    query = (query or "").strip()
    if query:
        queryset = queryset.filter(Q(name__icontains=query) | Q(email__icontains=query))
    return queryset.order_by("name", "email")
