from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from access.services import issue_access
from accounts.models import User
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from journeys.models import Journey, JourneyStatus, WorkflowKind
from journeys.services import fulfill_journey
from objectives.services import create_dossier, create_project
from organizations.models import Organization
from personal_assets.models import PersonalAssetUse
from personal_assets.services import create_personal_asset, create_personal_asset_version
from questionnaires.models import QuestionType
from questionnaires.services import (
    add_question,
    create_form,
    create_form_version,
    publish_form_version,
    request_form,
)
from recognition.economy import redeem_reward
from recognition.models import RecognitionRedemption, RewardDefinition, RewardKind
from recognition.services import get_or_create_account
from social.bilateral_services import create_action_need, create_action_proposal
from social.models import (
    ActionNeedIntakePolicy,
    ActionNeedVisibility,
    ActionProposalDirection,
    ActionProposalStatus,
)
from topics.models import ActionMatchKind


PASSWORD = "Makolo!2026-Z10-Continuity"


class Z10CrossSurfaceContinuityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="z10-user",
            email="z10-user@makolo.test",
            password=PASSWORD,
        )
        self.owner = User.objects.create_user(
            username="z10-owner",
            email="z10-owner@makolo.test",
            password=PASSWORD,
        )
        self.other = User.objects.create_user(
            username="z10-other",
            email="z10-other@makolo.test",
            password=PASSWORD,
        )
        self.activity = Activity.objects.create(
            title="Expérience Z10",
            created_by=self.owner,
            owner_profile=self.owner,
            status=ActivityStatus.PUBLISHED,
        )
        grant_activity_role(
            profile=self.owner,
            activity=self.activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner,
            source="z10-test",
        )
        self.journey = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="Occurrence Z10",
            start_at=timezone.now() + timedelta(hours=2),
            end_at=timezone.now() + timedelta(hours=5),
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        self.access_journey = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.access = issue_access(
            beneficiary=self.user,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=self.access_journey,
            source_key="z10:access",
        )
        self.client.force_authenticate(self.user)

    def test_journey_action_moves_now_without_losing_ongoing_identity(self):
        form = create_form(
            activity=self.activity,
            key="z10-form",
            title="Formulaire Z10",
            actor=self.owner,
        )
        version = create_form_version(
            form=form,
            actor=self.owner,
            title="Formulaire Z10",
        )
        add_question(
            form_version=version,
            actor=self.owner,
            key="full_name",
            label="Nom complet",
            question_type=QuestionType.SHORT_TEXT,
            position=10,
            required=True,
        )
        publish_form_version(form_version=version, actor=self.owner)
        form_request = request_form(
            form_version=version,
            journey=self.journey,
            actor=self.owner,
            required=True,
        )

        now = self.client.get("/api/v1/me/now/").json()["data"]["items"]
        ongoing = self.client.get("/api/v1/me/ongoing/").json()["data"]["items"]
        now_item = next(
            row for row in now
            if row["source"] == {"kind": "journey", "id": str(self.journey.pk)}
        )
        ongoing_item = next(
            row for row in ongoing
            if row["source"] == {"kind": "journey", "id": str(self.journey.pk)}
        )
        self.assertEqual(now_item["links"]["detail"], f"/api/v1/me/journeys/{self.journey.pk}/")
        self.assertEqual(ongoing_item["links"]["detail"], f"/api/v1/me/journeys/{self.journey.pk}/")

        detail = self.client.get(now_item["links"]["detail"]).json()["data"]
        form_row = next(row for row in detail["forms"] if row["id"] == str(form_request.pk))
        self.assertEqual(form_row["capabilities"], ["complete_form"])

        saved = self.client.post(
            form_row["links"]["save"],
            {"answers": {"full_name": "Amina Z10"}},
            format="json",
        )
        self.assertEqual(saved.status_code, 200)
        submitted = self.client.post(form_row["links"]["submit"], {}, format="json")
        self.assertEqual(submitted.status_code, 200)

        after_now = self.client.get("/api/v1/me/now/").json()["data"]["items"]
        after_ongoing = self.client.get("/api/v1/me/ongoing/").json()["data"]["items"]
        self.assertFalse(
            any(
                row["source"] == {"kind": "journey", "id": str(self.journey.pk)}
                for row in after_now
            )
        )
        self.assertTrue(
            any(
                row["source"] == {"kind": "journey", "id": str(self.journey.pk)}
                for row in after_ongoing
            )
        )

    def test_terminal_journey_moves_to_history_with_same_canonical_id(self):
        before = self.client.get(f"/api/v1/me/journeys/{self.journey.pk}/")
        self.assertEqual(before.status_code, 200)
        self.assertEqual(before.json()["data"]["identity"]["id"], str(self.journey.pk))

        fulfill_journey(journey=self.journey, actor=self.owner, reason="z10-test")

        ongoing = self.client.get("/api/v1/me/ongoing/").json()["data"]["items"]
        self.assertFalse(
            any(
                row["source"] == {"kind": "journey", "id": str(self.journey.pk)}
                for row in ongoing
            )
        )
        history = self.client.get("/api/v1/me/history/").json()["data"]["items"]
        history_row = next(
            row for row in history
            if row["source"] == {"kind": "journey", "id": str(self.journey.pk)}
        )
        self.assertEqual(
            history_row["links"]["detail"],
            f"/api/v1/me/journeys/{self.journey.pk}/",
        )
        detail = self.client.get(history_row["links"]["detail"])
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["data"]["identity"]["id"], str(self.journey.pk))

    def test_access_occurrence_identity_continues_from_ongoing_to_day_of(self):
        ongoing = self.client.get("/api/v1/me/ongoing/").json()["data"]["items"]
        access_row = next(
            row for row in ongoing
            if row["source"] == {"kind": "access", "id": str(self.access.pk)}
        )
        self.assertEqual(
            access_row["occurrence"],
            {"kind": "occurrence", "id": str(self.occurrence.pk)},
        )
        self.assertEqual(
            access_row["links"]["detail"],
            f"/api/v1/me/accesses/{self.access.pk}/",
        )
        self.assertEqual(
            access_row["links"]["day_of"],
            f"/api/v1/me/occurrences/{self.occurrence.pk}/day-of/",
        )

        collection = self.client.get("/api/v1/me/accesses/").json()["data"]["items"]
        collection_row = next(
            row for row in collection
            if row["identity"] == {"kind": "access", "id": str(self.access.pk)}
        )
        self.assertEqual(collection_row["links"]["detail"], access_row["links"]["detail"])
        detail = self.client.get(collection_row["links"]["detail"]).json()["data"]
        self.assertEqual(detail["identity"], {"kind": "access", "id": str(self.access.pk)})
        self.assertEqual(detail["occurrence"]["id"], str(self.occurrence.pk))

        day_of = self.client.get(access_row["links"]["day_of"]).json()["data"]
        self.assertEqual(day_of["occurrence"]["id"], str(self.occurrence.pk))
        day_access = next(row for row in day_of["access"] if row["identity"]["id"] == str(self.access.pk))
        self.assertEqual(day_access["identity"], {"kind": "access", "id": str(self.access.pk)})

    def test_dossier_and_project_ongoing_links_reach_owner_depths(self):
        dossier = create_dossier(
            actor=self.user,
            owner_profile=self.user,
            title="Dossier Z10",
        )
        project = create_project(
            actor=self.user,
            owner_profile=self.user,
            title="Projet Z10",
        )

        ongoing = self.client.get("/api/v1/me/ongoing/").json()["data"]["items"]
        dossier_row = next(
            row for row in ongoing
            if row["source"] == {"kind": "dossier", "id": str(dossier.pk)}
        )
        project_row = next(
            row for row in ongoing
            if row["source"] == {"kind": "project", "id": str(project.pk)}
        )
        self.assertEqual(dossier_row["capabilities"], ["open_detail"])
        self.assertEqual(project_row["capabilities"], ["open_detail"])
        self.assertEqual(self.client.get(dossier_row["links"]["detail"]).status_code, 200)
        self.assertEqual(self.client.get(project_row["links"]["detail"]).status_code, 200)

    def test_now_action_proposal_hands_off_to_owner_api_and_disappears_after_response(self):
        need = create_action_need(
            actor=self.user,
            owner_profile=self.user,
            title="Besoin personnel Z10",
            match_kind=ActionMatchKind.COLLABORATE,
            visibility=ActionNeedVisibility.PUBLIC,
            intake_policy=ActionNeedIntakePolicy.OPEN,
        )
        proposal = create_action_proposal(
            actor=self.other,
            need=need,
            candidate_profile=self.other,
            direction=ActionProposalDirection.CANDIDATE_TO_OWNER,
            client_reference="z10-personal-proposal",
        )

        now = self.client.get("/api/v1/me/now/").json()["data"]["items"]
        row = next(
            item for item in now
            if item["source"] == {"kind": "action_proposal", "id": str(proposal.pk)}
        )
        self.assertEqual(row["capabilities"], ["respond"])
        detail = self.client.get(row["links"]["detail"])
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["identity"]["id"], str(proposal.pk))
        self.assertEqual(detail.json()["acting_context"]["kind"], "profile")

        response = self.client.post(
            row["links"]["respond"],
            {"status": ActionProposalStatus.ACCEPTED},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["identity"]["id"], str(proposal.pk))
        self.assertEqual(response.json()["state"], ActionProposalStatus.ACCEPTED)

        after = self.client.get("/api/v1/me/now/").json()["data"]["items"]
        self.assertFalse(
            any(
                item["source"] == {"kind": "action_proposal", "id": str(proposal.pk)}
                for item in after
            )
        )

    def test_space_action_proposal_requires_explicit_space_context(self):
        space = Organization.objects.create(
            name="Space Z10",
            slug="space-z10",
            created_by=self.user,
        )
        grant_space_role(
            profile=self.user,
            space=space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.user,
            source="z10-test",
        )
        need = create_action_need(
            actor=self.user,
            space=space,
            title="Besoin Space Z10",
            match_kind=ActionMatchKind.COLLABORATE,
            visibility=ActionNeedVisibility.PUBLIC,
            intake_policy=ActionNeedIntakePolicy.OPEN,
        )
        proposal = create_action_proposal(
            actor=self.other,
            need=need,
            candidate_profile=self.other,
            direction=ActionProposalDirection.CANDIDATE_TO_OWNER,
            client_reference="z10-space-proposal",
        )

        detail_url = f"/api/v1/social/action-proposals/{proposal.pk}/"
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["acting_context"]["kind"], "space")
        self.assertEqual(detail.json()["acting_context"]["id"], str(space.pk))
        self.assertTrue(detail.json()["acting_context"]["explicit"])

        respond_url = f"/api/v1/social/action-proposals/{proposal.pk}/respond/"
        missing = self.client.post(
            respond_url,
            {"status": ActionProposalStatus.ACCEPTED},
            format="json",
        )
        self.assertEqual(missing.status_code, 400)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ActionProposalStatus.PENDING)

        accepted = self.client.post(
            respond_url,
            {
                "status": ActionProposalStatus.ACCEPTED,
                "acting_space_id": str(space.pk),
            },
            format="json",
        )
        self.assertEqual(accepted.status_code, 200)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ActionProposalStatus.ACCEPTED)

    def test_recognition_now_uses_same_redemption_and_owner_decision_routes(self):
        owner_account = get_or_create_account(profile=self.owner)
        owner_account.points_balance = 100
        owner_account.lifetime_earned = 100
        owner_account.save(
            update_fields=["points_balance", "lifetime_earned", "updated_at"]
        )
        reward = RewardDefinition.objects.create(
            code="z10-benefit",
            version=1,
            name="Bénéfice Z10",
            kind=RewardKind.OTHER,
            points_cost=20,
            beneficiary_allowed=True,
            acceptance_required=True,
            fulfillment={"owner_domain": "z10-test"},
        )
        redemption = redeem_reward(
            owner_account=owner_account,
            reward=reward,
            idempotency_key="z10-benefit-redemption",
            actor_profile=self.owner,
            beneficiary_profile=self.user,
        )

        now = self.client.get("/api/v1/me/now/").json()["data"]["items"]
        row = next(
            item for item in now
            if item["source"] == {
                "kind": "recognition_redemption",
                "id": str(redemption.pk),
            }
        )
        self.assertEqual(row["capabilities"], ["accept", "decline"])
        accepted = self.client.post(row["links"]["accept"], {}, format="json")
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["id"], str(redemption.pk))
        self.assertEqual(
            RecognitionRedemption.objects.filter(pk=redemption.pk).count(),
            1,
        )

        after = self.client.get("/api/v1/me/now/").json()["data"]["items"]
        self.assertFalse(
            any(
                item["source"] == {
                    "kind": "recognition_redemption",
                    "id": str(redemption.pk),
                }
                for item in after
            )
        )

    def test_resource_reuse_replays_same_owner_artifact_without_duplicate(self):
        asset = create_personal_asset(
            controller=self.user,
            subject_profile=self.user,
            title="CV Z10",
        )
        version = create_personal_asset_version(
            actor=self.user,
            asset=asset,
            uploaded_file=SimpleUploadedFile(
                "cv-z10.pdf",
                b"%PDF-1.4 z10",
                content_type="application/pdf",
            ),
        )
        url = f"/api/v1/me/resources/versions/{version.pk}/reuse/"
        first = self.client.post(
            url,
            {"journey_id": str(self.journey.pk)},
            format="json",
        )
        second = self.client.post(
            url,
            {"journey_id": str(self.journey.pk)},
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(
            first.json()["data"]["result"]["id"],
            second.json()["data"]["result"]["id"],
        )
        self.assertEqual(
            PersonalAssetUse.objects.filter(
                asset_version=version,
                journey_artifact__journey=self.journey,
            ).count(),
            1,
        )

    def test_mark_live_handoff_returns_to_operations_without_parallel_identity(self):
        response = self.client.post(
            "/api/v1/me/mark/",
            {
                "input": {"kind": "text", "value": "Je suis arrivé"},
                "context": {"occurrence_id": str(self.occurrence.pk)},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["state"], "resolved")
        self.assertEqual(data["result"]["kind"], "occurrence")
        self.assertEqual(data["result"]["id"], str(self.occurrence.pk))
        self.assertEqual(data["handoff"]["owner"], "operations")
        self.assertEqual(data["handoff"]["surface"], "occurrence_day_of")
        self.assertEqual(
            data["links"]["day_of"],
            f"/api/v1/me/occurrences/{self.occurrence.pk}/day-of/",
        )

    def test_foreign_canonical_ids_do_not_leak_through_personal_cross_surfaces(self):
        foreign_activity = Activity.objects.create(
            title="Secret Z10",
            created_by=self.other,
            owner_profile=self.other,
            status=ActivityStatus.PUBLISHED,
        )
        foreign_journey = Journey.objects.create(
            initiated_by=self.other,
            beneficiary=self.other,
            activity=foreign_activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )

        rendered = str(
            {
                "now": self.client.get("/api/v1/me/now/").json(),
                "ongoing": self.client.get("/api/v1/me/ongoing/").json(),
                "history": self.client.get("/api/v1/me/history/").json(),
            }
        )
        self.assertNotIn(str(foreign_journey.pk), rendered)
        self.assertNotIn("Secret Z10", rendered)
        self.assertEqual(
            self.client.get(f"/api/v1/me/journeys/{foreign_journey.pk}/").status_code,
            404,
        )
