import importlib
import uuid
from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from activities.models import Activity, ActivityStatus, ActivityVisibility
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from journeys.collaboration_models import (
    JourneyArtifactKind,
    JourneyArtifactReview,
    JourneyArtifactReviewStatus,
    JourneyArtifactSensitivity,
    JourneyAssignment,
    JourneyAssignmentResponsibility,
    JourneyAssignmentStatus,
    JourneyBlocker,
    JourneyBlockerCategory,
    JourneyBlockerSeverity,
    JourneyBlockerStatus,
    JourneyStep,
    JourneyStepKind,
    JourneyStepOrigin,
    JourneyStepStatus,
)
from journeys.collaboration_services import create_artifact
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus
from services.models import ServiceCurrentOutcome, ServiceDetails, ServiceJourneyContext, ServiceKind


E2E_PASSWORD = "Makolo-E2E-2026!"
SERVICE_ACTIVITY_ID = uuid.UUID("693d18fe-e954-4bcb-836f-cdfffa64d361")
SERVICE_JOURNEY_ID = uuid.UUID("2ba34e06-cf8d-4e66-8a55-f7271bac6cf0")


class Command(BaseCommand):
    help = "Prepare the compact Services V1 browser fixtures for DJANGO_ENV=e2e."

    def handle(self, *args, **options):
        if not getattr(settings, "IS_E2E", False):
            raise CommandError("prepare_services_e2e est réservé à DJANGO_ENV=e2e.")

        service_authority_seed = importlib.import_module(
            "authorization.migrations.0012_services_opportunity_permissions"
        )
        service_authority_seed.seed_t34b_authorization(apps, None)

        participant = User.objects.get(email="participant@e2e.makolo.test")
        staff = User.objects.get(email="staff@e2e.makolo.test")
        manager = self._user("service.manager@e2e.makolo.test", "e2e-service-manager")
        facilitator = self._user("service.facilitator@e2e.makolo.test", "e2e-service-facilitator")
        reviewer = self._user("service.reviewer@e2e.makolo.test", "e2e-service-reviewer")
        same_space = self._user("service.same-space@e2e.makolo.test", "e2e-service-same-space")

        space = Organization.objects.create(
            name="Makolo E2E Services",
            description="Espace déterministe pour la release gate Services V1.",
            city="Lubumbashi",
            country="RDC",
            public_profile=False,
            created_by=manager,
        )
        team = Team.objects.create(
            organization=space,
            name="Équipe Services E2E",
            is_default=True,
            is_active=True,
        )
        TeamMembership.objects.create(
            team=team,
            user=same_space,
            status=TeamMembershipStatus.ACTIVE,
            invited_by=manager,
        )

        activity = Activity.objects.create(
            pk=SERVICE_ACTIVITY_ID,
            space=space,
            created_by=manager,
            title="Accompagnement Services V1 E2E",
            slug="accompagnement-services-v1-e2e",
            short_description="Dossier déterministe pour les parcours navigateur Services.",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        ServiceDetails.objects.create(
            activity=activity,
            service_kind=ServiceKind.APPLICATION_SUPPORT,
        )
        grant_activity_role(
            profile=manager,
            activity=activity,
            role=SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
            source="e2e-services",
        )
        grant_activity_role(
            profile=facilitator,
            activity=activity,
            role=SystemRoleCode.ACTIVITY_SERVICE_FACILITATOR,
            source="e2e-services",
        )
        grant_activity_role(
            profile=reviewer,
            activity=activity,
            role=SystemRoleCode.ACTIVITY_SERVICE_REVIEWER,
            source="e2e-services",
        )

        now = timezone.now()
        journey = Journey.objects.create(
            pk=SERVICE_JOURNEY_ID,
            initiated_by=participant,
            beneficiary=participant,
            activity=activity,
            workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.IN_PROGRESS,
            submitted_at=now - timedelta(days=4),
            confirmed_at=now - timedelta(days=4),
            started_at=now - timedelta(days=3),
        )
        ServiceJourneyContext.objects.create(
            journey=journey,
            objective="Finaliser une démarche Services V1 de démonstration.",
            current_outcome=ServiceCurrentOutcome.ACTION_REQUIRED,
        )
        JourneyAssignment.objects.create(
            journey=journey,
            profile=facilitator,
            responsibility=JourneyAssignmentResponsibility.FACILITATOR,
            status=JourneyAssignmentStatus.ACTIVE,
            assigned_by=manager,
            assigned_at=now - timedelta(days=3),
        )
        JourneyAssignment.objects.create(
            journey=journey,
            profile=reviewer,
            responsibility=JourneyAssignmentResponsibility.REVIEWER,
            status=JourneyAssignmentStatus.ACTIVE,
            assigned_by=manager,
            assigned_at=now - timedelta(days=2),
        )
        step = JourneyStep.objects.create(
            journey=journey,
            kind=JourneyStepKind.DOCUMENT,
            title="Fournir le document demandé",
            status=JourneyStepStatus.READY,
            position=10,
            is_required=True,
            due_at=now - timedelta(days=1),
            origin=JourneyStepOrigin.MANUAL,
            created_by=manager,
            status_changed_by=manager,
            status_reason="e2e_services_ready",
        )
        JourneyBlocker.objects.create(
            journey=journey,
            step=step,
            category=JourneyBlockerCategory.MISSING_DOCUMENT,
            severity=JourneyBlockerSeverity.HIGH,
            title="Document complémentaire requis",
            status=JourneyBlockerStatus.ACTIVE,
            detected_by=manager,
        )
        restricted = create_artifact(
            journey=journey,
            step=step,
            uploaded_file=SimpleUploadedFile(
                "e2e-restricted.pdf",
                b"%PDF-1.4\nMakolo Services E2E restricted fixture\n%%EOF",
                content_type="application/pdf",
            ),
            uploaded_by=participant,
            kind=JourneyArtifactKind.IDENTITY_DOCUMENT,
            title="Document restreint Services E2E",
            sensitivity=JourneyArtifactSensitivity.RESTRICTED,
        )
        JourneyArtifactReview.objects.create(
            artifact=restricted,
            reviewer=reviewer,
            requested_by=manager,
            status=JourneyArtifactReviewStatus.REQUESTED,
            requested_at=now - timedelta(hours=2),
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Services E2E ready: activity={activity.pk} journey={journey.pk} staff={staff.email}"
            )
        )

    def _user(self, email, username):
        user = User.objects.create(
            email=email,
            username=username,
            first_name="Service",
            last_name=username.replace("e2e-service-", "").title(),
            is_active=True,
            is_verified=True,
            email_verified=True,
            onboarding_completed=True,
            onboarding_step=5,
        )
        user.set_password(E2E_PASSWORD)
        user.save(update_fields=["password"])
        return user
