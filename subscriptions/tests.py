from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .contracts import (
    AcquisitionMode,
    CatalogVisibility,
    EntitlementAggregationStrategy,
    FeatureEnforcementPolicy,
    FeatureValueType,
    PlanVersionStatus,
    SubscriptionPlanType,
    SubscriptionSubjectType,
)
from .models import FeatureDefinition, PlanBenefit, PlanEntitlement, PlanVersion, SubscriptionPlan
from .selectors import get_current_default_base_plan
from .services import CatalogTransitionError, publish_plan_version, retire_plan_version


class CatalogMixin:
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            username="catalog-staff", email="catalog-staff@example.test", password="test-only-password"
        )

    def feature(self, code="test.boolean", **overrides):
        data = {
            "code": code,
            "name": code,
            "domain": "test",
            "value_type": FeatureValueType.BOOLEAN,
            "supports_profile": True,
            "supports_space": True,
            "aggregation_strategy": EntitlementAggregationStrategy.BOOLEAN_OR,
            "enforcement_policy": FeatureEnforcementPolicy.FEATURE_GATE,
        }
        data.update(overrides)
        return FeatureDefinition.objects.create(**data)

    def plan(self, code="profile-base", **overrides):
        data = {
            "code": code,
            "plan_type": SubscriptionPlanType.BASE,
            "subject_type": SubscriptionSubjectType.PROFILE,
            "created_by": self.staff,
        }
        data.update(overrides)
        return SubscriptionPlan.objects.create(**data)

    def version(self, plan, number=1, **overrides):
        data = {
            "plan": plan,
            "version": number,
            "name": f"{plan.code} v{number}",
            "catalog_visibility": CatalogVisibility.PUBLIC,
            "acquisition_mode": AcquisitionMode.SELF_SERVICE,
            "created_by": self.staff,
        }
        data.update(overrides)
        return PlanVersion.objects.create(**data)

    def configure(self, version, feature=None):
        feature = feature or self.feature(f"feature.{version.plan.code}.{version.version}")
        PlanBenefit.objects.create(plan_version=version, title="Benefit", position=0)
        return PlanEntitlement.objects.create(plan_version=version, feature=feature, value=True)


