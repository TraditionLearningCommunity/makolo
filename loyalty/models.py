import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class MembershipStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    ACTIVE = "active", "Active"
    EXPIRED = "expired", "Expirée"
    CANCELLED = "cancelled", "Annulée"


class LedgerKind(models.TextChoices):
    ORDER = "order", "Commande"
    ORDER_REVERSAL = "order_reversal", "Annulation commande"
    CHECKIN = "checkin", "Check-in"
    MEMBERSHIP_BONUS = "membership_bonus", "Bonus membership"
    REWARD = "reward", "Récompense"
    ADJUSTMENT = "adjustment", "Ajustement"


class LoyaltyProgram(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.OneToOneField("organizations.Organization", on_delete=models.CASCADE, related_name="loyalty_program")
    name = models.CharField(max_length=160, default="Programme fidélité")
    description = models.TextField(blank=True)
    points_name = models.CharField(max_length=40, default="points")
    points_per_order = models.PositiveIntegerField(default=10)
    points_per_ticket = models.PositiveIntegerField(default=5)
    points_per_checkin = models.PositiveIntegerField(default=20)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_loyalty_programs")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.organization} — {self.name}"


class LoyaltyTier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(LoyaltyProgram, on_delete=models.CASCADE, related_name="tiers")
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40)
    threshold_points = models.PositiveIntegerField(default=0)
    points_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.00"))
    benefits = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["threshold_points", "name"]
        constraints = [
            models.UniqueConstraint(fields=["program", "code"], name="loyalty_tier_program_code_unique"),
            models.UniqueConstraint(fields=["program", "threshold_points"], name="loyalty_tier_threshold_unique"),
        ]

    def clean(self):
        self.code = (self.code or "").strip().upper()
        if self.points_multiplier < 1 or self.points_multiplier > 10:
            raise ValidationError({"points_multiplier": "Le multiplicateur doit être compris entre 1 et 10."})

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.program.organization} — {self.name}"


class MembershipPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(LoyaltyProgram, on_delete=models.CASCADE, related_name="membership_plans")
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=40)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="USD")
    duration_days = models.PositiveIntegerField(default=365)
    points_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.00"))
    join_bonus_points = models.PositiveIntegerField(default=0)
    benefit_promotion = models.ForeignKey("promotions.Promotion", on_delete=models.SET_NULL, related_name="membership_plans", null=True, blank=True)
    benefits = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_membership_plans")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price", "name"]
        constraints = [models.UniqueConstraint(fields=["program", "code"], name="membership_plan_program_code_unique")]

    def clean(self):
        self.code = (self.code or "").strip().upper()
        self.currency = (self.currency or "").strip().upper()
        errors = {}
        if self.price < 0:
            errors["price"] = "Le prix ne peut pas être négatif."
        if len(self.currency) != 3:
            errors["currency"] = "Devise ISO à trois lettres requise."
        if not 1 <= self.duration_days <= 3650:
            errors["duration_days"] = "La durée doit être comprise entre 1 et 3650 jours."
        if self.points_multiplier < 1 or self.points_multiplier > 10:
            errors["points_multiplier"] = "Le multiplicateur doit être compris entre 1 et 10."
        if self.benefit_promotion_id and self.benefit_promotion.organization_id != self.program.organization_id:
            errors["benefit_promotion"] = "L'offre doit appartenir à la même organisation."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        self.currency = (self.currency or "USD").strip().upper()
        super().save(*args, **kwargs)

    @property
    def is_free(self):
        return self.price == 0

    def __str__(self):
        return f"{self.program.organization} — {self.name}"


class MembershipSubscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(LoyaltyProgram, on_delete=models.PROTECT, related_name="subscriptions")
    plan = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name="subscriptions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="loyalty_memberships")
    status = models.CharField(max_length=16, choices=MembershipStatus.choices, default=MembershipStatus.PENDING)
    price_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="USD")
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    activation_source = models.CharField(max_length=16, blank=True)
    activated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="activated_loyalty_memberships", null=True, blank=True)
    benefit_code = models.ForeignKey("promotions.PromotionCode", on_delete=models.SET_NULL, related_name="membership_subscriptions", null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at"]
        constraints = [models.UniqueConstraint(fields=["program", "user"], condition=Q(status__in=["pending", "active"]), name="membership_one_current_program_user")]
        indexes = [models.Index(fields=["program", "status"], name="membership_program_status_idx"), models.Index(fields=["ends_at", "status"], name="membership_end_status_idx")]

    def clean(self):
        if self.plan_id and self.program_id and self.plan.program_id != self.program_id:
            raise ValidationError({"plan": "Le plan appartient à un autre programme."})

    @property
    def is_current(self):
        return self.status == MembershipStatus.ACTIVE

    def __str__(self):
        return f"{self.user} — {self.plan} — {self.status}"


class LoyaltyAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(LoyaltyProgram, on_delete=models.CASCADE, related_name="accounts")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="loyalty_accounts")
    points_balance = models.PositiveIntegerField(default=0)
    lifetime_earned = models.PositiveIntegerField(default=0)
    lifetime_redeemed = models.PositiveIntegerField(default=0)
    current_tier = models.ForeignKey(LoyaltyTier, on_delete=models.SET_NULL, related_name="accounts", null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["program", "user"], name="loyalty_account_program_user_unique")]
        indexes = [models.Index(fields=["program", "points_balance"], name="loyalty_account_balance_idx")]

    def __str__(self):
        return f"{self.user} — {self.program.organization} — {self.points_balance}"


class LoyaltyReward(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(LoyaltyProgram, on_delete=models.CASCADE, related_name="rewards")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    points_cost = models.PositiveIntegerField()
    promotion = models.ForeignKey("promotions.Promotion", on_delete=models.SET_NULL, related_name="loyalty_rewards", null=True, blank=True)
    fulfillment_instructions = models.TextField(blank=True)
    max_redemptions_per_member = models.PositiveSmallIntegerField(default=1)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_loyalty_rewards")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["points_cost", "name"]

    def clean(self):
        errors = {}
        if self.points_cost < 1:
            errors["points_cost"] = "Le coût doit être positif."
        if self.max_redemptions_per_member < 1:
            errors["max_redemptions_per_member"] = "La limite doit être positive."
        if self.promotion_id and self.promotion.organization_id != self.program.organization_id:
            errors["promotion"] = "L'offre doit appartenir à la même organisation."
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "La fin doit être postérieure au début."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.program.organization} — {self.name}"


class LoyaltyRewardRedemption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(LoyaltyAccount, on_delete=models.PROTECT, related_name="reward_redemptions")
    reward = models.ForeignKey(LoyaltyReward, on_delete=models.PROTECT, related_name="redemptions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="loyalty_reward_redemptions")
    status = models.CharField(max_length=16, default="redeemed")
    points_cost = models.PositiveIntegerField()
    promotion_code = models.ForeignKey("promotions.PromotionCode", on_delete=models.SET_NULL, related_name="loyalty_reward_redemptions", null=True, blank=True)
    redeemed_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-redeemed_at"]
        indexes = [models.Index(fields=["reward", "user", "status"], name="loyalty_reward_user_idx")]


class LoyaltyLedgerEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(LoyaltyAccount, on_delete=models.PROTECT, related_name="ledger_entries")
    kind = models.CharField(max_length=32, choices=LedgerKind.choices)
    points = models.IntegerField()
    description = models.CharField(max_length=255)
    idempotency_key = models.CharField(max_length=180, unique=True)
    order = models.ForeignKey("tickets.TicketOrder", on_delete=models.SET_NULL, related_name="loyalty_ledger_entries", null=True, blank=True)
    ticket = models.ForeignKey("tickets.Ticket", on_delete=models.SET_NULL, related_name="loyalty_ledger_entries", null=True, blank=True)
    subscription = models.ForeignKey(MembershipSubscription, on_delete=models.SET_NULL, related_name="ledger_entries", null=True, blank=True)
    reward_redemption = models.ForeignKey(LoyaltyRewardRedemption, on_delete=models.SET_NULL, related_name="ledger_entries", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="created_loyalty_ledger_entries", null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=~Q(points=0), name="loyalty_ledger_points_nonzero")]
        indexes = [models.Index(fields=["account", "created_at"], name="loyalty_ledger_account_idx")]

    def __str__(self):
        return f"{self.account} — {self.points:+d}"
