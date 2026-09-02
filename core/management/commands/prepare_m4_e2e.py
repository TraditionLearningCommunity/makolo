import importlib
from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization
from trust.models import ProofType
from trust.services import issue_proof


class Command(BaseCommand):
    help = "Add deterministic M4 Trust browser fixtures after prepare_e2e."

    def handle(self, *args, **options):
        if not getattr(settings, "IS_E2E", False):
            raise CommandError("prepare_m4_e2e est réservé à DJANGO_ENV=e2e.")

        permission_seed = importlib.import_module("authorization.migrations.0014_trust_permissions")
        permission_seed.seed_trust_permissions(apps, None)

        owner = User.objects.get(email="owner@e2e.makolo.test")
        participant = User.objects.get(email="participant@e2e.makolo.test")
        staff = User.objects.get(email="staff@e2e.makolo.test")
        space = Organization.objects.get(name="Makolo E2E Events")

        activity, _ = Activity.objects.get_or_create(
            space=space,
            title="Trust expérience E2E",
            defaults={
                "created_by": owner,
                "short_description": "Expérience canonique terminée pour Feedback et Proof M4.",
                "status": ActivityStatus.PUBLISHED,
            },
        )
        now = timezone.now()
        occurrence, _ = Occurrence.objects.get_or_create(
            activity=activity,
            label="Expérience Trust terminée",
            defaults={
                "start_at": now - timedelta(days=2, hours=2),
                "end_at": now - timedelta(days=2),
                "timezone": "Africa/Lubumbashi",
                "status": OccurrenceStatus.COMPLETED,
            },
        )
        journey, _ = Journey.objects.get_or_create(
            beneficiary=participant,
            activity=activity,
            occurrence=occurrence,
            defaults={
                "initiated_by": participant,
                "workflow": WorkflowKind.REGISTRATION,
                "status": JourneyStatus.FULFILLED,
                "fulfilled_at": now - timedelta(days=2),
            },
        )
        if journey.status != JourneyStatus.FULFILLED:
            journey.status = JourneyStatus.FULFILLED
            journey.fulfilled_at = journey.fulfilled_at or (now - timedelta(days=2))
            journey.save(update_fields=["status", "fulfilled_at", "updated_at"])

        issue_proof(
            journey=journey,
            proof_type=ProofType.JOURNEY_COMPLETED,
            actor=staff,
            is_public=True,
        )
        self.stdout.write(self.style.SUCCESS("Makolo M4 E2E fixtures prepared."))
