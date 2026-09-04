import inspect

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from access.models import Access
from accounts.models import UserProfile
from activities.models import Activity, ActivityStatus, ActivityVisibility
from authorization.constants import PermissionCode, SystemRoleCode
from authorization.models import Mandate
from authorization.services import can, grant_space_role
from journeys.models import Journey
from notifications.models import Notification, NotificationDelivery
from organizations.models import Organization, OrganizationMembership
from topics.models import ActivityTopic, OpenToKind, ProfileInterest, ProfileOpenTo, Topic

from . import profile_search
from .bilateral_services import (
    cancel_profile_solicitation,
    close_action_need,
    create_action_need,
    create_profile_solicitation,
    respond_to_profile_solicitation,
)
from .models import ActionNeedStatus, ProfileSolicitation, ProfileSolicitationStatus
from .profile_search import search_profiles_for_need


User = get_user_model()
PASSWORD = "Strong-G7-Password-2026!"


def make_user(*, username, first_name="", last_name="", public=True, searchable=True):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.test",
        password=PASSWORD,
        first_name=first_name,
        last_name=last_name,
        phone="+243999000111",
    )
    UserProfile.objects.create(
        user=user,
        city="Lubumbashi",
        country="RDC",
        address=f"Adresse privée {username}",
        latitude=-11.66,
        longitude=27.48,
        public_profile=public,
        searchable=searchable,
    )
    return user