class FeatureDefinitionTests(CatalogMixin, TestCase):
    def test_seeded_features_are_backed_by_existing_domains(self):
        activities = FeatureDefinition.objects.get(code="activities.create")
        self.assertEqual(activities.domain, "activities")
        self.assertTrue(activities.supports_profile and activities.supports_space)
        team = FeatureDefinition.objects.get(code="team.members")
        self.assertEqual(team.value_type, FeatureValueType.INTEGER)
        self.assertEqual(team.usage_provider, "organizations.active_team_members")
        self.assertTrue(team.supports_space)
        self.assertFalse(team.supports_profile)
        custom_roles = FeatureDefinition.objects.get(code="custom_roles")
        self.assertEqual(custom_roles.domain, "authorization")
        self.assertTrue(custom_roles.supports_space)

    def test_code_unique_valid_and_technical_contract_stable(self):
        feature = self.feature("valid.feature")
        with self.assertRaises(ValidationError):
            self.feature("Invalid Feature")
        with self.assertRaises(ValidationError):
            self.feature("valid.feature")
        feature.code = "renamed.feature"
        with self.assertRaises(ValidationError):
            feature.save()
        with self.assertRaises(ValidationError):
            FeatureDefinition.objects.filter(pk=feature.pk).update(value_type=FeatureValueType.INTEGER)

    def test_subject_value_type_and_aggregation_contracts_are_strict(self):
        with self.assertRaises(ValidationError):
            self.feature("test.no_subject", supports_profile=False, supports_space=False)
        with self.assertRaises(ValidationError):
            self.feature("test.bad_bool", aggregation_strategy=EntitlementAggregationStrategy.SUM)
        with self.assertRaises(ValidationError):
            self.feature(
                "test.bad_numeric",
                value_type=FeatureValueType.INTEGER,
                aggregation_strategy=EntitlementAggregationStrategy.BOOLEAN_OR,
                enforcement_policy=FeatureEnforcementPolicy.PRESERVE_EXISTING_BLOCK_NEW,
                usage_provider="test.usage",
            )

    def test_enum_validation_is_closed(self):
        feature = self.feature(
            "test.enum",
            value_type=FeatureValueType.ENUM,
            aggregation_strategy=EntitlementAggregationStrategy.REPLACE,
            enum_values=["basic", "advanced"],
        )
        self.assertEqual(feature.normalize_entitlement_value("advanced"), "advanced")
        with self.assertRaises(ValidationError):
            feature.normalize_entitlement_value("unknown")
        with self.assertRaises(ValidationError):
            self.feature(
                "test.empty_enum",
                value_type=FeatureValueType.ENUM,
                aggregation_strategy=EntitlementAggregationStrategy.REPLACE,
                enum_values=[],
            )

    def test_boolean_integer_and_decimal_values_are_strict(self):
        boolean = self.feature("test.bool")
        self.assertIs(boolean.normalize_entitlement_value(True), True)
        with self.assertRaises(ValidationError):
            boolean.normalize_entitlement_value(1)

        integer = self.feature(
            "test.integer",
            value_type=FeatureValueType.INTEGER,
            aggregation_strategy=EntitlementAggregationStrategy.SUM,
            enforcement_policy=FeatureEnforcementPolicy.PRESERVE_EXISTING_BLOCK_NEW,
            usage_provider="test.integer_usage",
            minimum_value=Decimal("0"),
            maximum_value=Decimal("10"),
        )
        self.assertEqual(integer.normalize_entitlement_value(10), 10)
        for invalid in (True, 1.5, "5", -1, 11):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                integer.normalize_entitlement_value(invalid)

        decimal_feature = self.feature(
            "test.decimal",
            value_type=FeatureValueType.DECIMAL,
            aggregation_strategy=EntitlementAggregationStrategy.MAX,
            enforcement_policy=FeatureEnforcementPolicy.PRESERVE_EXISTING_BLOCK_NEW,
            usage_provider="test.decimal_usage",
            minimum_value=Decimal("0"),
        )
        self.assertEqual(decimal_feature.normalize_entitlement_value("1.250"), "1.25")
        with self.assertRaises(ValidationError):
            decimal_feature.normalize_entitlement_value("nan")


class SubscriptionPlanTests(CatalogMixin, TestCase):
    def test_profile_space_and_addon_are_distinct(self):
        profile = self.plan("base-profile")
        space = self.plan("base-space", subject_type=SubscriptionSubjectType.SPACE)
        addon = self.plan("space-addon", plan_type=SubscriptionPlanType.ADDON, subject_type=SubscriptionSubjectType.SPACE)
        self.assertNotEqual(profile.subject_type, space.subject_type)
        self.assertEqual(addon.plan_type, SubscriptionPlanType.ADDON)

    def test_default_constraints(self):
        with self.assertRaises(ValidationError):
            self.plan("bad-addon", plan_type=SubscriptionPlanType.ADDON, is_default=True)
        self.plan("profile-default", is_default=True)
        with self.assertRaises((ValidationError, IntegrityError)):
            with transaction.atomic():
                self.plan("profile-default-two", is_default=True)
        self.plan("space-default", subject_type=SubscriptionSubjectType.SPACE, is_default=True)

    def test_code_plan_type_subject_and_current_version_are_guarded(self):
        plan = self.plan("stable-plan")
        plan.code = "changed-plan"
        with self.assertRaises(ValidationError):
            plan.save()
        plan.refresh_from_db()
        plan.subject_type = SubscriptionSubjectType.SPACE
        with self.assertRaises(ValidationError):
            plan.save()
        with self.assertRaises(ValidationError):
            SubscriptionPlan.objects.filter(pk=plan.pk).update(current_version_id=None)


