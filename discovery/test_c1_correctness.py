from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence, OccurrencePlace, OccurrencePlaceRole, OccurrenceStatus
from capacity.models import CapacityPool
from commerce.models import Offer, OfferStatus, PaymentMode
from commerce.selectors import applicable_offers
from core.product_language import vertical_for
from events.models import Event
from geography.models import Place, SpacePlace, SpacePlaceRole
from groups.models import ActivityGroupEligibility, ActivityGroupEligibilityStatus, Group, GroupMembership, GroupMembershipSource, GroupMembershipStatus
from opportunities.models import Opportunity, OpportunityKind, OpportunityPublicationStatus, OpportunityRevision
from organizations.models import Organization, OrganizationFollow
from services.models import OpportunityPolicy, ServiceDetails, ServiceKind
from transport.selectors import next_public_departure_for_activity
from transport.services import create_transport_departure, create_transport_route, create_transport_service, publish_transport_departure

from .candidate_identity import occurrence_candidate_key, opportunity_candidate_key, service_activity_candidate_key
from .recommendations import activity_destination, build_activity_recommendations
from .search import search_occurrences
from .services import build_trending
from .unified import public_opportunity_discovery_items, public_service_discovery_items


User = get_user_model()


class C1DiscoveryCorrectnessTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.owner = User.objects.create_user(username="c1-owner", email="c1-owner@example.test", password="StrongPass2026!")
        self.participant = User.objects.create_user(username="c1-participant", email="c1-participant@example.test", password="StrongPass2026!")
        self.outsider = User.objects.create_user(username="c1-outsider", email="c1-outsider@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(
            name="C1 Space",
            slug="c1-space",
            city="Lubumbashi",
            country="CD",
            public_profile=True,
            created_by=self.owner,
        )
        self.place = Place.objects.create(
            name="C1 Lubumbashi",
            locality="Lubumbashi",
            country_code="CD",
            latitude=Decimal("-11.664700"),
            longitude=Decimal("27.479400"),
            timezone="Africa/Lubumbashi",
            created_by=self.owner,
        )
        self.destination = Place.objects.create(
            name="C1 Kolwezi",
            locality="Kolwezi",
            country_code="CD",
            latitude=Decimal("-10.716700"),
            longitude=Decimal("25.466700"),
            timezone="Africa/Lubumbashi",
            created_by=self.owner,
        )
        for place in (self.place, self.destination):
            SpacePlace.objects.create(
                organization=self.space,
                place=place,
                role=SpacePlaceRole.SERVICE_POINT,
                is_public=True,
            )

    def activity(self, title, *, owner_profile=False):
        kwargs = {
            "created_by": self.owner,
            "title": title,
            "status": ActivityStatus.PUBLISHED,
            "visibility": ActivityVisibility.PUBLIC,
        }
        if owner_profile:
            kwargs["owner_profile"] = self.owner
        else:
            kwargs["space"] = self.space
        return Activity.objects.create(**kwargs)

    def occurrence(self, activity, *, start=None, status=OccurrenceStatus.SCHEDULED, place=True):
        start = start or self.now + timedelta(days=2)
        occurrence = Occurrence.objects.create(
            activity=activity,
            start_at=start,
            end_at=start + timedelta(hours=2),
            timezone="Africa/Lubumbashi",
            status=status,
        )
        if place:
            OccurrencePlace.objects.create(
                occurrence=occurrence,
                place=self.place,
                role=OccurrencePlaceRole.PRIMARY,
            )
        return occurrence

    def published_opportunity(self, title, *, opens_at=None, deadline_at=None):
        opportunity = Opportunity.objects.create(kind=OpportunityKind.SCHOLARSHIP, created_by=self.owner)
        revision = OpportunityRevision.objects.create(
            opportunity=opportunity,
            version=1,
            title=title,
            summary=f"Résumé {title}",
            issuer_name="Fondation C1",
            opens_at=opens_at,
            deadline_at=deadline_at,
            timezone="Africa/Lubumbashi",
            created_by=self.owner,
        )
        OpportunityRevision.objects.filter(pk=revision.pk).update(published_at=self.now)
        Opportunity.objects.filter(pk=opportunity.pk).update(
            current_revision=revision,
            publication_status=OpportunityPublicationStatus.PUBLISHED,
            published_at=self.now,
        )
        opportunity.refresh_from_db()
        revision.refresh_from_db()
        return opportunity, revision

    def transport_service(self, title="C1 Transport"):
        route = create_transport_route(
            space=self.space,
            name=f"{title} route",
            stops=[self.place, self.destination],
        )
        return create_transport_service(
            space=self.space,
            created_by=self.owner,
            route=route,
            title=title,
        )

    def departure(self, service, *, start, status=OccurrenceStatus.SCHEDULED):
        departure = create_transport_departure(
            service=service,
            start_at=start,
            end_at=start + timedelta(hours=4),
            timezone_name="Africa/Lubumbashi",
            capacity=30,
        )
        publish_transport_departure(departure=departure)
        if status != OccurrenceStatus.SCHEDULED:
            Occurrence.objects.filter(pk=departure.occurrence_id).update(status=status)
            departure.occurrence.refresh_from_db()
        return departure

    def test_candidate_identity_is_canonical_and_family_is_not_vertical(self):
        activity = self.activity("Identity Event")
        first = self.occurrence(activity, start=self.now + timedelta(days=1))
        second = self.occurrence(activity, start=self.now + timedelta(days=2))
        self.assertEqual(occurrence_candidate_key(first), occurrence_candidate_key(first.pk))
        self.assertNotEqual(occurrence_candidate_key(first), occurrence_candidate_key(second))

        service_activity = self.activity("Identity Service")
        ServiceDetails.objects.create(activity=service_activity, service_kind=ServiceKind.ORIENTATION)
        self.assertEqual(str(service_activity_candidate_key(service_activity)), f"service_activity:{service_activity.pk}")

    def test_opportunity_identity_survives_revision_change(self):
        opportunity, first_revision = self.published_opportunity("Bourse C1", deadline_at=self.now + timedelta(days=10))
        original_key = opportunity_candidate_key(opportunity)
        second_revision = OpportunityRevision.objects.create(
            opportunity=opportunity,
            version=2,
            title="Bourse C1 mise à jour",
            summary="Version 2",
            issuer_name="Fondation C1",
            deadline_at=self.now + timedelta(days=20),
            timezone="Africa/Lubumbashi",
            created_by=self.owner,
        )
        OpportunityRevision.objects.filter(pk=second_revision.pk).update(published_at=self.now)
        Opportunity.objects.filter(pk=opportunity.pk).update(current_revision=second_revision)
        opportunity.refresh_from_db()
        second_revision.refresh_from_db()
        self.assertEqual(original_key, opportunity_candidate_key(opportunity))
        rows = public_opportunity_discovery_items({"q": "Bourse C1"})
        self.assertEqual(rows[0]["candidate_key"], str(original_key))
        self.assertEqual(rows[0]["revision_id"], str(second_revision.pk))
        self.assertNotEqual(rows[0]["revision_id"], str(first_revision.pk))

    def test_open_upcoming_closed_opportunity_truth_and_service_context(self):
        open_opp, _ = self.published_opportunity(
            "Bourse Ouverte C1",
            opens_at=self.now - timedelta(days=1),
            deadline_at=self.now + timedelta(days=5),
        )
        upcoming_opp, _ = self.published_opportunity(
            "Bourse Future C1",
            opens_at=self.now + timedelta(days=3),
            deadline_at=self.now + timedelta(days=10),
        )
        self.published_opportunity(
            "Bourse Fermée C1",
            opens_at=self.now - timedelta(days=10),
            deadline_at=self.now - timedelta(days=1),
        )
        service_activity = self.activity("Accompagnement Bourses C1")
        ServiceDetails.objects.create(
            activity=service_activity,
            service_kind=ServiceKind.APPLICATION_SUPPORT,
            opportunity_policy=OpportunityPolicy.REQUIRED,
        )

        open_services = public_service_discovery_items({"q": "Bourse Ouverte C1"})
        self.assertEqual(len(open_services), 1)
        self.assertIn(str(open_opp.pk), open_services[0]["url"])

        future_services = public_service_discovery_items({"q": "Bourse Future C1"})
        closed_services = public_service_discovery_items({"q": "Bourse Fermée C1"})
        self.assertEqual(future_services, [])
        self.assertEqual(closed_services, [])

        upcoming_rows = public_opportunity_discovery_items({"q": "Bourse Future C1"})
        self.assertEqual(upcoming_rows[0]["temporal_state"], "upcoming")
        self.assertEqual(upcoming_rows[0]["candidate_key"], str(opportunity_candidate_key(upcoming_opp)))
        self.assertEqual(public_opportunity_discovery_items({"q": "Bourse Fermée C1"}), [])

    def test_related_opportunity_and_service_remain_distinct_possibilities(self):
        opportunity, _ = self.published_opportunity("Bourse Relation C1", deadline_at=self.now + timedelta(days=5))
        activity = self.activity("Aide Bourse Relation C1")
        ServiceDetails.objects.create(
            activity=activity,
            service_kind=ServiceKind.APPLICATION_SUPPORT,
            opportunity_policy=OpportunityPolicy.REQUIRED,
        )
        opportunity_rows = public_opportunity_discovery_items({"q": "Bourse Relation C1"})
        service_rows = public_service_discovery_items({"q": "Bourse Relation C1"})
        self.assertEqual(opportunity_rows[0]["candidate_key"], str(opportunity_candidate_key(opportunity)))
        self.assertEqual(service_rows[0]["candidate_key"], str(service_activity_candidate_key(activity)))
        self.assertNotEqual(opportunity_rows[0]["candidate_key"], service_rows[0]["candidate_key"])

    def test_transport_destination_ignores_past_cancelled_and_chooses_earliest_valid_future(self):
        service = self.transport_service()
        past = self.departure(service, start=self.now + timedelta(days=1))
        Occurrence.objects.filter(pk=past.occurrence_id).update(
            start_at=self.now - timedelta(days=2),
            end_at=self.now - timedelta(days=2, hours=-4),
        )
        cancelled = self.departure(service, start=self.now + timedelta(hours=12), status=OccurrenceStatus.CANCELLED)
        later = self.departure(service, start=self.now + timedelta(days=3))
        earliest = self.departure(service, start=self.now + timedelta(days=2))

        selected = next_public_departure_for_activity(service.activity, now=self.now)
        self.assertEqual(selected.pk, earliest.pk)
        label, url = activity_destination(service.activity, transport_departure=selected)
        self.assertEqual(label, "Voir")
        self.assertEqual(url, reverse("transport:departure-detail", kwargs={"pk": earliest.pk}))
        self.assertNotIn(str(past.pk), url)
        self.assertNotIn(str(cancelled.pk), url)
        self.assertNotIn(str(later.pk), url)

    def test_event_secondary_occurrence_never_inherits_primary_acquisition(self):
        activity = self.activity("Event Multi C1")
        primary = self.occurrence(activity, start=self.now + timedelta(days=1))
        secondary = self.occurrence(activity, start=self.now + timedelta(days=2))
        event = Event.objects.create(activity=activity, slug="event-multi-c1")
        pool = CapacityPool.objects.create(
            activity=activity,
            occurrence=primary,
            label="Primary only",
            total_quantity=7,
        )
        Offer.objects.create(
            activity=activity,
            occurrence=primary,
            capacity_pool=pool,
            name="Primary ticket",
            unit_price=Decimal("15.00"),
            currency="USD",
            payment_mode=PaymentMode.UPFRONT,
            status=OfferStatus.ACTIVE,
        )

        rows = search_occurrences({"q": "Event Multi C1"}, now=self.now).items
        by_id = {row.occurrence_id: row for row in rows}
        primary_row = by_id[str(primary.pk)]
        secondary_row = by_id[str(secondary.pk)]
        self.assertEqual(primary_row.price.minimum, Decimal("15.00"))
        self.assertIsNone(secondary_row.price.minimum)
        self.assertIsNone(secondary_row.availability.remaining)
        self.assertEqual(secondary_row.cta_label, "Voir l’événement")
        self.assertEqual(secondary_row.url, reverse("events:detail", kwargs={"slug": event.slug}))
        self.assertNotEqual(primary_row.candidate_key, secondary_row.candidate_key)

    def test_activity_scoped_and_occurrence_scoped_offers_are_explicitly_applicable(self):
        activity = self.activity("Offers C1")
        first = self.occurrence(activity, start=self.now + timedelta(days=1))
        second = self.occurrence(activity, start=self.now + timedelta(days=2))
        activity_offer = Offer.objects.create(
            activity=activity,
            name="Activity offer",
            unit_price=Decimal("20.00"),
            currency="USD",
            payment_mode=PaymentMode.UPFRONT,
            status=OfferStatus.ACTIVE,
        )
        first_offer = Offer.objects.create(
            activity=activity,
            occurrence=first,
            name="First only",
            unit_price=Decimal("10.00"),
            currency="USD",
            payment_mode=PaymentMode.UPFRONT,
            status=OfferStatus.ACTIVE,
        )
        Offer.objects.create(
            activity=activity,
            occurrence=second,
            name="Inactive second",
            unit_price=Decimal("5.00"),
            currency="USD",
            payment_mode=PaymentMode.UPFRONT,
            status=OfferStatus.INACTIVE,
        )
        self.assertEqual(set(applicable_offers(occurrence=first)), {activity_offer, first_offer})
        self.assertEqual(set(applicable_offers(occurrence=second).filter(status=OfferStatus.ACTIVE)), {activity_offer})
        self.assertEqual(list(applicable_offers(activity=activity)), [activity_offer])

        rows = search_occurrences({"q": "Offers C1"}, now=self.now).items
        by_id = {row.occurrence_id: row for row in rows}
        self.assertEqual(by_id[str(first.pk)].price.minimum, Decimal("10.00"))
        self.assertEqual(by_id[str(second.pk)].price.minimum, Decimal("20.00"))

    def test_group_eligibility_is_composed_into_search(self):
        activity = self.activity("Groupe C1")
        occurrence = self.occurrence(activity)
        group = Group.objects.create(name="Groupe réservé C1", owner_profile=self.owner, created_by=self.owner)
        ActivityGroupEligibility.objects.create(
            group=group,
            activity=activity,
            status=ActivityGroupEligibilityStatus.APPROVED,
            requested_by=self.owner,
            decided_by=self.owner,
        )
        outsider_ids = {row.occurrence_id for row in search_occurrences({"q": "Groupe C1"}, profile=self.outsider, now=self.now).items}
        self.assertNotIn(str(occurrence.pk), outsider_ids)
        GroupMembership.objects.create(
            group=group,
            profile=self.participant,
            status=GroupMembershipStatus.ACTIVE,
            source=GroupMembershipSource.MANUAL,
        )
        member_ids = {row.occurrence_id for row in search_occurrences({"q": "Groupe C1"}, profile=self.participant, now=self.now).items}
        self.assertIn(str(occurrence.pk), member_ids)

    def test_vertical_resolution_recognizes_service_and_generic(self):
        event_activity = self.activity("Vertical Event C1")
        self.occurrence(event_activity)
        Event.objects.create(activity=event_activity, slug="vertical-event-c1")
        service_activity = self.activity("Vertical Service C1")
        ServiceDetails.objects.create(activity=service_activity, service_kind=ServiceKind.ORIENTATION)
        self.occurrence(service_activity)
        generic_activity = self.activity("Vertical Generic C1")
        self.occurrence(generic_activity)
        transport = self.transport_service("Vertical Transport C1")
        self.departure(transport, start=self.now + timedelta(days=2))
        self.assertEqual(vertical_for(event_activity), "event")
        self.assertEqual(vertical_for(service_activity), "service")
        self.assertEqual(vertical_for(transport.activity), "transport")
        self.assertEqual(vertical_for(generic_activity), "generic")
        service_rows = search_occurrences({"q": "Vertical Service C1"}, now=self.now).items
        self.assertEqual(service_rows[0].vertical, "service")

    def test_activity_first_recommendations_require_viable_possibility_and_keep_reasons_unique(self):
        OrganizationFollow.objects.create(organization=self.space, user=self.participant)
        dead_event_activity = self.activity("Dead Event C1")
        Event.objects.create(activity=dead_event_activity, slug="dead-event-c1")
        live_event_activity = self.activity("Live Event C1")
        self.occurrence(live_event_activity, start=self.now + timedelta(days=3))
        Event.objects.create(activity=live_event_activity, slug="live-event-c1")
        service_activity = self.activity("Live Service C1")
        ServiceDetails.objects.create(activity=service_activity, service_kind=ServiceKind.ORIENTATION)
        dead_transport = self.transport_service("Dead Transport C1")
        live_transport = self.transport_service("Live Transport C1")
        self.departure(live_transport, start=self.now + timedelta(days=4))

        rows = build_activity_recommendations(self.participant, limit=20)
        by_id = {row.activity.pk: row for row in rows}
        self.assertNotIn(dead_event_activity.pk, by_id)
        self.assertNotIn(dead_transport.activity.pk, by_id)
        self.assertIn(live_event_activity.pk, by_id)
        self.assertIn(service_activity.pk, by_id)
        self.assertIn(live_transport.activity.pk, by_id)
        for row in rows:
            self.assertEqual(len(row.reasons), len({reason.code for reason in row.reasons}))

    def test_common_pagination_never_repeats_service_candidates(self):
        for index in range(26):
            activity = self.activity(f"Pagination Service {index:02d} C1")
            ServiceDetails.objects.create(activity=activity, service_kind=ServiceKind.ORIENTATION)
        page1 = self.client.get(reverse("discovery:home"), {"vertical": "service", "page": 1})
        page2 = self.client.get(reverse("discovery:home"), {"vertical": "service", "page": 2})
        keys1 = {row["candidate_key"] for row in page1.context["service_items"]}
        keys2 = {row["candidate_key"] for row in page2.context["service_items"]}
        self.assertEqual(page1.context["result_count"], 26)
        self.assertEqual(page2.context["result_count"], 26)
        self.assertTrue(keys1)
        self.assertTrue(keys2)
        self.assertFalse(keys1 & keys2)

    def test_result_and_mappable_counts_are_semantically_distinct(self):
        activity = self.activity("Map Occurrence C1")
        self.occurrence(activity)
        service_activity = self.activity("Map Service C1")
        ServiceDetails.objects.create(activity=service_activity, service_kind=ServiceKind.ORIENTATION)
        response = self.client.get(reverse("discovery:home"))
        self.assertEqual(response.context["result_count"], 2)
        self.assertEqual(response.context["mappable_result_count"], 1)

    def test_trending_is_not_exposed_on_for_you_but_baseline_remains_callable(self):
        response = self.client.get(reverse("discovery:for-you"))
        self.assertNotContains(response, "Demandés récemment")
        self.assertIsInstance(build_trending(limit=3), list)