class G7ProfileSearchTests(TestCase):
    def setUp(self):
        self.owner = make_user(username="g7-owner", first_name="Gilbert")
        self.candidate = make_user(username="g7-amina", first_name="Amina", last_name="B")
        self.topic = Topic.objects.create(code="g7-tech", label="Technologie")
        self.need = create_action_need(
            actor=self.owner,
            owner_profile=self.owner,
            title="Mentors pour atelier IA",
            open_to_kind=OpenToKind.MENTOR,
            topics=[self.topic],
        )
        ProfileOpenTo.objects.create(
            profile=self.candidate,
            kind=OpenToKind.MENTOR,
            is_active=True,
            is_public=False,
            is_searchable=True,
        )

    def candidate_ids(self):
        return {candidate.profile_id for candidate in search_profiles_for_need(need=self.need)}

    def test_public_searchable_and_searchable_open_to_is_candidate(self):
        self.assertIn(self.candidate.pk, self.candidate_ids())

    def test_searchable_false_is_absent(self):
        self.candidate.profile.searchable = False
        self.candidate.profile.save(update_fields=["searchable", "updated_at"])
        self.assertNotIn(self.candidate.pk, self.candidate_ids())

    def test_public_profile_false_is_absent(self):
        self.candidate.profile.public_profile = False
        self.candidate.profile.save(update_fields=["public_profile", "updated_at"])
        self.assertNotIn(self.candidate.pk, self.candidate_ids())

    def test_open_to_non_searchable_is_absent_even_when_public(self):
        row = ProfileOpenTo.objects.get(profile=self.candidate, kind=OpenToKind.MENTOR)
        row.is_public = True
        row.is_searchable = False
        row.save(update_fields=["is_public", "is_searchable", "updated_at"])
        self.assertNotIn(self.candidate.pk, self.candidate_ids())

    def test_private_interest_is_never_a_reason(self):
        ProfileInterest.objects.create(profile=self.candidate, topic=self.topic, is_public=False)
        candidate = search_profiles_for_need(need=self.need)[0]
        self.assertFalse(any("Technologie" in reason for reason in candidate.reasons))

    def test_public_interest_is_an_explainable_reason_without_score(self):
        ProfileInterest.objects.create(profile=self.candidate, topic=self.topic, is_public=True)
        candidate = search_profiles_for_need(need=self.need)[0]
        self.assertIn("Centre d’intérêt public : Technologie", candidate.reasons)
        self.assertFalse(any("/100" in reason or "%" in reason for reason in candidate.reasons))

    def test_private_activity_is_never_a_reason(self):
        activity = Activity.objects.create(
            owner_profile=self.candidate,
            created_by=self.candidate,
            title="Atelier privé secret",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PRIVATE,
        )
        ActivityTopic.objects.create(activity=activity, topic=self.topic)
        candidate = search_profiles_for_need(need=self.need)[0]
        self.assertFalse(any("Atelier privé secret" in reason for reason in candidate.reasons))

    def test_public_activity_can_be_an_explainable_reason(self):
        activity = Activity.objects.create(
            owner_profile=self.candidate,
            created_by=self.candidate,
            title="Atelier Python public",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        ActivityTopic.objects.create(activity=activity, topic=self.topic)
        candidate = search_profiles_for_need(need=self.need)[0]
        self.assertIn("A organisé « Atelier Python public »", candidate.reasons)

    def test_candidate_projection_does_not_expose_private_domains_or_pii(self):
        candidate = search_profiles_for_need(need=self.need)[0]
        self.assertEqual(
            set(candidate.__dataclass_fields__),
            {"profile_id", "display_name", "city", "country", "open_to_label", "reasons"},
        )
        rendered = " ".join((candidate.display_name, candidate.city, candidate.country, *candidate.reasons))
        self.assertNotIn(self.candidate.email, rendered)
        self.assertNotIn(self.candidate.phone, rendered)
        self.assertNotIn(self.candidate.profile.address, rendered)
        self.assertNotIn(str(self.candidate.profile.latitude), rendered)
        self.assertNotIn(str(self.candidate.profile.longitude), rendered)

    def test_people_search_does_not_consult_private_action_domains(self):
        source = inspect.getsource(profile_search)
        for forbidden_import in (
            "from discovery.models",
            "from objectives",
            "from journeys",
            "from payments",
            "from personal_assets",
        ):
            self.assertNotIn(forbidden_import, source)


class G7NeedPermissionTests(TestCase):
    def setUp(self):
        self.owner = make_user(username="g7-personal")
        self.space_manager = make_user(username="g7-space-manager")
        self.member_only = make_user(username="g7-member-only")
        self.outsider = make_user(username="g7-outsider")
        self.space = Organization.objects.create(name="Tech Hub G7", created_by=self.space_manager)
        grant_space_role(
            profile=self.space_manager,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.space_manager,
            source="g7-test",
        )
        OrganizationMembership.objects.create(
            organization=self.space,
            user=self.member_only,
            role="event_manager",
            is_active=True,
        )

    def test_personal_need_is_allowed_only_for_its_profile_owner(self):
        need = create_action_need(
            actor=self.owner,
            owner_profile=self.owner,
            title="Assistant photo",
            open_to_kind=OpenToKind.COLLABORATE,
        )
        self.assertEqual(need.owner_profile, self.owner)
        with self.assertRaises(PermissionDenied):
            create_action_need(
                actor=self.outsider,
                owner_profile=self.owner,
                title="Usurpation",
                open_to_kind=OpenToKind.COLLABORATE,
            )

    def test_space_need_requires_canonical_permission(self):
        self.assertTrue(can(self.space_manager, PermissionCode.SPACE_MANAGE, space=self.space))
        need = create_action_need(
            actor=self.space_manager,
            space=self.space,
            title="Mentors",
            open_to_kind=OpenToKind.MENTOR,
        )
        self.assertEqual(need.space, self.space)
        self.assertEqual(need.created_by, self.space_manager)

    def test_membership_alone_does_not_authorize_space_need(self):
        self.assertFalse(can(self.member_only, PermissionCode.SPACE_MANAGE, space=self.space))
        with self.assertRaises(PermissionDenied):
            create_action_need(
                actor=self.member_only,
                space=self.space,
                title="Bypass interdit",
                open_to_kind=OpenToKind.MENTOR,
            )

    def test_outsider_cannot_create_space_need(self):
        with self.assertRaises(PermissionDenied):
            create_action_need(
                actor=self.outsider,
                space=self.space,
                title="Outsider",
                open_to_kind=OpenToKind.MENTOR,
            )

    def test_space_activity_need_requires_activity_authority(self):
        activity = Activity.objects.create(space=self.space, created_by=self.space_manager, title="Atelier Space G7")
        self.assertTrue(can(self.space_manager, PermissionCode.ACTIVITY_MANAGE, activity=activity))
        need = create_action_need(
            actor=self.space_manager,
            space=self.space,
            activity=activity,
            title="Intervenant atelier",
            open_to_kind=OpenToKind.SPEAK,
        )
        self.assertEqual(need.activity, activity)
        with self.assertRaises(PermissionDenied):
            create_action_need(
                actor=self.outsider,
                space=self.space,
                activity=activity,
                title="Intervenant illégitime",
                open_to_kind=OpenToKind.SPEAK,
            )


class G7SolicitationLifecycleTests(TestCase):
    def setUp(self):
        self.sender = make_user(username="g7-sender", first_name="Sarah")
        self.recipient = make_user(username="g7-recipient", first_name="Amina")
        self.third_party = make_user(username="g7-third", first_name="Patrick")
        self.need = create_action_need(
            actor=self.sender,
            owner_profile=self.sender,
            title="Mentorat IA",
            open_to_kind=OpenToKind.MENTOR,
        )
        ProfileOpenTo.objects.create(
            profile=self.recipient,
            kind=OpenToKind.MENTOR,
            is_active=True,
            is_searchable=True,
        )

    def create_solicitation(self, message="Nous cherchons deux mentors."):
        return create_profile_solicitation(
            actor=self.sender,
            need=self.need,
            recipient_profile=self.recipient,
            message=message,
        )

    def test_creation_and_notification_are_in_product_without_pii(self):
        solicitation = self.create_solicitation()
        self.assertEqual(solicitation.status, ProfileSolicitationStatus.PENDING)
        notification = Notification.objects.get(dedup_key=f"g7-solicitation:{solicitation.pk}")
        self.assertEqual(notification.recipient, self.recipient)
        self.assertIn("Mentorat IA", notification.message)
        self.assertNotIn(self.recipient.email, notification.message)
        self.assertNotIn(self.recipient.phone, notification.message)
        self.assertFalse(NotificationDelivery.objects.filter(notification=notification).exists())

    def test_duplicate_pending_is_blocked(self):
        self.create_solicitation()
        with self.assertRaises(ValidationError):
            self.create_solicitation()
        self.assertEqual(ProfileSolicitation.objects.filter(need=self.need, recipient_profile=self.recipient).count(), 1)

    def test_recipient_can_accept_without_creating_authority_or_action_domains(self):
        solicitation = self.create_solicitation()
        before = (Mandate.objects.count(), Journey.objects.count(), Access.objects.count())
        respond_to_profile_solicitation(
            actor=self.recipient,
            solicitation=solicitation,
            status=ProfileSolicitationStatus.ACCEPTED,
        )
        solicitation.refresh_from_db()
        self.assertEqual(solicitation.status, ProfileSolicitationStatus.ACCEPTED)
        self.assertEqual(before, (Mandate.objects.count(), Journey.objects.count(), Access.objects.count()))

    def test_recipient_can_decline(self):
        solicitation = self.create_solicitation()
        respond_to_profile_solicitation(actor=self.recipient, solicitation=solicitation, status=ProfileSolicitationStatus.DECLINED)
        solicitation.refresh_from_db()
        self.assertEqual(solicitation.status, ProfileSolicitationStatus.DECLINED)

    def test_third_party_cannot_answer(self):
        solicitation = self.create_solicitation()
        with self.assertRaises(PermissionDenied):
            respond_to_profile_solicitation(actor=self.third_party, solicitation=solicitation, status=ProfileSolicitationStatus.ACCEPTED)
        solicitation.refresh_from_db()
        self.assertEqual(solicitation.status, ProfileSolicitationStatus.PENDING)

    def test_sender_can_cancel_pending(self):
        solicitation = self.create_solicitation()
        cancel_profile_solicitation(actor=self.sender, solicitation=solicitation)
        solicitation.refresh_from_db()
        self.assertEqual(solicitation.status, ProfileSolicitationStatus.CANCELLED)

    def test_closed_need_blocks_new_solicitation(self):
        close_action_need(actor=self.sender, need=self.need)
        self.need.refresh_from_db()
        self.assertEqual(self.need.status, ActionNeedStatus.CLOSED)
        with self.assertRaises(ValidationError):
            self.create_solicitation()

    def test_personal_need_cannot_solicit_self(self):
        ProfileOpenTo.objects.create(profile=self.sender, kind=OpenToKind.MENTOR, is_active=True, is_searchable=True)
        with self.assertRaises(ValidationError):
            create_profile_solicitation(actor=self.sender, need=self.need, recipient_profile=self.sender)

    def test_response_web_endpoint_rejects_third_party(self):
        solicitation = self.create_solicitation()
        self.client.force_login(self.third_party)
        response = self.client.post(
            reverse("social:solicitation-respond", kwargs={"pk": solicitation.pk}),
            {"status": ProfileSolicitationStatus.ACCEPTED},
        )
        self.assertEqual(response.status_code, 403)
        solicitation.refresh_from_db()
        self.assertEqual(solicitation.status, ProfileSolicitationStatus.PENDING)
