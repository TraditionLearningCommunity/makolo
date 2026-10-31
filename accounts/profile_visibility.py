"""Owner-controlled Profile presentation visibility.

Privacy policies compose canonical facts; they are not copies of those facts.
The current viewer's active collective relationships are evaluated at read
time. Organizational permissions never grant Passport visibility by themselves.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import (
    PROFILE_VISIBILITY_FIELDS,
    ProfileVisibilityAudience,
    ProfileVisibilityAudienceKind as Audience,
    ProfileVisibilityPolicy,
    ProfileVisibilityTargetKind as Target,
)
from groups.models import Group, GroupMembership, GroupMembershipStatus, GroupStatus
from organizations.console_context import authorized_space_ids
from organizations.models import TeamMembership, TeamMembershipStatus


def _authenticated(profile):
    return bool(
        profile is not None
        and getattr(profile, "is_authenticated", False)
        and getattr(profile, "is_active", False)
    )


def _collective_memberships(profile):
    """Same canonical sources as Moi, without treating administrative access as membership.

    The Me preview is bounded, so it cannot be used as the authority source.
    Superuser access without a concrete mandate is not a collective relation.
    """
    if not _authenticated(profile):
        return {"spaces": set(), "teams": set(), "groups": set()}
    teams = set(
        TeamMembership.objects.filter(
            user=profile, status=TeamMembershipStatus.ACTIVE,
            team__is_active=True,
        ).values_list("team_id", flat=True)
    )
    team_spaces = set(
        TeamMembership.objects.filter(
            user=profile, status=TeamMembershipStatus.ACTIVE,
            team__is_active=True,
        ).values_list("team__organization_id", flat=True)
    )
    # Groups in Moi also include groups viewable via permission; visibility
    # of another person's Profile requires a real member/owner relationship.
    groups = set(
        GroupMembership.objects.filter(
            profile=profile, status=GroupMembershipStatus.ACTIVE,
            group__status=GroupStatus.ACTIVE,
        ).values_list("group_id", flat=True)
    )
    groups.update(
        Group.objects.filter(owner_profile=profile, status=GroupStatus.ACTIVE)
        .values_list("pk", flat=True)
    )
    mandated_spaces = authorized_space_ids(profile)
    if mandated_spaces is not None:
        team_spaces.update(mandated_spaces)
    return {"spaces": team_spaces, "teams": teams, "groups": groups}


class ProfileVisibilityResolver:
    """Authoritative, request-scoped policy evaluator; fail-closed for overrides."""

    def __init__(self, *, owner, viewer=None, allow_collectives=True):
        self.owner = owner
        self.viewer = viewer
        self.is_owner = bool(_authenticated(viewer) and owner.pk == viewer.pk)
        self.allow_collectives = allow_collectives
        self._policies = {}
        for row in (
            ProfileVisibilityPolicy.objects.filter(owner=owner)
            .prefetch_related("audiences")
        ):
            key = (
                row.target_kind,
                row.field_key if row.target_kind == Target.FIELD
                else str(row.interest_id if row.target_kind == Target.INTEREST else row.open_to_id),
            )
            self._policies[key] = tuple(row.audiences.all())
        self._owner_memberships = None
        self._viewer_memberships = None

    def _audience_allows(self, rules):
        if any(row.kind == Audience.PUBLIC for row in rules):
            return True
        if not _authenticated(self.viewer) or not self.allow_collectives:
            # Explicit person grants should still work when collective
            # audiences are disabled (for example on a direct view).
            return any(
                row.kind == Audience.SELECTED_PROFILE
                and row.selected_profile_id == getattr(self.viewer, "pk", None)
                for row in rules
            ) if _authenticated(self.viewer) else False
        if any(
            row.kind == Audience.SELECTED_PROFILE
            and row.selected_profile_id == self.viewer.pk
            for row in rules
        ):
            return True
        if self._owner_memberships is None:
            self._owner_memberships = _collective_memberships(self.owner)
        if self._viewer_memberships is None:
            self._viewer_memberships = _collective_memberships(self.viewer)
        owner, viewer = self._owner_memberships, self._viewer_memberships
        common = {
            kind: owner[kind] & viewer[kind]
            for kind in ("spaces", "teams", "groups")
        }
        for row in rules:
            if row.kind == Audience.MY_COLLECTIVES and any(common.values()):
                return True
            if row.kind == Audience.SELECTED_SPACE and row.selected_space_id in common["spaces"]:
                return True
            if row.kind == Audience.SELECTED_TEAM and row.selected_team_id in common["teams"]:
                return True
            if row.kind == Audience.SELECTED_GROUP and row.selected_group_id in common["groups"]:
                return True
        return False

    def allows(self, *, target_kind, key, legacy_public=True):
        if self.is_owner:
            return True
        rules = self._policies.get((target_kind, str(key)))
        if rules is None:
            return bool(legacy_public)
        # An existing policy with no audiences is a deliberate private choice.
        return self._audience_allows(rules)

    def field(self, key):
        if key not in PROFILE_VISIBILITY_FIELDS:
            return False
        return self.allows(target_kind=Target.FIELD, key=key)

    def interest(self, row):
        return self.allows(
            target_kind=Target.INTEREST, key=row.pk,
            legacy_public=row.is_public,
        )

    def open_to(self, row):
        return self.allows(
            target_kind=Target.OPEN_TO, key=row.pk,
            legacy_public=row.is_public and row.is_active,
        )


@transaction.atomic
def replace_profile_visibility(*, owner, target_kind, field_key="", interest=None,
                               open_to=None, audiences=()):
    """Replace all audiences atomically, strictly scoped to the owner.

    Audience items are dicts with kind and optional id. No raw model field is
    selectable outside the publishable allowlist. Empty audiences = private.
    """
    if not _authenticated(owner):
        raise ValidationError("Le propriétaire doit être authentifié.")
    if target_kind == Target.FIELD:
        if field_key not in PROFILE_VISIBILITY_FIELDS or interest or open_to:
            raise ValidationError("Information de Profil non publiable.")
    elif target_kind == Target.INTEREST:
        if field_key or not interest or open_to or interest.profile_id != owner.pk:
            raise ValidationError("Intérêt non autorisé.")
    elif target_kind == Target.OPEN_TO:
        if field_key or interest or not open_to or open_to.profile_id != owner.pk:
            raise ValidationError("Ouvert à non autorisé.")
    else:
        raise ValidationError("Information de confidentialité inconnue.")
    if not isinstance(audiences, (list, tuple)) or len(audiences) > 100:
        raise ValidationError("Nombre d'audiences invalide.")

    selected = []
    keys = set()
    memberships = _collective_memberships(owner)
    for item in audiences:
        if not isinstance(item, dict):
            raise ValidationError("Audience invalide.")
        kind, target_id = item.get("kind"), item.get("id")
        if kind in (Audience.PUBLIC, Audience.MY_COLLECTIVES):
            if target_id is not None:
                raise ValidationError("Cette audience ne prend pas de destinataire.")
            key = (kind, "")
            values = {}
        elif kind == Audience.SELECTED_PROFILE:
            from django.contrib.auth import get_user_model
            recipient = get_user_model().objects.filter(pk=target_id, is_active=True).first()
            if not recipient:
                raise ValidationError("Destinataire inconnu.")
            key = (kind, str(recipient.pk))
            values = {"selected_profile": recipient}
        elif kind in (Audience.SELECTED_SPACE, Audience.SELECTED_TEAM, Audience.SELECTED_GROUP):
            from organizations.models import Organization, Team
            model, membership_key, values_key = {
                Audience.SELECTED_SPACE: (Organization, "spaces", "selected_space"),
                Audience.SELECTED_TEAM: (Team, "teams", "selected_team"),
                Audience.SELECTED_GROUP: (Group, "groups", "selected_group"),
            }[kind]
            obj = model.objects.filter(pk=target_id).first()
            if obj is None or obj.pk not in memberships[membership_key]:
                raise ValidationError("Ce collectif ne vous appartient pas en tant que relation active.")
            key = (kind, str(obj.pk))
            values = {values_key: obj}
        else:
            raise ValidationError("Audience inconnue.")
        if key in keys:
            raise ValidationError("Une audience est présente plusieurs fois.")
        keys.add(key)
        selected.append((kind, values))

    # PUBLIC already includes every viewer; mixing it with narrower audiences
    # is an easy way to disclose a fact unintentionally from the editor.
    if (Audience.PUBLIC, "") in keys and len(keys) > 1:
        raise ValidationError(
            "Tout le monde est exclusif : retirez Public pour restreindre la visibilité."
        )

    criteria = {"owner": owner, "target_kind": target_kind}
    if target_kind == Target.FIELD:
        criteria["field_key"] = field_key
    elif target_kind == Target.INTEREST:
        criteria["interest"] = interest
    else:
        criteria["open_to"] = open_to
    policy, _created = ProfileVisibilityPolicy.objects.select_for_update().get_or_create(**criteria)
    # Validate all new rules before changing the old selection.
    entries = [
        ProfileVisibilityAudience(policy=policy, kind=kind, **values)
        for kind, values in selected
    ]
    for row in entries:
        row.full_clean(validate_unique=False, validate_constraints=False)
    policy.audiences.all().delete()
    ProfileVisibilityAudience.objects.bulk_create(entries)
    return policy
