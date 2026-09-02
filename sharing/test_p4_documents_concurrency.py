import threading
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from activities.models import Activity, ActivityStatus, ActivityVisibility
from journeys.collaboration_models import JourneyArtifactKind
from journeys.models import Journey, WorkflowKind

from .document_services import absorb_capture_into_journey, create_inbound_capture
from .inbound_models import InboundCaptureSourceKind


User = get_user_model()


def run_pair(fn):
    barrier = threading.Barrier(2)
    outcomes = []
    lock = threading.Lock()

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            outcome = ("ok", fn())
        except Exception as exc:
            outcome = ("error", exc)
        finally:
            connections.close_all()
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    if any(thread.is_alive() for thread in threads):
        raise AssertionError("Concurrent P4 absorption worker did not terminate.")
    return outcomes


@skipUnless(connection.vendor == "postgresql", "P4 inbound absorption concurrency requires PostgreSQL")
class P4InboundConcurrencyTests(TransactionTestCase):
    serialized_rollback = True

    def setUp(self):
        self.owner = User.objects.create_user(username="p4-concurrency-owner", password="x")
        activity = Activity.objects.create(
            owner_profile=self.owner,
            created_by=self.owner,
            title="P4 concurrency service",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.journey = Journey.objects.create(
            initiated_by=self.owner,
            beneficiary=self.owner,
            activity=activity,
            workflow=WorkflowKind.SERVICE,
        )
        capture = create_inbound_capture(
            actor=self.owner,
            source_kind=InboundCaptureSourceKind.FILE,
            uploaded_file=SimpleUploadedFile(
                "cv.pdf",
                b"%PDF-1.4\n% concurrency\n",
                content_type="application/pdf",
            ),
        )
        self.capture_id = capture.pk
        self.owner_id = self.owner.pk
        self.journey_id = self.journey.pk

    def test_two_simultaneous_absorptions_create_one_artifact(self):
        def absorb():
            actor = User.objects.get(pk=self.owner_id)
            return absorb_capture_into_journey(
                actor=actor,
                capture_id=self.capture_id,
                journey_id=self.journey_id,
                kind=JourneyArtifactKind.CV,
                title="CV concurrent",
            ).pk

        outcomes = run_pair(absorb)
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 2, outcomes)
        artifact_ids = {value for kind, value in outcomes if kind == "ok"}
        self.assertEqual(len(artifact_ids), 1, outcomes)
        self.assertEqual(Journey.objects.get(pk=self.journey_id).artifacts.count(), 1)
