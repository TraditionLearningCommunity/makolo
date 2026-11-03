import uuid

from django.test import SimpleTestCase
from django.urls import reverse

from presentations.media_selectors import ResolvedPresentationMedia

from .media_bindings import apply_recognition_media


class DiscoveryPresentationMediaBindingTests(SimpleTestCase):
    def setUp(self):
        self.activity_id = str(uuid.uuid4())
        self.occurrence_id = str(uuid.uuid4())

    def _projection(self):
        return {
            "identity": {"resource": {"kind": "activity", "id": self.activity_id}},
            "representation": {"kind": "route", "image_url": "/media/existing-event.png"},
            "media_bindings": [
                {
                    "resource": {"url": "/media/existing-event.png"},
                    "target": {"kind": "activity", "id": self.activity_id},
                    "purpose": "RECOGNIZE",
                }
            ],
        }

    def _media(self, *, occurrence_id=None, position=0):
        return ResolvedPresentationMedia(
            use_id=str(uuid.uuid4()), asset_id=str(uuid.uuid4()),
            activity_id=self.activity_id, occurrence_id=occurrence_id,
            purpose="recognize", mime_type="image/png",
            alt_text="Lieu de cette possibilité", position=position,
        )

    def test_public_media_populates_image_and_binding_from_same_use(self):
        media = self._media()
        projection = apply_recognition_media(self._projection(), [media])
        url = reverse("presentations:published-media-file", kwargs={"use_id": media.use_id})
        self.assertEqual(projection["representation"]["image_url"], url)
        self.assertEqual(projection["media_bindings"][0]["resource"]["url"], url)
        self.assertEqual(projection["media_bindings"][0]["purpose"], "RECOGNIZE")
        self.assertEqual(projection["media_bindings"][0]["target"]["id"], self.activity_id)
        self.assertEqual(projection["media_bindings"][0]["resource"]["alt_text"], media.alt_text)
        self.assertEqual(projection["media_bindings"][1]["resource"]["url"], "/media/existing-event.png")

    def test_occurrence_specific_media_never_leaks_to_other_occurrence(self):
        common = self._media(position=5)
        scoped = self._media(occurrence_id=self.occurrence_id, position=9)
        another = self._media(occurrence_id=str(uuid.uuid4()), position=0)
        result = apply_recognition_media(
            self._projection(), [common, another, scoped],
            occurrence_id=self.occurrence_id,
        )
        self.assertEqual(result["media_bindings"][0]["resource"]["id"], scoped.use_id)
        self.assertEqual(result["media_bindings"][1]["resource"]["id"], common.use_id)
        self.assertNotIn(
            another.use_id,
            [row["resource"].get("id") for row in result["media_bindings"]],
        )

    def test_no_explicit_media_preserves_existing_fallback(self):
        original = self._projection()
        result = apply_recognition_media(original, [])
        self.assertEqual(result["representation"]["kind"], "route")
        self.assertEqual(result["representation"]["image_url"], "/media/existing-event.png")
        self.assertEqual(len(result["media_bindings"]), 1)

    def test_projection_bounds_explicit_gallery(self):
        result = apply_recognition_media(self._projection(), [
            self._media(position=index) for index in range(18)
        ])
        self.assertEqual(len(result["media_bindings"]), 7)
