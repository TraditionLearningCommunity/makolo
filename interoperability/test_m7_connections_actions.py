from types import SimpleNamespace

from django.test import SimpleTestCase

from intelligence.interoperability import connection_ref
from interoperability.actions import (
    ActionAuthorizationError,
    ActionConnectionRequired,
    ActionDefinition,
    ActionExecutionContext,
    ActionRegistry,
)
from interoperability.connections import (
    ConnectionAuthorizationError,
    ConnectionRef,
    ConnectionScope,
    ConnectionUnavailable,
    authorize_connection,
)
from interoperability.registry import CapabilityDefinition, InteroperabilityRegistry


class ConnectionAuthorizationTests(SimpleTestCase):
    def test_profile_connection_is_private_to_owner(self):
        connection = ConnectionRef(id="c1", scope=ConnectionScope.PROFILE, enabled=True, profile_id="p1")
        authorize_connection(
            actor_id="p1",
            connection=connection,
            has_platform_authority=lambda: False,
            has_space_authority=lambda _space_id: False,
        )
        with self.assertRaises(ConnectionAuthorizationError):
            authorize_connection(
                actor_id="p2",
                connection=connection,
                has_platform_authority=lambda: True,
                has_space_authority=lambda _space_id: True,
            )

    def test_space_membership_is_not_an_authority_shortcut(self):
        connection = ConnectionRef(id="c1", scope=ConnectionScope.SPACE, enabled=True, space_id="s1")
        with self.assertRaises(ConnectionAuthorizationError):
            authorize_connection(
                actor_id="p1",
                connection=connection,
                has_platform_authority=lambda: False,
                has_space_authority=lambda _space_id: False,
            )

    def test_disabled_connection_is_unavailable_even_for_owner(self):
        connection = ConnectionRef(id="c1", scope=ConnectionScope.PROFILE, enabled=False, profile_id="p1")
        with self.assertRaises(ConnectionUnavailable):
            authorize_connection(
                actor_id="p1",
                connection=connection,
                has_platform_authority=lambda: True,
                has_space_authority=lambda _space_id: True,
            )

    def test_intelligence_profile_connection_projects_canonical_user_id(self):
        connection = SimpleNamespace(
            pk="c1",
            scope="profile",
            enabled=True,
            profile_id="profile-row-id",
            profile=SimpleNamespace(user_id="canonical-user-id"),
            space_id=None,
        )
        ref = connection_ref(connection)
        self.assertEqual(ref.profile_id, "canonical-user-id")
        authorize_connection(
            actor_id="canonical-user-id",
            connection=ref,
            has_platform_authority=lambda: False,
            has_space_authority=lambda _space_id: False,
        )


class ActionRegistryTests(SimpleTestCase):
    def setUp(self):
        registry = InteroperabilityRegistry()
        registry.register_capability(CapabilityDefinition(code="notify.send", owner="notifications"))
        self.actions = ActionRegistry(registry)
        self.calls = []

    def _register(self, *, authorize=lambda _context: True, requires_connection=True, idempotent=False):
        self.actions.register(
            ActionDefinition(
                code="notifications.send",
                capability="notify.send",
                owner="notifications",
                authorize=authorize,
                requires_connection=requires_connection,
                idempotent=idempotent,
                handler=lambda context, payload: self.calls.append((context, payload)) or {"accepted": True},
            )
        )

    def test_action_denies_before_handler(self):
        self._register(authorize=lambda _context: False, requires_connection=False)
        with self.assertRaises(ActionAuthorizationError):
            self.actions.execute("notifications.send", context=ActionExecutionContext(actor=object()), payload={})
        self.assertEqual(self.calls, [])

    def test_connection_required_before_handler(self):
        self._register()
        with self.assertRaises(ActionConnectionRequired):
            self.actions.execute("notifications.send", context=ActionExecutionContext(actor=object()), payload={})
        self.assertEqual(self.calls, [])

    def test_domain_handler_runs_only_after_authority_and_connection(self):
        self._register()
        connection = ConnectionRef(id="c1", scope=ConnectionScope.PROFILE, enabled=True, profile_id="p1")
        result = self.actions.execute(
            "notifications.send",
            context=ActionExecutionContext(actor=object(), connection=connection),
            payload={"message": "minimal"},
            authorize_connection=lambda _connection: None,
        )
        self.assertEqual(result, {"accepted": True})
        self.assertEqual(len(self.calls), 1)