class PublicationTests(CatalogMixin, TestCase):
    def setUp(self):
        self.plan_obj = self.plan("versioned-plan", is_default=True)
        self.feature_obj = self.feature("versioned.feature")

    def test_version_unique_and_draft_mutable(self):
        version = self.version(self.plan_obj)
        version.name = "Nom modifié"
        version.save()
        with self.assertRaises((ValidationError, IntegrityError)):
            with transaction.atomic():
                self.version(self.plan_obj, 1)

    def test_publish_only_via_service_and_moves_current(self):
        version = self.version(self.plan_obj)
        self.configure(version, self.feature_obj)
        version.status = PlanVersionStatus.PUBLISHED
        with self.assertRaises(ValidationError):
            version.save()
        published = publish_plan_version(version)
        self.plan_obj.refresh_from_db()
        self.assertEqual(published.status, PlanVersionStatus.PUBLISHED)
        self.assertEqual(self.plan_obj.current_version_id, published.pk)
        self.assertIsNotNone(published.published_at)
        with self.assertRaises(ValidationError):
            PlanVersion.objects.filter(pk=published.pk).update(name="bypass")

    def test_published_version_benefits_entitlements_are_immutable(self):
        version = self.version(self.plan_obj)
        benefit = PlanBenefit.objects.create(plan_version=version, title="Benefit", position=0)
        entitlement = PlanEntitlement.objects.create(plan_version=version, feature=self.feature_obj, value=True)
        publish_plan_version(version)

        version.name = "Mutation"
        with self.assertRaises(ValidationError):
            version.save()
        benefit.title = "Mutation"
        with self.assertRaises(ValidationError):
            benefit.save()
        entitlement.value = False
        with self.assertRaises(ValidationError):
            entitlement.save()
        with self.assertRaises(ValidationError):
            PlanBenefit.objects.create(plan_version=version, title="New", position=1)
        with self.assertRaises(ValidationError):
            PlanEntitlement.objects.create(
                plan_version=version, feature=self.feature("versioned.other"), value=True
            )
        with self.assertRaises(ValidationError):
            benefit.delete()
        with self.assertRaises(ValidationError):
            entitlement.delete()
        with self.assertRaises(ValidationError):
            PlanBenefit.objects.filter(plan_version=version).delete()
        with self.assertRaises(ValidationError):
            PlanVersion.objects.filter(pk=version.pk).delete()

    def test_n_plus_one_retires_previous_and_preserves_history(self):
        v1 = self.version(self.plan_obj, 1)
        self.configure(v1, self.feature_obj)
        publish_plan_version(v1)
        v2 = self.version(self.plan_obj, 2, change_summary="Nouvelle configuration")
        self.configure(v2, self.feature_obj)
        publish_plan_version(v2)
        v1.refresh_from_db()
        v2.refresh_from_db()
        self.plan_obj.refresh_from_db()
        self.assertEqual(v1.status, PlanVersionStatus.RETIRED)
        self.assertIsNotNone(v1.retired_at)
        self.assertTrue(PlanVersion.objects.filter(pk=v1.pk).exists())
        self.assertEqual(v2.status, PlanVersionStatus.PUBLISHED)
        self.assertEqual(self.plan_obj.current_version_id, v2.pk)

    def test_non_contiguous_and_repeat_publication_are_controlled_refusals(self):
        v1 = self.version(self.plan_obj, 1)
        self.configure(v1, self.feature_obj)
        publish_plan_version(v1)
        v3 = self.version(self.plan_obj, 3)
        self.configure(v3, self.feature_obj)
        with self.assertRaises(CatalogTransitionError):
            publish_plan_version(v3)
        with self.assertRaises(CatalogTransitionError):
            publish_plan_version(v1)

    def test_inconsistent_entitlement_rolls_back_publication(self):
        inactive = self.feature("inactive.feature", is_active=False)
        version = self.version(self.plan_obj)
        PlanEntitlement.objects.bulk_create([PlanEntitlement(plan_version=version, feature=inactive, value=True)])
        with self.assertRaises(ValidationError):
            publish_plan_version(version)
        version.refresh_from_db()
        self.plan_obj.refresh_from_db()
        self.assertEqual(version.status, PlanVersionStatus.DRAFT)
        self.assertIsNone(self.plan_obj.current_version_id)

    def test_current_version_cannot_be_retired_without_replacement(self):
        version = self.version(self.plan_obj)
        self.configure(version, self.feature_obj)
        publish_plan_version(version)
        with self.assertRaises(CatalogTransitionError):
            retire_plan_version(version)


