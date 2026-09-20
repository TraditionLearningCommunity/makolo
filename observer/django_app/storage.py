import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateObserverArtifactStorage(FileSystemStorage):
    """Private storage for external observation bytes.

    Files live outside MEDIA_ROOT and never expose a public storage URL. The
    location is resolved from settings at access time so tests/deployments can
    override it without rebuilding model fields.
    """

    def __init__(self):
        super().__init__(location=None, base_url=None)

    @property
    def base_location(self):
        return str(settings.MAKOLO_OBSERVER_ARTIFACT_ROOT)

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError("Les artefacts Observer n'ont pas d'URL publique.")


private_observer_artifact_storage = PrivateObserverArtifactStorage()
