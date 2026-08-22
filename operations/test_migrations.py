import uuid
from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


EVENT_ACTIVITY_NAMESPACE = uuid.UUID("c72bc780-36d3-4ee0-8f8d-e0a0a173086c")


def stable_event_projection_id(kind, event_id):
    return uuid.uuid5(EVENT_ACTIVITY_NAMESPACE, f"event:{event_id}:{kind}")


class OperationsCanonicalIncidentMigrationTests(TransactionTestCase):
    """Exercise the real upgrade path with legacy Operations data present."""

    migrate_from = [
        ("events", "0007_cutover_event_to_activity"),
        ("operations", "0001_initial"),
    ]
    migrate_to = [
        ("events", "0007_cutover_event_to_activity"),
        ("operations", "0002_canonical_incident_scope"),
    ]

    def test_existing_event_incident_backfills_after_event_cutover(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        User = old_apps.get_model("accounts", "User")
        Organization = old_apps.get_model("organizations", "Organization")
        Activity = old_apps.get_model("activities", "Activity")
        Occurrence = old_apps.get_model("activities", "Occurrence")
        Event = old_apps.get_model("events", "Event")
        OperationsIncident = old_apps.get_model("operations", "OperationsIncident")

        user = User.objects.create(
            username="ops-migration-owner",
            email="ops-migration-owner@example.test",
            password="!",
        )
        organization = Organization.objects.create(
            name="Operations migration space",
            slug="operations-migration-space",
            created_by_id=user.pk,
        )
        activity = Activity.objects.create(
            space_id=organization.pk,
            created_by_id=user.pk,
            title="Historical Event activity",
            slug="historical-event-activity",
            status="published",
            visibility="public",
        )
        event = Event.objects.create(
            activity_id=activity.pk,
            slug="historical-event",
        )
        start_at = timezone.now() + timedelta(days=1)
        occurrence = Occurrence.objects.create(
            pk=stable_event_projection_id("occurrence", event.pk),
            activity_id=activity.pk,
            start_at=start_at,
            end_at=start_at + timedelta(hours=2),
            timezone="Africa/Lubumbashi",
            status="scheduled",
        )
        incident = OperationsIncident.objects.create(
            title="Historical incident",
            category="event",
            severity="medium",
            status="open",
            description="Incident created before the canonical Operations cutover.",
            opened_by_id=user.pk,
            event_id=event.pk,
            organization_id=None,
        )

        # At events.0007 the historical Event model no longer has the generic
        # start/end/organization fields. This is the state that failed on the
        # existing PythonAnywhere beta database.
        self.assertNotIn("start_at", {field.name for field in Event._meta.fields})
        self.assertNotIn("end_at", {field.name for field in Event._meta.fields})
        self.assertNotIn("organization", {field.name for field in Event._meta.fields})

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        migrated_apps = executor.loader.project_state(self.migrate_to).apps
        MigratedIncident = migrated_apps.get_model("operations", "OperationsIncident")

        migrated = MigratedIncident.objects.get(pk=incident.pk)
        self.assertEqual(migrated.activity_id, activity.pk)
        self.assertEqual(migrated.occurrence_id, occurrence.pk)
        self.assertEqual(migrated.organization_id, organization.pk)
