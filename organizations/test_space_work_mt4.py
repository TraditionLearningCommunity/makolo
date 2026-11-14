"""MT4 targeted Education/Services N1 N2 N3 and canonical creation gates."""
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError as DjangoValidationError

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from activities.models import Activity, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import (
    grant_activity_role, grant_space_role, revoke_mandate,
)
from journeys.collaboration_models import (
    JourneyBlocker, JourneyBlockerStatus, JourneyStep, JourneyStepStatus,
)
from journeys.models import (
    Journey, JourneyRequest, JourneyStatus, RequestPurpose, WorkflowKind,
)
from organizations.models import Organization, SpaceArchetype
from services.models import ServiceDetails, ServiceJourneyContext, ServiceKind
from subscriptions.runtime_models import Subscription


class MT4SpaceEducationServicesTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="mt4-owner", password="x",
        )
        self.outsider = User.objects.create_user(
            username="mt4-outsider", password="x",
        )
        self.learner = User.objects.create_user(
            username="mt4-learner", email="mt4-private@example.test", password="x",
        )
        self.space = Organization.objects.create(
            name="MT4 Espace", slug="mt4-space", created_by=self.owner,
            archetype=SpaceArchetype.EDUCATION,
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        self.client.force_login(self.owner)
        self.work_url = reverse(
            "organizations_api:workspace-work", kwargs={"slug": self.space.slug},
        )
        self.create_url = reverse(
            "organizations_api:workspace-work-g2-create",
            kwargs={"slug": self.space.slug},
        )

    def activity(self, title="Programme de proximité"):
        return Activity.objects.create(
            title=title, space=self.space, created_by=self.owner,
            status="published",
        )

    def journey(self, activity, kind=WorkflowKind.REGISTRATION,
                state=JourneyStatus.PENDING_APPROVAL):
        return Journey.objects.create(
            activity=activity, initiated_by=self.learner,
            beneficiary=self.learner, workflow=kind, status=state,
        )

    def depth_url(self, kind, pk, **params):
        from urllib.parse import urlencode
        url = reverse(
            "organizations:space-work-depth-g2",
            kwargs={"slug": self.space.slug, "kind": kind, "owner_id": pk},
        )
        return url + (f"?{urlencode(params)}" if params else "")

    def case_url(self, journey):
        return reverse(
            "organizations_api:workspace-service-case",
            kwargs={"slug": self.space.slug, "journey_id": journey.pk},
        )

    def test_education_n1_to_n2_programme_session_and_real_request(self):
        activity = self.activity()
        occurrence = Occurrence.objects.create(
            activity=activity, label="Session sur le terrain",
            start_at=timezone.now() + timedelta(days=3),
            status=OccurrenceStatus.SCHEDULED,
        )
        registration = self.journey(activity)
        request = JourneyRequest.objects.create(
            journey=registration, requester=self.learner,
            purpose=RequestPurpose.REGISTRATION,
        )
        n1 = self.client.get(
            reverse("organizations:space-work", kwargs={"slug": self.space.slug})
        )
        self.assertEqual(n1.status_code, 200)
        programme = next(
            row for section in n1.context["work_sections"]
            for row in section["items"]
            if row["source"] == {"kind": "activity", "id": str(activity.pk)}
        )
        self.assertIn("/work/g2/activity/", programme["owner_url"])
        n2 = self.client.get(programme["owner_url"])
        self.assertEqual(n2.status_code, 200)
        self.assertContains(n2, "Sessions de ce programme")
        self.assertContains(n2, "Gérer les ressources")
        self.assertContains(n2, "Gérer les formulaires")
        self.assertContains(n2, "Session sur le terrain")
        self.assertContains(n2, "Inscriptions")
        self.assertNotContains(n2, self.learner.email)
        self.assertEqual(len(n2.context["work_g2"]["linked_work"]), 1)
        entry = n2.context["work_g2"]["linked_work"][0]
        self.assertEqual(
            entry["request_owner"],
            {"kind": "journey_request", "id": str(request.pk)},
        )
        detail = self.client.get(entry["url"])
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Examiner l'inscription")
        self.assertNotContains(detail, self.learner.email)
        session_url = n2.context["work_g2"]["related"][0]["url"]
        self.assertEqual(self.client.get(session_url).status_code, 200)
        self.assertEqual(
            self.client.get(self.work_url, {
                "kind": "occurrence", "id": str(occurrence.pk),
            }).json()["selection"]["source"]["id"],
            str(occurrence.pk),
        )

    def test_no_request_is_not_an_approval_button(self):
        activity = self.activity()
        registration = self.journey(activity)
        response = self.client.get(self.depth_url("journey", registration.pk))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Examiner l'inscription")
        owner = self.client.get(self.work_url, {
            "kind": "activity", "id": str(activity.pk),
        }).json()["selection"]
        self.assertEqual(owner["related_work"]["items"][0]["request_owner"], None)

    def test_education_related_paginations_remain_bounded_and_private(self):
        activity = self.activity()
        for n in range(15):
            Occurrence.objects.create(
                activity=activity, label=f"Session {n:02}",
                start_at=timezone.now() + timedelta(days=n + 1),
                status=OccurrenceStatus.SCHEDULED,
            )
            self.journey(activity, state=JourneyStatus.IN_PROGRESS)
        selected = self.client.get(self.work_url, {
            "kind": "activity", "id": str(activity.pk),
        }).json()["selection"]
        self.assertEqual(len(selected["related_occurrences"]["items"]), 12)
        self.assertEqual(len(selected["related_work"]["items"]), 12)
        self.assertTrue(selected["related_occurrences"]["has_more"])
        self.assertTrue(selected["related_work"]["has_more"])
        page = self.client.get(self.work_url, {
            "kind": "activity", "id": str(activity.pk),
            "related_offset": 12, "related_work_offset": 12,
        })
        self.assertEqual(page.status_code, 200)
        self.assertEqual(
            len(page.json()["selection"]["related_occurrences"]["items"]), 3
        )
        self.assertEqual(
            len(page.json()["selection"]["related_work"]["items"]), 3
        )
        for invalid in ("-1", "abc", "10001"):
            self.assertEqual(self.client.get(self.work_url, {
                "kind": "activity", "id": str(activity.pk),
                "related_work_offset": invalid,
            }).status_code, 400)
        self.assertEqual(self.client.get(self.work_url, {
            "related_work_offset": 12,
        }).status_code, 400)
        self.assertNotIn(self.learner.email, str(page.json()))

    def test_activity_mandate_is_not_a_space_portfolio_or_cross_owner(self):
        allowed = self.activity("Programme autorisé")
        hidden = self.activity("Programme privé")
        actor = User.objects.create_user(username="mt4-delegated", password="x")
        mandate = grant_activity_role(
            profile=actor, activity=allowed,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_login(actor)
        responsibility = f"mandate:{mandate.pk}"
        self.assertEqual(self.client.get(self.depth_url(
            "activity", allowed.pk, responsibility=responsibility,
        )).status_code, 200)
        self.assertEqual(self.client.get(self.depth_url(
            "activity", hidden.pk, responsibility=responsibility,
        )).status_code, 404)
        self.assertEqual(self.client.get(self.work_url, {
            "kind": "activity", "id": str(hidden.pk),
            "responsibility": responsibility,
        }).json()["selection"], None)
        self.assertEqual(self.client.get(self.create_url).status_code, 405)
        self.assertEqual(self.client.post(self.create_url, {
            "title": "Programme forgé",
        }).status_code, 404)
        revoke_mandate(mandate=mandate, actor=self.owner)
        self.assertEqual(self.client.get(self.depth_url(
            "activity", allowed.pk, responsibility=responsibility,
        )).status_code, 404)

    def test_programme_creation_is_real_activity_and_not_service(self):
        post = self.client.post(self.create_url, {
            "title": "Comptabilité pratique",
            "short_description": "Cours introductif",
            "visibility": "private",
        }, content_type="application/json")
        self.assertEqual(post.status_code, 201)
        body = post.json()
        obj = Activity.objects.get(pk=body["activity"]["id"])
        self.assertEqual(obj.space_id, self.space.pk)
        self.assertEqual(obj.status, "draft")
        self.assertIsNone(body["service"])
        self.assertFalse(hasattr(obj, "service_details"))
        self.assertEqual(post["Cache-Control"], "private, no-store")

    def test_education_web_form_preselects_space_and_creates(self):
        url = reverse(
            "organizations:space-work-create-g2",
            kwargs={"slug": self.space.slug},
        )
        first = self.client.get(url)
        self.assertEqual(first.status_code, 200)
        self.assertContains(first, "Nouveau programme")
        forged = self.client.post(url, {
            "organization": str(self.space.pk),
            "title": "Programme Web",
            "short_description": "Intro",
            "visibility": "private",
        })
        self.assertEqual(forged.status_code, 302)
        self.assertEqual(forged.url, reverse(
            "organizations:space-work", kwargs={"slug": self.space.slug},
        ))
        self.assertTrue(Activity.objects.filter(
            space=self.space, title="Programme Web", status="draft",
        ).exists())

    def _switch_service(self):
        self.space.archetype = SpaceArchetype.SERVICE_PROVIDER
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self.activity("Accompagnement dossiers")
        ServiceDetails.objects.create(
            activity=activity,
            service_kind=ServiceKind.ADMINISTRATIVE_SUPPORT,
        )
        # The Space owner identity does not imply a Services operator Mandate.
        # Grant the actual activity-scoped role for dossier actions.
        grant_activity_role(
            profile=self.owner, activity=activity,
            role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
            granted_by=self.owner,
        )
        journey = self.journey(
            activity, kind=WorkflowKind.SERVICE,
            state=JourneyStatus.IN_PROGRESS,
        )
        context = ServiceJourneyContext.objects.create(
            journey=journey, objective="Préparer les documents nécessaires",
        )
        return activity, journey, context

    def test_service_n1_n2_owner_links_and_native_case_read(self):
        activity, journey, context = self._switch_service()
        response = self.client.get(self.depth_url("activity", activity.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dossiers liés à cette prestation")
        self.assertNotContains(response, self.learner.email)
        self.assertEqual(len(response.context["work_g2"]["linked_work"]), 1)
        item = response.context["work_g2"]["linked_work"][0]
        self.assertEqual(item["source"]["id"], str(journey.pk))
        detail = self.client.get(item["url"])
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Travailler sur le dossier")
        source = self.client.get(self.work_url, {
            "kind": "journey", "id": str(journey.pk),
        }).json()["selection"]
        self.assertIn("open_service_case_native", [
            handoff["intent"] for handoff in source["owner_handoffs"]
        ])
        owner = self.client.get(self.case_url(journey))
        self.assertEqual(owner.status_code, 200, owner.content)
        self.assertEqual(owner.json()["owner"]["id"], str(journey.pk))
        self.assertEqual(owner.json()["objective"], context.objective)
        self.assertNotIn(self.learner.email, str(owner.json()))
        self.assertEqual(owner["Cache-Control"], "private, no-store")

    def test_native_service_step_mutations_revalidate_owner(self):
        activity, journey, context = self._switch_service()
        step = JourneyStep.objects.create(
            journey=journey, title="Préparer les pièces",
            status=JourneyStepStatus.READY,
        )
        url = self.case_url(journey)
        read = self.client.get(url)
        self.assertEqual(read.status_code, 200)
        self.assertTrue(read.json()["steps"][0]["can_start"])
        started = self.client.post(
            url, {"action": "start_step", "id": str(step.pk)},
            content_type="application/json",
        )
        self.assertEqual(started.status_code, 200, started.content)
        self.assertTrue(started.json()["confirmed_by_owner"])
        step.refresh_from_db()
        self.assertEqual(step.status, JourneyStepStatus.IN_PROGRESS)
        done = self.client.post(
            url, {"action": "complete_step", "id": str(step.pk)},
            content_type="application/json",
        )
        self.assertEqual(done.status_code, 200, done.content)
        step.refresh_from_db()
        self.assertEqual(step.status, JourneyStepStatus.COMPLETED)

    def test_service_blockers_are_owner_scoped_and_resolved_by_service(self):
        activity, journey, context = self._switch_service()
        blocker = JourneyBlocker.objects.create(
            journey=journey, title="Pièce manquante",
            status=JourneyBlockerStatus.ACTIVE,
        )
        url = self.case_url(journey)
        before = self.client.get(url)
        self.assertEqual(before.status_code, 200)
        self.assertEqual(before.json()["blockers"][0]["id"], str(blocker.pk))
        answer = self.client.post(url, {
            "action": "resolve_blocker", "id": str(blocker.pk),
        }, content_type="application/json")
        self.assertEqual(answer.status_code, 200, answer.content)
        blocker.refresh_from_db()
        self.assertEqual(blocker.status, JourneyBlockerStatus.RESOLVED)
        self.assertEqual(answer.json()["blockers"], [])

    def test_service_outsider_and_other_owners_get_no_private_case(self):
        activity, journey, context = self._switch_service()
        foreign = Journey.objects.create(
            activity=activity, initiated_by=self.outsider,
            beneficiary=self.outsider, workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.IN_PROGRESS,
        )
        # An unknown context cannot be presented as a complete operator case.
        self.assertEqual(self.client.get(self.case_url(foreign)).status_code, 404)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.case_url(journey)).status_code, 404)
        self.assertEqual(self.client.post(self.case_url(journey), {
            "action": "start_step", "id": str(journey.pk),
        }, content_type="application/json").status_code, 404)
        self.assertEqual(self.client.get(self.depth_url(
            "journey", journey.pk,
        )).status_code, 404)

    def test_prestation_creation_atomic_service_or_nothing(self):
        self.space.archetype = SpaceArchetype.SERVICE_PROVIDER
        self.space.save(update_fields=["archetype", "updated_at"])
        invalid = self.client.post(self.create_url, {
            "title": "Service invalide",
            "service_kind": "impossible",
        }, content_type="application/json")
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(Activity.objects.filter(
            title="Service invalide", space=self.space,
        ).exists())
        allowed = self.client.post(self.create_url, {
            "title": "Aide administrative",
            "service_kind": ServiceKind.ADMINISTRATIVE_SUPPORT,
            "visibility": "private",
        }, content_type="application/json")
        self.assertEqual(allowed.status_code, 201, allowed.content)
        activity = Activity.objects.get(pk=allowed.json()["activity"]["id"])
        self.assertEqual(activity.space_id, self.space.pk)
        self.assertEqual(activity.status, "draft")
        self.assertEqual(
            activity.service_details.service_kind,
            ServiceKind.ADMINISTRATIVE_SUPPORT,
        )
        self.assertEqual(
            str(activity.service_details.pk),
            allowed.json()["service"]["id"],
        )

    def test_subscription_denial_hides_creation_and_prevents_orphan(self):
        subscription = Subscription.objects.get(space=self.space)
        subscription.status = "suspended"
        subscription.save(update_fields=["status"])
        result = self.client.get(self.work_url)
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()["capabilities"]["create_g2"])
        answer = self.client.post(self.create_url, {
            "title": "Programme interdit",
        }, content_type="application/json")
        self.assertEqual(answer.status_code, 404)
        self.assertFalse(Activity.objects.filter(
            title="Programme interdit", space=self.space,
        ).exists())

    def test_service_creation_failure_rolls_back_activity(self):
        self.space.archetype = SpaceArchetype.SERVICE_PROVIDER
        self.space.save(update_fields=["archetype", "updated_at"])
        with patch(
            "organizations.space_work_g2_creation.create_service_details",
            side_effect=DjangoValidationError("Service non configuré"),
        ):
            response = self.client.post(self.create_url, {
                "title": "Prestation à ne pas laisser orpheline",
                "service_kind": ServiceKind.OTHER,
            }, content_type="application/json")
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Activity.objects.filter(
            title="Prestation à ne pas laisser orpheline",
            space=self.space,
        ).exists())

    def test_service_creation_web_uses_owner_service(self):
        self.space.archetype = SpaceArchetype.SERVICE_PROVIDER
        self.space.save(update_fields=["archetype", "updated_at"])
        url = reverse(
            "organizations:space-work-create-g2",
            kwargs={"slug": self.space.slug},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nouvelle prestation")
        result = self.client.post(url, {
            "organization": str(self.space.pk),
            "title": "Accompagnement scolaire",
            "short_description": "Aider à préparer les dossiers",
            "visibility": "private",
            "service_kind": ServiceKind.EDUCATION_GUIDANCE,
        })
        self.assertEqual(result.status_code, 302, result.content)
        created = Activity.objects.get(
            title="Accompagnement scolaire", space=self.space,
        )
        self.assertEqual(
            created.service_details.service_kind,
            ServiceKind.EDUCATION_GUIDANCE,
        )

    def test_native_service_case_pagination_and_foreign_step_rejection(self):
        activity, case, _ = self._switch_service()
        other = self.journey(
            activity, kind=WorkflowKind.SERVICE,
            state=JourneyStatus.IN_PROGRESS,
        )
        ServiceJourneyContext.objects.create(journey=other)
        foreign_step = JourneyStep.objects.create(
            journey=other, title="Étape autre dossier",
            status=JourneyStepStatus.READY,
        )
        for n in range(53):
            JourneyStep.objects.create(
                journey=case, title=f"Étape {n:02}",
                position=n, status=JourneyStepStatus.READY,
            )
        url = self.case_url(case)
        first = self.client.get(url)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(len(first.json()["steps"]), 50)
        self.assertTrue(first.json()["steps_has_more"])
        self.assertEqual(first.json()["steps_page"]["offset"], 0)
        second = self.client.get(url, {"steps_offset": 50})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(second.json()["steps"]), 3)
        self.assertFalse(second.json()["steps_has_more"])
        self.assertEqual(second.json()["steps_page"]["offset"], 50)
        self.assertEqual(self.client.get(
            url, {"steps_offset": "-1"},
        ).status_code, 400)
        response = self.client.post(url, {
            "action": "start_step", "id": str(foreign_step.pk),
        }, content_type="application/json")
        self.assertEqual(response.status_code, 404)
        foreign_step.refresh_from_db()
        self.assertEqual(foreign_step.status, JourneyStepStatus.READY)

    def test_native_service_case_operator_revocation_denies_read_and_command(self):
        activity, case, _ = self._switch_service()
        actor = User.objects.create_user(username="mt4-case-mandate", password="x")
        mandate = grant_activity_role(
            profile=actor, activity=activity,
            role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_login(actor)
        url = self.case_url(case)
        self.assertEqual(self.client.get(url).status_code, 200)
        revoke_mandate(mandate=mandate, actor=self.owner)
        self.assertEqual(self.client.get(url).status_code, 404)
        response = self.client.post(url, {
            "action": "resolve_blocker", "id": str(case.pk),
        }, content_type="application/json")
        self.assertEqual(response.status_code, 404)

    def test_education_and_services_have_no_implicit_group_authority(self):
        programme = self.activity("Programme collectif")
        from groups.models import Group, GroupMembership
        group = Group.objects.create(
            name="Collectif des élèves", space=self.space,
            created_by=self.owner,
        )
        GroupMembership.objects.create(group=group, profile=self.outsider)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(
            self.depth_url("activity", programme.pk),
        ).status_code, 404)
        self.assertEqual(self.client.post(self.create_url, {
            "title": "Programme forgé",
        }, content_type="application/json").status_code, 404)
