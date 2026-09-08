from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import Access, AccessStatus
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus, OccurrenceTimingKind
from authorization.constants import PermissionCode
from authorization.models import AuthorityScope, Permission, Role, RolePermission
from authorization.services import grant_space_role
from journeys.collaboration_models import JourneyBlocker, JourneyBlockerStatus, JourneyStep, JourneyStepStatus
from journeys.models import Journey, JourneyStatus, WorkflowKind
from objectives.models import DossierJourneyDependency, DossierJourneyLink
from objectives.readiness import HIDDEN_COLLECTIVE_SIGNAL
from objectives.services import create_dossier
from organizations.models import Organization, Team, TeamMembership
from recognition.models import RecognitionAccount, RecognitionRedemption, RedemptionStatus, RewardDefinition
from social.bilateral_services import create_action_need, create_action_proposal
from social.models import ActionProposalDirection, ActionNeedIntakePolicy, ActionNeedVisibility
from topics.models import ActionMatchKind, ProfileOpenTo, SpaceOpenTo

from .home_presentation import build_mature_home


User = get_user_model()
PASSWORD = "Strong-M8A-Password-2026!"


def make_user(username):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.test",
        password=PASSWORD,
    )


def grant_action_network_manage(*, actor, space):
    permission = Permission.objects.get(code=PermissionCode.SPACE_ACTION_NETWORK_MANAGE)
    role = Role.objects.create(
        code=f"m8a-action-network-{actor.username}",
        name="Gestion réseau d’action M8-A",
        scope_type=AuthorityScope.SPACE,
        organization=space,
        is_system=False,
        is_active=True,
    )
    RolePermission.objects.create(role=role, permission=permission)
    return grant_space_role(
        profile=actor,
        space=space,
        role=role,
        granted_by=actor,
        source="m8a-test",
    )


