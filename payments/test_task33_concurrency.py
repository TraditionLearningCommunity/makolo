import threading
from decimal import Decimal
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from activities.models import Activity
from authorization.services import grant_activity_role
from journeys.collaboration_models import JourneyArtifactKind, JourneyAssignmentResponsibility
from journeys.collaboration_services import assign_journey, create_artifact
from services.models import ServiceKind
from services.services import create_service_details, create_service_journey

from .models import Payment, PaymentEvidence, PaymentEvidenceStatus, PaymentObligationProcessingMode, PaymentObligationReason, PaymentObligationStatus, PaymentProvider, PaymentStatus
from .obligation_services import create_payment_obligation, submit_payment_evidence, verify_payment_evidence, reject_payment_evidence
from .services import cancel_payment, complete_payment, complete_sandbox_payment, initiate_obligation_payment, refund_payment


User = get_user_model()


def run_pair(first, second):
    barrier = threading.Barrier(2)
    outcomes = []
    lock = threading.Lock()

    def worker(fn):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            result = fn()
            outcome = ("ok", result)
        except Exception as exc:
            outcome = ("error", exc)
        finally:
            connections.close_all()
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=worker, args=(first,)), threading.Thread(target=worker, args=(second,))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=25)
    if any(thread.is_alive() for thread in threads):
        raise AssertionError("Concurrent T33 payment worker did not terminate.")
    return outcomes


