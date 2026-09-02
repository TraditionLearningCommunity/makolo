import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from access.models import Access, AccessCredential
from accounts.models import UserProfile
from activities.models import Activity, ActivityStatus, ActivityVisibility
from journeys.collaboration_models import (
    JourneyArtifact,
    JourneyArtifactKind,
    JourneyArtifactSensitivity,
    JourneyBlocker,
    JourneyNote,
    JourneyNoteVisibility,
    JourneyStep,
    JourneyStepDependency,
    JourneyStepKind,
    JourneyStepStatus,
)
from journeys.models import Journey, WorkflowKind
from opportunities.models import (
    Opportunity,
    OpportunityKind,
    OpportunityPublicationStatus,
    OpportunityRevision,
)
from payments.models import (
    PaymentObligation,
    PaymentObligationProcessingMode,
    PaymentObligationReason,
)
from preparation.models import ActivityResource, ResourceKind, ResourceStatus, ResourceVisibility
from questionnaires.models import (
    Form,
    FormAnswer,
    FormQuestion,
    FormRequest,
    FormResponse,
    FormVersion,
    FormVersionStatus,
    QuestionType,
)
from services.models import (
    OpportunityPolicy,
    ServiceDetails,
    ServiceJourneyContext,
    ServiceKind,
    ServicePlanTemplate,
    ServicePlanTemplateStatus,
    ServicePlanTemplateStep,
    ServicePlanTemplateStepDependency,
)

from .journey_reuse import (
    accept_journey_share,
    build_journey_share_snapshot,
    create_direct_journey_share,
    evaluate_journey_share,
)
from .models import JourneyShareAcceptance, ShareLink, ShareStatus


User = get_user_model()


