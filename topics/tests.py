from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity, ActivityStatus, ActivityVisibility
from discovery.models import ActivityBookmark
from discovery.recommendations import build_activity_recommendations
from organizations.models import Organization, OrganizationFollow

from .models import ActivityTopic, ProfileInterest, Topic
from .services import public_profile_interests, replace_profile_interests


User = get_user_model()


class G2TopicsInterestsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="g2-user",
            email="g2-user@example.test",
            password="StrongPass2026!",
        )
        self.other = User.objects.create_user(
            username="g2-other",
            email="g2-other@example.test",
            password="StrongPass2026!",
        )
        self.owner = User.objects.create_user(
            username="g2-owner",
            email="g2-owner@example.test",
            password="StrongPass2026!",
        )
        self.tech, _ = Topic.objects.get_or_create(
            code="technologie",
            defaults={"label": "Technologie", "is_active": True},
        )
        self.culture, _ = Topic.objects.get_or_create(
            code="culture",
            defaults={"label": "Culture", "is_active": True},
        )
        self.space = Organization.objects.create(
            name="G2 Topic Space",
            created_by=self.owner,
            public_profile=True,
        )
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.owner,
            title="Atelier IA responsable",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )

    def test_topic_code_and_profile_topic_are_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Topic.objects.create(code=self.tech.code, label="Technologie bis")

        ProfileInterest.objects.create(profile=self.user, topic=self.tech)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProfileInterest.objects.create(profile=self.user, topic=self.tech)

    def test_replace_interests_adds_removes_and_preserves_retained_visibility(self):
        existing = ProfileInterest.objects.create(profile=self.user, topic=self.tech, is_public=True)
        replace_profile_interests(profile=self.user, topic_ids=[self.tech.pk, self.culture.pk])
        self.assertEqual(
            set(ProfileInterest.objects.filter(profile=self.user).values_list("topic_id", flat=True)),
            {self.tech.pk, self.culture.pk},
        )
        existing.refresh_from_db()
        self.assertTrue(existing.is_public)
        self.assertFalse(ProfileInterest.objects.get(profile=self.user, topic=self.culture).is_public)

        replace_profile_interests(profile=self.user, topic_ids=[self.culture.pk])
        self.assertFalse(ProfileInterest.objects.filter(profile=self.user, topic=self.tech).exists())
        self.assertTrue(ProfileInterest.objects.filter(profile=self.user, topic=self.culture).exists())

    def test_interest_is_private_by_default_and_public_selector_does_not_leak_it(self):
        interest = ProfileInterest.objects.create(profile=self.user, topic=self.tech)
        self.assertFalse(interest.is_public)
        self.assertEqual(list(public_profile_interests(profile=self.user)), [])
        interest.is_public = True
        interest.save(update_fields=["is_public", "updated_at"])
        self.assertEqual(list(public_profile_interests(profile=self.user)), [interest])

    def test_inactive_topic_cannot_be_added(self):
        inactive = Topic.objects.create(code="archive-g2", label="Archive G2", is_active=False)
        with self.assertRaises(ValidationError):
            replace_profile_interests(profile=self.user, topic_ids=[inactive.pk])
        self.assertFalse(ProfileInterest.objects.filter(profile=self.user).exists())

    def test_interest_settings_require_login_and_are_scoped_to_current_user(self):
        url = reverse("account:interests")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        ProfileInterest.objects.create(profile=self.user, topic=self.tech)
        self.client.force_login(self.other)
        response = self.client.post(url, {"topics": [str(self.culture.pk)]})
        self.assertRedirects(response, url)
        self.assertTrue(ProfileInterest.objects.filter(profile=self.user, topic=self.tech).exists())
        self.assertTrue(ProfileInterest.objects.filter(profile=self.other, topic=self.culture).exists())
        self.assertFalse(ProfileInterest.objects.filter(profile=self.other, topic=self.tech).exists())

    def test_interest_settings_page_explains_explicit_and_private_behavior(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("account:interests"))
        self.assertContains(response, "Centres d’intérêt")
        self.assertContains(response, "privés par défaut")
        self.assertContains(response, "ne sont jamais déduits automatiquement")

    def test_bookmark_and_follow_do_not_create_profile_interests(self):
        ActivityBookmark.objects.create(user=self.user, activity=self.activity)
        OrganizationFollow.objects.create(user=self.user, organization=self.space)
        self.assertFalse(ProfileInterest.objects.filter(profile=self.user).exists())

    def test_user_without_interests_has_no_interest_recommendation(self):
        ActivityTopic.objects.create(activity=self.activity, topic=self.tech)
        rows = build_activity_recommendations(self.user)
        self.assertEqual(rows, [])

    def test_declared_private_interest_recommends_matching_public_activity(self):
        ProfileInterest.objects.create(profile=self.user, topic=self.tech, is_public=False)
        ActivityTopic.objects.create(activity=self.activity, topic=self.tech)
        rows = build_activity_recommendations(self.user)
        row = next(item for item in rows if item.activity.pk == self.activity.pk)
        reasons = {reason.code: reason.label for reason in row.reasons}
        self.assertIn("declared_interest:technologie", reasons)
        self.assertEqual(
            reasons["declared_interest:technologie"],
            "Parce que Technologie fait partie de vos centres d’intérêt.",
        )

    def test_private_activity_is_not_recommended_even_when_topic_matches(self):
        private_activity = Activity.objects.create(
            space=self.space,
            created_by=self.owner,
            title="Atelier privé",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PRIVATE,
        )
        ProfileInterest.objects.create(profile=self.user, topic=self.tech)
        ActivityTopic.objects.create(activity=private_activity, topic=self.tech)
        ids = {row.activity.pk for row in build_activity_recommendations(self.user)}
        self.assertNotIn(private_activity.pk, ids)