def pdf_upload(name):
    return SimpleUploadedFile(name, b"%PDF-1.4\nT33\n%%EOF", content_type="application/pdf")


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
@skipUnless(connection.vendor == "postgresql", "T33 payment concurrency requires PostgreSQL")
class PaymentObligationConcurrencyTests(TransactionTestCase):
    serialized_rollback = True
    reset_sequences = False

    def setUp(self):
        self.manager = User.objects.create_user(username="t33-conc-manager", email="t33-conc-manager@example.com", password="x", is_staff=True)
        self.beneficiary = User.objects.create_user(username="t33-conc-beneficiary", email="t33-conc-beneficiary@example.com", password="x")
        self.activity = Activity.objects.create(owner_profile=self.manager, created_by=self.manager, title="T33 payment concurrency")
        grant_activity_role(profile=self.manager, activity=self.activity)
        service = create_service_details(activity=self.activity, actor=self.manager, service_kind=ServiceKind.APPLICATION_SUPPORT)
        self.journey = create_service_journey(service=service, initiated_by=self.beneficiary, beneficiary=self.beneficiary)
        assign_journey(journey=self.journey, profile=self.manager, responsibility=JourneyAssignmentResponsibility.LEAD, is_primary=True, assigned_by=self.manager)

    def make_obligation(self, key="t33:concurrency", mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER):
        return create_payment_obligation(
            journey=self.journey,
            reason=PaymentObligationReason.SERVICE_PROCESS,
            label="T33 concurrent fee",
            amount=Decimal("25.00"),
            currency="USD",
            processing_mode=mode,
            external_payee_name="External institution",
            created_by=self.manager,
            source_key=key,
        )

    def payment_attempt(self, obligation_id, key):
        from .models import PaymentObligation
        obligation = PaymentObligation.objects.get(pk=obligation_id)
        actor = User.objects.get(pk=self.beneficiary.pk)
        return initiate_obligation_payment(obligation=obligation, actor=actor, provider=PaymentProvider.SANDBOX, method="card", idempotency_key=key).pk

    def test_two_attempts_can_be_created_concurrently(self):
        obligation = self.make_obligation("t33:concurrent:attempts")
        outcomes = run_pair(
            lambda: self.payment_attempt(obligation.pk, "conc-attempt-a"),
            lambda: self.payment_attempt(obligation.pk, "conc-attempt-b"),
        )
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 2)
        self.assertEqual(Payment.objects.filter(obligation=obligation).count(), 2)

    def test_two_successes_leave_exactly_one_succeeded(self):
        obligation = self.make_obligation("t33:concurrent:success")
        p1 = initiate_obligation_payment(obligation=obligation, actor=self.beneficiary, provider=PaymentProvider.SANDBOX, method="card", idempotency_key="success-a")
        p2 = initiate_obligation_payment(obligation=obligation, actor=self.beneficiary, provider=PaymentProvider.SANDBOX, method="card", idempotency_key="success-b")
        outcomes = run_pair(
            lambda: complete_payment(payment=Payment.objects.get(pk=p1.pk), provider_reference="CONC-SUCCESS-A").pk,
            lambda: complete_payment(payment=Payment.objects.get(pk=p2.pk), provider_reference="CONC-SUCCESS-B").pk,
        )
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 1)
        self.assertEqual(Payment.objects.filter(obligation=obligation, status=PaymentStatus.SUCCEEDED).count(), 1)
        obligation.refresh_from_db()
        self.assertEqual(obligation.status, PaymentObligationStatus.SATISFIED)

    def test_duplicate_sandbox_completion_is_idempotent(self):
        obligation = self.make_obligation("t33:concurrent:sandbox")
        payment = initiate_obligation_payment(obligation=obligation, actor=self.beneficiary, provider=PaymentProvider.SANDBOX, method="card", idempotency_key="sandbox-dup")
        outcomes = run_pair(
            lambda: complete_sandbox_payment(payment=Payment.objects.get(pk=payment.pk), actor=User.objects.get(pk=self.beneficiary.pk)).status,
            lambda: complete_sandbox_payment(payment=Payment.objects.get(pk=payment.pk), actor=User.objects.get(pk=self.beneficiary.pk)).status,
        )
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 2)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCEEDED)

    def test_success_vs_cancel_never_leaves_impossible_state(self):
        obligation = self.make_obligation("t33:concurrent:cancel")
        payment = initiate_obligation_payment(obligation=obligation, actor=self.beneficiary, provider=PaymentProvider.SANDBOX, method="card", idempotency_key="success-vs-cancel")
        run_pair(
            lambda: complete_payment(payment=Payment.objects.get(pk=payment.pk), provider_reference="SUCCESS-VS-CANCEL").status,
            lambda: cancel_payment(payment=Payment.objects.get(pk=payment.pk), actor=User.objects.get(pk=self.beneficiary.pk)).status,
        )
        payment.refresh_from_db()
        obligation.refresh_from_db()
        self.assertIn(payment.status, {PaymentStatus.SUCCEEDED, PaymentStatus.CANCELLED})
        expected = PaymentObligationStatus.SATISFIED if payment.status == PaymentStatus.SUCCEEDED else PaymentObligationStatus.PENDING
        self.assertEqual(obligation.status, expected)

    def test_success_vs_refund_serializes_lifecycle(self):
        obligation = self.make_obligation("t33:concurrent:refund")
        payment = initiate_obligation_payment(obligation=obligation, actor=self.beneficiary, provider=PaymentProvider.SANDBOX, method="card", idempotency_key="success-vs-refund")
        run_pair(
            lambda: complete_payment(payment=Payment.objects.get(pk=payment.pk), provider_reference="SUCCESS-VS-REFUND").status,
            lambda: refund_payment(payment=Payment.objects.get(pk=payment.pk), actor=User.objects.get(pk=self.manager.pk), idempotency_key="concurrent-refund").status,
        )
        payment.refresh_from_db()
        obligation.refresh_from_db()
        self.assertIn(payment.status, {PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED})
        if payment.status == PaymentStatus.REFUNDED:
            self.assertEqual(obligation.status, PaymentObligationStatus.REFUNDED)

    def test_evidence_verify_and_verify_vs_reject_are_serialized(self):
        obligation = self.make_obligation("t33:concurrent:evidence", PaymentObligationProcessingMode.EXTERNAL)
        artifact = create_artifact(journey=self.journey, uploaded_file=pdf_upload("proof.pdf"), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.PAYMENT_RECEIPT, title="Proof")
        evidence = submit_payment_evidence(obligation=obligation, artifact=artifact, actor=self.beneficiary, paid_at=timezone.now())
        outcomes = run_pair(
            lambda: verify_payment_evidence(evidence=PaymentEvidence.objects.get(pk=evidence.pk), actor=User.objects.get(pk=self.manager.pk)).status,
            lambda: verify_payment_evidence(evidence=PaymentEvidence.objects.get(pk=evidence.pk), actor=User.objects.get(pk=self.manager.pk)).status,
        )
        self.assertEqual(sum(kind == "ok" for kind, _ in outcomes), 2)
        evidence.refresh_from_db()
        self.assertEqual(evidence.status, PaymentEvidenceStatus.VERIFIED)

        obligation2 = self.make_obligation("t33:concurrent:evidence-race", PaymentObligationProcessingMode.EXTERNAL)
        artifact2 = create_artifact(journey=self.journey, uploaded_file=pdf_upload("proof2.pdf"), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.PAYMENT_RECEIPT, title="Proof 2")
        evidence2 = submit_payment_evidence(obligation=obligation2, artifact=artifact2, actor=self.beneficiary, paid_at=timezone.now())
        run_pair(
            lambda: verify_payment_evidence(evidence=PaymentEvidence.objects.get(pk=evidence2.pk), actor=User.objects.get(pk=self.manager.pk)).status,
            lambda: reject_payment_evidence(evidence=PaymentEvidence.objects.get(pk=evidence2.pk), actor=User.objects.get(pk=self.manager.pk), review_note="reject").status,
        )
        evidence2.refresh_from_db()
        self.assertIn(evidence2.status, {PaymentEvidenceStatus.VERIFIED, PaymentEvidenceStatus.REJECTED})
        self.assertEqual(PaymentEvidence.objects.filter(pk=evidence2.pk).count(), 1)

    def test_two_distinct_evidence_submissions_are_preserved(self):
        obligation = self.make_obligation("t33:concurrent:two-evidence", PaymentObligationProcessingMode.EXTERNAL)
        a1 = create_artifact(journey=self.journey, uploaded_file=pdf_upload("p1.pdf"), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.PAYMENT_RECEIPT, title="P1")
        a2 = create_artifact(journey=self.journey, uploaded_file=pdf_upload("p2.pdf"), uploaded_by=self.beneficiary, kind=JourneyArtifactKind.PAYMENT_RECEIPT, title="P2")
        run_pair(
            lambda: submit_payment_evidence(obligation=type(obligation).objects.get(pk=obligation.pk), artifact=type(a1).objects.get(pk=a1.pk), actor=User.objects.get(pk=self.beneficiary.pk), paid_at=timezone.now()).pk,
            lambda: submit_payment_evidence(obligation=type(obligation).objects.get(pk=obligation.pk), artifact=type(a2).objects.get(pk=a2.pk), actor=User.objects.get(pk=self.beneficiary.pk), paid_at=timezone.now()).pk,
        )
        self.assertEqual(PaymentEvidence.objects.filter(obligation=obligation).count(), 2)
