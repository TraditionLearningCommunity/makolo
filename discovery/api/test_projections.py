import uuid
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone

from core.participant_presentation import ParticipantActivityState
from discovery.card_contract import (
    ActionPresentation,
    DiscoveryCardPresentation,
    ParticipantActionSet,
    RepresentationPresentation,
)

from .composition import _primary_action_for_projection
from .projections import (
    project_funding_possibility,
    project_occurrence_possibility,
    project_opportunity_possibility,
    project_service_possibility,
)


def _participant_state(**overrides):
    values = {
        "availability": "available",
        "availability_label": "Disponible",
        "participant_state": "none",
        "label": None,
        "secondary_label": None,
        "primary_action": "Voir",
        "primary_url": "/owner/",
        "visual_variant": "brand",
        "expires_at": None,
    }
    values.update(overrides)
    return ParticipantActivityState(**values)


def _card(
    *,
    candidate_key,
    activity_id=None,
    occurrence_id=None,
    title="Possibilité",
    summary="Résumé utile",
    operator_name="Organisation publique",
    representation=None,
    primary=None,
    url="/owner/detail/",
):
    representation = representation or RepresentationPresentation(
        kind="identity",
        eyebrow="Contexte",
    )
    primary = primary or ActionPresentation(
        code="view",
        role="primary",
        label="Voir",
        icon="arrow-right",
        state="available",
        url=url,
        emphasis="primary",
    )
    return DiscoveryCardPresentation(
        candidate_key=candidate_key,
        activity_id=activity_id,
        occurrence_id=occurrence_id,
        presentation_kind="generic",
        vertical_label="Possibilité",
        title=title,
        summary=summary,
        operator_label="Proposé par",
        operator_name=operator_name,
        representation=representation,
        facts=(),
        participant_state=None,
        actions=ParticipantActionSet(
            save=ActionPresentation(
                code="save",
                role="save",
                label="Enregistrer",
                icon="orbit",
                state="available",
                url="/web/save/",
            ),
            primary=primary,
            share=ActionPresentation(
                code="share",
                role="share",
                label="Partager",
                icon="share-2",
                state="available",
                url="/web/share/",
            ),
        ),
        url=url,
    )


def _all_keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from _all_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _all_keys(nested)


