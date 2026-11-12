import asyncio
import hashlib
import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from channels.testing import WebsocketCommunicator
from django.test import SimpleTestCase, override_settings
from redis.exceptions import ConnectionError as RedisConnectionError

from .realtime_auth import consume_ticket, ticket_key
from .realtime_events import point_group
from .routing import websocket_urlpatterns


@override_settings(CONVERSATIONS_REDIS_PREFIX="test:conversations")
class RealtimeTicketTests(SimpleTestCase):
    def test_ticket_key_contains_hash_only(self):
        ticket = "temporary-credential-which-must-not-be-logged"
        self.assertNotIn(ticket, ticket_key(ticket))
        self.assertIn(hashlib.sha256(ticket.encode()).hexdigest(), ticket_key(ticket))

    @patch("conversations.realtime_auth.redis_client")
    def test_consumption_uses_atomic_getdel_and_replay_fails(self, client):
        client.return_value.getdel.side_effect = [json.dumps({"profile_id": "owner", "expires": 1}), None]
        ticket = "x" * 43
        self.assertEqual(consume_ticket(ticket)["profile_id"], "owner")
        self.assertIsNone(consume_ticket(ticket))
        self.assertEqual(client.return_value.getdel.call_count, 2)

    @patch("conversations.realtime_auth.redis_client")
    def test_expired_ticket_cannot_authenticate(self, client):
        client.return_value.getdel.return_value = None
        self.assertIsNone(consume_ticket("x" * 43))


@override_settings(CONVERSATIONS_REALTIME_ENABLED=True, ALLOWED_HOSTS=["testserver"],
                   CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}})
class RealtimeSocketTests(SimpleTestCase):
    def communicator(self, origin="https://testserver", path="/ws/v1/conversations/"):
        return WebsocketCommunicator(AllowedHostsOriginValidator(URLRouter(websocket_urlpatterns)), path,
                                     headers=[(b"origin", origin.encode())])

    @patch("conversations.consumers.within_budget", return_value=True)
    async def test_hostile_origin_never_accepts(self, budget):
        socket = self.communicator(origin="https://attacker.invalid")
        accepted, _ = await socket.connect()
        self.assertFalse(accepted)

    @patch("conversations.consumers.within_budget", return_value=True)
    async def test_subscription_requires_ticket(self, budget):
        socket = self.communicator()
        self.assertTrue((await socket.connect())[0])
        await socket.send_json_to({"type": "subscribe", "point_id": str(uuid4())})
        event = await socket.receive_output()
        self.assertEqual(event["code"], 4401)
        await socket.disconnect()

    @patch("conversations.consumers.within_budget", return_value=True)
    @patch("conversations.consumers.consume_ticket", return_value={"profile_id": "owner"})
    @patch("conversations.consumers.authorize", new_callable=AsyncMock)
    async def test_revocation_on_open_socket_blocks_next_signal(self, authorize, ticket, budget):
        authorize.return_value = "owner"
        point_id = str(uuid4())
        socket = self.communicator()
        await socket.connect()
        await socket.send_json_to({"type": "authenticate", "ticket": "x" * 43})
        self.assertEqual((await socket.receive_json_from())["type"], "authenticated")
        await socket.send_json_to({"type": "subscribe", "point_id": point_id})
        self.assertEqual((await socket.receive_json_from())["type"], "subscribed")
        authorize.return_value = None
        await get_channel_layer().group_send(point_group(point_id), {
            "type": "scoped.signal", "signal": "point_changed", "point_id": point_id, "stream_version": 3,
        })
        frame = await socket.receive_json_from()
        self.assertEqual(frame["code"], "access_revoked")
        self.assertNotIn("stream_version", frame)
        await socket.disconnect()

    @patch("conversations.consumers.within_budget", return_value=True)
    async def test_oversized_frame_closes_without_processing(self, budget):
        socket = self.communicator()
        await socket.connect()
        await socket.send_to(text_data="x" * 4097)
        self.assertEqual((await socket.receive_output())["code"], 1009)
        await socket.disconnect()

    @patch("conversations.consumers.within_budget", side_effect=RedisConnectionError("unavailable"))
    async def test_transport_fails_closed_when_redis_is_unavailable(self, budget):
        socket = self.communicator()
        self.assertFalse((await socket.connect())[0])

    @patch("conversations.consumers.within_budget", return_value=True)
    async def test_credentials_in_query_are_refused(self, budget):
        socket = self.communicator(path="/ws/v1/conversations/?ticket=forbidden")
        self.assertFalse((await socket.connect())[0])
