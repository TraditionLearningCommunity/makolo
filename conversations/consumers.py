import asyncio
import hashlib
import json
import time
from uuid import UUID

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.core.exceptions import ValidationError
from redis.exceptions import RedisError

from .point_models import ConversationPoint
from .point_services import _active_window, point_response_allowed, point_visible_to
from .realtime_auth import bound_actor, consume_ticket
from .realtime_events import point_group
from .realtime_limits import within_budget
from .realtime_presence import mark_active


@database_sync_to_async
def authorize(binding, point_id=None, *, ephemeral=False):
    actor = bound_actor(binding)
    if actor is None:
        return None
    if point_id is None:
        return str(actor.pk)
    point = ConversationPoint.objects.select_related("conversation__policy").filter(pk=point_id, kind="exchange").first()
    if point is None or not point_visible_to(actor, point):
        return None
    if ephemeral:
        # Replies with restricted visibility must not disclose identities here.
        if point.response_visibility != "point_viewers" or not point_response_allowed(actor, point):
            return None
        try:
            _active_window(point)
        except ValidationError:
            return None
    return str(actor.pk)


class ConversationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.binding = None
        self.authenticated = False
        self.subscriptions = set()
        self.deadline_task = None
        self.started = time.monotonic()
        self.frames = 0
        if not settings.CONVERSATIONS_REALTIME_ENABLED or self.scope.get("query_string"):
            await self.close(code=1013)
            return
        address = str(self.scope.get("client", ("",))[0])
        try:
            allowed = await sync_to_async(within_budget)("connect-budget", hashlib.sha256(address.encode()).hexdigest(), maximum=60, seconds=60)
        except (RedisError, OSError):
            allowed = False
        if not allowed:
            await self.close(code=1013)
            return
        await self.accept()
        self.deadline_task = asyncio.create_task(self.expire_auth())

    async def expire_auth(self):
        try:
            await self._guard_auth()
        except (RedisError, OSError):
            await self.close(code=1013)

    async def _guard_auth(self):
        await asyncio.sleep(5)
        if not self.authenticated:
            await self.close(code=4401)
            return
        while True:
            await asyncio.sleep(20)
            if not await authorize(self.binding):
                await self.close(code=4401)
                return
            for point_id in tuple(self.subscriptions):
                if not await authorize(self.binding, point_id):
                    await self.revoke(point_id)
                else:
                    await self.channel_layer.group_add(point_group(point_id), self.channel_name)

    async def disconnect(self, code):
        if self.deadline_task:
            self.deadline_task.cancel()
        for point_id in self.subscriptions:
            try:
                await self.channel_layer.group_discard(point_group(point_id), self.channel_name)
            except (RedisError, OSError):
                pass  # Membership expires; there is no durable mutation to retry.

    async def send_frame(self, **frame):
        await self.send(text_data=json.dumps(frame))

    async def revoke(self, point_id):
        self.subscriptions.discard(point_id)
        try:
            await self.channel_layer.group_discard(point_group(point_id), self.channel_name)
        except (RedisError, OSError):
            await self.close(code=1013)
            return
        await self.send_frame(type="error", code="access_revoked", point_id=point_id)

    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None or len(text_data.encode()) > settings.CONVERSATIONS_REALTIME_FRAME_BYTES:
            await self.close(code=1009)
            return
        if time.monotonic() - self.started >= 10:
            self.started, self.frames = time.monotonic(), 0
        self.frames += 1
        if self.frames > 50:
            await self.close(code=4429)
            return
        try:
            data = json.loads(text_data)
            if not isinstance(data, dict):
                raise ValueError
            kind = data.get("type")
            if self.binding is None:
                if kind != "authenticate":
                    await self.close(code=4401)
                    return
                self.binding = await sync_to_async(consume_ticket)(data.get("ticket"))
                if not await authorize(self.binding):
                    await self.close(code=4401)
                    return
                self.authenticated = True
                await self.send_frame(type="authenticated")
                return
            if not await authorize(self.binding):
                await self.close(code=4401)
                return
            if kind == "ping":
                await self.send_frame(type="pong")
                return
            if kind not in {"subscribe", "unsubscribe", "typing", "presence"}:
                raise ValueError
            point_id = str(UUID(str(data.get("point_id"))))
            if kind == "unsubscribe":
                self.subscriptions.discard(point_id)
                await self.channel_layer.group_discard(point_group(point_id), self.channel_name)
                return
            ephemeral = kind in {"typing", "presence"}
            actor_id = await authorize(self.binding, point_id, ephemeral=ephemeral)
            if actor_id is None:
                await self.send_frame(type="error", code="inaccessible")
                return
            if kind == "subscribe":
                if len(self.subscriptions) >= settings.CONVERSATIONS_REALTIME_MAX_SUBSCRIPTIONS and point_id not in self.subscriptions:
                    await self.send_frame(type="error", code="subscription_limit")
                    return
                await self.channel_layer.group_add(point_group(point_id), self.channel_name)
                self.subscriptions.add(point_id)
                await self.send_frame(type="subscribed", point_id=point_id)
            elif point_id in self.subscriptions:
                permitted = await sync_to_async(within_budget)(f"{kind}-budget", f"{point_id}:{actor_id}", maximum=1, seconds=3 if kind == "typing" else 20)
                if permitted:
                    ttl = await sync_to_async(mark_active)(point_id, actor_id, typing=kind == "typing")
                    await self.channel_layer.group_send(point_group(point_id), {
                        "type": "scoped.signal", "signal": f"{kind}_changed", "point_id": point_id,
                        "profile_id": actor_id, "ttl": ttl,
                    })
        except (ValueError, TypeError, KeyError):
            await self.send_frame(type="error", code="invalid_frame")
        except (RedisError, OSError):
            await self.close(code=1013)

    async def scoped_signal(self, event):
        point_id = event["point_id"]
        if point_id not in self.subscriptions:
            return
        ephemeral = event["signal"] in {"typing_changed", "presence_changed"}
        if not await authorize(self.binding, point_id):
            await self.revoke(point_id)
            return
        if ephemeral and not await authorize(self.binding, point_id, ephemeral=True):
            return
        await self.send_frame(**{**{k: v for k, v in event.items() if k not in {"type", "signal"}}, "type": event["signal"]})
