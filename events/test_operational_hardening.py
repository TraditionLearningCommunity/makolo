from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from events.validators import validate_event_cover


class EventCoverOperationalValidationTests(SimpleTestCase):
    def test_event_cover_rejects_corrupt_image(self):
        upload = SimpleUploadedFile(
            "cover.webp",
            b"not-a-real-image",
            content_type="image/webp",
        )
        with self.assertRaises(ValidationError):
            validate_event_cover(upload)

    def test_event_cover_accepts_valid_image(self):
        buffer = BytesIO()
        Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")
        upload = SimpleUploadedFile(
            "cover.png",
            buffer.getvalue(),
            content_type="image/png",
        )
        validate_event_cover(upload)
