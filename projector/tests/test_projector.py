from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence, OccurrenceStatus, OccurrenceTimingKind
from activities.services import create_occurrence, reschedule_occurrence, set_occurrence_status
from core.models import DomainEventOutbox
from domain_events.contracts import DomainEventType

from projector.contracts import ProjectionChangeSignal, UniverseProjectionRoot, ValueState
from projector.domain_events import change_signal_from_domain_event
from projector.exceptions import MissingCanonicalDependency, StaleUniverseProjection
from projector.services import build_delta, build_full_snapshot, project_change, project_full_snapshot


class InMemoryUniversePort:
    """Actor 8 fake implementing the ordering contract expected by Actor 7."""

    def __init__(self):
        self.strategy_version = None
        self.roots = {}

    @staticmethod
    def _revision(root):
        return datetime.fromisoformat(root.source_revision)

    def apply_snapshot(self, snapshot):
        self.strategy_version = snapshot.strategy_version
        self.roots = {root.projection_ref: root for root in snapshot.roots}

    def apply_delta(self, delta):
        if self.strategy_version not in (None, delta.strategy_version):
            raise StaleUniverseProjection("Delta construit avec une stratégie obsolète.")
        self.strategy_version = delta.strategy_version
        for ref in delta.removals:
            self.roots.pop(ref, None)
        for root in delta.upserts:
            current = self.roots.get(root.projection_ref)
            if current is not None and self._revision(root) < self._revision(current):
                raise StaleUniverseProjection("Révision canonique plus ancienne refusée.")
            if (
                current is not None
                and self._revision(root) == self._revision(current)
                and root.semantic_fingerprint != current.semantic_fingerprint
            ):
                raise StaleUniverseProjection(
                    "Même révision canonique avec un contenu différent."
                )
            self.roots[root.projection_ref] = root


