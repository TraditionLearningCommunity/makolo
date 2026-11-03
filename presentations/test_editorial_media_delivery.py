"""New MPS editorial media never receives a direct public storage URL."""
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings

from accounts.models import UserProfile
from activities.models import ActivityStatus
from activities.services import create_activity
from presentations.asset_models import PresentationAsset
from presentations.catalog import ensure_builtin_catalog
from presentations.enums import PresentationPurpose
from presentations.services import (
    configure_activity_presentation, publish_activity_presentation,
)
from presentations.views import _editorial_from_post


class EditorialProtectedMediaTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        media_override = override_settings(MEDIA_ROOT=self.tmp.name)
        media_override.enable()
        self.addCleanup(media_override.disable)
        self.owner = get_user_model().objects.create_user(
            username="mps-editorial-owner", password="StrongPass2026!",
        )
        UserProfile.objects.create(
            user=self.owner, public_profile=True, searchable=True,
        )
        self.activity = create_activity(
            owner_profile=self.owner, created_by=self.owner,
            title="Image éditoriale", status=ActivityStatus.PUBLISHED,
        )

    def test_new_editorial_upload_uses_authorized_file_route(self):
        request = RequestFactory().post(
            "/unused/",
            {"hero_image": SimpleUploadedFile(
                "hero.png", bytes.fromhex("89504e470d0a1a0a") + b"test",
                content_type="image/png",
            )},
        )
        request.user = self.owner
        editorial = _editorial_from_post(
            request, PresentationPurpose.PUBLIC_PAGE, activity=self.activity,
        )
        url = editorial["hero_image"]
        self.assertIn("/presentation/media/editorial/assets/", url)
        self.assertNotIn("/media/presentations/assets/", url)
        asset = PresentationAsset.objects.latest("created_at")
        self.addCleanup(
            lambda: asset.private_file.storage.delete(asset.private_file.name)
            if asset.private_file else None
        )
        self.assertFalse(bool(asset.file))
        self.assertTrue(bool(asset.private_file))
        self.assertTrue(asset.private_file.storage.exists(asset.private_file.name))
        self.assertEqual(self.client.get(url).status_code, 404)

        templates, themes = ensure_builtin_catalog(actor=self.owner)
        binding = configure_activity_presentation(
            actor=self.owner, activity=self.activity,
            purpose=PresentationPurpose.PUBLIC_PAGE,
            template_version=templates["makolo-essential"],
            theme_version=themes["makolo-violet"],
            editorial_data=editorial,
        )
        # The owner can preview a draft, but the public cannot.
        self.client.force_login(self.owner)
        preview = self.client.get(url)
        self.assertEqual(preview.status_code, 200)
        preview.close()
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 404)

        publish_activity_presentation(actor=self.owner, presentation=binding)
        published = self.client.get(url)
        self.assertEqual(published.status_code, 200)
        self.assertEqual(published["Cache-Control"], "private, no-store, max-age=0")
        published.close()

        privacy = self.owner.profile
        privacy.public_profile = False
        privacy.save(update_fields=["public_profile"])
        self.assertEqual(self.client.get(url).status_code, 404)
