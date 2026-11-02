"""C8: a late provider probe must never certify a rotated or removed key."""
from unittest.mock import Mock, patch

from django.test import TestCase
from django.contrib import admin
from django.utils import timezone
from intelligence.admin import ProviderConnectionAdmin
from intelligence.credentials import get_provider_secret

from accounts.models import User, UserProfile
from intelligence.contracts import IntelligenceResult
from intelligence.connection_management import (
    create_connection, disconnect_connection, update_connection,
)
from intelligence.health import test_provider_connection
from intelligence.models import ProviderConnection, ProviderHealth, ProviderScope


@patch.dict(
    "os.environ",
    {"INTELLIGENCE_CREDENTIAL_MASTER_KEY": "unit-c8-health-master-key"},
)
class ProviderHealthConcurrentLifecycleTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(
            username="c8-health-owner", password="test",
        )
        UserProfile.objects.create(user=self.actor)
        self.connection = create_connection(
            actor=self.actor, scope=ProviderScope.PROFILE,
            payload={
                "provider": "openai",
                "name": "C8 provider health",
                "model": "test-model",
                "api_key": "original-c8-test-key",
                "consent": True,
            },
        )

    def _probe_with(self, operation):
        provider = Mock()
        provider.supports.side_effect = lambda capability: (
            capability.value == "text_generate"
        )
        def execute(request):
            operation(request)
            return IntelligenceResult(available=True, output="OK")
        provider.execute.side_effect = execute
        with patch(
            "intelligence.health.build_configured_provider",
            return_value=provider,
        ):
            return test_provider_connection(self.connection)

    def test_successful_probe_can_record_health(self):
        result = self._probe_with(lambda request: None)
        self.assertEqual(result, ProviderHealth.HEALTHY)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.health_status, ProviderHealth.HEALTHY)
        self.assertIsNotNone(self.connection.last_checked_at)

    def test_unavailable_result_cannot_certify_provider(self):
        provider = Mock()
        provider.supports.side_effect = lambda cap: cap.value == "text_generate"
        provider.execute.return_value = IntelligenceResult.unavailable(
            "invalid_credentials",
        )
        with patch(
            "intelligence.health.build_configured_provider",
            return_value=provider,
        ):
            result = test_provider_connection(self.connection)
        self.assertEqual(result, ProviderHealth.INVALID_CREDENTIALS)
        self.connection.refresh_from_db()
        self.assertEqual(
            self.connection.health_status,
            ProviderHealth.INVALID_CREDENTIALS,
        )

    def test_rotation_wins_over_late_healthy_probe(self):
        def rotate(request):
            update_connection(
                actor=self.actor, connection=self.connection,
                payload={"api_key": "new-c8-test-key"},
            )
        result = self._probe_with(rotate)
        self.assertEqual(result, ProviderHealth.UNKNOWN)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.health_status, ProviderHealth.UNKNOWN)
        self.assertIsNone(self.connection.last_checked_at)
        self.assertIsNone(self.connection.last_latency_ms)

    def test_disable_wins_over_late_healthy_probe(self):
        def disable(request):
            update_connection(
                actor=self.actor, connection=self.connection,
                payload={"enabled": False},
            )
        result = self._probe_with(disable)
        self.assertEqual(result, ProviderHealth.UNKNOWN)
        self.connection.refresh_from_db()
        self.assertFalse(self.connection.enabled)
        self.assertNotEqual(self.connection.health_status, ProviderHealth.HEALTHY)

    def test_admin_credential_rotation_invalidates_old_health(self):
        self.connection.health_status = ProviderHealth.HEALTHY
        self.connection.last_checked_at = timezone.now()
        self.connection.last_latency_ms = 8
        self.connection.save(update_fields=[
            "health_status", "last_checked_at", "last_latency_ms", "updated_at",
        ])
        model_admin = ProviderConnectionAdmin(ProviderConnection, admin.site)
        fake_form = Mock()
        fake_form.cleaned_data = {"api_key": "admin-replacement-test-key"}
        model_admin.save_model(
            request=Mock(user=self.actor),
            obj=self.connection,
            form=fake_form,
            change=True,
        )
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.health_status, ProviderHealth.UNKNOWN)
        self.assertIsNone(self.connection.last_checked_at)
        self.assertIsNone(self.connection.last_latency_ms)
        self.assertEqual(
            get_provider_secret(connection=self.connection),
            "admin-replacement-test-key",
        )

    def test_removed_connection_is_not_recreated_by_old_probe(self):
        def disconnect(request):
            disconnect_connection(
                actor=self.actor, connection=self.connection,
            )
        result = self._probe_with(disconnect)
        self.assertEqual(result, ProviderHealth.UNKNOWN)
        self.assertFalse(
            ProviderConnection.objects.filter(pk=self.connection.pk).exists()
        )
