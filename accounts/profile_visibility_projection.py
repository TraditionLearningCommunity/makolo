"""Owner-only privacy settings read model shared by API and Web.

It reads canonical facts and existing collective relationships; it never
persists presentation copies or grants authority to act for another Profile.
"""
from accounts.models import (
    PROFILE_VISIBILITY_FIELDS, ProfileVisibilityPolicy,
    ProfileVisibilityTargetKind as Target,
)
from accounts.profile_visibility import _collective_memberships
from groups.models import Group
from organizations.models import Organization, Team
from topics.models import ProfileInterest, ProfileOpenTo


def build_profile_visibility_settings(profile):
    policies = ProfileVisibilityPolicy.objects.filter(
        owner=profile
    ).prefetch_related("audiences")
    by_key = {
        (p.target_kind, p.field_key if p.target_kind == Target.FIELD
         else str(p.interest_id if p.target_kind == Target.INTEREST else p.open_to_id)): p
        for p in policies
    }

    def setting(kind, key, *, default_public):
        policy = by_key.get((kind, str(key)))
        if policy is None:
            return {"default_public": bool(default_public), "audiences": [
                {"kind": "public"}] if default_public else [], "configured": False}
        return {
            "default_public": bool(default_public),
            "configured": True,
            "audiences": [
                {"kind": row.kind, **(
                    {"id": str(row.selected_profile_id),
                     "label": row.selected_profile.full_name or row.selected_profile.username}
                    if row.selected_profile_id else
                    {"id": str(row.selected_space_id)} if row.selected_space_id else
                    {"id": str(row.selected_team_id)} if row.selected_team_id else
                    {"id": str(row.selected_group_id)} if row.selected_group_id else {}
                )}
                for row in policy.audiences.all()
            ],
        }

    memberships = _collective_memberships(profile)
    return {
        "collectives": {
            "spaces": [
                {"id": str(obj.pk), "label": obj.name, "kind": "selected_space"}
                for obj in Organization.objects.filter(pk__in=memberships["spaces"]).order_by("name")
            ],
            "teams": [
                {"id": str(obj.pk), "label": obj.name, "kind": "selected_team"}
                for obj in Team.objects.filter(pk__in=memberships["teams"]).order_by("name")
            ],
            "groups": [
                {"id": str(obj.pk), "label": obj.name, "kind": "selected_group"}
                for obj in Group.objects.filter(pk__in=memberships["groups"]).order_by("name")
            ],
        },
        "audience_kinds": [
            "public", "my_collectives", "selected_space", "selected_team",
            "selected_group", "selected_profile",
        ],
        "fields": {
            key: setting(Target.FIELD, key, default_public=True)
            for key in PROFILE_VISIBILITY_FIELDS
        },
        "interests": [
            {"id": str(row.pk), "label": row.topic.label,
             **setting(Target.INTEREST, row.pk, default_public=row.is_public)}
            for row in ProfileInterest.objects.filter(
                profile=profile, topic__is_active=True
            ).select_related("topic").order_by("topic__label")
        ],
        "open_to": [
            {"id": str(row.pk), "label": row.get_kind_display(),
             **setting(Target.OPEN_TO, row.pk, default_public=row.is_public)}
            for row in ProfileOpenTo.objects.filter(
                profile=profile, is_active=True,
            ).order_by("kind")
        ],
    }

