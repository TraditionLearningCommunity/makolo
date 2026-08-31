import importlib

from django.apps import apps
from django.conf import settings
from django.core.management import BaseCommand, CommandError

from accounts.models import User
from authorization.constants import SystemRoleCode
from authorization.models import AuthorityScope, Mandate, Role
from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus
from requirements.contracts import RequirementMode
from subscriptions.contracts import (
    AcquisitionMode,
    CatalogVisibility,
    RequirementDisclosure,
    RequirementFailurePolicy,
    RequirementPhase,
    SubscriptionPlanType,
    SubscriptionSubjectType,
)
from subscriptions.eligibility_models import PlanRequirement
from subscriptions.models import FeatureDefinition, PlanBenefit, PlanEntitlement, PlanVersion, SubscriptionPlan
from subscriptions.services import publish_plan_version


E2E_PASSWORD = "Makolo-E2E-2026!"


class Command(BaseCommand):
    help = "Prepare deterministic Subscription V1 browser fixtures for DJANGO_ENV=e2e."

    def handle(self, *args, **options):
        if not getattr(settings, "IS_E2E", False):
            raise CommandError("prepare_subscriptions_e2e est réservé à DJANGO_ENV=e2e.")

        subscription_authority_seed = importlib.import_module(
            "authorization.migrations.0013_subscription_permissions"
        )
        subscription_authority_seed.seed_subscription_permissions(apps, None)

        owner = User.objects.get(email="owner@e2e.makolo.test")
        space = Organization.objects.get(name="Makolo E2E Events")
        viewer = self._user("subscription.viewer@e2e.makolo.test", "e2e-subscription-viewer")
        member = self._user("subscription.member@e2e.makolo.test", "e2e-subscription-member")

        space_admin = Role.objects.get(code=SystemRoleCode.SPACE_ADMIN, is_system=True, is_active=True)
        Mandate.objects.get_or_create(
            profile=viewer,
            role=space_admin,
            scope_type=AuthorityScope.SPACE,
            space=space,
            defaults={"granted_by": owner, "source": "e2e-subscription-viewer"},
        )

        team, _ = Team.objects.get_or_create(
            organization=space,
            name="Subscription E2E Team",
            defaults={"is_default": False, "is_active": True},
        )
        TeamMembership.objects.get_or_create(
            team=team,
            user=member,
            defaults={
                "status": TeamMembershipStatus.ACTIVE,
                "invited_by": owner,
            },
        )

        subscription_seed = importlib.import_module(
            "subscriptions.migrations.0004_default_bases_and_backfill"
        )
        subscription_seed.seed_bases_and_backfill(apps, None)

        profile_target = self._profile_target()
        space_target = self._space_target()
        self.stdout.write(
            self.style.SUCCESS(
                "Subscription E2E fixtures ready: "
                f"profile={profile_target.pk} space={space_target.pk} viewer={viewer.email} member={member.email}"
            )
        )

    def _user(self, email, username):
        user, _ = User.objects.get_or_create(
            email=email,
            defaults={"username": username, "is_active": True},
        )
        user.username = username
        user.is_active = True
        user.set_password(E2E_PASSWORD)
        user.save(update_fields=["username", "is_active", "password"])
        return user

    def _profile_target(self):
        plan, _ = SubscriptionPlan.objects.get_or_create(
            code="e2e.profile.plus",
            defaults={
                "plan_type": SubscriptionPlanType.BASE,
                "subject_type": SubscriptionSubjectType.PROFILE,
                "is_default": False,
                "is_active": True,
            },
        )
        if plan.current_version_id:
            return plan.current_version
        version = PlanVersion.objects.create(
            plan=plan,
            version=1,
            name="Makolo E2E Profil Plus",
            short_description="Formule factice pour valider le parcours Subscription Profile.",
            catalog_visibility=CatalogVisibility.PUBLIC,
            acquisition_mode=AcquisitionMode.SELF_SERVICE,
            display_order=20,
        )
        PlanBenefit.objects.create(
            plan_version=version,
            title="Parcours Subscription complet",
            description="Benefit de démonstration sans implication commerciale réelle.",
            position=0,
            is_highlighted=True,
        )
        PlanEntitlement.objects.create(
            plan_version=version,
            feature=FeatureDefinition.objects.get(code="activities.create"),
            value=True,
        )
        PlanRequirement.objects.create(
            plan_version=version,
            key="profile.account_age.e2e",
            title="Compte actif",
            description="Le compte doit être actif depuis au moins zéro jour.",
            phase=RequirementPhase.ACQUISITION,
            mode=RequirementMode.AUTOMATIC,
            evaluator_key="profile.account_age_days",
            config={"operator": ">=", "value": 0},
            is_mandatory=True,
            position=0,
            failure_policy=RequirementFailurePolicy.BLOCK,
            disclosure=RequirementDisclosure.VISIBLE,
        )
        PlanRequirement.objects.create(
            plan_version=version,
            key="profile.confirm_choice.e2e",
            title="Confirmer votre choix",
            description="Une action reste à effectuer avant la finalisation.",
            phase=RequirementPhase.ACQUISITION,
            mode=RequirementMode.ACTION,
            is_mandatory=True,
            position=1,
            failure_policy=RequirementFailurePolicy.BLOCK,
            disclosure=RequirementDisclosure.VISIBLE,
        )
        return publish_plan_version(version)

    def _space_target(self):
        plan, _ = SubscriptionPlan.objects.get_or_create(
            code="e2e.space.plus",
            defaults={
                "plan_type": SubscriptionPlanType.BASE,
                "subject_type": SubscriptionSubjectType.SPACE,
                "is_default": False,
                "is_active": True,
            },
        )
        if plan.current_version_id:
            return plan.current_version
        version = PlanVersion.objects.create(
            plan=plan,
            version=1,
            name="Makolo E2E Espace Plus",
            short_description="Formule factice pour valider le parcours Subscription Space.",
            catalog_visibility=CatalogVisibility.PUBLIC,
            acquisition_mode=AcquisitionMode.SELF_SERVICE,
            display_order=20,
        )
        PlanBenefit.objects.create(
            plan_version=version,
            title="Équipe et rôles personnalisés",
            description="Benefit de démonstration basé sur des Entitlements réels.",
            position=0,
            is_highlighted=True,
        )
        for code, value in (
            ("activities.create", True),
            ("custom_roles", True),
            ("team.members", 10),
        ):
            PlanEntitlement.objects.create(
                plan_version=version,
                feature=FeatureDefinition.objects.get(code=code),
                value=value,
            )
        return publish_plan_version(version)
