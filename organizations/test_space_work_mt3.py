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
from journeys.models import (
    Journey, JourneyRequest, JourneyStatus, RequestPurpose, WorkflowKind,
)
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

    def test_native_g1_activity_selection_returns_bounded_owner_relations(self):
        activity = self.activity("Activité à plusieurs dates")
        occurrences = [
            self.occurrence(activity, label=f"Date {i:02}", days=i + 1)
            for i in range(16)
        ]
        url = "/api/v1/organizations/workspaces/mt3-actions/work/"
        first = self.client.get(url, {
            "kind": "activity", "id": str(activity.pk),
        })
        self.assertEqual(first.status_code, 200)
        selected = first.json()["selection"]
        related = selected["related_occurrences"]
        self.assertEqual(related["limit"], 12)
        self.assertEqual(related["offset"], 0)
        self.assertEqual(len(related["items"]), 12)
        self.assertTrue(related["has_more"])
        self.assertEqual(
            [row["source"]["id"] for row in related["items"]],
            [str(o.pk) for o in occurrences[:12]],
        )
        self.assertTrue(all(row["openable"] for row in related["items"]))
        second = self.client.get(url, {
            "kind": "activity", "id": str(activity.pk),
            "related_offset": "12",
        })
        self.assertEqual(second.status_code, 200)
        page = second.json()["selection"]["related_occurrences"]
        self.assertEqual(len(page["items"]), 4)
        self.assertFalse(page["has_more"])
        self.assertEqual(page["offset"], 12)
        self.assertNotIn("related_occurrences", self.client.get(url).json())

    def test_native_g1_owner_related_page_cannot_cross_actor_or_scope(self):
        allowed = self.activity("Action autorisée")
        foreign = self.activity("Action privée")
        self.occurrence(allowed, label="Réalisation autorisée")
        self.occurrence(foreign, label="Réalisation interdite")
        actor = User.objects.create_user(username="mt3-native-mandate", password="x")
        mandate = grant_activity_role(
            profile=actor, activity=allowed,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        url = "/api/v1/organizations/workspaces/mt3-actions/work/"
        self.client.force_login(actor)
        params = {"kind": "activity", "id": str(allowed.pk),
                  "responsibility": f"mandate:{mandate.pk}"}
        yes = self.client.get(url, params)
        self.assertEqual(yes.status_code, 200)
        self.assertIn("Réalisation autorisée", str(yes.json()))
        self.assertNotIn("Réalisation interdite", str(yes.json()))
        no = self.client.get(url, {**params, "id": str(foreign.pk)})
        self.assertEqual(no.status_code, 200)
        self.assertIsNone(no.json()["selection"])
        for invalid in ("-1", "not-a-number", "10001"):
            self.assertEqual(
                self.client.get(url, {**params, "related_offset": invalid}).status_code,
                400,
            )
        self.assertEqual(
            self.client.get(url, {"related_offset": "12"}).status_code,
            400,
        )
        revoke_mandate(mandate=mandate, actor=self.owner)
        self.assertEqual(self.client.get(url, params).status_code, 404)

    def test_elapsed_scheduled_occurrence_is_relation_not_dead_n2_link(self):
        activity = self.activity("Action ancienne")
        elapsed = Occurrence.objects.create(
            activity=activity, label="Séance non clôturée",
            start_at=timezone.now() - timedelta(days=3),
            end_at=timezone.now() - timedelta(days=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        response = self.client.get(self.depth_url("activity", activity.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Séance non clôturée")
        self.assertContains(response, "Date passée · état à actualiser")
        self.assertFalse(response.context["work_depth"]["related"][0]["openable"])
        owner = self.client.get("/api/v1/organizations/workspaces/mt3-actions/work/", {
            "kind": "activity", "id": str(activity.pk),
        })
        item = owner.json()["selection"]["related_occurrences"]["items"][0]
        self.assertEqual(item["source"]["id"], str(elapsed.pk))
        self.assertFalse(item["openable"])

    def test_real_registration_request_has_exact_web_owner_handoff(self):
        activity = self.activity("Atelier citoyen")
        beneficiary = User.objects.create_user(
            username="mt3-requester", email="mt3-private@example.test", password="x",
        )
        journey = Journey.objects.create(
            initiated_by=beneficiary, beneficiary=beneficiary,
            activity=activity, workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.PENDING_APPROVAL,
        )
        before = self.client.get(self.depth_url("journey", journey.pk))
        self.assertEqual(before.status_code, 200)
        self.assertNotContains(before, "Examiner la demande")
        request = JourneyRequest.objects.create(
            journey=journey, requester=beneficiary,
            purpose=RequestPurpose.REGISTRATION,
        )
        after = self.client.get(self.depth_url("journey", journey.pk))
        self.assertEqual(after.status_code, 200)
        self.assertContains(after, "Examiner la demande")
        action = next(
            a for a in after.context["work_depth"]["actions"]
            if a["label"] == "Examiner la demande"
        )
        self.assertIn(f"request={request.pk}", action["url"])
        queue = self.client.get(action["url"])
        self.assertEqual(queue.status_code, 200)
        self.assertEqual([row.pk for row in queue.context["page_obj"]], [request.pk])
        self.client.force_login(self.outsider)
        self.assertNotEqual(self.client.get(action["url"]).status_code, 200)

    def test_g1_creation_reuses_activity_owner_and_returns_to_space(self):
        root_url = reverse(
            "organizations:space-work", kwargs={"slug": self.space.slug},
        )
        root = self.client.get(root_url)
        self.assertEqual(root.status_code, 200)
        self.assertContains(root, "Nouvelle initiative")
        create_link = root.context["work_create_url"]
        self.assertIn("space=mt3-actions", create_link)
        form = self.client.get(create_link)
        self.assertEqual(form.status_code, 200)
        self.assertContains(form, "Nouvelle initiative")
        self.assertEqual(form.context["form"].initial["organization"], self.space.pk)
        created = self.client.post(create_link, {
            "organization": str(self.space.pk),
            "title": "Nouvelle initiative réelle",
            "short_description": "Action collective",
            "description": "Une initiative réelle.",
            "visibility": "private",
        })
        self.assertEqual(created.status_code, 302)
        self.assertEqual(created.url, root_url)
        activity = Activity.objects.get(title="Nouvelle initiative réelle")
        self.assertEqual(activity.space_id, self.space.pk)
        self.assertIsNone(activity.owner_profile_id)
        self.assertEqual(activity.status, "draft")

    def test_g1_context_does_not_transfer_create_authority(self):
        activity = self.activity("Initiative portée")
        actor = User.objects.create_user(username="mt3-no-space-create", password="x")
        mandate = grant_activity_role(
            profile=actor, activity=activity,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_login(actor)
        response = self.client.get(
            reverse("organizations:space-work", kwargs={"slug": self.space.slug}),
            {"responsibility": f"mandate:{mandate.pk}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["work_create_url"])
        self.assertNotContains(response, "Nouvelle initiative")
        owner_form = self.client.get(
            reverse("activities:create") + "?space=mt3-actions",
        )
        self.assertEqual(owner_form.status_code, 200)
        self.assertNotContains(owner_form, "Métier · Actions du quartier")
        forged = self.client.post(reverse("activities:create"), {
            "organization": str(self.space.pk),
            "title": "Initiative sans autorité",
            "visibility": "private",
        })
        self.assertEqual(forged.status_code, 403)
        self.assertFalse(
            Activity.objects.filter(title="Initiative sans autorité").exists(),
        )