class ProjectorActor7Tests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="projector-owner",
            email="projector-owner@example.com",
            password="Actor7-Test-2026!",
        )
        self.activity = Activity.objects.create(
            owner_profile=self.owner,
            created_by=self.owner,
            title="Voyage Lubumbashi Kolwezi",
        )
        self.start = timezone.now() + timedelta(days=4)
        self.occurrence = create_occurrence(
            activity=self.activity,
            start_at=self.start,
            end_at=self.start + timedelta(hours=5),
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )

    def test_creation_signal_and_bootstrap_share_the_same_current_truth(self):
        event = DomainEventOutbox.objects.get(
            event_type=DomainEventType.OCCURRENCE_CREATED,
            source_id=str(self.occurrence.pk),
        )
        self.assertEqual(event.payload["occurrence_id"], str(self.occurrence.pk))
        self.assertEqual(event.payload["activity_id"], str(self.activity.pk))
        self.assertNotIn("email", event.payload)
        signal = change_signal_from_domain_event(event)
        self.assertIsNotNone(signal)
        delta = build_delta(signal)
        snapshot = build_full_snapshot()
        self.assertEqual(
            delta.upserts[0].semantic_fingerprint,
            snapshot.roots[0].semantic_fingerprint,
        )
        self.assertEqual(len(snapshot.roots), 1)
        self.assertEqual(
            snapshot.roots[0].projection_ref,
            f"occurrence-plan:{self.occurrence.pk}",
        )

    def test_multiple_backend_facts_compose_one_non_body_universe_plan(self):
        root = build_full_snapshot().roots[0]
        self.assertEqual({ref.kind for ref in root.source_facts}, {"activity", "occurrence"})
        self.assertEqual(len(root.plans), 1)
        self.assertEqual(root.bodies, ())
        self.assertEqual(root.plans[0].kind, "declared_realization_plan")

    def test_public_contract_contains_no_django_model_or_queryset(self):
        root = build_full_snapshot().roots[0]
        for field in fields(UniverseProjectionRoot):
            value = getattr(root, field.name)
            self.assertFalse(hasattr(value, "_meta"))
            self.assertFalse(hasattr(value, "query"))

    def test_deterministic_semantics_ignore_projection_run_time(self):
        first = build_full_snapshot()
        second = build_full_snapshot()
        self.assertEqual(first.semantic_fingerprint, second.semantic_fingerprint)
        self.assertEqual(
            first.roots[0].semantic_fingerprint,
            second.roots[0].semantic_fingerprint,
        )

    def test_unknown_is_not_zero_false_or_midnight(self):
        date_only = Occurrence.objects.create(
            activity=self.activity,
            start_date=(self.start + timedelta(days=1)).date(),
            timing_kind=OccurrenceTimingKind.DATE_ONLY,
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        root = build_delta(
            ProjectionChangeSignal(
                change_ref="bootstrap-local",
                fact_kind="occurrence",
                fact_id=str(date_only.pk),
                event_type="bootstrap",
            )
        ).upserts[0]
        self.assertEqual(root.plans[0].temporal.start_time.state, ValueState.UNKNOWN)
        self.assertIsNone(root.plans[0].temporal.start_time.value)

    def test_all_day_time_is_not_applicable(self):
        all_day = Occurrence.objects.create(
            activity=self.activity,
            start_date=(self.start + timedelta(days=2)).date(),
            timing_kind=OccurrenceTimingKind.ALL_DAY,
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        root = build_delta(
            ProjectionChangeSignal(
                change_ref="bootstrap-all-day",
                fact_kind="occurrence",
                fact_id=str(all_day.pk),
                event_type="bootstrap",
            )
        ).upserts[0]
        self.assertEqual(
            root.plans[0].temporal.start_time.state,
            ValueState.NOT_APPLICABLE,
        )

    def test_completed_occurrence_does_not_prove_realization_body(self):
        self.occurrence.status = OccurrenceStatus.COMPLETED
        self.occurrence.save(update_fields=["status", "updated_at"])
        root = build_delta(
            ProjectionChangeSignal(
                change_ref="completed",
                fact_kind="occurrence",
                fact_id=str(self.occurrence.pk),
                event_type="bootstrap",
            )
        ).upserts[0]
        self.assertEqual(root.plans[0].lifecycle, "closed")
        self.assertEqual(root.bodies, ())

    def test_cancellation_preserves_plan_and_does_not_create_body(self):
        set_occurrence_status(
            occurrence=self.occurrence,
            status=OccurrenceStatus.CANCELLED,
        )
        event = DomainEventOutbox.objects.get(
            event_type=DomainEventType.OCCURRENCE_CANCELLED,
            source_id=str(self.occurrence.pk),
        )
        signal = change_signal_from_domain_event(event)
        self.assertIsNotNone(signal)
        delta = build_delta(signal)
        self.assertEqual(delta.removals, ())
        self.assertEqual(delta.upserts[0].plans[0].lifecycle, "cancelled")
        self.assertEqual(delta.upserts[0].bodies, ())

    def test_snapshot_plus_delta_converges_to_rebuilt_snapshot(self):
        port = InMemoryUniversePort()
        project_full_snapshot(port=port)
        reschedule_occurrence(
            occurrence=self.occurrence,
            start_at=self.start + timedelta(days=2),
            end_at=self.start + timedelta(days=2, hours=5),
            timezone="Africa/Lubumbashi",
        )
        event = DomainEventOutbox.objects.filter(
            event_type=DomainEventType.OCCURRENCE_RESCHEDULED,
            source_id=str(self.occurrence.pk),
        ).latest("created_at")
        signal = change_signal_from_domain_event(event)
        self.assertIsNotNone(signal)
        project_change(change=signal, port=port)
        rebuilt = build_full_snapshot()
        expected = {root.projection_ref: root for root in rebuilt.roots}
        self.assertEqual(
            port.roots[f"occurrence-plan:{self.occurrence.pk}"].semantic_fingerprint,
            expected[f"occurrence-plan:{self.occurrence.pk}"].semantic_fingerprint,
        )

    def test_duplicate_change_is_semantically_idempotent(self):
        reschedule_occurrence(
            occurrence=self.occurrence,
            start_at=self.start + timedelta(days=1),
            end_at=self.start + timedelta(days=1, hours=5),
            timezone="Africa/Lubumbashi",
        )
        event = DomainEventOutbox.objects.filter(
            event_type=DomainEventType.OCCURRENCE_RESCHEDULED,
            source_id=str(self.occurrence.pk),
        ).latest("created_at")
        signal = change_signal_from_domain_event(event)
        first = build_delta(signal)
        second = build_delta(signal)
        self.assertEqual(
            first.upserts[0].semantic_fingerprint,
            second.upserts[0].semantic_fingerprint,
        )
        self.assertEqual(
            first.upserts[0].source_revision,
            second.upserts[0].source_revision,
        )

    def test_old_computed_delta_cannot_regress_newer_projection(self):
        old_delta = build_delta(
            ProjectionChangeSignal(
                change_ref="old",
                fact_kind="occurrence",
                fact_id=str(self.occurrence.pk),
                event_type="bootstrap",
            )
        )
        reschedule_occurrence(
            occurrence=self.occurrence,
            start_at=self.start + timedelta(days=3),
            end_at=self.start + timedelta(days=3, hours=5),
            timezone="Africa/Lubumbashi",
        )
        event = DomainEventOutbox.objects.filter(
            event_type=DomainEventType.OCCURRENCE_RESCHEDULED,
            source_id=str(self.occurrence.pk),
        ).latest("created_at")
        new_delta = build_delta(change_signal_from_domain_event(event))

        port = InMemoryUniversePort()
        port.apply_delta(new_delta)
        with self.assertRaises(StaleUniverseProjection):
            port.apply_delta(old_delta)

    def test_missing_dependency_is_not_translated_into_universe_removal(self):
        missing = ProjectionChangeSignal(
            change_ref="missing",
            fact_kind="occurrence",
            fact_id="00000000-0000-0000-0000-000000000000",
            event_type="test",
        )
        with self.assertRaises(MissingCanonicalDependency):
            build_delta(missing)

    def test_contract_projects_no_profile_pii_secret_or_readiness(self):
        raw = repr(build_full_snapshot())
        self.assertNotIn(self.owner.email, raw)
        self.assertNotIn(self.owner.username, raw)
        self.assertNotIn("credential", raw.lower())
        self.assertNotIn("readiness", raw.lower())

    def test_unselected_domain_event_is_ignored(self):
        event = type(
            "Event",
            (),
            {
                "pk": "event-1",
                "event_type": DomainEventType.PAYMENT_SUCCEEDED,
                "source_type": "payment",
                "source_id": "payment-1",
            },
        )()
        self.assertIsNone(change_signal_from_domain_event(event))
