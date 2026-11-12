"""Best effort invalidations after durable commit, without private content."""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


def point_group(point_id):
    return f"conversation.point.{point_id}"


def invalidate_point(point, *, signal="point_changed"):
    point_id, version = str(point.pk), point.exchange_stream_version

    def publish():
        if not settings.CONVERSATIONS_REALTIME_ENABLED:
            return
        try:
            async_to_sync(get_channel_layer().group_send)(point_group(point_id), {
                "type": "scoped.signal", "point_id": point_id,
                "signal": signal, "stream_version": version,
            })
        except Exception:
            # Redis exception details may include a URL containing credentials.
            logger.warning("Conversation realtime invalidation unavailable; REST catch-up required")

    transaction.on_commit(publish)


def invalidate_receipts(point):
    invalidate_point(point, signal="receipt_changed")
