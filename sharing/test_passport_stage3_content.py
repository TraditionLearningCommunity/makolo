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
from groups.models import Group, GroupStatus
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

    def test_archived_group_does_not_appear_as_current_affiliation(self):
        active = Group.objects.create(
            name="Collectif actif stage 3",
            owner_profile=self.amina,
            created_by=self.amina,
            status=GroupStatus.ACTIVE,
        )
        archived = Group.objects.create(
            name="Collectif archive stage 3",
            owner_profile=self.amina,
            created_by=self.amina,
            status=GroupStatus.ARCHIVED,
        )
        complete = build_profile_passport(self.amina, variant="complete")
        group_names = {row["name"] for row in complete.group_affiliations}
        self.assertIn(active.name, group_names)
        self.assertNotIn(archived.name, group_names)
        public = build_profile_passport(self.amina, variant="public")
        self.assertEqual(public.group_affiliations, ())

    def test_collection_privacy_is_one_gate_without_disclosing_private_atoms(self):
        from accounts.profile_visibility import replace_profile_visibility

        before = build_profile_passport(self.amina, variant="public")
        self.assertTrue(before.interests)
        replace_profile_visibility(
            owner=self.amina, target_kind="field",
            field_key="interests", audiences=[],
        )
        after = build_profile_passport(self.amina, variant="public")
        self.assertEqual(after.interests, ())
        self.assertGreater(
            len(build_profile_passport(self.amina, variant="complete").interests),
            len(after.interests),
        )
        replace_profile_visibility(
            owner=self.amina, target_kind="field",
            field_key="interests", audiences=[{"kind": "public"}],
        )
        restored = build_profile_passport(self.amina, variant="public")
        self.assertEqual(
            [row.pk for row in restored.interests],
            [row.pk for row in before.interests],
        )
        # An already private declaration is never silently published.
        self.assertLess(
            len(restored.interests),
            len(build_profile_passport(self.amina, variant="complete").interests),
        )

    def test_public_variant_keeps_every_publicly_admissible_fact_family(self):
        public = build_profile_passport(self.amina, variant="public")
        complete = build_profile_passport(self.amina, variant="complete")
        self.assertEqual(public.identity["name"], complete.identity["name"])
        self.assertEqual(public.identity["bio"], complete.identity["bio"])
        self.assertEqual(public.identity["links"], complete.identity["links"])
        self.assertIn(self.owned_public, public.activities)
        self.assertNotIn(self.owned_private, public.activities)
        self.assertTrue(public.interests)
        self.assertLessEqual(len(public.proofs), len(complete.proofs))
        self.assertLessEqual(len(public.credentials), len(complete.credentials))
        self.assertNotIn("owner_details", public.identity)

    def test_personalized_default_keeps_public_identity_and_links(self):
        from accounts.profile_visibility import replace_profile_visibility

        public = build_profile_passport(self.amina, variant="public")
        thematic = build_profile_passport(
            self.amina, variant="thematic", topic_codes=[self.tech.code],
        )
        custom = build_profile_passport(
            self.amina, variant="custom", selected_sections=[],
        )
        for projection in (thematic, custom):
            self.assertEqual(projection.identity["name"], public.identity["name"])
            self.assertEqual(projection.identity["bio"], public.identity["bio"])
            self.assertEqual(projection.identity["links"], public.identity["links"])

        # A deliberate private setting still takes precedence over the
        # implicit custom baseline. The owner keeps the full version.
        replace_profile_visibility(
            owner=self.amina,
            target_kind="field",
            field_key="bio",
            audiences=[],
        )
        custom = build_profile_passport(
            self.amina, variant="custom", selected_sections=[],
        )
        self.assertEqual(custom.identity["bio"], "")
        complete = build_profile_passport(self.amina, variant="complete")
        self.assertEqual(complete.identity["bio"], "Bio publique Amina")
