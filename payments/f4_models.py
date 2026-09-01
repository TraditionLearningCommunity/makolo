import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .models import FinancialAllocationLine, LedgerEntry, PaymentObligation


class FundFlowStrategy(models.TextChoices):
    PLATFORM_COLLECT = "platform_collect", "Collecte Makolo"
    PROVIDER_SPLIT = "provider_split", "Split provider"
    DIRECT_TO_PAYEE = "direct_to_payee", "Direct bénéficiaire"
    EXTERNAL = "external", "Hors rails Makolo"


class FundFlowSourceLevel(models.TextChoices):
    PLATFORM = "platform", "Défaut Makolo"
    SPACE = "space", "Espace"
    ACTIVITY = "activity", "Activity"
    OFFER = "offer", "Offer"


class FinancialDestinationType(models.TextChoices):
    BANK_ACCOUNT = "bank_account", "Compte bancaire"
    MOBILE_MONEY = "mobile_money", "Mobile money"
    CONNECTED_ACCOUNT = "connected_account", "Compte provider connecté"
    MERCHANT_ACCOUNT = "merchant_account", "Compte marchand"
    OTHER = "other", "Autre"


class FinancialDestinationStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    ACTIVE = "active", "Active"
    DISABLED = "disabled", "Désactivée"


class SettlementStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    READY = "ready", "Prêt"
    PROCESSING = "processing", "En traitement"
    SETTLED = "settled", "Réglé"
    CANCELLED = "cancelled", "Annulé"
    FAILED = "failed", "Échoué"


class PayoutProvider(models.TextChoices):
    SANDBOX = "sandbox", "Sandbox"
    MANUAL = "manual", "Manuel"


class PayoutStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    PROCESSING = "processing", "En traitement"
    SUCCEEDED = "succeeded", "Réussi"
    FAILED = "failed", "Échoué"
    CANCELLED = "cancelled", "Annulé"
    REVERSED = "reversed", "Reversé"


class FundMovementType(models.TextChoices):
    PAYOUT = "payout", "Payout"
    PAYOUT_REVERSAL = "payout_reversal", "Reversal payout"
    DIRECT_PAYEE = "direct_payee", "Paiement direct bénéficiaire"
    PROVIDER_SPLIT_PAYEE = "provider_split_payee", "Split provider bénéficiaire"
    PROVIDER_SPLIT_PLATFORM = "provider_split_platform", "Split provider Makolo"
    EXTERNAL_PAYEE = "external_payee", "Paiement externe bénéficiaire"


class FundFlowConfiguration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    platform_default = models.BooleanField(default=False)
    space = models.OneToOneField(
        "organizations.Organization", on_delete=models.CASCADE, related_name="fund_flow_configuration", null=True, blank=True
    )
    activity = models.OneToOneField(
        "activities.Activity", on_delete=models.CASCADE, related_name="fund_flow_configuration", null=True, blank=True
    )
    offer = models.OneToOneField(
        "commerce.Offer", on_delete=models.CASCADE, related_name="fund_flow_configuration", null=True, blank=True
    )
    strategy = models.CharField(max_length=32, choices=FundFlowStrategy.choices)
    configured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="configured_fund_flows", null=True, blank=True
    )
    configured_at = models.DateTimeField(default=timezone.now)
    reason = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(platform_default=True, space__isnull=True, activity__isnull=True, offer__isnull=True)
                    | Q(platform_default=False, space__isnull=False, activity__isnull=True, offer__isnull=True)
                    | Q(platform_default=False, space__isnull=True, activity__isnull=False, offer__isnull=True)
                    | Q(platform_default=False, space__isnull=True, activity__isnull=True, offer__isnull=False)
                ),
                name="fundflow_exactly_one_scope",
            ),
            models.UniqueConstraint(
                fields=["platform_default"], condition=Q(platform_default=True), name="fundflow_single_platform_default"
            ),
        ]

    @property
    def source_level(self):
        if self.offer_id:
            return FundFlowSourceLevel.OFFER
        if self.activity_id:
            return FundFlowSourceLevel.ACTIVITY
        if self.space_id:
            return FundFlowSourceLevel.SPACE
        return FundFlowSourceLevel.PLATFORM

    def clean(self):
        scopes = int(self.platform_default) + int(bool(self.space_id)) + int(bool(self.activity_id)) + int(bool(self.offer_id))
        if scopes != 1:
            raise ValidationError("Une configuration Fund Flow cible exactement un niveau.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class FinancialDestination(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payee_space = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="financial_destinations", null=True, blank=True
    )
    payee_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="financial_destinations", null=True, blank=True
    )
    destination_type = models.CharField(max_length=32, choices=FinancialDestinationType.choices)
    provider = models.CharField(max_length=60, blank=True)
    external_reference = models.CharField(max_length=220, blank=True)
    display_name = models.CharField(max_length=160)
    masked_label = models.CharField(max_length=160, blank=True)
    last_digits = models.CharField(max_length=8, blank=True)
    status = models.CharField(max_length=16, choices=FinancialDestinationStatus.choices, default=FinancialDestinationStatus.PENDING)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_financial_destinations", null=True, blank=True
    )
    disabled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="disabled_financial_destinations", null=True, blank=True
    )
    disabled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(payee_space__isnull=False, payee_profile__isnull=True)
                    | Q(payee_space__isnull=True, payee_profile__isnull=False)
                ),
                name="findest_exactly_one_owner",
            )
        ]
        indexes = [models.Index(fields=["status", "destination_type"], name="findest_status_type_idx")]

    def clean(self):
        if bool(self.payee_space_id) == bool(self.payee_profile_id):
            raise ValidationError("Une destination appartient exactement à un Space ou un Profile.")
        if self.last_digits and (not self.last_digits.isdigit() or len(self.last_digits) > 8):
            raise ValidationError({"last_digits": "last_digits doit rester un suffixe numérique masqué."})
        forbidden = {"secret", "password", "pin", "private_key", "api_key", "token_secret"}
        if any(str(key).lower() in forbidden for key in (self.metadata or {}).keys()):
            raise ValidationError({"metadata": "Les secrets financiers ne doivent pas être stockés."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.payouts.exists():
            raise ValidationError("Une destination auditée par un Payout ne peut pas être supprimée.")
        return super().delete(*args, **kwargs)


class FundFlowRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    obligation = models.OneToOneField(PaymentObligation, on_delete=models.PROTECT, related_name="fund_flow_record")
    strategy = models.CharField(max_length=32, choices=FundFlowStrategy.choices)
    source_level = models.CharField(max_length=16, choices=FundFlowSourceLevel.choices)
    source_object_id = models.CharField(max_length=64, blank=True)
    platform_custody = models.BooleanField(default=False)
    platform_receivable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3)
    source_key = models.CharField(max_length=220, unique=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(platform_receivable_amount__gte=0), name="fundflow_receivable_nonnegative")
        ]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding and FundFlowRecord.objects.filter(pk=self.pk).exists():
            raise ValidationError("Un FundFlowRecord historique est immuable.")
        self.currency = (self.currency or "").upper()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un FundFlowRecord historique ne peut pas être supprimé.")


