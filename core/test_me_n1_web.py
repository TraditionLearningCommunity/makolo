"""N1 Web must render the same owner-projected personal capital as mobile."""
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.storage import staticfiles_storage
from django.test import TestCase
from django.urls import reverse
from topics.models import ProfileInterest, ProfileOpenTo, OpenToKind, Topic
from activities.models import Activity, ActivityStatus
from discovery.models import ActivityBookmark


class PersonalMeN1WebTests(TestCase):
    def setUp(self):
        self.profile = get_user_model().objects.create_user(
            username="me_n1_preview",
            first_name="Amina", last_name="Test",
        )
        self.url = reverse("core:participant-me")

    def test_identity_and_empty_territories_remain_visible(self):
        self.client.force_login(self.profile)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-mk-surface="me"')
        self.assertContains(response, "Amina Test")
        self.assertContains(response, "Passeport Makolo")
        self.assertContains(response, "Ce qui compte pour moi")
        self.assertContains(response, "Mes collectifs")
        self.assertContains(response, "Mes accès")
        self.assertContains(response, "Mes ressources")
        self.assertContains(response, "Aucune ressource pour le moment.")
        self.assertNotContains(response, "Profil complété à")
        self.assertNotContains(response, "AccessCredential")

    def test_web_n1_uses_an_explicit_stylesheet_and_preserves_owner_links(self):
        self.client.force_login(self.profile)
        response = self.client.get(self.url)
        self.assertContains(response, staticfiles_storage.url("css/me-n1.css"))
        self.assertContains(response, reverse("core:participant-accesses"))
        self.assertContains(response, reverse("personal_assets:list"))
        self.assertContains(response, reverse("sharing:passport-me"))

    def test_anonymous_view_is_not_public(self):
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_choices_hub_and_avatar_are_genuine_owner_handoffs(self):
        self.client.force_login(self.profile)
        root = self.client.get(self.url)
        self.assertContains(root, reverse("core:participant-me-choices"))
        self.assertContains(root, reverse("account:profile"))
        self.assertContains(root, "Mon historique")
        self.assertNotContains(root, "Vous avez tout exploré")
        hub = self.client.get(reverse("core:participant-me-choices"))
        self.assertEqual(hub.status_code, 200)
        self.assertContains(hub, reverse("account:interests"))
        self.assertContains(hub, reverse("account:open-to"))
        self.assertContains(hub, reverse("discovery:bookmarks"))
        self.assertContains(hub, reverse("discovery:watch-list"))

    def test_moi_root_shows_three_saved_items_and_real_total(self):
        self.client.force_login(self.profile)
        for index in range(5):
            activity = Activity.objects.create(
                owner_profile=self.profile,
                created_by=self.profile,
                title=f"Possibilité échantillon {index}",
                status=ActivityStatus.PUBLISHED,
            )
            ActivityBookmark.objects.create(user=self.profile, activity=activity)
        root = self.client.get(self.url)
        self.assertEqual(root.status_code, 200)
        self.assertContains(root, "Voir les 5 enregistrés")
        self.assertEqual(root.content.count(b'class="mk-me-n1-saved-title"'), 3)

    def test_consideration_settings_edits_only_the_authenticated_profile(self):
        other = get_user_model().objects.create_user(username="me_n1_unrelated")
        topic = Topic.objects.create(code="me-topic-for-settings", label="Musique")
        self.client.force_login(self.profile)
        url = reverse("personal-projections:consideration-settings")
        before = self.client.get(url)
        self.assertEqual(before.status_code, 200)
        self.assertEqual(before.json()["meta"]["projection"], "personal.me.settings")
        changed = self.client.put(url,
            data='{"family":"interests","values":["%s"]}' % topic.pk,
            content_type="application/json")
        self.assertEqual(changed.status_code, 200)
        self.assertTrue(ProfileInterest.objects.filter(
            profile=self.profile, topic=topic).exists())
        self.assertFalse(ProfileInterest.objects.filter(profile=other).exists())
        enabled = self.client.put(url,
            data='{"family":"open_to","values":["%s"]}' % OpenToKind.MENTOR,
            content_type="application/json")
        self.assertEqual(enabled.status_code, 200)
        self.assertTrue(ProfileOpenTo.objects.filter(
            profile=self.profile, kind=OpenToKind.MENTOR).exists())
        rejected = self.client.put(url,
            data='{"family":"interests","values":[],"profile_id":"other"}',
            content_type="application/json")
        self.assertEqual(rejected.status_code, 400)
        self.assertTrue(ProfileInterest.objects.filter(
            profile=self.profile, topic=topic).exists())

    def test_preview_pages_are_private_and_bounded(self):
        preview = reverse("personal-projections:me-preview", kwargs={"territory": "considerations"})
        self.assertNotEqual(self.client.get(preview).status_code, 200)
        self.client.force_login(self.profile)
        response = self.client.get(preview, {"family": "interests", "offset": "6", "limit": "24"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["meta"]["projection"], "personal.me.preview")
        data = response.json()["data"]
        self.assertEqual(data["territory"], "considerations")
        self.assertEqual(data["offset"], 6)
        self.assertEqual(data["family"], "interests")
        self.assertEqual(data["actor"]["id"], str(self.profile.pk))
        self.assertEqual(data["collection"]["items"], [])
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_preview_rejects_scope_override_and_unbounded_requests(self):
        self.client.force_login(self.profile)
        preview = reverse("personal-projections:me-preview", kwargs={"territory": "resources"})
        self.assertEqual(self.client.get(preview, {"family": "documents", "profile_id": "other"}).status_code, 400)
        self.assertEqual(self.client.get(preview, {"family": "documents", "offset": -1}).status_code, 400)
        self.assertEqual(self.client.get(preview, {"family": "documents", "limit": 1000}).status_code, 400)
        self.assertEqual(self.client.get(preview, {"family": "unknown"}).status_code, 400)
        self.assertEqual(
            self.client.get(reverse("personal-projections:me-preview",
                kwargs={"territory": "unknown"})).status_code, 400
        )

    def test_every_declared_interest_is_seen_once_across_continuations(self):
        topics = [
            Topic.objects.create(code=f"me-topic-{n:02d}", label=f"Sujet {n:02d}")
            for n in range(13)
        ]
        for topic in topics:
            ProfileInterest.objects.create(profile=self.profile, topic=topic)
        self.client.force_login(self.profile)
        root = self.client.get(reverse("personal-projections:me")).json()["data"]
        first = root["considerations"]["interests"]
        self.assertEqual(first["count"], 13)
        self.assertEqual(first["next_offset"], 6)
        self.assertTrue(first["has_more"])
        preview = reverse("personal-projections:me-preview",
            kwargs={"territory": "considerations"})
        ids = [row["id"] for row in first["items"]]
        offset = first["next_offset"]
        for _ in range(10):
            response = self.client.get(preview, {
                "family": "interests", "offset": offset, "limit": 3,
            })
            self.assertEqual(response.status_code, 200)
            data = response.json()["data"]
            self.assertEqual(data["actor"]["id"], str(self.profile.pk))
            self.assertEqual(data["family"], "interests")
            page = data["collection"]
            ids.extend(row["id"] for row in page["items"])
            self.assertEqual(page["next_offset"], offset + len(page["items"]))
            offset = page["next_offset"]
            if not page["has_more"]:
                break
        else:
            self.fail("Pagination did not reach the real end")
        self.assertEqual(len(ids), 13)
        self.assertEqual(len(set(ids)), 13)
        self.assertEqual(offset, 13)

    def test_other_persons_interests_never_appear_on_my_continuation(self):
        other = get_user_model().objects.create_user(
            username="me_n1_other", first_name="Autre", last_name="profil",
        )
        topic = Topic.objects.create(code="me-private-other", label="Sujet privé")
        ProfileInterest.objects.create(profile=other, topic=topic)
        self.client.force_login(self.profile)
        preview = reverse("personal-projections:me-preview",
            kwargs={"territory": "considerations"})
        response = self.client.get(preview, {"family": "interests", "offset": 0})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["collection"]["items"], [])