class JourneyReuseP3Tests(TestCase):
    password = "Strong-p3-password-2026!"

    def setUp(self):
        self.sender = User.objects.create_user(
            username="p3-christophe",
            email="p3-christophe@makolo.test",
            password=self.password,
            first_name="Christophe",
        )
        self.recipient = User.objects.create_user(
            username="p3-gilbert",
            email="p3-gilbert@makolo.test",
            password=self.password,
            first_name="Gilbert",
        )
        self.other = User.objects.create_user(
            username="p3-other",
            email="p3-other@makolo.test",
            password=self.password,
            first_name="Patrick",
        )
        self.sender_profile = UserProfile.objects.create(user=self.sender, searchable=True)
        self.recipient_profile = UserProfile.objects.create(user=self.recipient, searchable=True)
        self.other_profile = UserProfile.objects.create(user=self.other, searchable=True)
        self.activity = Activity.objects.create(
            owner_profile=self.sender,
            created_by=self.sender,
            title="Accompagnement bourse P3",
            short_description="Chemin canonique de test P3.",
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )
        self.service = ServiceDetails.objects.create(
            activity=self.activity,
            service_kind=ServiceKind.APPLICATION_SUPPORT,
            opportunity_policy=OpportunityPolicy.OPTIONAL,
        )
        self.template = ServicePlanTemplate.objects.create(
            service=self.service,
            key="scholarship-path",
            version=1,
            name="Parcours bourse",
            created_by=self.sender,
        )
        self.template_a = ServicePlanTemplateStep.objects.create(
            template=self.template,
            kind=JourneyStepKind.ACTION,
            title="Lire les critères",
            description="Comprendre le chemin.",
            position=1,
        )
        self.template_b = ServicePlanTemplateStep.objects.create(
            template=self.template,
            kind=JourneyStepKind.DOCUMENT,
            title="Préparer votre CV",
            description="Joindre votre propre CV.",
            position=2,
        )
        self.template_c = ServicePlanTemplateStep.objects.create(
            template=self.template,
            kind=JourneyStepKind.PAYMENT,
            title="Vérifier les frais actuels",
            description="Le montant vient du flow financier courant.",
            position=3,
        )
        ServicePlanTemplateStepDependency.objects.create(step=self.template_b, depends_on=self.template_a)
        ServicePlanTemplateStepDependency.objects.create(step=self.template_c, depends_on=self.template_b)
        self.template.status = ServicePlanTemplateStatus.PUBLISHED
        self.template.save(update_fields=["status", "updated_at"])

        self.opportunity = Opportunity.objects.create(kind=OpportunityKind.SCHOLARSHIP, created_by=self.sender)
        self.revision1 = OpportunityRevision.objects.create(
            opportunity=self.opportunity,
            version=1,
            title="Bourse P3",
            summary="Bourse de test.",
            issuer_name="Fondation P3",
            deadline_at=timezone.now() + timezone.timedelta(days=30),
            timezone="Africa/Lubumbashi",
            created_by=self.sender,
        )
        self.revision1.published_at = timezone.now()
        self.revision1._allow_publication = True
        self.revision1.save(update_fields=["published_at"])
        self.opportunity.publication_status = OpportunityPublicationStatus.PUBLISHED
        self.opportunity.current_revision = self.revision1
        self.opportunity.published_at = self.revision1.published_at
        self.opportunity._allow_lifecycle_transition = True
        self.opportunity.save(update_fields=["publication_status", "current_revision", "published_at", "updated_at"])

        self.source = Journey.objects.create(
            initiated_by=self.sender,
            beneficiary=self.sender,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
        )
        ServiceJourneyContext.objects.create(
            journey=self.source,
            service_plan_template=self.template,
            opportunity=self.opportunity,
            opportunity_revision=self.revision1,
            objective="SECRET_PRIVATE_OBJECTIVE",
        )
        self._add_private_source_state()

    def _add_private_source_state(self):
        live_a = JourneyStep.objects.create(
            journey=self.source,
            kind=JourneyStepKind.ACTION,
            title="Source live step",
            description="État personnel source",
            position=1,
        )
        JourneyStep.objects.filter(pk=live_a.pk).update(status=JourneyStepStatus.COMPLETED)
        live_b = JourneyStep.objects.create(
            journey=self.source,
            kind=JourneyStepKind.DOCUMENT,
            title="Source blocked step",
            position=2,
        )
        JourneyStepDependency.objects.create(step=live_b, depends_on=live_a)
        JourneyBlocker.objects.create(
            journey=self.source,
            step=live_b,
            title="SECRET_PERSONAL_BLOCKER",
            description="Passeport personnel expiré",
        )
        JourneyNote.objects.create(
            journey=self.source,
            author=self.sender,
            visibility=JourneyNoteVisibility.INTERNAL,
            body="SECRET_PRIVATE_NOTE",
        )
        JourneyArtifact.objects.create(
            journey=self.source,
            step=live_b,
            kind=JourneyArtifactKind.IDENTITY_DOCUMENT,
            title="SECRET_ID_DOCUMENT",
            file="SECRET_ID_DOCUMENT.pdf",
            sensitivity=JourneyArtifactSensitivity.NORMAL,
            uploaded_by=self.sender,
            size=10,
            mime_type="application/pdf",
            content_hash="a" * 64,
        )

        form = Form.objects.create(
            activity=self.activity,
            key="application",
            title="Formulaire candidature",
            created_by=self.sender,
        )
        version = FormVersion.objects.create(
            form=form,
            version=1,
            title="Formulaire candidature",
            created_by=self.sender,
        )
        question = FormQuestion.objects.create(
            form_version=version,
            key="motivation",
            label="Motivation",
            question_type=QuestionType.LONG_TEXT,
            position=1,
        )
        FormVersion.objects.filter(pk=version.pk).update(
            status=FormVersionStatus.PUBLISHED,
            published_at=timezone.now(),
        )
        version.refresh_from_db()
        request = FormRequest.objects.create(
            form_version=version,
            journey=self.source,
            created_by=self.sender,
        )
        response = FormResponse.objects.create(
            request=request,
            form_version=version,
            respondent=self.sender,
        )
        FormAnswer.objects.create(response=response, question=question, value="SECRET_FORM_ANSWER")

        PaymentObligation.objects.create(
            journey=self.source,
            reason=PaymentObligationReason.SERVICE_PROCESS,
            label="SECRET_PAYMENT_REFERENCE",
            amount=Decimal("50.00"),
            currency="USD",
            processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
            payer_profile=self.sender,
            payee_platform=True,
            source_key="SECRET_PAYMENT_REFERENCE",
            created_by=self.sender,
        )
        access = Access.objects.create(
            beneficiary=self.sender,
            activity=self.activity,
            journey=self.source,
            issued_by=self.sender,
            source_key="SECRET_ACCESS_CREDENTIAL",
        )
        AccessCredential.objects.create(access=access)

        ActivityResource.objects.create(
            activity=self.activity,
            key="public-guide",
            title="Guide public",
            kind=ResourceKind.TEXT,
            text_content="Guide générique public",
            visibility=ResourceVisibility.PUBLIC,
            status=ResourceStatus.PUBLISHED,
            created_by=self.sender,
        )
        ActivityResource.objects.create(
            activity=self.activity,
            key="secret-resource",
            title="SECRET_RESTRICTED_RESOURCE",
            kind=ResourceKind.TEXT,
            text_content="SECRET_RESTRICTED_RESOURCE",
            visibility=ResourceVisibility.RESTRICTED,
            status=ResourceStatus.PUBLISHED,
            created_by=self.sender,
        )

    def direct_share(self):
        return create_direct_journey_share(
            created_by=self.sender,
            recipient=self.recipient_profile,
            journey=self.source,
        )

    def test_snapshot_is_versioned_allowlisted_and_private_sentinels_do_not_travel(self):
        snapshot = build_journey_share_snapshot(journey=self.source, actor=self.sender)
        serialized = json.dumps(snapshot, sort_keys=True)
        self.assertEqual(snapshot["schema_version"], 1)
        self.assertEqual(len(snapshot["steps"]), 3)
        self.assertEqual(snapshot["steps"][0]["classification"], "REUSABLE")
        self.assertEqual(snapshot["steps"][1]["classification"], "PERSONALIZE")
        self.assertEqual(snapshot["steps"][2]["classification"], "REVALIDATE")
        self.assertEqual(len(snapshot["resources"]), 1)
        self.assertEqual(snapshot["resources"][0]["key"], "public-guide")
        for secret in (
            "SECRET_FORM_ANSWER",
            "SECRET_PRIVATE_NOTE",
            "SECRET_PRIVATE_OBJECTIVE",
            "SECRET_ID_DOCUMENT",
            "SECRET_PAYMENT_REFERENCE",
            "SECRET_ACCESS_CREDENTIAL",
            "SECRET_PERSONAL_BLOCKER",
            "SECRET_RESTRICTED_RESOURCE",
        ):
            self.assertNotIn(secret, serialized)

    def test_journey_share_is_recipient_bound_and_has_no_public_link(self):
        created = self.direct_share()
        self.assertEqual(created.envelope.subject_type, "journey")
        self.assertFalse(ShareLink.objects.filter(envelope=created.envelope).exists())
        self.assertEqual(created.delivery.recipient, self.recipient_profile)

    def test_accept_creates_independent_journey_with_initial_steps_and_no_private_state(self):
        created = self.direct_share()
        result = accept_journey_share(delivery_id=created.delivery.pk, user=self.recipient)
        destination = result.journey
        self.source.refresh_from_db()
        self.assertNotEqual(destination.pk, self.source.pk)
        self.assertEqual(self.source.beneficiary_id, self.sender.pk)
        self.assertEqual(destination.beneficiary_id, self.recipient.pk)
        self.assertEqual(destination.initiated_by_id, self.recipient.pk)
        self.assertEqual(destination.status, "draft")
        self.assertEqual(destination.steps.count(), 3)
        self.assertEqual(
            list(destination.steps.order_by("position").values_list("status", flat=True)),
            [JourneyStepStatus.READY, JourneyStepStatus.PENDING, JourneyStepStatus.PENDING],
        )
        self.assertEqual(destination.steps.filter(dependencies__isnull=False).count(), 2)
        self.assertEqual(destination.artifacts.count(), 0)
        self.assertEqual(destination.notes.count(), 0)
        self.assertEqual(destination.blockers.count(), 0)
        self.assertEqual(destination.assignments.count(), 0)
        self.assertEqual(destination.form_requests.count(), 0)
        self.assertEqual(destination.payment_obligations.count(), 0)
        self.assertEqual(destination.accesses.count(), 0)

    def test_accept_is_idempotent(self):
        created = self.direct_share()
        first = accept_journey_share(delivery_id=created.delivery.pk, user=self.recipient)
        second = accept_journey_share(delivery_id=created.delivery.pk, user=self.recipient)
        self.assertEqual(first.journey.pk, second.journey.pk)
        self.assertEqual(JourneyShareAcceptance.objects.filter(delivery=created.delivery).count(), 1)
        self.assertEqual(Journey.objects.filter(beneficiary=self.recipient, activity=self.activity).count(), 1)

    def test_wrong_recipient_cannot_accept(self):
        created = self.direct_share()
        with self.assertRaises(Exception):
            accept_journey_share(delivery_id=created.delivery.pk, user=self.other)
        self.assertFalse(Journey.objects.filter(beneficiary=self.other, activity=self.activity).exists())

    def test_revoked_envelope_cannot_materialize(self):
        created = self.direct_share()
        created.envelope.status = ShareStatus.REVOKED
        created.envelope.revoked_at = timezone.now()
        created.envelope.save(update_fields=["status", "revoked_at", "updated_at"])
        with self.assertRaises(Exception):
            accept_journey_share(delivery_id=created.delivery.pk, user=self.recipient)
        self.assertFalse(Journey.objects.filter(beneficiary=self.recipient, activity=self.activity).exists())

    def test_opportunity_revision_is_revalidated_and_destination_uses_current_revision(self):
        created = self.direct_share()
        revision2 = OpportunityRevision.objects.create(
            opportunity=self.opportunity,
            version=2,
            title="Bourse P3 actualisée",
            summary="Révision actuelle.",
            issuer_name="Fondation P3",
            deadline_at=timezone.now() + timezone.timedelta(days=45),
            timezone="Africa/Lubumbashi",
            created_by=self.sender,
        )
        revision2.published_at = timezone.now()
        revision2._allow_publication = True
        revision2.save(update_fields=["published_at"])
        self.opportunity.current_revision = revision2
        self.opportunity._allow_lifecycle_transition = True
        self.opportunity.save(update_fields=["current_revision", "updated_at"])
        evaluation = evaluate_journey_share(created.subject)
        self.assertIn("opportunity_revision", evaluation["stale"])
        result = accept_journey_share(delivery_id=created.delivery.pk, user=self.recipient)
        self.assertEqual(result.journey.service_context.opportunity_revision_id, revision2.pk)

    def test_new_template_version_is_used_without_rewriting_snapshot(self):
        created = self.direct_share()
        original_snapshot = json.loads(json.dumps(created.subject.snapshot))
        template2 = ServicePlanTemplate.objects.create(
            service=self.service,
            key=self.template.key,
            version=2,
            name="Parcours bourse actualisé",
            created_by=self.sender,
        )
        ServicePlanTemplateStep.objects.create(
            template=template2,
            kind=JourneyStepKind.ACTION,
            title="Étape actuelle",
            position=1,
        )
        template2.status = ServicePlanTemplateStatus.PUBLISHED
        template2.save(update_fields=["status", "updated_at"])
        evaluation = evaluate_journey_share(created.subject)
        self.assertIn("service_template", evaluation["stale"])
        result = accept_journey_share(delivery_id=created.delivery.pk, user=self.recipient)
        self.assertEqual(result.journey.service_context.service_plan_template_id, template2.pk)
        created.subject.refresh_from_db()
        self.assertEqual(created.subject.snapshot, original_snapshot)

    def test_delivery_ui_shows_honest_reuse_language(self):
        created = self.direct_share()
        self.client.login(username=self.recipient.username, password=self.password)
        response = self.client.get(f"/shares/{created.delivery.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Utiliser ce parcours")
        self.assertContains(response, "à personnaliser")
        self.assertContains(response, "à revalider")
        self.assertNotContains(response, "SECRET_FORM_ANSWER")
        self.assertNotContains(response, "SECRET_ID_DOCUMENT")
