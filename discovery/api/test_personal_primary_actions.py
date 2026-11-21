from django.test import SimpleTestCase

from discovery.api.composition import _primary_action_for_projection


class PersonalDiscoveryPrimaryActionTests(SimpleTestCase):
    def _projection(self, engagement):
        return {
            "links": {"detail": "/api/v1/discovery/items/activity/known/"},
            "engagement": engagement,
        }

    def test_commerce_checkout_uses_verified_journey(self):
        engagement = {
            "owner": "commerce", "state": "owner_api",
            "capabilities": ["checkout"],
            "resource": {"kind": "journey", "id": "journey-id"},
            "links": {"checkout": "/api/v1/commerce/journeys/journey-id/checkout/",
                      "native": "/commerce/journeys/journey-id/checkout"},
        }
        action = _primary_action_for_projection(self._projection(engagement))
        self.assertEqual(action["code"], "checkout")
        self.assertEqual(action["destination"]["path"],
                         "/commerce/journeys/journey-id/checkout")

    def test_direct_activity_offer_action_is_owner_verified(self):
        engagement = {
            "owner": "commerce", "state": "owner_api",
            "capabilities": ["inspect_offers"],
            "resource": {"kind": "activity", "id": "activity-id"},
            "links": {
                "native": "/commerce/activities/activity-id/checkout",
                "offers": "/api/v1/commerce/activities/activity-id/checkout/",
            },
        }
        action = _primary_action_for_projection(self._projection(engagement))
        self.assertEqual(action["code"], "inspect_offers")
        self.assertEqual(action["label"], "Choisir une offre")
        self.assertEqual(action["destination"], {
            "kind": "native", "path": "/commerce/activities/activity-id/checkout",
        })

    def test_existing_order_takes_priority_over_new_checkout(self):
        engagement = {
            "owner": "commerce", "state": "owner_api",
            "capabilities": ["resume_order"],
            "resource": {"kind": "commerce_order", "id": "order-id"},
            "links": {"native": "/commerce/orders/order-id"},
        }
        self.assertEqual(
            _primary_action_for_projection(self._projection(engagement))["code"],
            "resume_order",
        )

    def test_existing_journey_can_continue(self):
        engagement = {
            "owner": "journeys", "state": "owner_api",
            "capabilities": ["continue"],
            "resource": {"kind": "journey", "id": "journey-id"},
            "links": {"native": "/journeys/journey-id"},
        }
        self.assertEqual(
            _primary_action_for_projection(self._projection(engagement))["code"],
            "continue",
        )

    def test_guest_service_start_is_visible_without_execution_permission(self):
        engagement = {
            "owner": "services",
            "state": "owner_api",
            "capabilities": ["start_after_auth"],
            "resource": {"kind": "service", "id": "service-id"},
            "links": {"start": "/api/v1/services/service-id/start/"},
            "presentation": {
                "capability": "start",
                "label": "Commencer",
                "enabled": False,
                "requires_auth": True,
            },
        }
        action = _primary_action_for_projection(self._projection(engagement))
        self.assertEqual(action["code"], "start")
        self.assertEqual(action["destination"], {
            "kind": "native",
            "path": "/services/service-id/start",
        })
        self.assertNotIn("start", engagement["capabilities"])
        self.assertFalse(engagement["presentation"]["enabled"])

    def test_guest_service_start_rejects_forged_auth_handoff(self):
        for engagement in (
            {
                "owner": "services",
                "state": "owner_contract",
                "capabilities": ["start_after_auth"],
                "resource": {"kind": "service", "id": "service-id"},
                "links": {"start": "/api/v1/services/service-id/start/"},
                "presentation": {
                    "capability": "start", "requires_auth": True,
                },
            },
            {
                "owner": "services",
                "state": "owner_api",
                "capabilities": [],
                "resource": {"kind": "service", "id": "service-id"},
                "links": {"start": "/api/v1/services/service-id/start/"},
                "presentation": {
                    "capability": "start", "requires_auth": True,
                },
            },
        ):
            with self.subTest(engagement=engagement):
                action = _primary_action_for_projection(self._projection(engagement))
                self.assertEqual(action["code"], "detail")

    def test_untrusted_or_unavailable_owner_action_falls_back_to_detail(self):
        for engagement in [
            {
                "owner": "commerce", "state": "owner_contract",
                "capabilities": ["checkout"],
                "resource": {"kind": "journey", "id": "journey-id"},
                "links": {"native": "/commerce/journeys/journey-id/checkout"},
            },
            {
                "owner": "commerce", "state": "owner_api",
                "capabilities": [],
                "resource": {"kind": "commerce_order", "id": "order-id"},
                "links": {"native": "/commerce/orders/order-id"},
            },
        ]:
            with self.subTest(engagement=engagement):
                self.assertEqual(
                    _primary_action_for_projection(self._projection(engagement))["code"],
                    "detail",
                )
