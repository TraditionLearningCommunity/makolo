from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateArtifactStorage(FileSystemStorage):
    """Django storage for private Journey artifacts.

    T31 deliberately keeps private files outside MEDIA_ROOT so DEBUG's static
    media helper cannot expose them by path. The storage has no public URL;
    reads must cross an authorized server-side boundary.
    """

    def __init__(self):
        location = Path(settings.MEDIA_ROOT).parent / "private_media"
        super().__init__(location=location, base_url=None)

    def url(self, name):
        raise ValueError("Les artifacts Journey privés n'ont pas d'URL publique.")


private_artifact_storage = PrivateArtifactStorage()
