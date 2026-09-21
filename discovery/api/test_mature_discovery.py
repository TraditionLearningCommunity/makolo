from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import (
    Activity,
    ActivityStatus,
    ActivityVisibility,
    Occurrence,
    OccurrenceStatus,
)
from discovery.models import ActivityBookmark, DiscoveryWatch
from events.models import Event
from funding.models import FundingDetails
from groups.models import (
    ActivityGroupEligibility,
    ActivityGroupEligibilityStatus,
    Group,
    GroupMembership,
    GroupMembershipStatus,
)
from journeys.models import Journey, JourneyStatus, WorkflowKind
from opportunities.models import (
    Opportunity,
    OpportunityKind,
    OpportunityPublicationStatus,
    OpportunityRevision,
    OpportunitySave,
)
from organizations.models import Organization
from services.models import OpportunityPolicy, ServiceDetails, ServiceKind
from topics.models import ProfileInterest


User = get_user_model()


class MatureDiscoveryAPITests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.owner = User.objects.create_user(
            username="z3-owner",
            email="z3-owner@example.test",
            password="StrongPass2026!",
        )
        self.participant = User.objects.create_user(
            username="z3-participant",
            email="z3-participant@example.test",
            password="StrongPass2026!",
        )
        self.outsider = User.objects.create_user(
            username="z3-outsider",
            email="z3-outsider@example.test",
            password="StrongPass2026!",
        )
        self.space = Organization.objects.create(
            name="Z3 Space",
            slug="z3-space",
            city="Lubumbashi",
            country="CD",
            public_profile=True,
            created_by=self.owner,
        )
        self.event_activity = self._activity("Z3 concert")
        self.event_occurrence = self._occurrence(self.event_activity)
        self.event = Event.objects.create(
            activity=self.event_activity,
            published_at=self.now,
        )

        self.service_activity = self._activity("Z3 accompagnement")
        self.service = ServiceDetails.objects.create(
            activity=self.service_activity,
            service_kind=ServiceKind.APPLICATION_SUPPORT,
            opportunity_policy=OpportunityPolicy.NONE,
        )

        self.funding_activity = self._activity("Z3 financement")
        self.funding = FundingDetails.objects.create(
            activity=self.funding_activity,
            currency="USD",
            target_amount=Decimal("1000.00"),
            opens_at=self.now - timedelta(days=1),
            closes_at=self.now + timedelta(days=30),
        )

        self.opportunity = Opportunity.objects.create(
            kind=OpportunityKind.SCHOLARSHIP,
            created_by=self.owner,
        )
        self.revision = OpportunityRevision.objects.create(
            opportunity=self.opportunity,
            version=1,
            title="Z3 bourse",
            summary="Bourse publique Z3",
            issuer_name="Fondation Z3",
            opens_at=self.now - timedelta(days=1),
            deadline_at=self.now + timedelta(days=30),
            timezone="Africa/Lubumbashi",
            created_by=self.owner,
        )
        OpportunityRevision.objects.filter(pk=self.revision.pk).update(
            published_at=self.now,
        )
        Opportunity.objects.filter(pk=self.opportunity.pk).update(
            current_revision=self.revision,
            publication_status=OpportunityPublicationStatus.PUBLISHED,
            published_at=self.now,
        )
        self.opportunity.refresh_from_db()
        self.revision.refresh_from_db()

    def _activity(self, title, *, visibility=ActivityVisibility.PUBLIC):
        return Activity.objects.create(
            space=self.space,
            created_by=self.owner,
            title=title,
            short_description=f"Résumé {title}",
            description=f"Description complète {title}",
            status=ActivityStatus.PUBLISHED,
            visibility=visibility,
        )

    def _occurrence(self, activity, *, start=None, status=OccurrenceStatus.SCHEDULED):
        start = start or self.now + timedelta(days=2)
        return Occurrence.objects.create(
            activity=activity,
            start_at=start,
            end_at=start + timedelta(hours=2),
            timezone="Africa/Lubumbashi",
            status=status,
        )

    def _items(self, **params):
        response = self.client.get(reverse("discovery_api:items"), params)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_collection_is_multi_family_and_has_no_ranking_contract(self):
        payload = self._items(q="Z3", page_size=20)
        self.assertEqual(payload["meta"]["projection"], "discovery.items")
        rows = payload["data"]["results"]
        families = {row["identity"]["family"] for row in rows}
        self.assertEqual(
            families,
            {"activity", "service_activity", "funding_activity", "opportunity"},
        )
        serialized = str(rows)
        for forbidden in (
            "global_score",
            "match_percentage",
            "attention_score",
            "'rank'",
            "'relevance'",
            "'probability'",
        ):
            self.assertNotIn(forbidden, serialized)
        opportunity = next(
            row for row in rows if row["identity"]["family"] == "opportunity"
        )
        self.assertEqual(
            opportunity["identity"]["resource"]["id"],
            str(self.opportunity.pk),
        )
        self.assertEqual(
            opportunity["identity"]["revision"]["id"],
            str(self.revision.pk),
        )
        self.assertIsNone(opportunity["identity"]["occurrence"])

    def test_collection_empty_is_valid_and_pagination_is_bounded(self):
        payload = self._items(q="does-not-exist-z3", page_size=999)
        self.assertEqual(payload["data"]["results"], [])
        self.assertEqual(payload["data"]["count"], 0)
        self.assertEqual(payload["data"]["page_size"], 50)
        self.assertFalse(payload["data"]["has_next"])

    def test_private_unlisted_cancelled_and_ended_do_not_enter_collection_or_detail(self):
        private = self._activity(
            "Z3 private",
            visibility=ActivityVisibility.PRIVATE,
        )
        self._occurrence(private)
        unlisted = self._activity(
            "Z3 unlisted",
            visibility=ActivityVisibility.UNLISTED,
        )
        self._occurrence(unlisted)
        cancelled = self._activity("Z3 cancelled")
        self._occurrence(cancelled, status=OccurrenceStatus.CANCELLED)
        ended = self._activity("Z3 ended")
        self._occurrence(
            ended,
            start=self.now - timedelta(days=2),
        )

        payload = self._items(q="Z3")
        ids = {
            row["identity"]["resource"]["id"]
            for row in payload["data"]["results"]
            if row["identity"]["family"] == "activity"
        }
        for hidden in (private, unlisted, cancelled, ended):
            self.assertNotIn(str(hidden.pk), ids)
            detail = self.client.get(
                reverse(
                    "discovery_api:item-detail",
                    kwargs={"family": "activity", "item_id": hidden.pk},
                )
            )
            self.assertEqual(detail.status_code, 404)

    def test_group_gated_service_and_funding_follow_viewer_membership(self):
        group = Group.objects.create(
            name="Z3 gated",
            space=self.space,
            created_by=self.owner,
        )
        for activity in (self.service_activity, self.funding_activity):
            ActivityGroupEligibility.objects.create(
                group=group,
                activity=activity,
                status=ActivityGroupEligibilityStatus.APPROVED,
                requested_by=self.owner,
                decided_by=self.owner,
                decided_at=self.now,
            )

        anonymous = self._items(q="Z3")
        anonymous_ids = {
            row["identity"]["resource"]["id"]
            for row in anonymous["data"]["results"]
        }
        self.assertNotIn(str(self.service_activity.pk), anonymous_ids)
        self.assertNotIn(str(self.funding_activity.pk), anonymous_ids)

        GroupMembership.objects.create(
            group=group,
            profile=self.participant,
            status=GroupMembershipStatus.ACTIVE,
        )
        self.client.force_login(self.participant)
        member = self._items(q="Z3")
        member_ids = {
            row["identity"]["resource"]["id"]
            for row in member["data"]["results"]
        }
        self.assertIn(str(self.service_activity.pk), member_ids)
        self.assertIn(str(self.funding_activity.pk), member_ids)

        self.client.force_login(self.outsider)
        outsider = self._items(q="Z3")
        outsider_ids = {
            row["identity"]["resource"]["id"]
            for row in outsider["data"]["results"]
        }
        self.assertNotIn(str(self.service_activity.pk), outsider_ids)
        self.assertNotIn(str(self.funding_activity.pk), outsider_ids)

    def test_detail_is_retrieve_not_search_and_preserves_owner_description(self):
        response = self.client.get(
            reverse(
                "discovery_api:item-detail",
                kwargs={
                    "family": "activity",
                    "item_id": self.event_activity.pk,
                },
            ),
            {"q": "not-the-title"},
        )
        self.assertEqual(response.status_code, 200)
        item = response.json()["data"]["item"]
        self.assertEqual(
            item["identity"]["resource"]["id"],
            str(self.event_activity.pk),
        )
        self.assertEqual(
            item["detail"]["description"],
            self.event_activity.description,
        )

    def test_personal_relation_is_resolved_for_request_user_only(self):
        Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.event_activity,
            occurrence=self.event_occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.DRAFT,
        )
        url = reverse(
            "discovery_api:item-detail",
            kwargs={
                "family": "activity",
                "item_id": self.event_activity.pk,
            },
        )

        self.client.force_login(self.participant)
        mine = self.client.get(url).json()["data"]["item"]
        self.assertEqual(
            mine["personal_relation"]["state"],
            "journey_pending",
        )

        self.client.force_login(self.outsider)
        other = self.client.get(url).json()["data"]["item"]
        self.assertEqual(other["personal_relation"]["state"], "none")
        self.assertNotIn(str(self.participant.pk), str(other))

    def test_profile_id_override_is_rejected(self):
        self.client.force_login(self.participant)
        response = self.client.get(
            reverse("discovery_api:items"),
            {"profile_id": self.outsider.pk},
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(str(self.outsider.email), response.content.decode())

    def test_save_is_explicit_and_does_not_create_interest_watch_or_journey(self):
        self.client.force_login(self.participant)
        url = reverse(
            "discovery_api:item-saved",
            kwargs={
                "family": "service_activity",
                "item_id": self.service_activity.pk,
            },
        )
        before = {
            "interests": ProfileInterest.objects.filter(
                profile=self.participant
            ).count(),
            "watches": DiscoveryWatch.objects.filter(
                owner=self.participant
            ).count(),
            "journeys": Journey.objects.filter(
                beneficiary=self.participant
            ).count(),
        }
        saved = self.client.put(url, {}, content_type="application/json")
        self.assertEqual(saved.status_code, 200, saved.content)
        self.assertTrue(
            ActivityBookmark.objects.filter(
                user=self.participant,
                activity=self.service_activity,
            ).exists()
        )
        item = saved.json()["data"]["item"]
        self.assertEqual(item["saved"]["state"], "saved")
        self.assertIn("unsave", item["capabilities"])

        after = {
            "interests": ProfileInterest.objects.filter(
                profile=self.participant
            ).count(),
            "watches": DiscoveryWatch.objects.filter(
                owner=self.participant
            ).count(),
            "journeys": Journey.objects.filter(
                beneficiary=self.participant
            ).count(),
        }
        self.assertEqual(before, after)

        removed = self.client.delete(url)
        self.assertEqual(removed.status_code, 200)
        self.assertFalse(
            ActivityBookmark.objects.filter(
                user=self.participant,
                activity=self.service_activity,
            ).exists()
        )

    def test_opportunity_save_uses_owner_truth(self):
        self.client.force_login(self.participant)
        url = reverse(
            "discovery_api:item-saved",
            kwargs={
                "family": "opportunity",
                "item_id": self.opportunity.pk,
            },
        )
        response = self.client.put(url, {}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            OpportunitySave.objects.filter(
                profile=self.participant,
                opportunity=self.opportunity,
            ).exists()
        )

    def test_watch_is_private_replayable_and_has_no_conservation_or_engagement_side_effect(self):
        self.client.force_login(self.participant)
        before_bookmarks = ActivityBookmark.objects.filter(
            user=self.participant
        ).count()
        before_journeys = Journey.objects.filter(
            beneficiary=self.participant
        ).count()
        before_interests = ProfileInterest.objects.filter(
            profile=self.participant
        ).count()

        created = self.client.post(
            reverse("discovery_api:watches"),
            {
                "name": "Z3 à suivre",
                "criteria": {"q": "Z3"},
            },
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        watch_id = created.json()["data"]["watch"]["id"]
        self.assertEqual(
            DiscoveryWatch.objects.get(pk=watch_id).owner_id,
            self.participant.pk,
        )

        results = self.client.get(
            reverse(
                "discovery_api:watch-results",
                kwargs={"watch_id": watch_id},
            )
        )
        self.assertEqual(results.status_code, 200, results.content)
        families = {
            row["identity"]["family"]
            for row in results.json()["data"]["results"]
        }
        self.assertIn("activity", families)
        self.assertIn("service_activity", families)
        self.assertEqual(
            results.json()["data"]["supported_families"],
            ["activity", "service_activity"],
        )

        self.assertEqual(
            ActivityBookmark.objects.filter(user=self.participant).count(),
            before_bookmarks,
        )
        self.assertEqual(
            Journey.objects.filter(beneficiary=self.participant).count(),
            before_journeys,
        )
        self.assertEqual(
            ProfileInterest.objects.filter(profile=self.participant).count(),
            before_interests,
        )

        self.client.force_login(self.outsider)
        denied = self.client.get(
            reverse(
                "discovery_api:watch-detail",
                kwargs={"watch_id": watch_id},
            )
        )
        self.assertEqual(denied.status_code, 404)

    def test_event_exposes_real_owner_api_handoff_without_creating_journey(self):
        before = Journey.objects.count()
        payload = self._items(q="Z3 concert")
        item = next(
            row
            for row in payload["data"]["results"]
            if row["identity"]["resource"]["id"] == str(self.event_activity.pk)
        )
        handoff = item["engagement"]
        self.assertEqual(handoff["state"], "owner_api")
        self.assertEqual(handoff["owner"], "events")
        self.assertEqual(
            handoff["links"]["detail"],
            reverse(
                "participant-event-detail",
                kwargs={"slug": self.event.slug},
            ),
        )
        self.assertEqual(
            handoff["links"]["offers"],
            reverse(
                "participant-ticket-type-list",
                kwargs={"slug": self.event.slug},
            ),
        )
        self.assertEqual(
            handoff["links"]["orders"],
            reverse("ticket-orders-list"),
        )
        self.assertEqual(Journey.objects.count(), before)

    def test_unknown_is_not_rewritten_as_impossible(self):
        payload = self._items(q="Z3 accompagnement")
        item = next(
            row
            for row in payload["data"]["results"]
            if row["identity"]["family"] == "service_activity"
        )
        self.assertEqual(item["availability"]["state"], "unknown")
        states = {fact["state"] for fact in item["assessment"]}
        self.assertIn("unknown", states)
        self.assertNotIn("impossible", str(item).lower())

    def test_map_uses_same_viewer_and_does_not_expose_personal_relation(self):
        self.client.force_login(self.participant)
        response = self.client.get(reverse("discovery_api:map"), {"q": "Z3"})
        self.assertEqual(response.status_code, 200)
        serialized = str(response.json()).lower()
        for forbidden in (
            "personal_relation",
            "journey_pending",
            "accesscredential",
            "secondary_label",
        ):
            self.assertNotIn(forbidden, serialized)
