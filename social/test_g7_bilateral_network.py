import inspect

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from access.models import Access
from accounts.models import UserProfile
from activities.involvement_models import (
    ActivityInvolvement,
    ActivityInvolvementFunctionKind,
    ActivityInvolvementNeedConfig,
    ActivityInvolvementVisibility,
)
from activities.models import Activity, ActivityStatus, ActivityVisibility
from authorization.constants import PermissionCode, SystemRoleCode
from authorization.models import Mandate
from authorization.services import can, grant_space_role
from journeys.models import Journey
from notifications.models import Notification, NotificationDelivery
from organizations.models import Organization, OrganizationMembership
from topics.models import (
    ActionMatchKind,
    ActivityTopic,
    ProfileInterest,
    ProfileOpenTo,
    SpaceOpenTo,
    Topic,
)

from . import profile_search
from .bilateral_services import (
    cancel_action_proposal,
    close_action_need,
    create_action_need,
    create_action_network_block,
    create_action_proposal,
    respond_to_action_proposal,
)
from .models import (
    ActionNeedCandidateKind,
    ActionNeedIntakePolicy,
    ActionNeedStatus,
    ActionNeedVisibility,
    ActionProposal,
    ActionProposalDirection,
    ActionProposalStatus,
)
from .profile_search import search_profiles_for_need, search_spaces_for_need


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
            match_kind=ActionMatchKind.MENTOR,
            topics=[self.topic],
        )
        ProfileOpenTo.objects.create(
            profile=self.candidate,
            kind=ActionMatchKind.MENTOR,
            is_active=True,
            is_public=False,
            is_searchable=True,
        )

    def candidate_ids(self):
        return {candidate.profile_id for candidate in search_profiles_for_need(need=self.need)}

    def test_searchable_profile_and_searchable_open_to_is_candidate(self):
        self.assertIn(self.candidate.pk, self.candidate_ids())

    def test_searchable_false_is_absent(self):
        self.candidate.profile.searchable = False
        self.candidate.profile.save(update_fields=["searchable", "updated_at"])
        self.assertNotIn(self.candidate.pk, self.candidate_ids())

    def test_non_public_but_searchable_profile_remains_private_candidate(self):
        self.candidate.profile.public_profile = False
        self.candidate.profile.save(update_fields=["public_profile", "updated_at"])
        self.assertIn(self.candidate.pk, self.candidate_ids())

    def test_open_to_non_searchable_is_absent_even_when_public(self):
        row = ProfileOpenTo.objects.get(profile=self.candidate, kind=ActionMatchKind.MENTOR)
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
            match_kind=ActionMatchKind.COLLABORATE,
        )
        self.assertEqual(need.owner_profile, self.owner)
        with self.assertRaises(PermissionDenied):
            create_action_need(
                actor=self.outsider,
                owner_profile=self.owner,
                title="Usurpation",
                match_kind=ActionMatchKind.COLLABORATE,
            )

    def test_space_need_requires_canonical_permission(self):
        self.assertTrue(can(self.space_manager, PermissionCode.SPACE_ACTION_NETWORK_MANAGE, space=self.space))
        need = create_action_need(
            actor=self.space_manager,
            space=self.space,
            title="Mentors",
            match_kind=ActionMatchKind.MENTOR,
        )
        self.assertEqual(need.space, self.space)
        self.assertEqual(need.created_by, self.space_manager)

    def test_membership_alone_does_not_authorize_space_need(self):
        self.assertFalse(can(self.member_only, PermissionCode.SPACE_ACTION_NETWORK_MANAGE, space=self.space))
        with self.assertRaises(PermissionDenied):
            create_action_need(
                actor=self.member_only,
                space=self.space,
                title="Bypass interdit",
                match_kind=ActionMatchKind.MENTOR,
            )

    def test_outsider_cannot_create_space_need(self):
        with self.assertRaises(PermissionDenied):
            create_action_need(
                actor=self.outsider,
                space=self.space,
                title="Outsider",
                match_kind=ActionMatchKind.MENTOR,
            )

    def test_space_activity_need_uses_network_authority(self):
        activity = Activity.objects.create(space=self.space, created_by=self.space_manager, title="Atelier Space G7")
        need = create_action_need(
            actor=self.space_manager,
            space=self.space,
            activity=activity,
            title="Intervenant atelier",
            match_kind=ActionMatchKind.SPEAK,
        )
        self.assertEqual(need.activity, activity)
        with self.assertRaises(PermissionDenied):
            create_action_need(
                actor=self.outsider,
                space=self.space,
                activity=activity,
                title="Intervenant illégitime",
                match_kind=ActionMatchKind.SPEAK,
            )


