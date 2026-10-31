"""Storage for new presentation images, isolated from publicly served MEDIA_ROOT."""
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivatePresentationStorage(FileSystemStorage):
    """No direct storage URLs: published uses cross the authorized delivery view."""

    def __init__(self):
        location = Path(settings.MEDIA_ROOT).parent / "private_presentation_assets"
        super().__init__(location=location, base_url=None)

    def url(self, name):
        raise ValueError("Les médias privés de Présentation n'ont pas d'URL directe.")


private_presentation_storage = PrivatePresentationStorage()