class MatureHomeCoreTests(TestCase):
    def setUp(self):
        self.user = make_user("m8a-user")
        self.activity = Activity.objects.create(
            title="Démarche M8-A",
            owner_profile=self.user,
            created_by=self.user,
            status=ActivityStatus.PUBLISHED,
        )

    def journey(self, **overrides):
        values = {
            "initiated_by": self.user,
            "beneficiary": self.user,
            "activity": self.activity,
            "workflow": WorkflowKind.REGISTRATION,
            "status": JourneyStatus.CONFIRMED,
        }
        values.update(overrides)
        return Journey.objects.create(**values)

    def test_home_is_private_and_empty_state_is_calm(self):
        response = self.client.get(reverse("core:participant-home"))
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.user)
        response = self.client.get(reverse("core:participant-home"))
        self.assertContains(response, "Tout est en ordre. ✓")
        self.assertNotContains(response, "Mes activités organisées")
        self.assertNotContains(response, "crédits")

    def test_blocker_wins_over_progress_and_ready_journey_creates_no_obligation(self):
        ready = self.journey()
        draft = self.journey(status=JourneyStatus.DRAFT)
        blocked = self.journey()
        JourneyBlocker.objects.create(
            journey=blocked,
            title="Blocage critique",
            status=JourneyBlockerStatus.ACTIVE,
        )
        home = build_mature_home(self.user)
        self.assertEqual(home.primary_attention.context_label, self.activity.title)
        self.assertEqual(home.primary_attention.priority, "p0_critical")
        identities = [home.primary_attention.identity, *(item.identity for item in home.action_items)]
        self.assertTrue(any(identity.context_id == str(draft.pk) for identity in identities))
        self.assertFalse(any(identity.context_id == str(ready.pk) for identity in identities))

    def test_dossier_hidden_influence_is_opaque(self):
        other = make_user("m8a-hidden")
        dossier = create_dossier(actor=self.user, owner_profile=self.user, title="Dossier M8-A")
        visible_activity = Activity.objects.create(owner_profile=self.user, created_by=self.user, title="Visible")
        hidden_activity = Activity.objects.create(owner_profile=other, created_by=other, title="SECRET JOURNEY")
        visible_journey = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=visible_activity,
            workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.CONFIRMED,
        )
        hidden_journey = Journey.objects.create(
            initiated_by=other,
            beneficiary=other,
            activity=hidden_activity,
            workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.DRAFT,
        )
        visible_link = DossierJourneyLink.objects.create(dossier=dossier, journey=visible_journey, linked_by=self.user)
        hidden_link = DossierJourneyLink.objects.create(dossier=dossier, journey=hidden_journey, linked_by=other)
        DossierJourneyDependency.objects.create(
            dossier=dossier,
            dependent_link=visible_link,
            required_link=hidden_link,
            created_by=other,
        )
        home = build_mature_home(self.user)
        rendered = repr(home)
        self.assertIn(HIDDEN_COLLECTIVE_SIGNAL, rendered)
        self.assertNotIn("SECRET JOURNEY", rendered)
        self.assertNotIn(str(hidden_journey.pk), rendered)

    def test_occurrence_temporal_precision_never_invents_midnight(self):
        now = timezone.now()
        date_only = Occurrence.objects.create(
            activity=self.activity,
            start_date=(now + timedelta(days=1)).date(),
            timing_kind=OccurrenceTimingKind.DATE_ONLY,
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        access = Access.objects.create(
            beneficiary=self.user,
            activity=self.activity,
            occurrence=date_only,
            status=AccessStatus.VALID,
        )
        home = build_mature_home(self.user, observed_at=now)
        item = next(row for row in home.upcoming if row.access_id == str(access.pk))
        self.assertIn("Heure à confirmer", item.timing_label)
        self.assertNotIn("00:00", item.timing_label)

        all_day = Occurrence.objects.create(
            activity=self.activity,
            start_date=(now + timedelta(days=2)).date(),
            timing_kind=OccurrenceTimingKind.ALL_DAY,
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        Access.objects.create(
            beneficiary=self.user,
            activity=self.activity,
            occurrence=all_day,
            status=AccessStatus.VALID,
        )
        cancelled = Occurrence.objects.create(
            activity=self.activity,
            start_date=(now + timedelta(days=3)).date(),
            timing_kind=OccurrenceTimingKind.DATE_ONLY,
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.CANCELLED,
        )
        Access.objects.create(
            beneficiary=self.user,
            activity=self.activity,
            occurrence=cancelled,
            status=AccessStatus.VALID,
        )
        home = build_mature_home(self.user, observed_at=now)
        self.assertTrue(any("Toute la journée" in row.timing_label for row in home.upcoming))
        self.assertFalse(any(row.access_id and "00:00" in row.timing_label for row in home.upcoming))


class MatureHomeActionNetworkTests(TestCase):
    def setUp(self):
        self.owner = make_user("m8a-owner")
        self.candidate = make_user("m8a-candidate")
        self.other = make_user("m8a-other")
        self.candidate.profile.searchable = True
        self.candidate.profile.save(update_fields=["searchable"])
        ProfileOpenTo.objects.create(
            profile=self.candidate,
            kind=ActionMatchKind.COLLABORATE,
            is_active=True,
            is_searchable=True,
        )

    def test_pending_profile_proposal_appears_and_expired_does_not(self):
        need = create_action_need(
            actor=self.owner,
            owner_profile=self.owner,
            title="Besoin M8-A",
            match_kind=ActionMatchKind.COLLABORATE,
        )
        proposal = create_action_proposal(
            actor=self.owner,
            need=need,
            candidate_profile=self.candidate,
        )
        home = build_mature_home(self.candidate)
        self.assertTrue(
            any(
                item.identity.context_id == str(proposal.pk)
                for item in (home.primary_attention, *home.action_items)
                if item is not None
            )
        )
        proposal.expires_at = timezone.now() - timedelta(seconds=1)
        proposal.save(update_fields=["expires_at", "updated_at"])
        expired_home = build_mature_home(self.candidate)
        self.assertFalse(
            any(
                item.identity.context_id == str(proposal.pk)
                for item in (expired_home.primary_attention, *expired_home.action_items)
                if item is not None
            )
        )

    def test_space_membership_alone_does_not_surface_space_proposal(self):
        space = Organization.objects.create(name="M8-A Space", created_by=self.owner)
        team = Team.objects.create(organization=space, name="Équipe", is_default=True)
        TeamMembership.objects.create(team=team, user=self.other)
        SpaceOpenTo.objects.create(
            space=space,
            kind=ActionMatchKind.PARTNER,
            is_active=True,
            is_searchable=True,
        )
        need = create_action_need(
            actor=self.owner,
            owner_profile=self.owner,
            title="Partenaire M8-A",
            match_kind=ActionMatchKind.PARTNER,
            candidate_kind="space",
        )
        proposal = create_action_proposal(actor=self.owner, need=need, candidate_space=space)
        outsider_home = build_mature_home(self.other)
        self.assertFalse(
            any(
                item.identity.context_id == str(proposal.pk)
                for item in (outsider_home.primary_attention, *outsider_home.action_items)
                if item is not None
            )
        )
        grant_action_network_manage(actor=self.other, space=space)
        authorized_home = build_mature_home(self.other)
        self.assertTrue(
            any(
                item.identity.context_id == str(proposal.pk)
                for item in (authorized_home.primary_attention, *authorized_home.action_items)
                if item is not None
            )
        )


class MatureHomeRecognitionTests(TestCase):
    def test_only_pending_beneficiary_decision_surfaces_not_balance(self):
        owner = make_user("m8a-rec-owner")
        beneficiary = make_user("m8a-rec-beneficiary")
        owner_account = RecognitionAccount.objects.create(profile=owner, points_balance=50, lifetime_earned=50)
        RecognitionAccount.objects.create(profile=beneficiary, points_balance=999, lifetime_earned=999)
        reward = RewardDefinition.objects.create(
            code="m8a-benefit",
            version=1,
            name="Bénéfice M8-A",
            points_cost=10,
            acceptance_required=True,
            fulfillment={"owner_domain": "recognition"},
        )
        empty = build_mature_home(beneficiary)
        self.assertTrue(empty.all_clear)
        redemption = RecognitionRedemption.objects.create(
            owner_account=owner_account,
            reward=reward,
            beneficiary_profile=beneficiary,
            points_cost=10,
            status=RedemptionStatus.REQUESTED,
            idempotency_key="m8a-redemption",
            fulfillment_snapshot={"consent_state": "pending"},
        )
        home = build_mature_home(beneficiary)
        self.assertFalse(home.all_clear)
        self.assertEqual(home.primary_attention.identity.context_id, str(redemption.pk))
        self.assertNotIn("999", repr(home))


class MatureHomeDeduplicationTests(TestCase):
    def test_same_canonical_action_identity_is_deduplicated_by_resolver(self):
        user = make_user("m8a-dedupe")
        from preparation.contextual_actions import ContextualAction, ContextualActionIdentity, ContextualActionPriority, ContextualActionability, resolve_contextual_actions
        now = timezone.now()
        identity = ContextualActionIdentity("test", "stable:1", "respond", "test", "1")
        first = ContextualAction(identity, "test", ContextualActionPriority.P1_REQUIRED, ContextualActionability.ACTIONABLE, ("a",), "Répondre", "Premier", now)
        second = ContextualAction(identity, "test", ContextualActionPriority.P1_REQUIRED, ContextualActionability.ACTIONABLE, ("b",), "Autre texte", "Deuxième", now)
        result = resolve_contextual_actions((first, second), observed_at=now)
        self.assertEqual(len(result.actions), 1)