class ActionProposalLifecycleTests(TestCase):
    def setUp(self):
        self.sender = make_user(username="g7-sender", first_name="Sarah")
        self.recipient = make_user(username="g7-recipient", first_name="Amina")
        self.third_party = make_user(username="g7-third", first_name="Patrick")
        self.need = create_action_need(
            actor=self.sender,
            owner_profile=self.sender,
            title="Mentorat IA",
            match_kind=ActionMatchKind.MENTOR,
        )
        ProfileOpenTo.objects.create(
            profile=self.recipient,
            kind=ActionMatchKind.MENTOR,
            is_active=True,
            is_searchable=True,
        )

    def create_proposal(self, message="Nous cherchons deux mentors."):
        return create_action_proposal(
            actor=self.sender,
            need=self.need,
            candidate_profile=self.recipient,
            message=message,
        )

    def test_creation_and_notification_are_in_product_without_pii(self):
        proposal = self.create_proposal()
        self.assertEqual(proposal.status, ActionProposalStatus.PENDING)
        notification = Notification.objects.get(dedup_key=f"action-proposal:{proposal.pk}")
        self.assertEqual(notification.recipient, self.recipient)
        self.assertIn("Mentorat IA", notification.message)
        self.assertNotIn(self.recipient.email, notification.message)
        self.assertNotIn(self.recipient.phone, notification.message)
        self.assertFalse(NotificationDelivery.objects.filter(notification=notification).exists())

    def test_duplicate_active_proposal_is_blocked(self):
        self.create_proposal()
        with self.assertRaises(ValidationError):
            self.create_proposal()
        self.assertEqual(ActionProposal.objects.filter(need=self.need, candidate_profile=self.recipient).count(), 1)

    def test_recipient_can_accept_without_creating_authority_or_action_domains(self):
        proposal = self.create_proposal()
        before = (Mandate.objects.count(), Journey.objects.count(), Access.objects.count())
        respond_to_action_proposal(
            actor=self.recipient,
            proposal=proposal,
            status=ActionProposalStatus.ACCEPTED,
        )
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ActionProposalStatus.ACCEPTED)
        self.assertEqual(before, (Mandate.objects.count(), Journey.objects.count(), Access.objects.count()))

    def test_recipient_can_decline(self):
        proposal = self.create_proposal()
        respond_to_action_proposal(actor=self.recipient, proposal=proposal, status=ActionProposalStatus.DECLINED)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ActionProposalStatus.DECLINED)

    def test_third_party_cannot_answer(self):
        proposal = self.create_proposal()
        with self.assertRaises(PermissionDenied):
            respond_to_action_proposal(actor=self.third_party, proposal=proposal, status=ActionProposalStatus.ACCEPTED)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ActionProposalStatus.PENDING)

    def test_sender_can_cancel_pending(self):
        proposal = self.create_proposal()
        cancel_action_proposal(actor=self.sender, proposal=proposal)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ActionProposalStatus.CANCELLED)

    def test_cancelled_need_blocks_new_proposal(self):
        close_action_need(actor=self.sender, need=self.need)
        self.need.refresh_from_db()
        self.assertEqual(self.need.status, ActionNeedStatus.CANCELLED)
        with self.assertRaises(ValidationError):
            self.create_proposal()

    def test_personal_need_cannot_solicit_self(self):
        ProfileOpenTo.objects.create(profile=self.sender, kind=ActionMatchKind.MENTOR, is_active=True, is_searchable=True)
        with self.assertRaises(ValidationError):
            create_action_proposal(actor=self.sender, need=self.need, candidate_profile=self.sender)

    def test_response_web_endpoint_rejects_third_party(self):
        proposal = self.create_proposal()
        self.client.force_login(self.third_party)
        response = self.client.post(
            reverse("social:solicitation-respond", kwargs={"pk": proposal.pk}),
            {"status": ActionProposalStatus.ACCEPTED},
        )
        self.assertEqual(response.status_code, 403)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ActionProposalStatus.PENDING)

    def test_open_need_accepts_explicit_candidate_proposal_without_open_to(self):
        candidate = make_user(username="g7-open-candidate")
        self.need.visibility = ActionNeedVisibility.PUBLIC
        self.need.intake_policy = ActionNeedIntakePolicy.OPEN
        self.need.save(update_fields=["visibility", "intake_policy", "updated_at"])
        proposal = create_action_proposal(
            actor=candidate,
            need=self.need,
            candidate_profile=candidate,
            direction=ActionProposalDirection.CANDIDATE_TO_OWNER,
            client_reference="mobile-1",
        )
        retry = create_action_proposal(
            actor=candidate,
            need=self.need,
            candidate_profile=candidate,
            direction=ActionProposalDirection.CANDIDATE_TO_OWNER,
            client_reference="mobile-1",
        )
        self.assertEqual(proposal.pk, retry.pk)

    def test_invite_only_need_rejects_candidate_initiated_proposal(self):
        candidate = make_user(username="g7-invite-only-candidate")
        self.need.visibility = ActionNeedVisibility.PUBLIC
        self.need.intake_policy = ActionNeedIntakePolicy.INVITE_ONLY
        self.need.save(update_fields=["visibility", "intake_policy", "updated_at"])
        with self.assertRaises(ValidationError):
            create_action_proposal(
                actor=candidate,
                need=self.need,
                candidate_profile=candidate,
                direction=ActionProposalDirection.CANDIDATE_TO_OWNER,
            )

    def test_block_removes_candidate_and_prevents_contact(self):
        create_action_network_block(
            actor=self.recipient,
            blocker_profile=self.recipient,
            blocked_profile=self.sender,
        )
        self.assertNotIn(self.recipient.pk, {item.profile_id for item in search_profiles_for_need(need=self.need)})
        with self.assertRaises(ValidationError):
            self.create_proposal()


