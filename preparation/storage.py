from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateResourceStorage(FileSystemStorage):
    """Private storage for preparation resources; files have no public URL."""

    def __init__(self):
        location = Path(settings.MEDIA_ROOT).parent / "private_resources"
        super().__init__(location=location, base_url=None)

    def url(self, name):
        raise ValueError("Les Resources privées n'ont pas d'URL publique.")


private_resource_storage = PrivateResourceStorage()
