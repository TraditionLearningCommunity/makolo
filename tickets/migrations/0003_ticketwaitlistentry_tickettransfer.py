import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tickets", "0002_align_generated_index_names"),
    ]

    operations = [
        migrations.CreateModel(
            name="TicketWaitlistEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("requested_quantity", models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])),
                ("status", models.CharField(choices=[("waiting", "En attente"), ("offered", "Place proposée"), ("converted", "Billet obtenu"), ("cancelled", "Retiré"), ("expired", "Offre expirée")], default="waiting", max_length=16)),
                ("offered_at", models.DateTimeField(blank=True, null=True)),
                ("offer_expires_at", models.DateTimeField(blank=True, null=True)),
                ("converted_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("offered_order", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="waitlist_entry", to="tickets.ticketorder")),
                ("ticket_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="waitlist_entries", to="tickets.tickettype")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ticket_waitlist_entries", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["created_at", "id"],
                "indexes": [
                    models.Index(fields=["ticket_type", "status", "created_at"], name="ticket_waitlist_queue_idx"),
                    models.Index(fields=["user", "status", "created_at"], name="ticket_waitlist_user_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(condition=models.Q(("status__in", ["waiting", "offered"])), fields=("ticket_type", "user"), name="ticket_waitlist_one_active_user"),
                ],
            },
        ),
        migrations.CreateModel(
            name="TicketTransfer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("recipient_email", models.EmailField(max_length=254)),
                ("status", models.CharField(choices=[("pending", "En attente"), ("accepted", "Accepté"), ("declined", "Refusé"), ("cancelled", "Annulé"), ("expired", "Expiré")], default="pending", max_length=16)),
                ("expires_at", models.DateTimeField()),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("declined_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("expired_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="incoming_ticket_transfers", to=settings.AUTH_USER_MODEL)),
                ("sender", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="outgoing_ticket_transfers", to=settings.AUTH_USER_MODEL)),
                ("ticket", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transfers", to="tickets.ticket")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["recipient", "status", "created_at"], name="ticket_transfer_recipient_idx"),
                    models.Index(fields=["sender", "status", "created_at"], name="ticket_transfer_sender_idx"),
                    models.Index(fields=["status", "expires_at"], name="ticket_transfer_expiry_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(condition=models.Q(("status", "pending")), fields=("ticket",), name="ticket_transfer_one_pending"),
                ],
            },
        ),
    ]