class SpaceMatchingTests(TestCase):
    def setUp(self):
        self.owner = make_user(username="space-need-owner")
        self.space = Organization.objects.create(name="Vodacom Test", created_by=self.owner, city="Kinshasa", country="RDC")
        self.need = create_action_need(
            actor=self.owner,
            owner_profile=self.owner,
            title="Sponsor principal",
            match_kind=ActionMatchKind.SPONSOR,
            candidate_kind=ActionNeedCandidateKind.SPACE,
        )

    def test_public_space_without_explicit_searchable_availability_is_absent(self):
        self.assertEqual(search_spaces_for_need(need=self.need), [])

    def test_space_open_to_makes_space_discoverable(self):
        SpaceOpenTo.objects.create(space=self.space, kind=ActionMatchKind.SPONSOR, is_active=True, is_searchable=True)
        candidates = search_spaces_for_need(need=self.need)
        self.assertEqual([candidate.space_id for candidate in candidates], [self.space.pk])
        rendered = " ".join((candidates[0].display_name, candidates[0].city, candidates[0].country, *candidates[0].reasons))
        self.assertNotIn(self.space.contact_email or "__never__", rendered)
        self.assertNotIn(self.space.contact_phone or "__never__", rendered)


class ActivityInvolvementRealizationTests(TestCase):
    def setUp(self):
        self.owner = make_user(username="inv-owner")
        self.candidate = make_user(username="inv-speaker")
        self.activity = Activity.objects.create(
            owner_profile=self.owner,
            created_by=self.owner,
            title="Conférence IA",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.need = create_action_need(
            actor=self.owner,
            owner_profile=self.owner,
            activity=self.activity,
            title="Conférencier principal",
            match_kind=ActionMatchKind.SPEAK,
            candidate_kind=ActionNeedCandidateKind.PROFILE,
        )
        ActivityInvolvementNeedConfig.objects.create(
            need=self.need,
            function_kind=ActivityInvolvementFunctionKind.SPEAKER,
            function_label="Conférencier principal",
            result_visibility=ActivityInvolvementVisibility.PUBLIC,
            presentation_tier=1,
        )
        ProfileOpenTo.objects.create(
            profile=self.candidate,
            kind=ActionMatchKind.SPEAK,
            is_active=True,
            is_searchable=True,
        )

    def test_acceptance_realizes_exactly_one_involvement_without_authority_transfer(self):
        proposal = create_action_proposal(
            actor=self.owner,
            need=self.need,
            candidate_profile=self.candidate,
        )
        authority_before = Mandate.objects.count()
        respond_to_action_proposal(
            actor=self.candidate,
            proposal=proposal,
            status=ActionProposalStatus.ACCEPTED,
        )
        involvement = ActivityInvolvement.objects.get(source_proposal=proposal)
        self.assertEqual(involvement.activity, self.activity)
        self.assertEqual(involvement.profile, self.candidate)
        self.assertEqual(involvement.visibility, ActivityInvolvementVisibility.PUBLIC)
        function = involvement.functions.get()
        self.assertEqual(function.kind, ActivityInvolvementFunctionKind.SPEAKER)
        self.assertEqual(function.presentation_tier, 1)
        self.assertEqual(Mandate.objects.count(), authority_before)
        self.assertEqual(Journey.objects.filter(profile=self.candidate).count(), 0)
        self.assertEqual(Access.objects.filter(profile=self.candidate).count(), 0)