class PossibilityProjectionContractTests(SimpleTestCase):
    def test_occurrence_projection_keeps_canonical_identity_and_resolved_relation(self):
        now = timezone.now()
        activity_id = str(uuid.uuid4())
        occurrence_id = str(uuid.uuid4())
        participant = _participant_state(
            participant_state="access_valid",
            primary_action="Voir mon accès",
            primary_url="/me/access/exact/",
            expires_at=now + timedelta(days=1),
        )
        item = SimpleNamespace(
            candidate_family="activity",
            candidate_key=f"activity:{activity_id}",
            activity_id=activity_id,
            occurrence_id=occurrence_id,
            matching_count=1,
            matching_occurrence_ids=[occurrence_id],
            timing_kind="exact",
            start_date=(now + timedelta(days=3)).date(),
            start_time=timezone.localtime(now + timedelta(days=3)).time().replace(tzinfo=None),
            end_date=(now + timedelta(days=3)).date(),
            end_time=timezone.localtime(now + timedelta(days=3, hours=2)).time().replace(tzinfo=None),
            start_at=now + timedelta(days=3),
            end_at=now + timedelta(days=3, hours=2),
            timezone="Africa/Lubumbashi",
            place=SimpleNamespace(
                id=str(uuid.uuid4()),
                name="Pullman",
                locality="Lubumbashi",
                latitude=-11.66,
                longitude=27.48,
            ),
            distance_km=3.2,
            price=SimpleNamespace(
                is_free=False,
                minimum=Decimal("20.00"),
                currency="USD",
            ),
            availability=SimpleNamespace(
                state="available",
                remaining=4,
            ),
            participant=participant,
        )
        card = _card(
            candidate_key=item.candidate_key,
            activity_id=activity_id,
            occurrence_id=occurrence_id,
            representation=RepresentationPresentation(
                kind="image",
                image_url="/media/concert.jpg",
                eyebrow="Concert",
            ),
            primary=ActionPresentation(
                code="access",
                role="primary",
                label="Mon accès",
                icon="pass",
                state="available",
                url="/me/access/exact/",
                emphasis="primary",
            ),
        )

        projection = project_occurrence_possibility(item, card, saved=True, can_save=True)

        self.assertEqual(projection["identity"]["family"], "activity")
        self.assertEqual(
            projection["identity"]["resource"],
            {"kind": "activity", "id": activity_id},
        )
        self.assertEqual(
            projection["identity"]["occurrence"],
            {"kind": "occurrence", "id": occurrence_id},
        )
        self.assertEqual(projection["price"]["minimum"], "20.00")
        self.assertEqual(projection["availability"], {"state": "available", "remaining": 4})
        self.assertEqual(projection["personal_relation"]["state"], "access_valid")
        self.assertEqual(projection["saved"]["state"], "saved")
        self.assertEqual(projection["watch"]["state"], "unknown")
        self.assertEqual(projection["capabilities"], ["view", "unsave", "access"])
        self.assertEqual(projection["links"]["access"], "/me/access/exact/")
        self.assertNotIn("save", projection["links"])
        self.assertNotIn("share", projection["links"])

    def test_service_projection_preserves_neutral_relation_and_unknown_availability(self):
        activity_id = str(uuid.uuid4())
        service_id = str(uuid.uuid4())
        participant = _participant_state(participant_state="none")
        item = {
            "candidate_family": "service_activity",
            "candidate_key": f"service_activity:{activity_id}",
            "activity_id": activity_id,
            "service_id": service_id,
            "participant": participant,
        }
        card = _card(candidate_key=item["candidate_key"], activity_id=activity_id)

        projection = project_service_possibility(item, card, saved=False, can_save=True)

        self.assertEqual(projection["personal_relation"]["state"], "none")
        self.assertEqual(projection["availability"]["state"], "unknown")
        self.assertEqual(projection["saved"]["state"], "not_saved")
        self.assertIn("save", projection["capabilities"])
        self.assertEqual(projection["links"]["detail"], "/owner/detail/")
        self.assertIn(
            {"kind": "service", "id": service_id},
            projection["provenance"]["resources"],
        )

    def test_saved_state_does_not_grant_save_capability_without_authority(self):
        activity_id = str(uuid.uuid4())
        item = {
            "candidate_family": "service_activity",
            "candidate_key": f"service_activity:{activity_id}",
            "activity_id": activity_id,
            "service_id": str(uuid.uuid4()),
            "participant": _participant_state(participant_state="none"),
        }
        card = _card(candidate_key=item["candidate_key"], activity_id=activity_id)

        projection = project_service_possibility(item, card, saved=False)

        self.assertEqual(projection["saved"]["state"], "not_saved")
        self.assertNotIn("save", projection["capabilities"])
        self.assertNotIn("unsave", projection["capabilities"])

    def test_funding_projection_keeps_unresolved_personal_relation_unknown(self):
        activity_id = str(uuid.uuid4())
        funding_id = uuid.uuid4()
        item = {
            "candidate_key": f"funding_activity:{activity_id}",
            "activity_id": activity_id,
            "funding": SimpleNamespace(pk=funding_id, opens_at=None, closes_at=None),
        }
        card = _card(candidate_key=item["candidate_key"], activity_id=activity_id)

        projection = project_funding_possibility(item, card)

        self.assertEqual(projection["identity"]["family"], "funding_activity")
        self.assertEqual(projection["personal_relation"], {"state": "unknown"})
        self.assertEqual(projection["saved"], {"state": "unknown"})
        self.assertEqual(projection["watch"], {"state": "unknown"})
        self.assertEqual(projection["capabilities"], ["view"])
        self.assertIn(
            {"kind": "funding", "id": str(funding_id)},
            projection["provenance"]["resources"],
        )

    def test_opportunity_projection_preserves_revision_without_fake_activity(self):
        opportunity_id = str(uuid.uuid4())
        revision_id = str(uuid.uuid4())
        item = {
            "candidate_family": "opportunity",
            "candidate_key": f"opportunity:{opportunity_id}",
            "opportunity_id": opportunity_id,
            "revision_id": revision_id,
            "temporal_state": "upcoming",
        }
        card = _card(
            candidate_key=item["candidate_key"],
            activity_id=None,
            title="Bourse Master Afrique",
            representation=RepresentationPresentation(
                kind="opportunity",
                eyebrow="À venir",
            ),
        )

        projection = project_opportunity_possibility(item, card, saved=True, can_save=True)

        self.assertEqual(
            projection["identity"]["resource"],
            {"kind": "opportunity", "id": opportunity_id},
        )
        self.assertIsNone(projection["identity"]["occurrence"])
        self.assertEqual(
            projection["identity"]["revision"],
            {"kind": "opportunity_revision", "id": revision_id},
        )
        self.assertEqual(projection["availability"]["state"], "upcoming")
        self.assertEqual(projection["personal_relation"], {"state": "unknown"})

    def test_projection_exposes_facts_not_frontend_interpretation_or_global_ranking(self):
        activity_id = str(uuid.uuid4())
        item = {
            "candidate_family": "service_activity",
            "candidate_key": f"service_activity:{activity_id}",
            "activity_id": activity_id,
            "service_id": str(uuid.uuid4()),
            "participant": _participant_state(
                label="Texte participant à ne pas transporter comme logique",
                secondary_label="Autre texte de présentation",
                visual_variant="warning",
            ),
        }
        card = _card(candidate_key=item["candidate_key"], activity_id=activity_id)

        projection = project_service_possibility(item, card)
        keys = set(_all_keys(projection))

        self.assertTrue(
            {
                "global_score",
                "match_percentage",
                "attention_score",
                "rank",
                "relevance",
                "probability",
                "confidence",
            }.isdisjoint(keys)
        )
        self.assertNotIn("visual_variant", keys)
        self.assertNotIn("primary_action", keys)
        self.assertNotIn("primary_url", keys)
        self.assertNotIn("availability_label", keys)
        self.assertNotIn("label", projection["personal_relation"])
        self.assertNotIn("access_credential", keys)


