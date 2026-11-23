"""Additive stream backfill. Pause Exchange writes during the migration window."""
import hashlib
import json
import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Exists, F, OuterRef, Q
from django.utils import timezone


def backfill(apps, schema_editor):
    Entry = apps.get_model("conversations", "PointExchangeEntry")
    Point = apps.get_model("conversations", "ConversationPoint")
    Attachment = apps.get_model("conversations", "ConversationPointAttachment")
    alias = schema_editor.connection.alias
    # The migration is atomic. PostgreSQL blocks older writers for the entire
    # backfill, including those not yet aware of the Point stream lock.
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute('LOCK TABLE conversations_pointexchangeentry IN SHARE ROW EXCLUSIVE MODE')
    for point_id in Entry.objects.using(alias).order_by().values_list("point_id", flat=True).distinct().iterator(chunk_size=500):
        batch = []
        sequence = 0
        rows = Entry.objects.using(alias).filter(point_id=point_id).annotate(
            _has_media=Exists(Attachment.objects.using(alias).filter(exchange_entry_id=OuterRef("pk"))))
        for row in rows.order_by("created_at", "id").iterator(chunk_size=500):
            sequence += 1
            row.sequence = row.last_change_version = sequence
            row.updated_at = row.created_at
            payload = {"body": row.body.strip(), "reply_to_id": str(row.reply_to_id) if row.reply_to_id else None,
                       "represented_space_id": str(row.represented_space_id) if row.represented_space_id else None,
                       "mentions": [], "references": []}
            row.origin_payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            if row._has_media:
                # Legacy uploads substituted the filename for an empty caption.
                # Do not invent an exact original payload that was never stored.
                row.origin_payload_hash = ""
            batch.append(row)
            if len(batch) == 500:
                Entry.objects.using(alias).bulk_update(batch, ["sequence", "last_change_version", "origin_payload_hash", "updated_at"])
                batch = []
        if batch:
            Entry.objects.using(alias).bulk_update(batch, ["sequence", "last_change_version", "origin_payload_hash", "updated_at"])
        Point.objects.using(alias).filter(pk=point_id).update(exchange_stream_version=sequence)


def identity():
    return ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False))


def entry_fk(related):
    return models.ForeignKey(to="conversations.pointexchangeentry", on_delete=django.db.models.deletion.CASCADE, related_name=related)


def actor_fk(*, protect=False):
    return models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT if protect else django.db.models.deletion.CASCADE)


class Migration(migrations.Migration):
    dependencies = [("conversations", "0008_collective_access"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField("conversationpoint", "exchange_stream_version", models.PositiveBigIntegerField(default=0)),
        migrations.AddField("pointexchangeentry", "sequence", models.PositiveBigIntegerField(null=True)),
        migrations.AddField("pointexchangeentry", "last_change_version", models.PositiveBigIntegerField(default=0)),
        migrations.AddField("pointexchangeentry", "edit_version", models.PositiveIntegerField(default=1)),
        migrations.AddField("pointexchangeentry", "edited_at", models.DateTimeField(null=True, blank=True)),
        migrations.AddField("pointexchangeentry", "updated_at", models.DateTimeField(auto_now=True, default=timezone.now), preserve_default=False),
        migrations.AddField("pointexchangeentry", "origin_payload_hash", models.CharField(max_length=64, blank=True)),
        migrations.AddField("pointexchangeentry", "content_kind", models.CharField(max_length=16, default="text", choices=[("text", "Texte"), ("media", "Média"), ("reference", "Référence"), ("mixed", "Mixte")])),
        migrations.RunPython(backfill, migrations.RunPython.noop),
        migrations.AlterField("pointexchangeentry", "sequence", models.PositiveBigIntegerField()),
        migrations.AddConstraint("pointexchangeentry", models.UniqueConstraint(fields=["point", "sequence"], name="conv_entry_sequence_unique")),
        migrations.AddIndex("pointexchangeentry", models.Index(fields=["point", "sequence"], name="conv_entry_sequence_idx")),
        migrations.AddIndex("pointexchangeentry", models.Index(fields=["point", "last_change_version"], name="conv_entry_delta_idx")),
        migrations.CreateModel(name="ConversationEntryReaction", fields=[identity(), ("entry", entry_fk("reactions")), ("actor", actor_fk()), ("emoji", models.CharField(max_length=16)), ("created_at", models.DateTimeField(auto_now_add=True))], options={"constraints": [models.UniqueConstraint(fields=["entry", "actor", "emoji"], name="conv_entry_reaction_unique")]}),
        migrations.CreateModel(name="ConversationEntryMention", fields=[identity(), ("entry", entry_fk("mentions")), ("profile", actor_fk()), ("created_at", models.DateTimeField(auto_now_add=True))], options={"constraints": [models.UniqueConstraint(fields=["entry", "profile"], name="conv_entry_mention_unique")]}),
        migrations.CreateModel(name="ConversationEntryRevision", fields=[identity(), ("entry", entry_fk("revisions")), ("editor", actor_fk(protect=True)), ("from_version", models.PositiveIntegerField()), ("to_version", models.PositiveIntegerField()), ("old_content_sha256", models.CharField(max_length=64)), ("new_content_sha256", models.CharField(max_length=64)), ("client_reference", models.CharField(max_length=80)), ("edited_at", models.DateTimeField(auto_now_add=True))], options={"constraints": [models.UniqueConstraint(fields=["entry", "to_version"], name="conv_entry_revision_unique"), models.UniqueConstraint(fields=["entry", "client_reference"], name="conv_entry_revision_ref_unique")]}),
        migrations.CreateModel(name="ConversationEntryReceipt", fields=[identity(), ("point", models.ForeignKey(to="conversations.conversationpoint", on_delete=django.db.models.deletion.CASCADE, related_name="entry_receipts")), ("profile", actor_fk()), ("delivered_sequence", models.PositiveBigIntegerField(default=0)), ("read_sequence", models.PositiveBigIntegerField(default=0)), ("delivered_at", models.DateTimeField(null=True, blank=True)), ("read_at", models.DateTimeField(null=True, blank=True)), ("updated_at", models.DateTimeField(auto_now=True))], options={"constraints": [models.UniqueConstraint(fields=["point", "profile"], name="conv_entry_receipt_unique"), models.CheckConstraint(condition=Q(read_sequence__lte=F("delivered_sequence")), name="conv_receipt_read_delivered")]}),
    ]
