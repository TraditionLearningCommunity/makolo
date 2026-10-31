"""MT3 — Generic/Community N2 navigation and real owner-backed N3 handoffs."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from activities.models import Activity, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role, revoke_mandate
from groups.models import Group, GroupMembership
from funding.models import FundingDetails
from funding.services import can_manage_funding
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization, SpaceArchetype
from services.models import ServiceDetails, ServiceJourneyContext, ServiceKind


class SpaceWorkG1DepthTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="mt3-owner", password="x")
        self.outsider = User.objects.create_user(username="mt3-outsider", password="x")
        self.space = Organization.objects.create(
            name="Actions du quartier", slug="mt3-actions",
            created_by=self.owner, archetype=SpaceArchetype.COMMUNITY,
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        self.client.force_login(self.owner)

    def activity(self, title="Nettoyage du quartier", status="published"):
        return Activity.objects.create(
            title=title, status=status,
            created_by=self.owner, space=self.space,
        )

    def occurrence(self, activity, label="Action terrain", days=4):
        return Occurrence.objects.create(
            activity=activity, label=label,
            start_at=timezone.now() + timedelta(days=days),
            status=OccurrenceStatus.SCHEDULED,
        )

    def depth_url(self, kind, pk, **params):
        from urllib.parse import urlencode
        url = reverse(
            "organizations:space-work-depth",
            kwargs={"slug": self.space.slug, "kind": kind, "owner_id": pk},
        )
        return url + (f"?{urlencode(params)}" if params else "")

    def test_initiative_root_opens_real_n2_and_its_occurrence(self):
        initiative = self.activity()
        action = self.occurrence(initiative)
        root = self.client.get(reverse(
            "organizations:space-work", kwargs={"slug": self.space.slug},
        ))
        self.assertEqual(root.status_code, 200)
        chapters = {section["key"]: section for section in root.context["work_sections"]}
        item = next(
            row for row in chapters["activities"]["items"]
            if row["source"]["id"] == str(initiative.pk)
        )
        self.assertIn("/work/activity/", item["owner_url"])
        self.assertIn("from=activities", item["owner_url"])
        response = self.client.get(item["owner_url"])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Les actions de cette initiative")
        self.assertContains(response, "Nettoyage du quartier")
        self.assertContains(response, "Action terrain")
        self.assertNotContains(response, "Aucune action datée")
        self.assertEqual(
            response.context["work_depth"]["identity"],
            f"activity:{initiative.pk}",
        )
        action_link = response.context["work_depth"]["related"][0]["url"]
        selected = self.client.get(action_link)
        self.assertEqual(selected.status_code, 200)
        self.assertContains(selected, "Action terrain")
        self.assertContains(selected, "Retour à l’initiative")
        self.assertEqual(
            selected.context["work_depth"]["back_url"],
            item["owner_url"],
        )
        self.assertEqual(
            selected.context["work_depth"]["parent_url"],
            item["owner_url"],
        )

    def test_generic_uses_common_shell_but_activity_language(self):
        self.space.archetype = SpaceArchetype.GENERIC
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self.activity("Atelier pratique")
        response = self.client.get(self.depth_url("activity", activity.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Les réalisations de cette activité")
        self.assertContains(response, "Atelier pratique")
        self.assertNotContains(response, "Les actions de cette initiative")
        self.assertContains(response, "Gérer l’activité")
        self.assertContains(response, "Gérer les ressources")
        self.assertIn("/preparation/manage/activity/", str(response.content))

    def test_durable_initiative_has_honest_calm_state_and_no_fictional_event(self):
        initiative = self.activity("Programme de mentorat")
        group = Group.objects.create(
            name="Bénévoles du quartier", space=self.space, created_by=self.owner,
        )
        response = self.client.get(self.depth_url("activity", initiative.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aucune action datée pour le moment.")
        self.assertNotContains(response, "Bénévoles du quartier")
        self.assertEqual(response.context["work_depth"]["related"], [])
        self.assertNotIn("funding", str(response.context["work_depth"]))
        self.assertTrue(group.pk)

    def test_funding_n3_only_for_existing_authorized_initiative(self):
        initiative = self.activity("Soutien au quartier")
        before = self.client.get(self.depth_url("activity", initiative.pk))
        self.assertEqual(before.status_code, 200)
        self.assertNotContains(before, "Gérer le financement")
        funding = FundingDetails.objects.create(activity=initiative)
        allowed = can_manage_funding(self.owner, funding)
        after = self.client.get(self.depth_url("activity", initiative.pk))
        self.assertEqual(after.status_code, 200)
        if allowed:
            self.assertContains(after, "Gérer le financement")
            self.assertContains(after, reverse("funding:manage", kwargs={"pk": funding.pk}))
        else:
            self.assertNotContains(after, "Gérer le financement")

    def test_occurrence_n2_shows_parent_and_only_phase_authorized_day_of(self):
        initiative = self.activity()
        later = self.occurrence(initiative, days=6)
        response = self.client.get(self.depth_url(
            "occurrence", later.pk, **{"from": "upcoming"},
        ))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Action terrain")
        self.assertContains(response, "Nettoyage du quartier")
        self.assertEqual(response.context["work_depth"]["actions"], [])
        self.assertIn("#work-upcoming", response.context["work_depth"]["back_url"])
        self.assertTrue(response.context["work_depth"]["parent_url"])

        arriving = Occurrence.objects.create(
            activity=initiative, label="Action immédiate",
            start_at=timezone.now() + timedelta(minutes=10),
            end_at=timezone.now() + timedelta(hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        enabled = self.client.get(self.depth_url("occurrence", arriving.pk))
        self.assertEqual(enabled.status_code, 200)
        actions = enabled.context["work_depth"]["actions"]
        self.assertTrue(any(a["label"] == "Ouvrir Jour J" for a in actions))

    def test_occurrences_are_paginated_and_each_link_rechecks_owner(self):
        initiative = self.activity()
        for index in range(15):
            self.occurrence(
                initiative, label=f"Action {index:02}", days=index + 1,
            )
        first = self.client.get(self.depth_url("activity", initiative.pk))
        self.assertEqual(len(first.context["work_depth"]["related"]), 12)
        next_page = first.context["work_depth"]["next_page_url"]
        self.assertIsNotNone(next_page)
        self.assertIn("page=2", next_page)
        second = self.client.get(next_page)
        self.assertEqual(len(second.context["work_depth"]["related"]), 3)
        self.assertIsNone(second.context["work_depth"]["next_page_url"])
        self.assertIsNotNone(second.context["work_depth"]["previous_page_url"])

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(next_page).status_code, 404)
        self.assertEqual(
            self.client.get(first.context["work_depth"]["related"][0]["url"]).status_code,
            404,
        )

    def test_activity_limited_mandate_denies_foreign_and_revoked_depths(self):
        allowed = self.activity("Initiative accessible")
        foreign = self.activity("Initiative protégée")
        actor = User.objects.create_user(username="mt3-scoped", password="x")
        mandate = grant_activity_role(
            profile=actor, activity=allowed,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_login(actor)
        context = {"responsibility": f"mandate:{mandate.pk}"}
        available = self.client.get(
            self.depth_url("activity", allowed.pk, **context),
        )
        self.assertEqual(available.status_code, 200)
        self.assertContains(available, "Initiative accessible")
        self.assertNotContains(available, "Initiative protégée")
        self.assertEqual(
            self.client.get(self.depth_url("activity", foreign.pk, **context)).status_code,
            404,
        )
        self.assertEqual(self.client.get(
            self.depth_url("activity", allowed.pk, responsibility="mandate:bad")
        ).status_code, 404)
        revoke_mandate(mandate=mandate, actor=self.owner)
        self.assertEqual(
            self.client.get(self.depth_url("activity", allowed.pk, **context)).status_code,
            404,
        )

    def test_community_membership_does_not_grant_n2_authority(self):
        initiative = self.activity()
        group = Group.objects.create(
            name="Collectif", space=self.space, created_by=self.owner,
        )
        GroupMembership.objects.create(group=group, profile=self.outsider)
        self.client.force_login(self.outsider)
        self.assertEqual(
            self.client.get(self.depth_url("activity", initiative.pk)).status_code,
            404,
        )

    def test_cross_space_and_other_archetypes_do_not_gain_g1_depth(self):
        activity = self.activity()
        foreign = Organization.objects.create(
            name="Autre Space", slug="mt3-foreign", created_by=self.owner,
        )
        extra = Activity.objects.create(
            title="Autre", space=foreign, created_by=self.owner,
        )
        self.assertEqual(
            self.client.get(self.depth_url("activity", extra.pk)).status_code,
            404,
        )
        for archetype in (SpaceArchetype.EDUCATION, SpaceArchetype.MEDIA):
            self.space.archetype = archetype
            self.space.save(update_fields=["archetype", "updated_at"])
            self.assertEqual(
                self.client.get(self.depth_url("activity", activity.pk)).status_code,
                404,
            )

    def test_mixed_service_journey_uses_real_operator_owner_handoff(self):
        self.space.archetype = SpaceArchetype.GENERIC
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self.activity("Aide administrative")
        ServiceDetails.objects.create(
            activity=activity, service_kind=ServiceKind.ADMINISTRATIVE_SUPPORT,
        )
        beneficiary = User.objects.create_user(
            username="mt3-service-beneficiary", password="x",
        )
        case = Journey.objects.create(
            initiated_by=beneficiary, beneficiary=beneficiary,
            activity=activity, workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.IN_PROGRESS,
        )
        operator = User.objects.create_user(username="mt3-operator", password="x")
        grant_activity_role(
            profile=operator, activity=activity,
            role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_login(operator)
        before = self.client.get(self.depth_url("journey", case.pk))
        self.assertEqual(before.status_code, 200)
        self.assertNotContains(before, "Ouvrir le dossier de prestation")
        ServiceJourneyContext.objects.create(journey=case)
        after = self.client.get(self.depth_url("journey", case.pk))
        self.assertEqual(after.status_code, 200)
        self.assertContains(after, "Ouvrir le dossier de prestation")
        self.assertContains(after, reverse("services:operator-case", kwargs={"pk": case.pk}))

    def test_journey_n2_is_contextual_without_private_beneficiary(self):
        activity = self.activity("Action citoyenne")
        beneficiary = User.objects.create_user(
            username="mt3-beneficiary", email="confidential-mt3@example.test",
            password="x",
        )
        journey = Journey.objects.create(
            initiated_by=beneficiary, beneficiary=beneficiary,
            activity=activity, workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.PENDING_APPROVAL,
        )
        result = self.client.get(self.depth_url("journey", journey.pk))
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, "Cette démarche")
        self.assertContains(result, "Action citoyenne")
        self.assertNotContains(result, beneficiary.email)
        self.assertTrue(result.context["work_depth"]["parent_url"])
