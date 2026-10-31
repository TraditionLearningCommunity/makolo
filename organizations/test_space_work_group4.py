"""Group 4: Creative and Media Space work, no orphan presentation media."""
from datetime import timedelta
from tempfile import TemporaryDirectory

from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import (
    Activity, ActivityStatus, Occurrence, OccurrenceStatus,
)
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from commerce.models import Offer, OfferStatus
from organizations.models import Organization, SpaceArchetype
from presentations.asset_models import PresentationAsset
from presentations.enums import Provenance
from presentations.media_models import PresentationMediaPurpose
from presentations.media_services import (
    associate_presentation_media, publish_presentation_media, retire_presentation_media,
)


class SpaceWorkGroup4Tests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        media_override = override_settings(MEDIA_ROOT=self.tmp.name)
        media_override.enable()
        self.addCleanup(media_override.disable)
        self.owner = User.objects.create_user(username="group4-owner", password="x")
        self.viewer = User.objects.create_user(username="group4-viewer", password="x")
        self.space = Organization.objects.create(
            name="Atelier Group 4", slug="atelier-group-4",
            archetype=SpaceArchetype.CREATIVE, created_by=self.owner,
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        self.client = APIClient()
        self.web = Client()
        self.url = reverse(
            "organizations_api:workspace-work", kwargs={"slug": self.space.slug}
        )
        self.web_url = reverse(
            "organizations:space-work", kwargs={"slug": self.space.slug}
        )

    def activity(self, title, *, status=ActivityStatus.PUBLISHED):
        activity = Activity.objects.create(
            space=self.space, created_by=self.owner,
            title=title, status=status,
        )
        grant_activity_role(
            profile=self.owner, activity=activity,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        return activity

    def media_use(self, activity, *, occurrence=None, publish=True, label="Visuel contextualisé"):
        asset = PresentationAsset(
            provenance=Provenance.SPACE,
            owner_space=self.space,
            uploaded_by=self.owner,
            mime_type="image/png",
            size=4,
            checksum="c" * 64,
        )
        asset.file.save("group4-image.png", ContentFile(b"test"), save=False)
        asset.save()
        use = associate_presentation_media(
            actor=self.owner, activity=activity,
            occurrence=occurrence, asset=asset,
            purpose=PresentationMediaPurpose.RECOGNIZE,
            alt_text=label,
        )
        if publish:
            publish_presentation_media(actor=self.owner, media_use=use)
        return use

    def test_creations_preserve_artistic_identity_with_real_progress_and_date(self):
        creation = self.activity("Album première")
        self.activity("Scénographie à préparer", status=ActivityStatus.DRAFT)
        now = timezone.now()
        live = Occurrence.objects.create(
            activity=creation, label="Répétition actuelle",
            start_at=now - timedelta(minutes=15),
            end_at=now + timedelta(hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        next_show = Occurrence.objects.create(
            activity=creation, label="Présentation publique",
            start_at=now + timedelta(days=8),
            end_at=now + timedelta(days=8, hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.client.force_authenticate(self.owner)
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200, result.data)
        world = result.data["business_world"]
        self.assertEqual(world["preferred_language"], "Créations")
        self.assertEqual(
            [g["identity"] for g in world["reading_groups"]],
            ["creation_work", "presentations", "creations"],
        )
        self.assertEqual(
            result.data["presentation"]["section_order"],
            ["active", "preparation", "upcoming", "activities"],
        )
        self.assertEqual(
            result.data["presentation"]["next_occurrence_label"],
            "Prochaine présentation",
        )
        row = next(
            r for r in result.data["sections"]["activities"]["items"]
            if r["source"]["id"] == str(creation.pk)
        )
        self.assertEqual(
            row["context"]["next_occurrence"]["id"], str(next_show.pk)
        )
        self.assertIn(str(live.pk), str(result.data["sections"]["active"]))
        self.assertNotIn("feed", str(result.data).lower())
        self.assertNotIn("portfolio", str(result.data).lower())
        self.assertNotIn("media_bindings", str(row))

    def test_productions_durable_and_edition_remain_distinct(self):
        self.space.archetype = SpaceArchetype.MEDIA
        self.space.save(update_fields=["archetype", "updated_at"])
        production = self.activity("Journal du soir")
        edition = Occurrence.objects.create(
            activity=production, label="Édition du lundi",
            start_at=timezone.now() + timedelta(days=3),
            end_at=timezone.now() + timedelta(days=3, hours=1),
            status=OccurrenceStatus.SCHEDULED,
        )
        Offer.objects.create(
            activity=production, name="Billet d'enregistrement",
            status=OfferStatus.ACTIVE,
        )
        self.client.force_authenticate(self.owner)
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200, result.data)
        world = result.data["business_world"]
        self.assertEqual(world["preferred_language"], "Productions")
        self.assertEqual(
            [g["identity"] for g in world["reading_groups"]],
            ["realizations", "productions", "related"],
        )
        self.assertEqual(
            result.data["presentation"]["section_order"],
            ["upcoming", "activities", "offers"],
        )
        self.assertEqual(
            result.data["presentation"]["next_occurrence_label"], "Prochaine édition"
        )
        production_row = result.data["sections"]["activities"]["items"][0]
        self.assertEqual(
            production_row["context"]["next_occurrence"]["id"], str(edition.pk)
        )
        self.assertEqual(production_row["source"]["id"], str(production.pk))
        self.assertNotIn("media_bindings", production_row)
        self.assertNotIn("feed", str(result.data).lower())

    def test_creative_calm_keeps_durable_creation_without_false_activity(self):
        creation = self.activity("Œuvre durable")
        self.client.force_authenticate(self.owner)
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(
            [g["identity"] for g in result.data["business_world"]["reading_groups"]],
            ["creations"],
        )
        self.assertIn(
            "créations durables", result.data["presentation"]["calm_message"]
        )
        self.assertEqual(result.data["sections"]["activities"]["items"][0]["source"]["id"],
                         str(creation.pk))
        self.assertNotIn("media_bindings", str(result.data))

    def test_published_recognition_is_contextual_and_revocable(self):
        creation = self.activity("Couverture réelle")
        draft = self.media_use(creation, publish=False, label="Visuel brouillon privé")
        self.client.force_authenticate(self.owner)
        result = self.client.get(self.url)
        row = result.data["sections"]["activities"]["items"][0]
        self.assertNotIn("media_bindings", row)
        publish_presentation_media(actor=self.owner, media_use=draft)
        fresh = self.client.get(self.url)
        row = fresh.data["sections"]["activities"]["items"][0]
        binding = row["media_bindings"][0]
        self.assertEqual(binding["owner"], row["source"])
        self.assertEqual(binding["purpose"], "recognize")
        self.assertEqual(binding["label"], "Visuel brouillon privé")
        self.assertEqual(
            binding["url"],
            reverse("presentations:published-media-file", kwargs={"use_id": draft.pk}),
        )
        self.assertNotIn("private_file", str(row))
        response = self.client.get(binding["url"])
        self.assertEqual(response.status_code, 200)
        response.close()
        retire_presentation_media(actor=self.owner, media_use=draft)
        after = self.client.get(self.url)
        self.assertNotIn(
            "media_bindings", after.data["sections"]["activities"]["items"][0]
        )
        self.assertEqual(self.client.get(binding["url"]).status_code, 404)

    def test_media_for_an_occurrence_does_not_leak_to_parent_or_sibling(self):
        self.space.archetype = SpaceArchetype.MEDIA
        self.space.save(update_fields=["archetype", "updated_at"])
        production = self.activity("Série documentaire")
        now = timezone.now()
        episode = Occurrence.objects.create(
            activity=production, label="Épisode 1",
            start_at=now + timedelta(days=2),
            end_at=now + timedelta(days=2, hours=1),
            status=OccurrenceStatus.SCHEDULED,
        )
        sibling = Occurrence.objects.create(
            activity=production, label="Épisode 2",
            start_at=now + timedelta(days=4),
            end_at=now + timedelta(days=4, hours=1),
            status=OccurrenceStatus.SCHEDULED,
        )
        use = self.media_use(
            production, occurrence=episode,
            label="Visuel spécifique épisode 1"
        )
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn(
            "media_bindings", response.data["sections"]["activities"]["items"][0]
        )
        entries = {
            r["source"]["id"]: r
            for r in response.data["sections"]["upcoming"]["items"]
        }
        self.assertIn("media_bindings", entries[str(episode.pk)])
        self.assertEqual(
            entries[str(episode.pk)]["media_bindings"][0]["resource_ref"],
            f"presentation_media_use:{use.pk}",
        )
        self.assertNotIn("media_bindings", entries[str(sibling.pk)])

    def test_private_space_keeps_media_delivery_private_in_work(self):
        creation = self.activity("Œuvre interne")
        use = self.media_use(creation)
        self.space.public_profile = False
        self.space.save(update_fields=["public_profile", "updated_at"])
        self.client.force_authenticate(self.owner)
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertIn("Œuvre interne", str(result.data))
        self.assertNotIn("media_bindings", str(result.data))
        self.assertEqual(
            self.client.get(
                reverse("presentations:published-media-file",
                        kwargs={"use_id": use.pk})
            ).status_code, 404
        )

    def test_limited_mandate_cannot_see_other_production_or_media(self):
        self.space.archetype = SpaceArchetype.MEDIA
        self.space.save(update_fields=["archetype", "updated_at"])
        allowed = self.activity("Édition autorisée")
        foreign = self.activity("Édition privée d'autre mandat")
        self.media_use(foreign, label="Visuel de l'édition interdite")
        grant_activity_role(
            profile=self.viewer, activity=allowed,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_authenticate(self.viewer)
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data["business_world"]["authority_scope"],
                         "activity_limited")
        self.assertIn("Édition autorisée", str(result.data))
        self.assertNotIn("Édition privée", str(result.data))
        self.assertNotIn("Visuel de l'édition interdite", str(result.data))
        self.assertEqual(
            result.data["business_world"]["perspectives"][0]["coverage_state"],
            "partial",
        )

    def test_creative_and_media_web_use_owner_handoff_and_real_media(self):
        creation = self.activity("Œuvre photographique")
        media = self.media_use(creation, label="Image de l'œuvre")
        self.web.force_login(self.owner)
        result = self.web.get(self.web_url)
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, "Créations durables")
        self.assertContains(result, "Voir la création")
        self.assertContains(result, "Image de l&#x27;œuvre")
        self.assertContains(
            result, reverse(
                "presentations:published-media-file",
                kwargs={"use_id": media.pk},
            )
        )
        self.assertContains(result, 'data-work-recognition="activity:')
        self.space.archetype = SpaceArchetype.MEDIA
        self.space.save(update_fields=["archetype", "updated_at"])
        media_result = self.web.get(self.web_url)
        self.assertEqual(media_result.status_code, 200)
        self.assertContains(media_result, "Productions durables")
        self.assertContains(media_result, "Voir la production")
        self.assertNotContains(media_result, "Publication générique")
