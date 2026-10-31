from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityStatus, ActivityVisibility
from groups.models import (
    ActivityGroupEligibility, ActivityGroupEligibilityStatus,
    Group, GroupMembership, GroupMembershipStatus,
)
from journeys.models import Journey, WorkflowKind
from organizations.models import Organization, SpaceLifecycle
from opportunities.models import OpportunityKind, OpportunitySourceType
from opportunities.services import (
    create_opportunity,
    create_opportunity_revision,
    create_opportunity_source,
    publish_opportunity_revision,
    withdraw_opportunity,
)

from .models import OpportunityPolicy, ServiceDetails, ServiceKind


class NativeServiceStartAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="native-service-owner", email="native-owner@example.test",
            password="test-pass-2026",
        )
        self.participant = User.objects.create_user(
            username="native-service-participant", email="native-user@example.test",
            password="test-pass-2026",
        )
        self.other = User.objects.create_user(
            username="native-service-other", email="native-other@example.test",
            password="test-pass-2026",
        )
        self.space = Organization.objects.create(
            name="Native Service Space", created_by=self.owner,
        )
        self.activity = Activity.objects.create(
            space=self.space, created_by=self.owner,
            title="Native Service", status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.service = ServiceDetails.objects.create(
            activity=self.activity, service_kind=ServiceKind.APPLICATION_SUPPORT,
            opportunity_policy=OpportunityPolicy.NONE,
        )
        self.url = reverse("services-api:start", kwargs={"pk": self.service.pk})
        self.key = "mobile-start-retry-key-0001"

    def _start(self, *, objective="Préparer mon dossier", key=None, **extra):
        return self.client.post(
            self.url,
            data={"objective": objective, **extra},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key or self.key,
        )

    def test_guest_is_denied_and_public_api_does_not_start_another_profile(self):
        result = self._start()
        self.assertIn(result.status_code, {401, 403})
        self.client.force_login(self.participant)
        result = self._start(beneficiary=str(self.other.pk))
        self.assertEqual(result.status_code, 400)
        self.assertFalse(Journey.objects.filter(
            initiated_by=self.participant, activity=self.activity,
        ).exists())

    def test_native_start_creates_one_journey_and_replay_does_not_duplicate(self):
        self.client.force_login(self.participant)
        information = self.client.get(self.url)
        self.assertEqual(information.status_code, 200)
        self.assertEqual(information.json()["capabilities"], ["start"])
        self.assertTrue(information.json()["requirements"]["idempotency_key_required"])
        created = self._start()
        self.assertEqual(created.status_code, 201)
        first_id = created.json()["journey"]["id"]
        self.assertFalse(created.json()["replayed"])
        self.assertTrue(created.json()["links"]["journey"].startswith("/api/v1/me/"))
        retry = self._start()
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json()["journey"]["id"], first_id)
        self.assertTrue(retry.json()["replayed"])
        self.assertEqual(Journey.objects.filter(
            initiated_by=self.participant, activity=self.activity,
            workflow=WorkflowKind.SERVICE,
        ).count(), 1)
        context = Journey.objects.get(pk=first_id).service_context
        self.assertEqual(len(context.start_operation_fingerprint), 64)
        self.assertNotEqual(context.start_operation_fingerprint, self.key)

    def test_reused_operation_key_with_changed_payload_returns_conflict(self):
        self.client.force_login(self.participant)
        self.assertEqual(self._start().status_code, 201)
        changed = self._start(objective="Une autre démarche")
        self.assertEqual(changed.status_code, 409)
        self.assertEqual(changed.json()["code"], "idempotency_conflict")
        self.assertEqual(Journey.objects.filter(
            initiated_by=self.participant, activity=self.activity,
        ).count(), 1)

    def test_key_is_bound_to_actor_and_service(self):
        self.client.force_login(self.participant)
        first = self._start()
        self.assertEqual(first.status_code, 201)
        self.client.force_login(self.other)
        second = self._start()
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(
            first.json()["journey"]["id"], second.json()["journey"]["id"]
        )

    def test_same_operation_key_on_distinct_services_creates_distinct_journeys(self):
        second_activity = Activity.objects.create(
            space=self.space, created_by=self.owner,
            title="Another Native Service", status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        second_service = ServiceDetails.objects.create(
            activity=second_activity,
            service_kind=ServiceKind.APPLICATION_SUPPORT,
            opportunity_policy=OpportunityPolicy.NONE,
        )
        self.client.force_login(self.participant)
        first = self._start()
        self.assertEqual(first.status_code, 201)
        second = self.client.post(
            reverse("services-api:start", kwargs={"pk": second_service.pk}),
            data={"objective": "Préparer mon dossier"},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=self.key,
        )
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(
            first.json()["journey"]["id"], second.json()["journey"]["id"]
        )
        self.assertEqual(
            Journey.objects.filter(
                initiated_by=self.participant, workflow=WorkflowKind.SERVICE,
            ).count(),
            2,
        )

    def test_missing_or_short_operation_key_is_rejected(self):
        self.client.force_login(self.participant)
        response = self.client.post(
            self.url, data={"objective": "X"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        response = self._start(key="short")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Journey.objects.filter(
            initiated_by=self.participant, activity=self.activity,
        ).count(), 0)

    def test_draft_or_group_restricted_service_is_not_accessible(self):
        self.client.force_login(self.participant)
        self.activity.status = ActivityStatus.DRAFT
        self.activity.save(update_fields=["status", "updated_at"])
        self.assertEqual(self._start().status_code, 404)
        self.activity.status = ActivityStatus.PUBLISHED
        self.activity.save(update_fields=["status", "updated_at"])
        group = Group.objects.create(
            name="Native gated", space=self.space, created_by=self.owner,
        )
        ActivityGroupEligibility.objects.create(
            group=group, activity=self.activity,
            status=ActivityGroupEligibilityStatus.APPROVED,
            requested_by=self.owner, decided_by=self.owner,
            decided_at=timezone.now(),
        )
        self.assertEqual(self._start().status_code, 404)
        GroupMembership.objects.create(
            group=group, profile=self.participant,
            status=GroupMembershipStatus.ACTIVE,
        )
        self.assertEqual(self._start().status_code, 201)

    def test_native_start_preserves_service_policy(self):
        self.client.force_login(self.participant)
        result = self._start(opportunity="not-an-opportunity")
        self.assertEqual(result.status_code, 400)
        self.service.opportunity_policy = OpportunityPolicy.REQUIRED
        self.service.save(update_fields=["opportunity_policy", "updated_at"])
        result = self._start()
        self.assertEqual(result.status_code, 400)
        self.assertEqual(Journey.objects.filter(
            initiated_by=self.participant, activity=self.activity,
        ).count(), 0)

    def test_retry_survives_opportunity_withdrawal_without_recreating_journey(self):
        User = get_user_model()
        curator = User.objects.create_user(
            username="native-start-curator", email="native-curator@example.test",
            password="test-pass-2026", is_superuser=True, is_staff=True,
        )
        opportunity = create_opportunity(
            actor=curator, kind=OpportunityKind.SCHOLARSHIP,
        )
        revision = create_opportunity_revision(
            opportunity=opportunity, actor=curator,
            title="Test scholarship", issuer_name="External organization",
            timezone_name="Africa/Lubumbashi",
        )
        create_opportunity_source(
            opportunity=opportunity, actor=curator,
            source_type=OpportunitySourceType.OFFICIAL,
            source_name="External official", url="https://example.test/official",
            is_primary=True,
        )
        publish_opportunity_revision(
            opportunity=opportunity, revision=revision, actor=curator,
        )
        self.service.opportunity_policy = OpportunityPolicy.REQUIRED
        self.service.save(update_fields=["opportunity_policy", "updated_at"])
        self.client.force_login(self.participant)
        created = self._start(opportunity=str(opportunity.pk))
        self.assertEqual(created.status_code, 201)
        withdraw_opportunity(opportunity=opportunity, actor=curator)
        replay = self._start(opportunity=str(opportunity.pk))
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.json()["replayed"])
        self.assertEqual(
            created.json()["journey"]["id"], replay.json()["journey"]["id"],
        )
        self.assertEqual(Journey.objects.filter(
            initiated_by=self.participant, activity=self.activity,
        ).count(), 1)

    def test_owner_retraction_hides_service_from_catalog_and_start(self):
        """The public owner selector is shared by Web and native Services."""
        from .views import public_services

        self.client.force_login(self.participant)
        self.assertTrue(public_services().filter(pk=self.service.pk).exists())
        self.assertEqual(self.client.get(self.url).status_code, 200)

        for field, rejected in (
            ("verification_status", "suspended"),
            ("lifecycle", SpaceLifecycle.ARCHIVED),
            ("public_profile", False),
            ("searchable", False),
        ):
            with self.subTest(field=field):
                previous = getattr(self.space, field)
                setattr(self.space, field, rejected)
                self.space.save(update_fields=[field])
                self.assertFalse(
                    public_services().filter(pk=self.service.pk).exists()
                )
                self.assertEqual(self.client.get(self.url).status_code, 404)
                self.assertEqual(self._start().status_code, 404)
                self.assertFalse(
                    Journey.objects.filter(
                        activity=self.activity, initiated_by=self.participant,
                    ).exists()
                )
                setattr(self.space, field, previous)
                self.space.save(update_fields=[field])
                self.assertTrue(
                    public_services().filter(pk=self.service.pk).exists()
                )
                self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_inactive_personal_service_owner_does_not_publish_start(self):
        from .views import public_services

        personal_activity = Activity.objects.create(
            owner_profile=self.owner,
            created_by=self.owner,
            title="Private owner service",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        personal_service = ServiceDetails.objects.create(
            activity=personal_activity,
            service_kind=ServiceKind.APPLICATION_SUPPORT,
            opportunity_policy=OpportunityPolicy.NONE,
        )
        path = reverse("services-api:start", kwargs={"pk": personal_service.pk})
        self.client.force_login(self.participant)
        self.assertEqual(self.client.get(path).status_code, 200)
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.assertFalse(public_services().filter(pk=personal_service.pk).exists())
        self.assertEqual(self.client.get(path).status_code, 404)
