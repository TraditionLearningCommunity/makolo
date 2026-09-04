import threading
import unittest
from datetime import datetime, timedelta, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from access.models import Access
from domain_events.contracts import DomainEventType
from domain_events.models import DomainEventConsumption, DomainEventConsumptionStatus
from domain_events.services import emit_domain_event, process_domain_events
from journeys.collaboration_models import (
    JourneyArtifact,
    JourneyArtifactKind,
    JourneyArtifactSensitivity,
)
from journeys.models import Journey
from notifications.models import Notification
from opportunities.models import (
    Opportunity,
    OpportunityKind,
    OpportunityPublicationStatus,
    OpportunityRequirement,
    OpportunityRequirementKind,
    OpportunityRevision,
    OpportunitySave,
)
from payments.models import Payment
from personal_assets.models import PersonalAsset, PersonalAssetUse, PersonalAssetVersion
from preparation.contextual_actions import (
    ContextualAction,
    ContextualActionIdentity,
    ContextualActionPriority,
    ContextualActionResult,
    ContextualActionability,
)
from preparation.proactive_preparation import NOTIFICATION_SIGNATURE_VERSION
from requirements.models import RequirementReuseApplication, RequirementReusePolicy, RequirementReuseSource
from services.models import ServiceRequirementAssessment, ServiceRequirementEvidence
from trust.models import Proof

from .proactive_models import ProactivePreparationCursor, ProactivePreparationWatchKind
from .proactive_preparation import (
    Evaluation,
    apply_evaluation,
    evaluate_saved_opportunity,
    run_proactive_preparation_cycle,
)


User = get_user_model()
NOW = datetime(2026, 9, 4, 1, 0, tzinfo=dt_timezone.utc)


def action(action_key, *, confirmation_required=False):
    return ContextualAction(
        identity=ContextualActionIdentity(
            source_domain="prepared_start",
            source_key="requirement:1",
            action_key=action_key,
            context_type="opportunity_revision",
            context_id="revision:1",
        ),
        kind="prepared_requirement.missing",
        priority=ContextualActionPriority.P1_REQUIRED,
        actionability=ContextualActionability.ACTIONABLE,
        reason_codes=("prepared_start.test",),
        label="Safe label",
        summary="Safe summary",
        observed_at=NOW,
        mandatory=True,
        confirmation_required=confirmation_required,
    )


def result(action_key, *, confirmation_required=False):
    primary = action(action_key, confirmation_required=confirmation_required)
    return ContextualActionResult(
        actions=(primary,),
        primary_attention=primary,
        primary_action=primary,
        observed_at=NOW,
    )


class ProactivePreparationCursorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="r3-user", email="r3-user@example.com")
        self.opportunity = Opportunity.objects.create(kind=OpportunityKind.JOB, created_by=self.user)
        self.saved = OpportunitySave.objects.create(profile=self.user, opportunity=self.opportunity)

    def evaluation(self, action_key, **kwargs):
        return Evaluation(
            result=result(action_key, **kwargs),
            watch_kind=ProactivePreparationWatchKind.OPPORTUNITY,
            recipient=self.user,
            opportunity_save=self.saved,
            revision_id="revision:1",
        )

    def test_cursor_model_is_registered_in_automation_app(self):
        from django.apps import apps

        self.assertIs(
            apps.get_model("automation", "ProactivePreparationCursor"),
            ProactivePreparationCursor,
        )

    def test_baseline_then_a_b_b_a_uses_monotonic_transition_sequence(self):
        baseline = apply_evaluation(self.evaluation("prepare_requirement"), observed_at=NOW)
        self.assertEqual(baseline.status, "baseline")
        cursor = ProactivePreparationCursor.objects.get(opportunity_save=self.saved)
        self.assertEqual(cursor.transition_sequence, 0)
        self.assertEqual(
            Notification.objects.filter(template_key="preparation.proactive").count(),
            0,
        )

        changed = apply_evaluation(
            self.evaluation("confirm_reuse", confirmation_required=True),
            observed_at=NOW,
        )
        self.assertTrue(changed.notification_created)
        cursor.refresh_from_db()
        self.assertEqual(cursor.transition_sequence, 1)
        self.assertEqual(
            Notification.objects.filter(template_key="preparation.proactive").count(),
            1,
        )

        same = apply_evaluation(
            self.evaluation("confirm_reuse", confirmation_required=True),
            observed_at=NOW,
        )
        self.assertEqual(same.status, "unchanged")
        cursor.refresh_from_db()
        self.assertEqual(cursor.transition_sequence, 1)

        reverted = apply_evaluation(self.evaluation("prepare_requirement"), observed_at=NOW)
        self.assertTrue(reverted.notification_created)
        cursor.refresh_from_db()
        self.assertEqual(cursor.transition_sequence, 2)
        keys = list(
            Notification.objects.filter(template_key="preparation.proactive")
            .order_by("created_at")
            .values_list("dedup_key", flat=True)
        )
        self.assertEqual(len(keys), 2)
        self.assertNotEqual(keys[0], keys[1])

    def test_unknown_signature_version_silently_rebaselines(self):
        apply_evaluation(self.evaluation("prepare_requirement"), observed_at=NOW)
        cursor = ProactivePreparationCursor.objects.get(opportunity_save=self.saved)
        cursor.signature_version = "r3-notification-v0"
        cursor.save(update_fields=["signature_version", "updated_at"])

        outcome = apply_evaluation(
            self.evaluation("confirm_reuse", confirmation_required=True),
            observed_at=NOW,
        )
        cursor.refresh_from_db()
        self.assertEqual(outcome.status, "rebaseline")
        self.assertEqual(cursor.signature_version, NOTIFICATION_SIGNATURE_VERSION)
        self.assertEqual(cursor.transition_sequence, 0)
        self.assertEqual(
            Notification.objects.filter(template_key="preparation.proactive").count(),
            0,
        )

    def test_cursor_rejects_wrong_recipient(self):
        other = User.objects.create_user(username="r3-other", email="r3-other@example.com")
        cursor = ProactivePreparationCursor(
            recipient=other,
            watch_kind=ProactivePreparationWatchKind.OPPORTUNITY,
            opportunity_save=self.saved,
            projection_signature="r2-result-v1:a",
            notification_signature="r3-notification-v1:a",
            signature_version=NOTIFICATION_SIGNATURE_VERSION,
        )
        with self.assertRaises(ValidationError):
            cursor.full_clean()

    def test_cursor_and_notification_metadata_contain_no_sensitive_payload(self):
        apply_evaluation(self.evaluation("prepare_requirement"), observed_at=NOW)
        apply_evaluation(
            self.evaluation("confirm_reuse", confirmation_required=True),
            observed_at=NOW,
        )
        cursor = ProactivePreparationCursor.objects.get(opportunity_save=self.saved)
        cursor_text = " ".join(
            str(getattr(cursor, field))
            for field in ("projection_signature", "notification_signature", "signature_version")
        ).lower()
        notification = Notification.objects.get(template_key="preparation.proactive")
        serialized = f"{notification.title} {notification.message} {notification.metadata}".lower()
        for forbidden in ("filename", "passport.pdf", "proof hash", "requirement text", "coordinates"):
            self.assertNotIn(forbidden, cursor_text)
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(
            set(notification.metadata),
            {"watch_kind", "transition_sequence", "opportunity_id", "revision_id"},
        )

    def test_owner_event_updates_cursor_without_duplicate_notification(self):
        apply_evaluation(self.evaluation("prepare_requirement"), observed_at=NOW)
        event = emit_domain_event(
            event_type=DomainEventType.OPPORTUNITY_REVISION_PUBLISHED,
            source_type="opportunity_revision",
            source_id="revision:2",
            idempotency_key="r3:test:revision-owner-covered",
            payload={
                "opportunity_id": str(self.opportunity.pk),
                "revision_id": "revision:2",
                "version": 2,
            },
            process_on_commit=False,
        )
        outcome = apply_evaluation(
            self.evaluation("confirm_reuse", confirmation_required=True),
            observed_at=NOW,
            domain_event=event,
            force_silent_rebaseline=True,
        )
        cursor = ProactivePreparationCursor.objects.get(opportunity_save=self.saved)
        self.assertTrue(outcome.material_changed)
        self.assertTrue(outcome.notification_suppressed)
        self.assertEqual(cursor.transition_sequence, 1)
        self.assertEqual(
            Notification.objects.filter(template_key="preparation.proactive").count(),
            0,
        )

    def test_autopilot_limit_zero_is_deterministic_and_bounded(self):
        stats = run_proactive_preparation_cycle(now=NOW, limit=0)
        self.assertEqual(
            stats,
            {
                "watches_checked": 0,
                "baselines_created": 0,
                "projection_changes": 0,
                "material_changes": 0,
                "notifications_created": 0,
                "notifications_suppressed": 0,
                "stale_watches_removed": 0,
            },
        )


