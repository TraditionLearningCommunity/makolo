"""P2 explicit presentation media-use regression tests."""
from datetime import timedelta
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.utils import timezone

from activities.models import ActivityStatus
from activities.services import create_activity, create_occurrence, update_activity_common
from authorization.services import grant_activity_role
from organizations.services import create_organization
from .asset_models import PresentationAsset
from .enums import Provenance
from .media_models import PresentationMediaPurpose, PresentationMediaState, PresentationMediaUse
from .media_selectors import public_presentation_media_for_activities
from .media_services import (
    associate_presentation_media, publish_presentation_media,
    retire_presentation_media, reorder_presentation_media, replace_presentation_media,
)

User = get_user_model()


class PresentationMediaUseTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.storage_override = override_settings(MEDIA_ROOT=self.tmp.name)
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)
        self.owner = User.objects.create_user(username="p2-owner", email="p2-owner@example.test", password="StrongPass2026!")
        self.other = User.objects.create_user(username="p2-other", email="p2-other@example.test", password="StrongPass2026!")
        self.activity = create_activity(
            owner_profile=self.owner, created_by=self.owner, title="Atelier P2",
            status=ActivityStatus.PUBLISHED,
        )
        self.occurrence = create_occurrence(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=3),
            timezone="Africa/Lubumbashi",
        )
        self.asset = self._asset("image1.png")

    def _asset(self, filename):
        asset = PresentationAsset(
            provenance=Provenance.USER, owner_profile=self.owner,
            uploaded_by=self.owner, mime_type="image/png", size=4,
            checksum="a" * 64,
        )
        asset.file.save(filename, ContentFile(b"test"), save=False)
        asset.save()
        return asset

    def _associate(self, **kwargs):
        return associate_presentation_media(
            actor=self.owner, activity=self.activity, asset=self.asset,
            purpose=PresentationMediaPurpose.RECOGNIZE, alt_text="Affiche de l’atelier",
            **kwargs,
        )

    def test_draft_is_not_public_and_publishing_is_explicit(self):
        use = self._associate()
        self.assertEqual(public_presentation_media_for_activities([self.activity])[str(self.activity.pk)], [])
        publish_presentation_media(actor=self.owner, media_use=use)
        found = public_presentation_media_for_activities([self.activity])[str(self.activity.pk)]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].asset_id, str(self.asset.pk))
        self.assertFalse(hasattr(found[0], "url"))
        retire_presentation_media(actor=self.owner, media_use=use)
        self.assertEqual(public_presentation_media_for_activities([self.activity])[str(self.activity.pk)], [])

    def test_unauthorized_actor_cannot_associate_publish_or_reorder(self):
        with self.assertRaises(PermissionDenied):
            associate_presentation_media(
                actor=self.other, activity=self.activity, asset=self.asset,
                purpose=PresentationMediaPurpose.RECOGNIZE, alt_text="Non autorisé",
            )
        use = self._associate()
        with self.assertRaises(PermissionDenied):
            publish_presentation_media(actor=self.other, media_use=use)
        with self.assertRaises(PermissionDenied):
            reorder_presentation_media(actor=self.other, media_use=use, position=3)
        self.assertEqual(use.state, PresentationMediaState.DRAFT)

    def test_asset_ownership_must_match_activity(self):
        foreign = create_activity(owner_profile=self.other, created_by=self.other, title="Autre Activity")
        with self.assertRaises(ValidationError):
            associate_presentation_media(
                actor=self.other, activity=foreign, asset=self.asset,
                purpose=PresentationMediaPurpose.RECOGNIZE, alt_text="Image étrangère",
            )

    def test_occurrence_cannot_cross_activity(self):
        foreign = create_activity(owner_profile=self.owner, created_by=self.owner, title="Autre Activity")
        occ = create_occurrence(activity=foreign, start_at=timezone.now() + timedelta(days=5), timezone="Africa/Lubumbashi")
        with self.assertRaises(ValidationError):
            self._associate(occurrence=occ)

    def test_occurrence_use_is_not_shared_without_explicit_context(self):
        use = self._associate(occurrence=self.occurrence)
        publish_presentation_media(actor=self.owner, media_use=use)
        none = public_presentation_media_for_activities([self.activity])
        self.assertEqual(none[str(self.activity.pk)], [])
        yes = public_presentation_media_for_activities([self.activity], occurrences=[self.occurrence])
        self.assertEqual(len(yes[str(self.activity.pk)]), 1)

    def test_unavailable_file_is_rejected_at_publication(self):
        use = self._associate()
        use.asset.file.storage.delete(use.asset.file.name)
        with self.assertRaises(ValidationError):
            publish_presentation_media(actor=self.owner, media_use=use)
        use.refresh_from_db()
        self.assertEqual(use.state, PresentationMediaState.DRAFT)

    def test_retired_media_can_be_replaced_without_republishing(self):
        use = self._associate()
        publish_presentation_media(actor=self.owner, media_use=use)
        replacement = replace_presentation_media(actor=self.owner, media_use=use, asset=self.asset)
        use.refresh_from_db()
        self.assertEqual(use.state, PresentationMediaState.RETIRED)
        self.assertEqual(replacement.state, PresentationMediaState.DRAFT)
        self.assertNotEqual(replacement.pk, use.pk)

    def test_selector_uses_bounded_queries(self):
        a2 = self._asset("image2.png")
        self._associate()
        associate_presentation_media(
            actor=self.owner, activity=self.activity, asset=a2,
            purpose=PresentationMediaPurpose.RECOGNIZE, alt_text="Deuxième affiche",
        )
        with self.assertNumQueries(1):
            public_presentation_media_for_activities([self.activity])

    def test_space_asset_requires_same_space(self):
        space = create_organization(creator=self.owner, name="Espace P2")
        space_activity = create_activity(
            space=space, created_by=self.owner, title="Atelier collectif",
            status=ActivityStatus.PUBLISHED,
        )
        space_asset = PresentationAsset(
            provenance=Provenance.SPACE, owner_space=space,
            uploaded_by=self.owner, mime_type="image/png", size=4,
            checksum="b" * 64,
        )
        space_asset.file.save("space.png", ContentFile(b"test"), save=False)
        space_asset.save()
        use = associate_presentation_media(
            actor=self.owner, activity=space_activity, asset=space_asset,
            purpose=PresentationMediaPurpose.RECOGNIZE, alt_text="Affiche de l’Espace",
        )
        publish_presentation_media(actor=self.owner, media_use=use)
        self.assertEqual(len(public_presentation_media_for_activities([space_activity])[str(space_activity.pk)]), 1)
        with self.assertRaises(ValidationError):
            associate_presentation_media(
                actor=self.owner, activity=self.activity, asset=space_asset,
                purpose=PresentationMediaPurpose.RECOGNIZE,
                alt_text="Asset appartenant à l’Espace",
            )

    def test_activity_manager_cannot_publish_another_users_space_asset(self):
        space = create_organization(creator=self.owner, name="Espace partagé P2")
        shared = create_activity(
            space=space, created_by=self.owner, title="Atelier Espace",
            status=ActivityStatus.PUBLISHED,
        )
        grant_activity_role(profile=self.other, activity=shared, granted_by=self.owner)
        asset = PresentationAsset(
            provenance=Provenance.SPACE, owner_space=space,
            uploaded_by=self.owner, mime_type="image/png", size=4,
            checksum="c" * 64,
        )
        asset.file.save("shared.png", ContentFile(b"test"), save=False)
        asset.save()
        with self.assertRaises(PermissionDenied):
            associate_presentation_media(
                actor=self.other, activity=shared, asset=asset,
                purpose=PresentationMediaPurpose.RECOGNIZE, alt_text="Confidentiel",
            )
        use = associate_presentation_media(
            actor=self.owner, activity=shared, asset=asset,
            purpose=PresentationMediaPurpose.RECOGNIZE, alt_text="Affiche autorisée",
        )
        with self.assertRaises(PermissionDenied):
            publish_presentation_media(actor=self.other, media_use=use)
        publish_presentation_media(actor=self.owner, media_use=use)

    def test_initial_published_state_cannot_bypass_service(self):
        with self.assertRaises(ValidationError):
            PresentationMediaUse.objects.create(
                activity=self.activity, asset=self.asset, created_by=self.owner,
                purpose=PresentationMediaPurpose.RECOGNIZE, alt_text="Affiche",
                state=PresentationMediaState.PUBLISHED, published_at=timezone.now(),
            )

    def test_retired_use_remains_unpublished(self):
        use = self._associate()
        publish_presentation_media(actor=self.owner, media_use=use)
        retire_presentation_media(actor=self.owner, media_use=use)
        with self.assertRaises(ValidationError):
            publish_presentation_media(actor=self.owner, media_use=use)

    def test_private_activity_not_exposed(self):
        use = self._associate()
        publish_presentation_media(actor=self.owner, media_use=use)
        update_activity_common(activity=self.activity, visibility="private")
        self.assertEqual(public_presentation_media_for_activities([self.activity]), {})
