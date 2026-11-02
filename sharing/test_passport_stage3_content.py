"""Stage 3 Passport content: thematic options come only from owner facts.

These are focused regressions for the existing G6 projection. They must
remain valid for Web and Flutter, which consume the same server selectors.
"""
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityStatus, ActivityVisibility
from core.api.z8_projection import build_personal_passport_depth_data
from journeys.models import Journey, JourneyStatus, WorkflowKind
from sharing.passport import build_profile_passport, profile_passport_topic_options
from sharing.test_g6_passport import G6PassportFixtureMixin
from topics.models import ActionMatchKind, ActivityTopic, ProfileOpenTo, Topic
from trust.models import Proof, ProofStatus, ProofType


class PassportStage3ThematicContentTests(G6PassportFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_open_to_only_theme_is_selectable_in_web_and_native_projection(self):
        topic = Topic.objects.create(
            code="stage3-mentorat", label="Mentorat stage 3",
        )
        opening = ProfileOpenTo.objects.create(
            profile=self.amina,
            kind=ActionMatchKind.MENTOR,
            topic=topic,
            is_active=True,
            is_public=False,
        )
        self.assertIn(
            topic.code,
            [row.code for row in profile_passport_topic_options(self.amina)],
        )
        projection = build_profile_passport(
            self.amina, variant="thematic", topic_codes=[topic.code],
        )
        self.assertEqual(list(projection.open_to), [opening])
        self.assertEqual(list(projection.interests), [])
        self.assertEqual(list(projection.activities), [])

        native = build_personal_passport_depth_data(
            self.amina, variant="thematic", topic_codes=[topic.code],
        )
        self.assertIn(
            {"code": topic.code, "label": topic.label},
            native["topic_options"],
        )
        self.assertEqual(
            [row["id"] for row in native["declared"]["open_to"]],
            [str(opening.pk)],
        )
        self.client.force_login(self.amina)
        web = self.client.get(
            reverse("sharing:passport-me"),
            {"variant": "thematic", "topic": topic.code},
        )
        self.assertEqual(web.status_code, 200)
        self.assertContains(web, topic.label)

    def test_inactive_open_to_does_not_offer_a_theme(self):
        topic = Topic.objects.create(
            code="stage3-inactive-opening", label="Ouverture inactive stage 3",
        )
        ProfileOpenTo.objects.create(
            profile=self.amina,
            kind=ActionMatchKind.MENTOR,
            topic=topic,
            is_active=False,
        )
        self.assertNotIn(
            topic.code,
            [row.code for row in profile_passport_topic_options(self.amina)],
        )
        projection = build_profile_passport(
            self.amina, variant="thematic", topic_codes=[topic.code],
        )
        self.assertEqual(list(projection.open_to), [])

    def test_revoked_proof_does_not_create_a_phantom_theme(self):
        topic = Topic.objects.create(
            code="stage3-revoked-proof", label="Preuve retiree stage 3",
        )
        activity = Activity.objects.create(
            space=self.space,
            created_by=self.space_owner,
            title="Activite uniquement preuve retiree stage 3",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PRIVATE,
        )
        ActivityTopic.objects.create(activity=activity, topic=topic)
        journey = Journey.objects.create(
            initiated_by=self.amina,
            beneficiary=self.amina,
            activity=activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.FULFILLED,
            fulfilled_at=timezone.now(),
        )
        Proof.objects.create(
            subject_profile=self.amina,
            journey=journey,
            proof_type=ProofType.PARTICIPATION_CONFIRMED,
            status=ProofStatus.REVOKED,
            is_public=False,
            issued_by=self.space_owner,
        )
        self.assertNotIn(
            topic.code,
            [row.code for row in profile_passport_topic_options(self.amina)],
        )
        projection = build_profile_passport(
            self.amina, variant="thematic", topic_codes=[topic.code],
        )
        self.assertEqual(list(projection.proofs), [])