class CanonicalSavedOpportunityR3Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="r3-canonical-opportunity",
            email="r3-canonical-opportunity@example.test",
        )
        self.opportunity = Opportunity.objects.create(
            kind=OpportunityKind.SCHOLARSHIP,
            created_by=self.user,
        )
        self.revision = self._revision(version=1, title="Version N")
        self.requirement = self._requirement(self.revision, key="r3-policy-n")
        self._publish(self.revision)
        self.saved = OpportunitySave.objects.create(profile=self.user, opportunity=self.opportunity)

    def _revision(self, *, version, title):
        return OpportunityRevision.objects.create(
            opportunity=self.opportunity,
            version=version,
            title=title,
            issuer_name="Institution test R3",
            timezone="Africa/Lubumbashi",
            deadline_at=timezone.now() + timedelta(days=30),
            created_by=self.user,
        )

    def _requirement(self, revision, *, key):
        requirement = OpportunityRequirement.objects.create(
            revision=revision,
            kind=OpportunityRequirementKind.DOCUMENT,
            title="CV test R3",
            is_mandatory=True,
            position=1,
        )
        RequirementReusePolicy.objects.create(
            requirement=requirement,
            key=key,
            source_type=RequirementReuseSource.LIBRARY,
            artifact_kind=JourneyArtifactKind.CV,
            require_not_expired=True,
            human_review_required=False,
        )
        return requirement

    def _publish(self, revision):
        published_at = timezone.now()
        OpportunityRevision.objects.filter(pk=revision.pk).update(published_at=published_at)
        Opportunity.objects.filter(pk=self.opportunity.pk).update(
            publication_status=OpportunityPublicationStatus.PUBLISHED,
            current_revision=revision,
            published_at=published_at,
        )
        self.opportunity.refresh_from_db()
        revision.refresh_from_db()

    def _library_candidate(self):
        asset = PersonalAsset.objects.create(
            controller=self.user,
            subject_profile=self.user,
            kind=JourneyArtifactKind.CV,
            title="Titre privé qui ne doit jamais sortir",
            sensitivity=JourneyArtifactSensitivity.NORMAL,
        )
        return PersonalAssetVersion.objects.create(
            asset=asset,
            version=1,
            file=SimpleUploadedFile("secret-r3-cv.pdf", b"%PDF-1.4\nr3"),
            mime_type="application/pdf",
            size=12,
            content_hash="b" * 64,
            expires_at=timezone.localdate() + timedelta(days=90),
            created_by=self.user,
        )

    def test_real_r1_missing_to_ready_transition_notifies_without_leaking_asset(self):
        initial = evaluate_saved_opportunity(self.saved)
        self.assertIsNotNone(initial)
        self.assertEqual(initial.result.primary_action.identity.action_key, "prepare_requirement")
        baseline = apply_evaluation(initial)
        self.assertEqual(baseline.status, "baseline")
        self.assertFalse(Journey.objects.exists())

        self._library_candidate()
        current = evaluate_saved_opportunity(self.saved)
        self.assertIsNotNone(current)
        self.assertIsNone(current.result.primary_action)
        outcome = apply_evaluation(current)

        self.assertTrue(outcome.material_changed)
        self.assertTrue(outcome.notification_created)
        notification = Notification.objects.get(template_key="preparation.proactive")
        rendered = f"{notification.title} {notification.message} {notification.metadata}".lower()
        self.assertNotIn("secret-r3-cv.pdf", rendered)
        self.assertNotIn("titre privé", rendered)
        self.assertNotIn("bbbbbbbb", rendered)
        self.assertFalse(Journey.objects.exists())

    def test_real_projection_has_no_business_side_effects(self):
        counters = {
            Journey: Journey.objects.count(),
            JourneyArtifact: JourneyArtifact.objects.count(),
            PersonalAssetUse: PersonalAssetUse.objects.count(),
            RequirementReuseApplication: RequirementReuseApplication.objects.count(),
            ServiceRequirementAssessment: ServiceRequirementAssessment.objects.count(),
            ServiceRequirementEvidence: ServiceRequirementEvidence.objects.count(),
            Proof: Proof.objects.count(),
            Payment: Payment.objects.count(),
            Access: Access.objects.count(),
        }
        evaluation = evaluate_saved_opportunity(self.saved)
        apply_evaluation(evaluation)
        for model, before in counters.items():
            self.assertEqual(model.objects.count(), before, model.__name__)

    def test_autopilot_discovers_saved_opportunity_as_silent_baseline(self):
        stats = run_proactive_preparation_cycle(limit=1)
        self.assertEqual(stats["watches_checked"], 1)
        self.assertEqual(stats["baselines_created"], 1)
        self.assertEqual(stats["notifications_created"], 0)
        cursor = ProactivePreparationCursor.objects.get(opportunity_save=self.saved)
        self.assertEqual(cursor.recipient_id, self.user.pk)
        self.assertEqual(cursor.transition_sequence, 0)

    def test_revision_n_plus_one_reuses_same_watch_and_suppresses_owner_duplicate(self):
        baseline = evaluate_saved_opportunity(self.saved)
        apply_evaluation(baseline)
        cursor = ProactivePreparationCursor.objects.get(opportunity_save=self.saved)
        cursor_id = cursor.pk

        revision_n1 = self._revision(version=2, title="Version N+1")
        self._requirement(revision_n1, key="r3-policy-n1")
        self._publish(revision_n1)
        event = emit_domain_event(
            event_type=DomainEventType.OPPORTUNITY_REVISION_PUBLISHED,
            source_type="opportunity_revision",
            source_id=revision_n1.pk,
            idempotency_key="r3:canonical:revision-n1",
            payload={
                "opportunity_id": str(self.opportunity.pk),
                "revision_id": str(revision_n1.pk),
                "version": 2,
            },
            process_on_commit=False,
        )
        process_domain_events(event_ids=[event.pk], limit=1)

        cursor = ProactivePreparationCursor.objects.get(pk=cursor_id)
        self.assertEqual(cursor.opportunity_save_id, self.saved.pk)
        self.assertEqual(cursor.transition_sequence, 1)
        self.assertEqual(
            Notification.objects.filter(template_key="preparation.proactive").count(),
            0,
        )

        self._library_candidate()
        current = evaluate_saved_opportunity(self.saved)
        self.assertEqual(current.revision_id, str(revision_n1.pk))
        outcome = apply_evaluation(current)
        self.assertTrue(outcome.notification_created)
        cursor.refresh_from_db()
        self.assertEqual(cursor.transition_sequence, 2)


