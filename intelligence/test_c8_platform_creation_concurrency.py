"""C8 PostgreSQL evidence: distinct operators share Platform connection ownership."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from accounts.models import User, UserProfile
from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from intelligence.connection_management import create_connection
from intelligence.models import ProviderConnection, ProviderScope


@patch.dict(
    "os.environ",
    {"INTELLIGENCE_CREDENTIAL_MASTER_KEY": "unit-c8-platform-lock-key"},
)
class PlatformConcurrentConnectionTests(TransactionTestCase):
    def setUp(self):
        self.operators = []
        for index in range(2):
            actor = User.objects.create_user(
                username=f"c8-platform-operator-{index}",
                password="test",
            )
            UserProfile.objects.create(user=actor)
            grant_platform_role(
                profile=actor, role=SystemRoleCode.PLATFORM_ADMIN,
                granted_by=actor,
            )
            self.operators.append(actor.pk)

    def test_distinct_platform_operators_cannot_create_duplicate_provider(self):
        if connection.vendor != "postgresql":
            self.skipTest("Real transaction lock behavior requires PostgreSQL.")
        barrier = Barrier(2, timeout=10)

        def create(actor_id):
            close_old_connections()
            try:
                barrier.wait()
                actor = User.objects.get(pk=actor_id)
                try:
                    create_connection(
                        actor=actor, scope=ProviderScope.PLATFORM,
                        payload={
                            "provider": "tavily",
                            "name": "C8 shared provider",
                            "api_key": "C8-NOT-LOGGED-KEY",
                            "consent": True,
                        },
                    )
                except ValidationError:
                    return "duplicate"
                return "created"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(create, self.operators))
        self.assertCountEqual(outcomes, ["created", "duplicate"])
        self.assertEqual(
            ProviderConnection.objects.filter(
                scope=ProviderScope.PLATFORM,
                name="C8 shared provider",
            ).count(),
            1,
        )
