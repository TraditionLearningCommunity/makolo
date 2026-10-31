from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import grant_activity_role, grant_space_role
from commerce.models import CommerceOrder, CommerceOrderStatus, Offer, OfferStatus
from groups.models import Group, GroupMembership
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization, SpaceArchetype, Team, TeamMembership, TeamMembershipStatus
from scanner.models import ScannerAssignment
from services.models import ServiceDetails, ServiceJourneyContext, ServiceKind
from transport.models import TransportRoute, Vehicle


class ZS3SpaceWorkProjectionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="zs3-owner", email="zs3-owner@test.local", password="x"
        )
        self.outsider = User.objects.create_user(
            username="zs3-outsider", email="zs3-outsider@test.local", password="x"
        )
        self.member = User.objects.create_user(
            username="zs3-member", email="zs3-member@test.local", password="x"
        )
        self.platform = User.objects.create_user(
            username="zs3-platform", email="zs3-platform@test.local", password="x"
        )
        self.space = Organization.objects.create(
            name="ZS3 Space",
            slug="zs3-space",
            created_by=self.owner,
        )
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )
        team = Team.objects.create(
            organization=self.space,
            name="Equipe ZS3",
            is_active=True,
        )
        TeamMembership.objects.create(
            team=team,
            user=self.member,
            status=TeamMembershipStatus.ACTIVE,
        )
        grant_platform_role(
            profile=self.platform,
            role=SystemRoleCode.PLATFORM_ADMIN,
            granted_by=self.platform,
        )
        self.client = APIClient()
        self.url = "/api/v1/organizations/workspaces/zs3-space/work/"

    def _activity(self, title="Activité ZS3", **kwargs):
        return Activity.objects.create(
            title=title,
            created_by=self.owner,
            space=self.space,
            **kwargs,
        )

    def test_owner_selection_revalidates_scope_and_works_beyond_preview(self):
        self.client.force_authenticate(self.owner)
        for index in range(21):
            self._activity(f"A {index:02}")
        selected = self._activity("Z selected")
        response = self.client.get(self.url, {"kind": "activity", "id": str(selected.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["selection"]["source"]["id"], str(selected.pk))
        foreign = Organization.objects.create(name="Foreign", slug="foreign-work", created_by=self.owner)
        hidden = Activity.objects.create(title="Hidden", space=foreign, created_by=self.owner)
        for kind, identity in (("activity", hidden.pk), ("activity", "bad-id"), ("unknown", selected.pk)):
            denied = self.client.get(self.url, {"kind": kind, "id": str(identity)})
            self.assertIsNone(denied.data["selection"])
            self.assertNotIn("Hidden", str(denied.data))

    def test_work_section_continuation_does_not_repeat_preview_or_cross_owner(self):
        self.client.force_authenticate(self.owner)
        expected = [self._activity(f"A {index:02}") for index in range(23)]
        first = self.client.get(self.url, {"section": "preparation", "offset": "0"})
        second = self.client.get(self.url, {"section": "preparation", "offset": "20"})
        self.assertEqual(set(second.data["sections"]), {"preparation"})
        preview = first.data["sections"]["preparation"]
        continuation = second.data["sections"]["preparation"]
        self.assertTrue(preview["has_more"])
        self.assertFalse(continuation["has_more"])
        identities = [item["source"]["id"] for item in preview["items"] + continuation["items"]]
        self.assertEqual(identities, [str(activity.pk) for activity in expected])
        self.assertNotIn("_offset", str(second.data))
        self.assertEqual(self.client.get(self.url, {"offset": "-1"}).status_code, 400)
        self.assertEqual(self.client.get(self.url, {"offset": "bad"}).status_code, 400)
        self.assertEqual(self.client.get(self.url, {"section": "not-an-owner"}).status_code, 404)

    def test_activity_lens_does_not_expose_transport_structure_or_foreign_activity(self):
        self.client.force_authenticate(self.owner)
        self.space.archetype = SpaceArchetype.TRANSPORT_OPERATOR
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self._activity("Scoped activity")
        hidden = self._activity("Other activity")
        mandate = grant_activity_role(
            profile=self.owner, activity=activity,
            role_code=SystemRoleCode.ACTIVITY_MANAGER, granted_by=self.owner,
        )
        route = TransportRoute.objects.create(space=self.space, name="Route privée")
        params = {"responsibility": f"mandate:{mandate.pk}"}
        response = self.client.get(self.url, params)
        self.assertNotIn("routes", response.data["sections"])
        for kind, identity in (("transport_route", route.pk), ("activity", hidden.pk)):
            selected = self.client.get(self.url, {**params, "kind": kind, "id": str(identity)})
            self.assertIsNone(selected.data["selection"])

    def test_auth_and_minimal_disclosure_boundaries(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, 404)

        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.get(self.url).status_code, 404)

        activity = self._activity("Scanner assignment only")
        ScannerAssignment.objects.create(
            activity=activity,
            agent=self.member,
            assigned_by=self.owner,
            label="Porte ZS3",
        )
        self.assertEqual(self.client.get(self.url).status_code, 404)

        group = Group.objects.create(
            name="Groupe ZS3",
            space=self.space,
            created_by=self.owner,
        )
        GroupMembership.objects.create(group=group, profile=self.member)
        self.assertEqual(self.client.get(self.url).status_code, 404)

        self.client.force_authenticate(self.platform)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_community_group_membership_never_grants_space_work_authority(self):
        self.space.archetype = SpaceArchetype.COMMUNITY
        self.space.save(update_fields=["archetype", "updated_at"])
        community_member = User.objects.create_user(
            username="zs3-community-member",
            email="community-member@test.local",
            password="x",
        )
        group = Group.objects.create(
            name="Communauté locale",
            space=self.space,
            created_by=self.owner,
        )
        GroupMembership.objects.create(group=group, profile=community_member)
        self.client.force_authenticate(community_member)

        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_community_presentation_keeps_initiative_as_ux_language_only(self):
        self.space.archetype = SpaceArchetype.COMMUNITY
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self._activity("Nettoyage du quartier")
        self.client.force_authenticate(self.owner)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["sections"]["activities"]["representation"], "Initiatives")
        row = next(
            item for item in response.data["sections"]["preparation"]["items"]
            if item["source"] == {"kind": "activity", "id": str(activity.pk)}
        )
        self.assertEqual(row["kind"], "activity")
        self.assertNotIn("permission", str(row).lower())

    def test_empty_collections_are_valid_and_do_not_invent_work(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        for key in ("preparation", "upcoming", "active", "blocked", "completed"):
            self.assertEqual(response.data["sections"][key]["items"], [])
            self.assertFalse(response.data["sections"][key]["has_more"])

    def test_all_archetypes_use_zs1_business_language(self):
        expected = {
            SpaceArchetype.GENERIC: "Activités",
            SpaceArchetype.CREATIVE: "Créations",
            SpaceArchetype.MEDIA: "Productions",
            SpaceArchetype.EDUCATION: "Programmes",
            SpaceArchetype.COMMERCE: "Commerce",
            SpaceArchetype.SERVICE_PROVIDER: "Prestations",
            SpaceArchetype.TRANSPORT_OPERATOR: "Transport",
            SpaceArchetype.COMMUNITY: "Initiatives",
        }
        self.client.force_authenticate(self.owner)
        for archetype, label in expected.items():
            self.space.archetype = archetype
            self.space.save(update_fields=["archetype", "updated_at"])
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["primary_business_label"], label)

    def test_generic_presentation_exposes_human_grammar_without_inventing_work(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["primary_business_label"], "Activités")
        self.assertEqual(
            response.data["presentation"]["empty_message"],
            "Aucune activité visible pour le moment.",
        )
        self.assertEqual(
            response.data["sections"]["activities"]["representation"],
            "Toutes les activités",
        )
        self.assertEqual(response.data["sections"]["activities"]["role"], "structure")

    def test_activity_occurrence_projection_preserves_owner_identity(self):
        activity = self._activity("Atelier")
        now = timezone.now()
        occurrence = Occurrence.objects.create(
            activity=activity,
            label="Atelier demain",
            start_at=now + timedelta(days=1),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        items = response.data["sections"]["upcoming"]["items"]
        row = next(item for item in items if item["source"]["id"] == str(occurrence.pk))
        self.assertEqual(row["source"], {"kind": "occurrence", "id": str(occurrence.pk)})
        self.assertEqual(row["links"]["detail"], f"/api/v1/occurrences/{occurrence.pk}/")
        self.assertEqual(row["links"]["activity"], f"/api/v1/activities/{activity.pk}/")

    def test_scanner_mandate_does_not_reveal_activity_work_or_selection(self):
        sensitive = self._activity("Brouillon privé de l'organisateur")
        scanner = User.objects.create_user(
            username="zs3-scanner-mandate",
            email="zs3-scanner-mandate@test.local",
            password="x",
        )
        grant_activity_role(
            profile=scanner,
            activity=sensitive,
            role_code=SystemRoleCode.ACTIVITY_SCANNER,
            granted_by=self.owner,
        )
        self.client.force_authenticate(scanner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["authority"]["scope"], "activity_limited")
        self.assertEqual(response.data["coverage_state"], "partial")
        self.assertNotIn(sensitive.title, str(response.data))
        self.assertFalse(any(section["items"] for section in response.data["sections"].values()))
        selected = self.client.get(
            self.url, {"kind": "activity", "id": str(sensitive.pk)}
        )
        self.assertEqual(selected.status_code, 200, selected.data)
        self.assertIsNone(selected.data["selection"])
        self.assertNotIn(sensitive.title, str(selected.data))

    def test_order_detail_uses_existing_owner_api_and_current_permissions(self):
        activity = self._activity("Commande dans l'Espace")
        buyer = User.objects.create_user(
            username="zs3-order-buyer",
            email="private-order-buyer@test.local",
            password="x",
        )
        journey = Journey.objects.create(
            initiated_by=buyer,
            beneficiary=buyer,
            activity=activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        order = CommerceOrder.objects.create(
            journey=journey,
            buyer=buyer,
            payee_space=self.space,
            status=CommerceOrderStatus.CONFIRMED,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.get(
            self.url, {"kind": "commerce_order", "id": str(order.pk)}
        )
        self.assertEqual(response.status_code, 200, response.data)
        row = response.data["selection"]
        self.assertIsNotNone(row)
        self.assertEqual(
            row["links"]["detail"],
            f"/api/v1/organizations/workspaces/{self.space.slug}/commerce/orders/{order.pk}/",
        )
        detail = self.client.get(row["links"]["detail"])
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data["reference"], order.reference)
        self.assertNotIn(buyer.email, str(detail.data))
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(row["links"]["detail"]).status_code, 404)
        self.assertEqual(
            self.client.get(self.url, {"kind": "commerce_order", "id": str(order.pk)}).status_code,
            404,
        )

    def test_activity_only_authority_is_bounded_and_responsibility_cannot_expand_it(self):
        allowed = self._activity("Activity autorisée")
        hidden = self._activity("Activity cachée")
        actor = User.objects.create_user(
            username="zs3-activity", email="zs3-activity@test.local", password="x"
        )
        mandate = grant_activity_role(
            profile=actor,
            activity=allowed,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        other_mandate = grant_activity_role(
            profile=self.outsider,
            activity=hidden,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_authenticate(actor)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["authority"]["scope"], "activity_limited")
        serialized = str(response.data)
        self.assertIn(str(allowed.pk), serialized)
        self.assertNotIn(str(hidden.pk), serialized)
        self.assertEqual(response.data["operational_footprint"]["signals"], [])

        scoped = self.client.get(self.url, {"responsibility": f"mandate:{mandate.pk}"})
        self.assertEqual(scoped.status_code, 200, scoped.data)
        self.assertIn(str(allowed.pk), str(scoped.data))
        self.assertNotIn(str(hidden.pk), str(scoped.data))

        foreign = self.client.get(
            self.url, {"responsibility": f"mandate:{other_mandate.pk}"}
        )
        self.assertEqual(foreign.status_code, 404)

    def test_creative_presentation_contextualizes_activity_without_creating_cms_truth(self):
        self.space.archetype = SpaceArchetype.CREATIVE
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self._activity("Album Première")
        self.client.force_authenticate(self.owner)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["sections"]["active"]["representation"], "En création")
        self.assertEqual(response.data["sections"]["upcoming"]["representation"], "À présenter")
        self.assertEqual(response.data["sections"]["activities"]["representation"], "Créations")
        row = next(
            item for item in response.data["sections"]["preparation"]["items"]
            if item["source"] == {"kind": "activity", "id": str(activity.pk)}
        )
        self.assertEqual(row["kind"], "activity")
        self.assertNotIn("publication", str(row).lower())
        self.assertNotIn("portfolio", str(response.data).lower())

    def test_media_presentation_uses_activity_owner_without_inventing_feed_or_media(self):
        self.space.archetype = SpaceArchetype.MEDIA
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self._activity("Journal du quartier")
        self.client.force_authenticate(self.owner)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["sections"]["active"]["representation"], "En production")
        self.assertEqual(response.data["sections"]["activities"]["representation"], "Productions")
        row = next(
            item for item in response.data["sections"]["preparation"]["items"]
            if item["source"] == {"kind": "activity", "id": str(activity.pk)}
        )
        self.assertNotIn("feed", str(response.data).lower())
        self.assertNotIn("media", str(row).lower())

    def test_commerce_offer_requires_activity_commerce_authority(self):
        self.space.archetype = SpaceArchetype.COMMERCE
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self._activity("Catalogue")
        Offer.objects.create(
            activity=activity,
            name="Offre ZS3",
            status=OfferStatus.ACTIVE,
        )
        commerce_actor = User.objects.create_user(
            username="zs3-commerce", email="zs3-commerce@test.local", password="x"
        )
        grant_activity_role(
            profile=commerce_actor,
            activity=activity,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_authenticate(commerce_actor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        offers = [
            item for item in response.data["sections"]["offers"]["items"]
            if item["source"]["kind"] == "offer"
        ]
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["title"], "Offre ZS3")
        self.assertEqual(offers[0]["context"]["pricing"]["unit_price"], "0.00")
        self.assertEqual(offers[0]["context"]["pricing"]["currency"], "USD")
        self.assertEqual(response.data["sections"]["preparation"]["representation"], "À traiter")
        self.assertEqual(response.data["sections"]["active"]["representation"], "Commandes actives")
        self.assertEqual(response.data["sections"]["offers"]["representation"], "Offres")
        self.assertEqual(response.data["sections"]["completed"]["representation"], "Historique")
        self.assertNotIn("payment", str(offers[0]).lower())

    def test_programmes_presentation_routes_pending_registrations_to_human_queue(self):
        self.space.archetype = SpaceArchetype.EDUCATION
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self._activity("Programme Comptabilité")
        beneficiary = User.objects.create_user(
            username="zs3-programme-pending",
            email="private-programme@test.local",
            password="x",
        )
        journey = Journey.objects.create(
            initiated_by=beneficiary,
            beneficiary=beneficiary,
            activity=activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.PENDING_APPROVAL,
        )
        self.client.force_authenticate(self.owner)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["sections"]["requests"]["representation"], "Inscriptions à traiter")
        self.assertEqual(response.data["sections"]["upcoming"]["representation"], "Prochaines sessions")
        row = next(
            item for item in response.data["sections"]["requests"]["items"]
            if item["source"] == {"kind": "journey", "id": str(journey.pk)}
        )
        self.assertNotIn(beneficiary.email, str(row))

    def test_mixed_space_requests_are_not_hidden_by_archetype(self):
        # The archetype only controls labels and order, not owner-domain access.
        activity = self._activity("Programme et service mixte")
        beneficiary = User.objects.create_user(
            username="zs3-mixed-beneficiary",
            email="mixed-private@test.local",
            password="x",
        )
        registration = Journey.objects.create(
            initiated_by=beneficiary,
            beneficiary=beneficiary,
            activity=activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.PENDING_APPROVAL,
        )
        ServiceDetails.objects.create(
            activity=activity, service_kind=ServiceKind.ADMINISTRATIVE_SUPPORT
        )
        grant_activity_role(
            profile=self.owner, activity=activity,
            role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
            granted_by=self.owner,
        )
        service_case = Journey.objects.create(
            initiated_by=beneficiary,
            beneficiary=beneficiary,
            activity=activity,
            workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.SUBMITTED,
        )
        self.client.force_authenticate(self.owner)
        for archetype in (SpaceArchetype.GENERIC, SpaceArchetype.COMMUNITY):
            self.space.archetype = archetype
            self.space.save(update_fields=["archetype", "updated_at"])
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200, response.data)
            requests = response.data["sections"]["requests"]["items"]
            identities = {item["source"]["id"] for item in requests}
            self.assertIn(str(registration.pk), identities)
            self.assertIn(str(service_case.pk), identities)
            self.assertNotIn(beneficiary.email, str(response.data))

    def test_education_journey_is_visible_without_beneficiary_leak(self):
        self.space.archetype = SpaceArchetype.EDUCATION
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self._activity("Programme Comptabilité")
        beneficiary = User.objects.create_user(
            username="zs3-student", email="private-student@test.local", password="x"
        )
        journey = Journey.objects.create(
            initiated_by=beneficiary,
            beneficiary=beneficiary,
            activity=activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.IN_PROGRESS,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        row = next(
            item for item in response.data["sections"]["active"]["items"]
            if item["source"] == {"kind": "journey", "id": str(journey.pk)}
        )
        self.assertEqual(row["continuity_facet"]["identity"], f"journey:{journey.pk}")
        self.assertNotIn(beneficiary.email, str(row))
        self.assertNotIn(beneficiary.username, str(row))

    def test_service_presentation_separates_requests_from_active_cases(self):
        self.space.archetype = SpaceArchetype.SERVICE_PROVIDER
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self._activity("Prestation Visa")
        ServiceDetails.objects.create(
            activity=activity,
            service_kind=ServiceKind.ADMINISTRATIVE_SUPPORT,
        )
        beneficiary = User.objects.create_user(
            username="zs3-service-pending",
            email="private-service-pending@test.local",
            password="x",
        )
        pending = Journey.objects.create(
            initiated_by=beneficiary,
            beneficiary=beneficiary,
            activity=activity,
            workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.SUBMITTED,
        )
        operator = User.objects.create_user(
            username="zs3-service-pending-operator",
            email="zs3-service-pending-operator@test.local",
            password="x",
        )
        grant_activity_role(
            profile=operator,
            activity=activity,
            role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_authenticate(operator)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["sections"]["requests"]["representation"], "Demandes à traiter")
        self.assertEqual(response.data["sections"]["active"]["representation"], "Dossiers en cours")
        row = next(
            item for item in response.data["sections"]["requests"]["items"]
            if item["source"] == {"kind": "journey", "id": str(pending.pk)}
        )
        self.assertNotIn(beneficiary.email, str(row))
        self.assertNotIn("requirement", str(row).lower())

    def test_service_case_uses_service_visibility_and_omits_private_case_data(self):
        self.space.archetype = SpaceArchetype.SERVICE_PROVIDER
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self._activity("Prestation Visa")
        ServiceDetails.objects.create(activity=activity, service_kind=ServiceKind.ADMINISTRATIVE_SUPPORT)
        beneficiary = User.objects.create_user(
            username="zs3-client", email="private-client@test.local", password="x"
        )
        journey = Journey.objects.create(
            initiated_by=beneficiary,
            beneficiary=beneficiary,
            activity=activity,
            workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.IN_PROGRESS,
        )
        operator = User.objects.create_user(
            username="zs3-service", email="zs3-service@test.local", password="x"
        )
        grant_activity_role(
            profile=operator,
            activity=activity,
            role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_authenticate(operator)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        row = next(
            item for item in response.data["sections"]["active"]["items"]
            if item["source"] == {"kind": "journey", "id": str(journey.pk)}
        )
        self.assertEqual(row["kind"], "service_case")
        self.assertNotIn(beneficiary.email, str(row))
        self.assertNotIn("requirement", str(row).lower())

    def test_service_case_link_requires_operator_scope_and_owner_context(self):
        activity = self._activity("Prestation avec contexte")
        ServiceDetails.objects.create(
            activity=activity, service_kind=ServiceKind.ADMINISTRATIVE_SUPPORT
        )
        beneficiary = User.objects.create_user(
            username="zs3-operator-beneficiary",
            email="zs3-operator-beneficiary@test.local",
            password="x",
        )
        journey = Journey.objects.create(
            initiated_by=beneficiary, beneficiary=beneficiary,
            activity=activity, workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.IN_PROGRESS,
        )
        operator = User.objects.create_user(
            username="zs3-operator-case",
            email="zs3-operator-case@test.local",
            password="x",
        )
        grant_activity_role(
            profile=operator, activity=activity,
            role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_authenticate(operator)
        without_context = self.client.get(self.url)
        row = next(
            item for item in without_context.data["sections"]["active"]["items"]
            if item["source"]["id"] == str(journey.pk)
        )
        self.assertNotIn("detail", row["links"])
        self.assertEqual(row["continuity_facet"]["next"], [])

        ServiceJourneyContext.objects.create(journey=journey)
        with_context = self.client.get(self.url)
        row = next(
            item for item in with_context.data["sections"]["active"]["items"]
            if item["source"]["id"] == str(journey.pk)
        )
        self.assertEqual(
            row["links"]["detail"],
            f"/api/v1/services/operator/journeys/{journey.pk}/",
        )
        self.assertIn("open_service_case", row["capabilities"])
        self.assertNotIn(beneficiary.email, str(row))
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_transport_presentation_contextualizes_without_reclassifying_structure(self):
        self.space.archetype = SpaceArchetype.TRANSPORT_OPERATOR
        self.space.save(update_fields=["archetype", "updated_at"])
        self._activity("Service Lubumbashi Kolwezi")
        TransportRoute.objects.create(space=self.space, name="Lubumbashi → Kolwezi")
        Vehicle.objects.create(space=self.space, label="Bus 18", passenger_capacity=50)
        self.client.force_authenticate(self.owner)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["sections"]["upcoming"]["representation"], "Prochains départs")
        self.assertEqual(response.data["sections"]["active"]["representation"], "Départs en cours")
        self.assertEqual(response.data["sections"]["activities"]["representation"], "Services")
        self.assertEqual(response.data["sections"]["routes"]["role"], "structure")
        self.assertEqual(response.data["sections"]["vehicles"]["role"], "structure")

    def test_transport_space_projection_uses_real_route_and_vehicle_owners(self):
        self.space.archetype = SpaceArchetype.TRANSPORT_OPERATOR
        self.space.save(update_fields=["archetype", "updated_at"])
        route = TransportRoute.objects.create(
            space=self.space,
            name="Lubumbashi → Kolwezi",
        )
        vehicle = Vehicle.objects.create(
            space=self.space,
            label="Bus 12",
            passenger_capacity=54,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["sections"]["routes"]["role"], "structure")
        self.assertEqual(response.data["sections"]["vehicles"]["role"], "structure")
        sources = {
            (item["source"]["kind"], item["source"]["id"])
            for key in ("routes", "vehicles")
            for item in response.data["sections"][key]["items"]
        }
        self.assertIn(("transport_route", str(route.pk)), sources)
        self.assertIn(("vehicle", str(vehicle.pk)), sources)
        self.assertNotIn(("transport_route", str(route.pk)), {
            (item["source"]["kind"], item["source"]["id"])
            for item in response.data["sections"]["active"]["items"]
        })
        self.assertNotIn("scanner", str(response.data["capabilities"]).lower())