class ProactivePreparationDomainEventTests(TestCase):
    def test_at_least_once_consumption_keeps_single_r3_consumption(self):
        user = User.objects.create_user(username="r3-event", email="r3-event@example.com")
        opportunity = Opportunity.objects.create(kind=OpportunityKind.JOB, created_by=user)
        saved = OpportunitySave.objects.create(profile=user, opportunity=opportunity)
        evaluation = Evaluation(
            result=result("prepare_requirement"),
            watch_kind=ProactivePreparationWatchKind.OPPORTUNITY,
            recipient=user,
            opportunity_save=saved,
            revision_id="revision:1",
        )
        apply_evaluation(evaluation, observed_at=NOW)
        event = emit_domain_event(
            event_type=DomainEventType.OPPORTUNITY_WITHDRAWN,
            source_type="opportunity",
            source_id=opportunity.pk,
            idempotency_key="r3:test:withdrawn",
            payload={"opportunity_id": str(opportunity.pk)},
            process_on_commit=False,
        )
        process_domain_events(event_ids=[event.pk], limit=1)
        process_domain_events(event_ids=[event.pk], limit=1)
        consumptions = DomainEventConsumption.objects.filter(
            event=event,
            consumer="preparation.proactive",
        )
        self.assertEqual(consumptions.count(), 1)
        self.assertEqual(consumptions.get().status, DomainEventConsumptionStatus.PROCESSED)
        self.assertFalse(
            ProactivePreparationCursor.objects.filter(opportunity_save=saved).exists()
        )


@unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL locking test")
class ProactivePreparationConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_two_workers_apply_one_material_transition_once(self):
        user = User.objects.create_user(username="r3-pg", email="r3-pg@example.com")
        opportunity = Opportunity.objects.create(kind=OpportunityKind.JOB, created_by=user)
        saved = OpportunitySave.objects.create(profile=user, opportunity=opportunity)
        baseline = Evaluation(
            result=result("prepare_requirement"),
            watch_kind=ProactivePreparationWatchKind.OPPORTUNITY,
            recipient=user,
            opportunity_save=saved,
            revision_id="revision:1",
        )
        apply_evaluation(baseline, observed_at=NOW)
        barrier = threading.Barrier(2)
        outcomes = []

        def worker():
            connections["default"].close()
            local_user = User.objects.get(pk=user.pk)
            local_saved = OpportunitySave.objects.get(pk=saved.pk)
            evaluation = Evaluation(
                result=result("confirm_reuse", confirmation_required=True),
                watch_kind=ProactivePreparationWatchKind.OPPORTUNITY,
                recipient=local_user,
                opportunity_save=local_saved,
                revision_id="revision:1",
            )
            barrier.wait(timeout=10)
            outcomes.append(apply_evaluation(evaluation, observed_at=NOW).status)
            connections["default"].close()

        threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        cursor = ProactivePreparationCursor.objects.get(opportunity_save=saved)
        self.assertEqual(cursor.transition_sequence, 1)
        self.assertEqual(
            Notification.objects.filter(template_key="preparation.proactive").count(),
            1,
        )
        self.assertCountEqual(outcomes, ["notified", "unchanged"])