class DiscoveryPrimaryActionHandoffTests(SimpleTestCase):
    def test_web_only_owner_action_is_not_promoted_to_native(self):
        projection = {
            "links": {"detail": "/api/v1/discovery/items/activity/example/"},
            "engagement": {
                "owner": "activities",
                "state": "owner_contract",
                "capabilities": ["reserve"],
                "links": {},
                "presentation": {
                    "capability": "reserve",
                    "label": "Réserver",
                    "web": "/events/example/reserve/",
                    "web_enabled": True,
                },
            },
        }
        action = _primary_action_for_projection(projection)
        self.assertEqual(action["code"], "detail")
        self.assertEqual(action["destination"]["kind"], "detail")

    def test_funding_action_points_to_owner_native_route(self):
        funding_id = str(uuid.uuid4())
        projection = {
            "links": {"detail": "/api/v1/discovery/items/funding_activity/example/"},
            "engagement": {
                "owner": "funding",
                "state": "owner_api",
                "capabilities": ["contribute"],
                "resource": {"kind": "funding", "id": funding_id},
                "links": {
                    "native": f"/funding/{funding_id}/contribute",
                    "contribute": f"/api/v1/funding/{funding_id}/contributions/",
                },
            },
        }
        action = _primary_action_for_projection(projection)
        self.assertEqual(action["code"], "contribute")
        self.assertEqual(
            action["destination"],
            {"kind": "native", "path": f"/funding/{funding_id}/contribute"},
        )

    def test_obtention_action_uses_existing_native_journey_owner(self):
        obtention_id = str(uuid.uuid4())
        projection = {
            "links": {"detail": "/api/v1/discovery/items/activity/example/"},
            "engagement": {
                "owner": "obtention",
                "state": "owner_api",
                "capabilities": ["start_journey"],
                "resource": {"kind": "obtention", "id": obtention_id},
                "links": {
                    "native": f"/obtention/{obtention_id}/choose",
                    "start_journey": f"/api/v1/obtention/{obtention_id}/journeys/",
                },
            },
        }
        action = _primary_action_for_projection(projection)
        self.assertEqual(action["code"], "start_journey")
        self.assertEqual(
            action["destination"],
            {"kind": "native", "path": f"/obtention/{obtention_id}/choose"},
        )

    def test_mismatched_funding_route_falls_back_to_detail(self):
        projection = {
            "links": {"detail": "/detail/"},
            "engagement": {
                "owner": "funding",
                "state": "owner_api",
                "capabilities": ["contribute"],
                "resource": {"kind": "funding", "id": str(uuid.uuid4())},
                "links": {
                    "native": "/funding/other/contribute",
                    "contribute": "/api/v1/funding/other/contributions/",
                },
            },
        }
        self.assertEqual(
            _primary_action_for_projection(projection)["code"], "detail"
        )
