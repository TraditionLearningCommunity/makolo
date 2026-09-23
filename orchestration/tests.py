from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity
from activities.services import create_activity
from organizations.models import Organization, Team, TeamMembership
from resolver.contracts import (
    AssertionKind,
    CanonicalRef,
    EndpointKind,
    ResolvedMaterial,
    ResolutionAssertion,
    ResolutionEndpoint,
    ResolutionOutcome,
    ResolutionStatus,
)
from resolver.identifiers import make_resolution_ref

from .activity_owner import ActivityResolvedMaterialHandler
from .contracts import OrchestrationContext, OrchestrationDecision
from .resolved_material import (
    ResolvedMaterialOwnerRegistry,
    orchestrate_resolved_material,
    orchestrate_resolution,
)


User = get_user_model()


def _material(*assertions, outcome=ResolutionOutcome.RESOLVED, completed_at=None):
    fingerprint = "actor5-test-fingerprint"
    interpretation_ref = "interpretation:test"
    completed_at = completed_at or timezone.now()
    return ResolvedMaterial(
        resolution_ref=make_resolution_ref(
            interpretation_ref=interpretation_ref,
            strategy_fingerprint=fingerprint,
        ),
        interpretation_ref=interpretation_ref,
        material_key="material:test",
        observation_ref="observation:test",
        target_key="web_url:v1:" + ("a" * 64),
        strategy_key="actor5-test",
        strategy_version="1",
        strategy_fingerprint=fingerprint,
        started_at=completed_at - timedelta(seconds=1),
        completed_at=completed_at,
        outcome=outcome,
        assertions=tuple(assertions),
    )


def _matched_entity(*, domain="activity", object_ref="1"):
    return ResolutionAssertion(
        assertion_ref="assertion:entity",
        candidate_ref="candidate:entity",
        kind=AssertionKind.ENTITY,
        status=ResolutionStatus.MATCHED,
        canonical_ref=CanonicalRef(domain, str(object_ref)),
        candidate_payload={"kind": "entity", "label": "Known"},
    )


def _new_entity():
    return ResolutionAssertion(
        assertion_ref="assertion:new",
        candidate_ref="candidate:new",
        kind=AssertionKind.ENTITY,
        status=ResolutionStatus.NEW_CANDIDATE,
        provisional_ref="provisional:test",
        candidate_payload={"kind": "entity", "label": "New"},
    )


def _activity_update(activity, *, value, predicate="title", assertion_ref="assertion:update"):
    return ResolutionAssertion(
        assertion_ref=assertion_ref,
        candidate_ref="candidate:update",
        kind=AssertionKind.FACT,
        status=ResolutionStatus.UPDATE,
        subject=ResolutionEndpoint(
            kind=EndpointKind.CANONICAL,
            ref=f"activity:{activity.pk}",
            canonical_ref=CanonicalRef("activity", str(activity.pk)),
        ),
        predicate=predicate,
        candidate_payload={
            "kind": "fact",
            "predicate": predicate,
            "value": {"kind": "text", "text": value},
        },
    )


class ResolvedMaterialDecisionTests(TestCase):
    def test_identity_match_is_no_action_not_mutation(self):
        result = orchestrate_resolved_material(_material(_matched_entity()))
        self.assertEqual(result.no_action_count, 1)
        self.assertEqual(
            result.decisions[0].reason_code,
            "identity_match_is_not_a_business_mutation",
        )

    def test_new_candidate_requires_review_and_creates_nothing(self):
        before = Activity.objects.count()
        result = orchestrate_resolved_material(_material(_new_entity()))
        self.assertEqual(result.review_count, 1)
        self.assertEqual(result.decisions[0].reason_code, "new_candidate_requires_owner_decision")
        self.assertEqual(Activity.objects.count(), before)

    def test_conflict_is_preserved_without_owner_dispatch(self):
        assertion = ResolutionAssertion(
            assertion_ref="assertion:conflict",
            candidate_ref="candidate:conflict",
            kind=AssertionKind.CONFLICT,
            status=ResolutionStatus.CONFLICT,
            predicate="title",
            candidate_payload={"reason": "conflicting_values"},
        )
        result = orchestrate_resolved_material(
            _material(assertion, outcome=ResolutionOutcome.CONFLICT)
        )
        self.assertEqual(result.conflict_count, 1)
        self.assertEqual(
            result.decisions[0].reason_code,
            "resolved_conflict_requires_no_mutation",
        )

    def test_unregistered_owner_routes_to_review_not_dynamic_orm(self):
        assertion = ResolutionAssertion(
            assertion_ref="assertion:unknown-owner",
            candidate_ref="candidate:unknown-owner",
            kind=AssertionKind.FACT,
            status=ResolutionStatus.UPDATE,
            subject=ResolutionEndpoint(
                kind=EndpointKind.CANONICAL,
                ref="opportunity:1",
                canonical_ref=CanonicalRef("opportunity", "1"),
            ),
            predicate="title",
            candidate_payload={
                "kind": "fact",
                "predicate": "title",
                "value": {"kind": "text", "text": "Changed"},
            },
        )
        result = orchestrate_resolved_material(_material(assertion))
        self.assertEqual(result.review_count, 1)
        self.assertEqual(result.decisions[0].reason_code, "owner_handler_not_registered")

    def test_handoff_consumes_resolver_source_port(self):
        material = _material(_matched_entity())

        class Source:
            def __init__(self):
                self.requested = None

            def get_material(self, resolution_ref):
                self.requested = resolution_ref
                return material

        source = Source()
        result = orchestrate_resolution(material.resolution_ref, source=source)
        self.assertEqual(source.requested, material.resolution_ref)
        self.assertEqual(result.resolution_ref, material.resolution_ref)


class ActivityOwnerOrchestrationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="actor5-owner",
            email="actor5-owner@example.test",
            password="StrongPass2026!",
        )
        self.other = User.objects.create_user(
            username="actor5-other",
            email="actor5-other@example.test",
            password="StrongPass2026!",
        )

    def _trusted_registry(self):
        registry = ResolvedMaterialOwnerRegistry()
        registry.register(
            "activity",
            ActivityResolvedMaterialHandler(
                source_authorizer=lambda **kwargs: True,
            ),
        )
        return registry

    def _fresh_material(self, assertion):
        return _material(
            assertion,
            completed_at=timezone.now() + timedelta(seconds=2),
        )

    def test_default_registry_does_not_trust_external_source_implicitly(self):
        activity = create_activity(
            owner_profile=self.owner,
            created_by=self.owner,
            title="Original",
        )
        assertion = _activity_update(activity, value="Observed change")
        result = orchestrate_resolved_material(
            self._fresh_material(assertion),
            context=OrchestrationContext(actor=self.owner),
        )
        activity.refresh_from_db()
        self.assertEqual(activity.title, "Original")
        self.assertEqual(result.review_count, 1)
        self.assertEqual(result.decisions[0].reason_code, "source_authority_not_established")

    def test_explicit_source_policy_and_owner_authority_apply_via_domain_service(self):
        activity = create_activity(
            owner_profile=self.owner,
            created_by=self.owner,
            title="Original",
        )
        assertion = _activity_update(activity, value="Canonical update")
        result = orchestrate_resolved_material(
            self._fresh_material(assertion),
            context=OrchestrationContext(actor=self.owner),
            registry=self._trusted_registry(),
        )
        activity.refresh_from_db()
        self.assertEqual(activity.title, "Canonical update")
        self.assertEqual(result.applied_count, 1)
        self.assertEqual(result.decisions[0].operation, "activity.update_common")

    def test_replay_of_same_update_is_no_action(self):
        activity = create_activity(
            owner_profile=self.owner,
            created_by=self.owner,
            title="Original",
        )
        material = self._fresh_material(_activity_update(activity, value="Canonical update"))
        first = orchestrate_resolved_material(
            material,
            context=OrchestrationContext(actor=self.owner),
            registry=self._trusted_registry(),
        )
        second = orchestrate_resolved_material(
            material,
            context=OrchestrationContext(actor=self.owner),
            registry=self._trusted_registry(),
        )
        self.assertEqual(first.applied_count, 1)
        self.assertEqual(second.no_action_count, 1)
        self.assertEqual(second.decisions[0].reason_code, "activity_update_already_applied")

    def test_stale_resolution_cannot_overwrite_newer_canonical_state(self):
        activity = create_activity(
            owner_profile=self.owner,
            created_by=self.owner,
            title="Current",
        )
        material = _material(
            _activity_update(activity, value="Old observation"),
            completed_at=activity.updated_at - timedelta(seconds=1),
        )
        result = orchestrate_resolved_material(
            material,
            context=OrchestrationContext(actor=self.owner),
            registry=self._trusted_registry(),
        )
        activity.refresh_from_db()
        self.assertEqual(activity.title, "Current")
        self.assertEqual(result.review_count, 1)
        self.assertEqual(result.decisions[0].reason_code, "canonical_state_newer_than_resolution")

    def test_space_parameter_cannot_fabricate_authority(self):
        space = Organization.objects.create(name="Actor 5 Space", created_by=self.owner)
        activity = create_activity(space=space, created_by=self.owner, title="Space Activity")
        team = Team.objects.create(organization=space, name="Team", is_default=True)
        TeamMembership.objects.create(team=team, user=self.other)

        result = orchestrate_resolved_material(
            self._fresh_material(_activity_update(activity, value="Forged")),
            context=OrchestrationContext(actor=self.other, represented_space=space),
            registry=self._trusted_registry(),
        )
        activity.refresh_from_db()
        self.assertEqual(activity.title, "Space Activity")
        self.assertEqual(result.rejected_count, 1)
        self.assertEqual(result.decisions[0].reason_code, "activity_manage_permission_required")

    def test_wrong_represented_space_is_rejected_even_for_personal_actor(self):
        space = Organization.objects.create(name="Wrong Actor 5 Space", created_by=self.owner)
        activity = create_activity(
            owner_profile=self.owner,
            created_by=self.owner,
            title="Personal Activity",
        )
        result = orchestrate_resolved_material(
            self._fresh_material(_activity_update(activity, value="Forged")),
            context=OrchestrationContext(actor=self.owner, represented_space=space),
            registry=self._trusted_registry(),
        )
        activity.refresh_from_db()
        self.assertEqual(activity.title, "Personal Activity")
        self.assertEqual(result.rejected_count, 1)
        self.assertEqual(
            result.decisions[0].reason_code,
            "personal_activity_cannot_use_represented_space",
        )

    def test_unsupported_predicate_never_uses_generic_setattr(self):
        activity = create_activity(
            owner_profile=self.owner,
            created_by=self.owner,
            title="Original",
        )
        result = orchestrate_resolved_material(
            self._fresh_material(
                _activity_update(activity, value="x", predicate="unknown_field")
            ),
            context=OrchestrationContext(actor=self.owner),
            registry=self._trusted_registry(),
        )
        self.assertEqual(result.review_count, 1)
        self.assertEqual(result.decisions[0].reason_code, "activity_predicate_not_supported")