class Settlement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=28, unique=True, editable=False)
    payee_space = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="settlements", null=True, blank=True
    )
    payee_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="settlements", null=True, blank=True
    )
    currency = models.CharField(max_length=3)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    status = models.CharField(max_length=16, choices=SettlementStatus.choices, default=SettlementStatus.DRAFT)
    available_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_settlements", null=True, blank=True
    )
    reason = models.CharField(max_length=300, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="settlement_amount_positive"),
            models.CheckConstraint(
                condition=(
                    Q(payee_space__isnull=False, payee_profile__isnull=True)
                    | Q(payee_space__isnull=True, payee_profile__isnull=False)
                ),
                name="settlement_exactly_one_payee",
            ),
        ]
        indexes = [models.Index(fields=["status", "currency", "created_at"], name="settlement_status_curr_idx")]

    def clean(self):
        self.currency = (self.currency or "").upper()
        if bool(self.payee_space_id) == bool(self.payee_profile_id):
            raise ValidationError("Un Settlement cible exactement un bénéficiaire.")
        if self.amount is None or self.amount <= 0:
            raise ValidationError({"amount": "Un Settlement doit être strictement positif."})

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"SET-{uuid.uuid4().hex[:14].upper()}"
        if self.pk and not self._state.adding and not getattr(self, "_allow_transition", False):
            previous = Settlement.objects.filter(pk=self.pk).values("payee_space_id", "payee_profile_id", "currency", "amount", "status").first()
            if previous:
                immutable = ("payee_space_id", "payee_profile_id", "currency", "amount")
                if any(previous[field] != getattr(self, field) for field in immutable):
                    raise ValidationError("Les termes financiers d’un Settlement sont immuables.")
                if previous["status"] != self.status:
                    raise ValidationError("Utilisez les services F4 pour changer l’état d’un Settlement.")
        self.full_clean()
        result = super().save(*args, **kwargs)
        self._allow_transition = False
        return result

    def delete(self, *args, **kwargs):
        if self.status != SettlementStatus.DRAFT or self.items.exists() or self.payouts.exists():
            raise ValidationError("Un Settlement audité doit être annulé, pas supprimé.")
        return super().delete(*args, **kwargs)


class SettlementItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    settlement = models.ForeignKey(Settlement, on_delete=models.PROTECT, related_name="items")
    ledger_entry = models.OneToOneField(LedgerEntry, on_delete=models.PROTECT, related_name="settlement_item")
    allocation_line = models.ForeignKey(FinancialAllocationLine, on_delete=models.PROTECT, related_name="settlement_items")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=~Q(amount=0), name="settlement_item_nonzero")]
        indexes = [models.Index(fields=["settlement", "created_at"], name="settlement_item_set_idx")]

    def clean(self):
        self.currency = (self.currency or "").upper()
        if self.amount == 0:
            raise ValidationError({"amount": "Un SettlementItem ne peut pas être nul."})
        if self.settlement_id and self.currency != self.settlement.currency:
            raise ValidationError({"currency": "Settlement et items doivent être mono-devise."})
        if self.ledger_entry_id:
            if self.currency != self.ledger_entry.currency or self.amount != self.ledger_entry.amount:
                raise ValidationError("Le SettlementItem doit refléter exactement son fait ledger.")
            if self.ledger_entry.allocation_line_id != self.allocation_line_id:
                raise ValidationError("Le SettlementItem doit conserver la ligne d’allocation source.")

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding and SettlementItem.objects.filter(pk=self.pk).exists():
            raise ValidationError("Un SettlementItem est immuable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un SettlementItem audité ne peut pas être supprimé.")


class Payout(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=28, unique=True, editable=False)
    settlement = models.ForeignKey(Settlement, on_delete=models.PROTECT, related_name="payouts")
    destination = models.ForeignKey(FinancialDestination, on_delete=models.PROTECT, related_name="payouts")
    attempt = models.PositiveIntegerField()
    provider = models.CharField(max_length=20, choices=PayoutProvider.choices)
    status = models.CharField(max_length=16, choices=PayoutStatus.choices, default=PayoutStatus.PENDING)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    currency = models.CharField(max_length=3)
    idempotency_key = models.CharField(max_length=160, unique=True, null=True, blank=True)
    provider_reference = models.CharField(max_length=220, blank=True)
    source_key = models.CharField(max_length=220, unique=True)
    provider_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    provider_settled_at = models.DateTimeField(null=True, blank=True)
    failure_code = models.CharField(max_length=120, blank=True)
    failure_message = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_payouts", null=True, blank=True
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    succeeded_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    reversed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payout_amount_positive"),
            models.UniqueConstraint(fields=["settlement", "attempt"], name="payout_settlement_attempt_unique"),
            models.UniqueConstraint(
                fields=["provider", "provider_reference"], condition=~Q(provider_reference=""), name="payout_provider_ref_unique"
            ),
        ]
        indexes = [models.Index(fields=["status", "provider", "created_at"], name="payout_status_provider_idx")]

    def clean(self):
        self.currency = (self.currency or "").upper()
        if self.settlement_id:
            if self.currency != self.settlement.currency or self.amount != self.settlement.amount:
                raise ValidationError("Un Payout doit reprendre exactement montant et devise du Settlement.")
            if self.destination_id:
                same_space = self.settlement.payee_space_id and self.destination.payee_space_id == self.settlement.payee_space_id
                same_profile = self.settlement.payee_profile_id and self.destination.payee_profile_id == self.settlement.payee_profile_id
                if not (same_space or same_profile):
                    raise ValidationError({"destination": "La destination appartient à un autre bénéficiaire."})
        if self.amount is None or self.amount <= 0:
            raise ValidationError({"amount": "Un Payout réel doit être strictement positif."})

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"POU-{uuid.uuid4().hex[:14].upper()}"
        if self.pk and not self._state.adding and not getattr(self, "_allow_transition", False):
            previous = Payout.objects.filter(pk=self.pk).values(
                "settlement_id", "destination_id", "amount", "currency", "provider", "provider_reference", "status"
            ).first()
            if previous:
                immutable = ("settlement_id", "destination_id", "amount", "currency", "provider")
                if any(previous[field] != getattr(self, field) for field in immutable):
                    raise ValidationError("Les termes d’un Payout sont immuables.")
                if previous["status"] != self.status or previous["provider_reference"] != self.provider_reference:
                    raise ValidationError("Utilisez les services F4 pour modifier un Payout.")
        self.full_clean()
        result = super().save(*args, **kwargs)
        self._allow_transition = False
        return result

    def delete(self, *args, **kwargs):
        raise ValidationError("Une tentative Payout est auditée et ne peut pas être supprimée.")


class FundMovement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    movement_type = models.CharField(max_length=32, choices=FundMovementType.choices)
    payout = models.ForeignKey(Payout, on_delete=models.PROTECT, related_name="fund_movements", null=True, blank=True)
    obligation = models.ForeignKey(PaymentObligation, on_delete=models.PROTECT, related_name="fund_movements", null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    provider = models.CharField(max_length=60, blank=True)
    provider_reference = models.CharField(max_length=220, blank=True)
    source_key = models.CharField(max_length=220, unique=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=~Q(amount=0), name="fundmovement_amount_nonzero")]
        indexes = [models.Index(fields=["movement_type", "occurred_at"], name="fundmovement_type_time_idx")]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding and FundMovement.objects.filter(pk=self.pk).exists():
            raise ValidationError("Un mouvement de fonds est append-only.")
        self.currency = (self.currency or "").upper()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un mouvement de fonds audité ne peut pas être supprimé.")
