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
    OccurrencePlace,
    OccurrencePlaceRole,
    OccurrenceStatus,
)
from discovery.models import ActivityBookmark, DiscoveryWatch
from events.models import Event
from funding.models import FundingDetails
from geography.models import Place, SpacePlace
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
from preparation.models import ActivityResource, ResourceKind, ResourceStatus, ResourceVisibility
from services.models import OpportunityPolicy, ServiceDetails, ServiceKind
from topics.models import ProfileInterest
from transport.models import TransportRoute, TransportRouteStop, TransportService


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

    def test_collection_includes_existing_detail_description(self):
        for profile in (None, self.participant):
            if profile is None:
                self.client.logout()
            else:
                self.client.force_login(profile)
            results = self._items(q="Z3", page_size=20)["data"]["results"]
            self.assertEqual(len(results), 4)
            for row in results:
                self.assertTrue(row["links"]["detail"].startswith("/api/v1/"))
                detail_response = self.client.get(row["links"]["detail"])
                self.assertEqual(detail_response.status_code, 200)
                detailed_row = detail_response.json()["data"]["item"]
                self.assertEqual(row.get("detail"), detailed_row.get("detail"))
                self.assertEqual(row["identity"], detailed_row["identity"])
                self.assertTrue(row["detail"]["description"])

    def test_collection_exposes_native_api_references_without_web_authority(self):
        from django.urls import resolve

        for viewer in (None, self.participant):
            if viewer is None:
                self.client.logout()
            else:
                self.client.force_login(viewer)
            rows = self._items(q="Z3", page_size=20)["data"]["results"]
            for row in rows:
                detail = row["links"]["detail"]
                saved = row["links"]["saved"]
                self.assertEqual(resolve(detail).url_name, "item-detail")
                self.assertEqual(resolve(saved).url_name, "item-saved")
                self.assertTrue(detail.startswith("/api/v1/"))
                self.assertTrue(saved.startswith("/api/v1/"))
                self.assertIn("view", row["capabilities"])
                self.assertEqual("save" in row["capabilities"], viewer is not None)
                engagement = row["engagement"]
                if engagement["state"] == "owner_contract":
                    self.assertEqual(engagement["links"], {})
                    self.assertEqual(engagement["capabilities"], [])
                    primary = engagement.get("presentation")
                    if primary is not None:
                        self.assertFalse(primary["enabled"])

    def test_public_service_exposes_login_continuation_not_start_authority(self):
        self.client.logout()
        rows = self._items(q="Z3 accompagnement", page_size=20)["data"]["results"]
        service = next(row for row in rows if row["identity"]["family"] == "service_activity")
        engagement = service["engagement"]
        self.assertEqual(engagement["owner"], "services")
        self.assertEqual(engagement["state"], "owner_api")
        self.assertEqual(engagement["capabilities"], ["start_after_auth"])
        self.assertNotIn("start", engagement["capabilities"])
        self.assertTrue(engagement["presentation"]["requires_auth"])
        self.assertFalse(engagement["presentation"]["enabled"])
        self.assertEqual(engagement["primary_action"]["code"], "start")
        self.assertEqual(
            engagement["primary_action"]["destination"],
            {"kind": "native", "path": f"/services/{self.service.pk}/start"},
        )
        # No private personal relation or start authorization leaks to guests.
        self.assertNotIn("journey", engagement)

        self.client.force_login(self.participant)
        personal_rows = self._items(
            q="Z3 accompagnement", page_size=20
        )["data"]["results"]
        personal = next(
            row for row in personal_rows
            if row["identity"]["family"] == "service_activity"
        )
        self.assertIn("start", personal["engagement"]["capabilities"])
        self.assertNotIn("start_after_auth", personal["engagement"]["capabilities"])

    def test_wire_exposes_only_known_owner_facts_and_empty_collections(self):
        rows = self._items(q="Z3", page_size=20)["data"]["results"]
        by_family = {row["identity"]["family"]: row for row in rows}
        self.assertEqual(
            set(by_family), {"activity", "service_activity", "funding_activity", "opportunity"}
        )
        for row in rows:
            for key in ("variants", "relations", "temporal_facts", "spatial_facts", "media_bindings"):
                self.assertIsInstance(row[key], list)
            self.assertEqual(row["relations"], [])
            self.assertEqual(row["media_bindings"], [])
        activity = by_family["activity"]
        self.assertEqual(activity["variants"], [])
        self.assertEqual(activity["spatial_facts"], [])
        self.assertTrue(activity["temporal_facts"])
        self.assertEqual(by_family["service_activity"]["temporal_facts"], [])
        self.assertEqual(by_family["service_activity"]["spatial_facts"], [])
        self.assertEqual(
            {fact["kind"] for fact in by_family["funding_activity"]["temporal_facts"]},
            {"opens_at", "closes_at"},
        )
        self.assertEqual(
            {fact["kind"] for fact in by_family["opportunity"]["temporal_facts"]},
            {"opens_at", "deadline_at"},
        )

    def test_multiple_occurrences_have_canonical_bounded_variant_references(self):
        second = self._occurrence(
            self.event_activity,
            start=self.now + timedelta(days=3),
        )
        event = next(
            row for row in self._items(q="Z3 concert")["data"]["results"]
            if row["identity"]["family"] == "activity"
        )
        self.assertEqual(
            {variant["occurrence"]["id"] for variant in event["variants"]},
            {str(self.event_occurrence.pk), str(second.pk)},
        )
        self.assertEqual(
            {variant["occurrence"]["kind"] for variant in event["variants"]},
            {"occurrence"},
        )
        # The API may serialize UTC while fixtures retain their local offset.
        # Compare instants, not their ISO-8601 textual representations.
        from datetime import datetime

        self.assertEqual(
            {
                datetime.fromisoformat(variant["timing"]["start_at"])
                for variant in event["variants"]
            },
            {self.event_occurrence.start_at, second.start_at},
        )
        self.assertEqual(event["identity"]["resource"]["id"], str(self.event_activity.pk))

    def test_spatial_facts_include_public_occurrence_place_roles(self):
        first = Place.objects.create(name="Z3 lieu principal", locality="Lubumbashi")
        second = Place.objects.create(name="Z3 point de rencontre", locality="Lubumbashi")
        OccurrencePlace.objects.create(
            occurrence=self.event_occurrence, place=first,
            role=OccurrencePlaceRole.PRIMARY,
        )
        OccurrencePlace.objects.create(
            occurrence=self.event_occurrence, place=second,
            role=OccurrencePlaceRole.MEETING_POINT,
        )
        event = next(
            row for row in self._items(q="Z3 concert")["data"]["results"]
            if row["identity"]["family"] == "activity"
        )
        self.assertEqual(
            {fact["role"] for fact in event["spatial_facts"]},
            {"primary", "meeting_point"},
        )
        self.assertEqual(
            {fact["place"]["id"] for fact in event["spatial_facts"]},
            {str(first.pk), str(second.pk)},
        )
        self.assertEqual(event["place"]["id"], str(first.pk))
        self.assertTrue(all(
            fact["occurrence"]["id"] == str(self.event_occurrence.pk)
            for fact in event["spatial_facts"]
        ))

    def test_private_space_place_is_not_exposed_by_spatial_facts(self):
        private_place = Place.objects.create(
            name="Z3 lieu privé", locality="Lubumbashi"
        )
        public_place = Place.objects.create(
            name="Z3 lieu public", locality="Lubumbashi"
        )
        SpacePlace.objects.create(
            organization=self.space, place=private_place, is_public=False
        )
        OccurrencePlace.objects.create(
            occurrence=self.event_occurrence,
            place=private_place,
            role=OccurrencePlaceRole.PRIMARY,
        )
        OccurrencePlace.objects.create(
            occurrence=self.event_occurrence,
            place=public_place,
            role=OccurrencePlaceRole.MEETING_POINT,
        )
        for profile in (None, self.participant):
            if profile is None:
                self.client.logout()
            else:
                self.client.force_login(profile)
            event = next(
                row for row in self._items(q="Z3 concert")["data"]["results"]
                if row["identity"]["family"] == "activity"
            )
            self.assertIsNone(event["place"])
            self.assertEqual(
                [fact["place"]["id"] for fact in event["spatial_facts"]],
                [str(public_place.pk)],
            )

    def test_transport_spatial_facts_preserve_route_roles_and_privacy(self):
        activity = self._activity("Z3 trajet")
        self._occurrence(activity)
        route = TransportRoute.objects.create(space=self.space, name="Z3 route")
        places = [
            Place.objects.create(name=name, locality="Lubumbashi")
            for name in (
                "Z3 départ", "Z3 escale publique", "Z3 arrêt privé", "Z3 arrivée"
            )
        ]
        for position, place in enumerate(places, start=1):
            TransportRouteStop.objects.create(
                route=route, place=place, position=position
            )
        SpacePlace.objects.create(
            organization=self.space, place=places[2], is_public=False
        )
        TransportService.objects.create(activity=activity, route=route)
        row = next(
            row for row in self._items(q="Z3 trajet")["data"]["results"]
            if row["identity"]["resource"]["id"] == str(activity.pk)
        )
        self.assertEqual(
            [(fact["role"], fact["place"]["id"]) for fact in row["spatial_facts"]],
            [
                ("departure", str(places[0].pk)),
                ("stopover", str(places[1].pk)),
                ("arrival", str(places[3].pk)),
            ],
        )
        self.assertEqual(row["identity"]["family"], "activity")

    def test_web_and_api_use_the_same_canonical_discovery_field(self):
        params = {"q": "Z3", "page_size": 20}
        api = self._items(**params)["data"]
        web = self.client.get(reverse("discovery:home"), params)

        self.assertEqual(web.status_code, 200, web.content)
        api_keys = [
            row["identity"]["candidate_key"]
            for row in api["results"]
        ]
        web_keys = [
            card.candidate_key
            for card in web.context["discovery_cards"]
        ]
        self.assertEqual(web_keys, api_keys)
        self.assertEqual(
            {constraint.key for constraint in web.context["applied_constraints"]},
            {
                item["key"]
                for item in api["exploration"]["constraints"]
            },
        )

    def test_collection_empty_is_valid_and_pagination_is_bounded(self):
        payload = self._items(q="does-not-exist-z3", page_size=999)
        self.assertEqual(payload["data"]["results"], [])
        self.assertEqual(payload["data"]["count"], 0)
        self.assertEqual(payload["data"]["page_size"], 50)
        self.assertFalse(payload["data"]["has_next"])
        self.assertEqual(payload["data"]["selection"]["state"], "empty")
        self.assertEqual(payload["data"]["selection"]["reason"], "no_match")
        self.assertEqual(payload["data"]["continuation"]["state"], "end")
        self.assertIsNone(payload["data"]["continuation"]["token"])
        self.assertEqual(
            payload["data"]["terminal"],
            {"state": "empty", "message": None},
        )

    def test_out_of_range_page_is_end_of_field_not_no_match(self):
        payload = self._items(q="Z3", page=999, page_size=1)["data"]
        self.assertGreater(payload["count"], 0)
        self.assertEqual(payload["results"], [])
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["selection"], {"state": "ready", "reason": None})
        self.assertEqual(payload["terminal"]["state"], "end_of_field")
        self.assertFalse(payload["has_next"])
        self.assertEqual(payload["continuation"]["state"], "end")
        self.assertIsNone(payload["continuation"]["token"])

    def test_generation_timestamp_does_not_assert_owner_fact_freshness(self):
        data = self._items(q="Z3")["data"]
        self.assertEqual(
            data["freshness"]["generated_at"],
            data["freshness"]["observed_at"],
        )
        self.assertEqual(data["freshness"]["fact_freshness"], "not_asserted")

    def test_public_resources_are_not_capped_at_six_and_web_discloses_all(self):
        for index in range(1, 9):
            ActivityResource.objects.create(
                activity=self.event_activity,
                key=f"document-{index:02d}",
                title=f"Document {index:02d}",
                kind=ResourceKind.TEXT,
                text_content=f"Contenu public {index}",
                visibility=ResourceVisibility.PUBLIC,
                status=ResourceStatus.PUBLISHED,
                created_by=self.owner,
                published_at=self.now,
            )
        ActivityResource.objects.create(
            activity=self.event_activity,
            key="private-document",
            title="Document privé",
            kind=ResourceKind.TEXT,
            text_content="Ne pas rendre public",
            visibility=ResourceVisibility.RESTRICTED,
            status=ResourceStatus.PUBLISHED,
            created_by=self.owner,
            published_at=self.now,
        )

        rows = self._items(q="Z3 concert")["data"]["results"]
        item = next(
            row for row in rows
            if row["identity"]["resource"]["id"] == str(self.event_activity.pk)
        )
        self.assertEqual(
            [entry["title"] for entry in item["resources"]],
            [f"Document {index:02d}" for index in range(1, 9)],
        )
        self.assertNotIn("Document privé", str(item))

        web = self.client.get(reverse("discovery:home"), {"q": "Z3 concert"})
        self.assertEqual(web.status_code, 200)
        self.assertContains(web, "Voir les 8 ressources")
        self.assertContains(web, "Document 08")
        self.assertNotContains(web, "Document privé")

    def test_public_owner_object_comes_from_logical_activity_owner(self):
        data = self._items(q="Z3 concert")["data"]
        item = next(
            row for row in data["results"]
            if row["identity"]["family"] == "activity"
        )
        owner = item["owner"]
        self.assertEqual(owner["identity"], {
            "kind": "space",
            "id": str(self.space.pk),
        })
        self.assertEqual(owner["representation"]["name"], self.space.name)
        self.assertEqual(owner["links"]["native"], f"/spaces/{self.space.slug}")
        self.assertEqual(owner["capabilities"], ["view_public"])
        self.assertEqual(item["date"]["kind"], "added_at")
        self.assertEqual(
            item["date"]["value"],
            self.event_activity.created_at.isoformat(),
        )

    def test_private_owner_is_not_promoted_to_public_navigation(self):
        self.space.public_profile = False
        self.space.save(update_fields=["public_profile"])
        item = next(
            row for row in self._items(q="Z3 concert")["data"]["results"]
            if row["identity"]["family"] == "activity"
        )
        self.assertIsNone(item["owner"])
        self.assertNotIn("created_by", item)

    def test_opportunity_issuer_is_external_without_makolo_identity(self):
        item = next(
            row for row in self._items(q="Z3 bourse")["data"]["results"]
            if row["identity"]["family"] == "opportunity"
        )
        self.assertEqual(item["owner"]["display_name"], "Fondation Z3")
        self.assertEqual(item["owner"]["identity"], {"kind": "external_issuer"})
        self.assertFalse(item["owner"]["links"])
        self.assertEqual(item["date"]["kind"], "published_at")
        self.assertEqual(
            item["date"]["value"], self.opportunity.published_at.isoformat()
        )

    def test_authenticated_service_start_refers_to_service_not_activity(self):
        self.client.force_login(self.participant)
        item = next(
            row for row in self._items(q="Z3 accompagnement")["data"]["results"]
            if row["identity"]["family"] == "service_activity"
        )
        handoff = item["engagement"]
        self.assertEqual(handoff["state"], "owner_api")
        self.assertEqual(
            handoff["resource"], {"kind": "service", "id": str(self.service.pk)}
        )
        self.assertIn("start", handoff["capabilities"])
        self.assertEqual(
            handoff["links"]["start"],
            reverse("services-api:start", kwargs={"pk": self.service.pk}),
        )
        self.assertTrue(handoff["presentation"]["enabled"])
        self.assertEqual(handoff["primary_action"]["code"], "start")
        self.assertEqual(
            handoff["primary_action"]["destination"],
            {"kind": "native", "path": f"/services/{self.service.pk}/start"},
        )

    def test_web_primary_action_is_not_an_unbacked_owner_capability(self):
        data = self._items(q="Z3 accompagnement")["data"]
        service = next(
            item for item in data["results"]
            if item["identity"]["family"] == "service_activity"
        )
        handoff = service["engagement"]
        self.assertEqual(handoff["state"], "owner_contract")
        self.assertEqual(handoff["capabilities"], [])
        presentation = handoff["presentation"]
        self.assertEqual(presentation["capability"], "start")
        self.assertFalse(presentation["enabled"])
        self.assertTrue(presentation["web_enabled"])
        self.assertTrue(presentation["web"])
        self.assertEqual(handoff["primary_action"]["code"], "detail")
        self.assertEqual(
            handoff["primary_action"]["destination"]["path"],
            service["links"]["detail"],
        )

    def test_authenticated_collection_exposes_discover_me_contract_and_cursor(self):
        self.client.force_login(self.participant)

        first = self._items(q="Z3", page_size=1)["data"]

        self.assertEqual(first["surface"], "discover_me")
        self.assertEqual(
            first["actor"],
            {"type": "profile", "id": str(self.participant.pk)},
        )
        self.assertEqual(first["viewer"], first["actor"])
        self.assertEqual(first["selection"], {"state": "ready", "reason": None})
        self.assertEqual(first["items"], first["results"])
        self.assertEqual(first["continuation"]["state"], "more")
        token = first["continuation"]["token"]
        self.assertTrue(token)

        second = self._items(
            q="Z3",
            page_size=1,
            continuation=token,
        )["data"]
        self.assertNotEqual(
            first["results"][0]["identity"]["candidate_key"],
            second["results"][0]["identity"]["candidate_key"],
        )

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
        self.assertEqual(handoff["primary_action"]["code"], "inspect_offers")
        self.assertEqual(
            handoff["primary_action"]["destination"],
            {"kind": "native", "path": f"/events/{self.event.slug}/tickets"},
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

    def test_service_and_funding_admission_reuse_owner_publication_rules(self):
        from organizations.models import SpaceLifecycle

        service_path = reverse(
            "discovery_api:item-detail",
            kwargs={"family": "service_activity", "item_id": self.service_activity.pk},
        )
        funding_path = reverse(
            "discovery_api:item-detail",
            kwargs={"family": "funding_activity", "item_id": self.funding_activity.pk},
        )
        for field, hidden in (
            ("verification_status", "suspended"),
            ("lifecycle", SpaceLifecycle.ARCHIVED),
            ("public_profile", False),
            ("searchable", False),
        ):
            with self.subTest(field=field):
                original = getattr(self.space, field)
                setattr(self.space, field, hidden)
                self.space.save(update_fields=[field])
                rows = self._items(q="Z3")["data"]["results"]
                ids = {row["identity"]["resource"]["id"] for row in rows}
                self.assertNotIn(str(self.service_activity.pk), ids)
                self.assertNotIn(str(self.funding_activity.pk), ids)
                self.assertEqual(self.client.get(service_path).status_code, 404)
                self.assertEqual(self.client.get(funding_path).status_code, 404)
                setattr(self.space, field, original)
                self.space.save(update_fields=[field])
                recovered = self._items(q="Z3")["data"]["results"]
                recovered_ids = {
                    row["identity"]["resource"]["id"] for row in recovered
                }
                self.assertIn(str(self.service_activity.pk), recovered_ids)
                self.assertIn(str(self.funding_activity.pk), recovered_ids)

    def test_public_resource_metadata_obeys_preparation_owner_gate(self):
        resource = ActivityResource.objects.create(
            activity=self.event_activity,
            key="owner-sensitive-document",
            title="Document publication conditionnelle",
            kind=ResourceKind.TEXT,
            text_content="Informations publiques seulement si le porteur publie",
            visibility=ResourceVisibility.PUBLIC,
            status=ResourceStatus.PUBLISHED,
            created_by=self.owner,
            published_at=self.now,
        )
        initial = self._items(q="Z3 concert")["data"]["results"]
        event = next(row for row in initial if row["identity"]["family"] == "activity")
        self.assertIn(str(resource.pk), str(event["resources"]))

        # The Activity can remain in the older public Event field even if its
        # owner's public profile was retracted. Preparation then denies the
        # Resource reader, so Discovery must not embed either body or metadata.
        self.space.public_profile = False
        self.space.save(update_fields=["public_profile"])
        later = self._items(q="Z3 concert")["data"]["results"]
        event = next(row for row in later if row["identity"]["family"] == "activity")
        self.assertIsNone(event["owner"])
        self.assertEqual(event["resources"], [])
        self.assertNotIn("owner-sensitive-document", str(event))

    def test_opportunity_resource_rejects_unsafe_legacy_external_url(self):
        from opportunities.models import OpportunitySource, OpportunitySourceType

        source = OpportunitySource.objects.create(
            opportunity=self.opportunity,
            source_type=OpportunitySourceType.OFFICIAL,
            source_name="Source ancienne",
            url="https://example.test/official",
        )
        OpportunitySource.objects.filter(pk=source.pk).update(
            url="javascript:alert(1)"
        )
        rows = self._items(q="Z3 bourse")["data"]["results"]
        opportunity = next(
            item for item in rows
            if item["identity"]["family"] == "opportunity"
        )
        resource = next(
            item for item in opportunity["resources"]
            if item["id"] == str(source.pk)
        )
        self.assertIsNone(resource["external_url"])
        self.assertNotIn("javascript:alert", str(resource))

    def test_invalid_cursor_and_exploration_return_api_validation_errors(self):
        self.client.force_login(self.participant)
        first = self._items(q="Z3", page_size=1)["data"]
        cursor = first["continuation"]["token"]
        self.assertIsNotNone(cursor)

        endpoint = reverse("discovery_api:items")
        for params in (
            {"q": "Z3 changed", "page_size": 1, "continuation": cursor},
            {"q": "Z3", "page_size": 2, "continuation": cursor},
            {"q": "Z3", "page_size": 1, "continuation": cursor + "tampered"},
            {"q": "Z3", "page_size": "not-an-int"},
            {"q": "Z3", "when": "invalid-temporal-preset"},
        ):
            with self.subTest(params=params):
                response = self.client.get(endpoint, params)
                self.assertEqual(response.status_code, 400, response.content)

        self.client.force_login(self.outsider)
        rejected = self.client.get(
            endpoint, {"q": "Z3", "page_size": 1, "continuation": cursor},
        )
        self.assertEqual(rejected.status_code, 400, rejected.content)

        bad_map = self.client.get(
            reverse("discovery_api:map"),
            {"when": "invalid-temporal-preset"},
        )
        self.assertEqual(bad_map.status_code, 400, bad_map.content)