class EntitlementBenefitSelectorTests(CatalogMixin, TestCase):
    def test_feature_unique_subject_compatible_and_active(self):
        space_plan = self.plan("space-plan", subject_type=SubscriptionSubjectType.SPACE)
        space_version = self.version(space_plan)
        space_feature = self.feature("space.only", supports_profile=False, supports_space=True)
        PlanEntitlement.objects.create(plan_version=space_version, feature=space_feature, value=True)
        with self.assertRaises((ValidationError, IntegrityError)):
            with transaction.atomic():
                PlanEntitlement.objects.create(plan_version=space_version, feature=space_feature, value=True)

        profile_version = self.version(self.plan("profile-plan"))
        with self.assertRaises(ValidationError):
            PlanEntitlement.objects.create(plan_version=profile_version, feature=space_feature, value=True)
        inactive = self.feature("inactive.config", is_active=False)
        with self.assertRaises(ValidationError):
            PlanEntitlement.objects.create(plan_version=profile_version, feature=inactive, value=True)

    def test_enum_decimal_and_benefit_position_validation(self):
        version = self.version(self.plan("typed-plan"))
        enum_feature = self.feature(
            "typed.enum",
            value_type=FeatureValueType.ENUM,
            aggregation_strategy=EntitlementAggregationStrategy.REPLACE,
            enum_values=["basic", "advanced"],
        )
        with self.assertRaises(ValidationError):
            PlanEntitlement.objects.create(plan_version=version, feature=enum_feature, value="other")
        PlanEntitlement.objects.create(plan_version=version, feature=enum_feature, value="advanced")
        decimal_feature = self.feature(
            "typed.decimal",
            value_type=FeatureValueType.DECIMAL,
            aggregation_strategy=EntitlementAggregationStrategy.MAX,
            enforcement_policy=FeatureEnforcementPolicy.PRESERVE_EXISTING_BLOCK_NEW,
            usage_provider="typed.decimal_usage",
            minimum_value=Decimal("0"),
        )
        entitlement = PlanEntitlement.objects.create(plan_version=version, feature=decimal_feature, value="1.250")
        self.assertEqual(entitlement.value, "1.25")
        PlanBenefit.objects.create(plan_version=version, title="One", position=0)
        with self.assertRaises((ValidationError, IntegrityError)):
            with transaction.atomic():
                PlanBenefit.objects.create(plan_version=version, title="Two", position=0)

    def test_default_selector_requires_published_current_base(self):
        plan = self.plan("selector-plan", is_default=True)
        version = self.version(plan)
        self.configure(version, self.feature("selector.feature"))
        publish_plan_version(version)
        selected = get_current_default_base_plan(SubscriptionSubjectType.PROFILE)
        self.assertEqual(selected.pk, plan.pk)
        self.assertEqual(selected.current_version_id, version.pk)
        self.assertIsNone(get_current_default_base_plan(SubscriptionSubjectType.SPACE))
        with self.assertRaises(ValidationError):
            get_current_default_base_plan("event")


class SubscriptionBoundaryTests(TestCase):
    def test_subscriptions_has_no_services_or_opportunities_import(self):
        root = Path(__file__).resolve().parent
        forbidden = {"services", "opportunities"}
        violations = []
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".", 1)[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    roots = {node.module.split(".", 1)[0]}
                else:
                    continue
                if roots & forbidden:
                    violations.append((path.name, sorted(roots & forbidden)))
        self.assertEqual(violations, [])
