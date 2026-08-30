from django.db import models


class SubscriptionSubjectType(models.TextChoices):
    PROFILE = "profile", "Profil"
    SPACE = "space", "Espace"


class SubscriptionPlanType(models.TextChoices):
    BASE = "base", "Base"
    ADDON = "addon", "Add-on"


class PlanVersionStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    PUBLISHED = "published", "Publiée"
    RETIRED = "retired", "Retirée"


class CatalogVisibility(models.TextChoices):
    PUBLIC = "public", "Publique"
    UNLISTED = "unlisted", "Non répertoriée"
    INTERNAL = "internal", "Interne"


class AcquisitionMode(models.TextChoices):
    SELF_SERVICE = "self_service", "Libre-service"
    STAFF_ONLY = "staff_only", "Staff uniquement"


class FeatureValueType(models.TextChoices):
    BOOLEAN = "boolean", "Booléen"
    INTEGER = "integer", "Entier"
    DECIMAL = "decimal", "Décimal"
    ENUM = "enum", "Énumération"


class EntitlementAggregationStrategy(models.TextChoices):
    BOOLEAN_OR = "BOOLEAN_OR", "Boolean OR"
    SUM = "SUM", "Somme"
    MAX = "MAX", "Maximum"
    REPLACE = "REPLACE", "Remplacement"


class FeatureEnforcementPolicy(models.TextChoices):
    FEATURE_GATE = "feature_gate", "Capacité activée/désactivée"
    PRESERVE_EXISTING_BLOCK_NEW = (
        "preserve_existing_block_new",
        "Préserver l’existant et bloquer les nouveaux usages au-delà de la limite",
    )


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    GRACE = "grace", "Grâce"
    SUSPENDED = "suspended", "Suspendue"
    CLOSED = "closed", "Fermée"


class SubscriptionItemStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Planifié"
    ACTIVE = "active", "Actif"
    ENDED = "ended", "Terminé"


class EntitlementSourceType(models.TextChoices):
    BASE = "base", "Base"
    ADDON = "addon", "Add-on"
    GRANT = "grant", "Grant"


class RequirementPhase(models.TextChoices):
    ACQUISITION = "acquisition", "Acquisition"
    ONGOING = "ongoing", "Ongoing"
    RENEWAL = "renewal", "Renewal"


class RequirementFailurePolicy(models.TextChoices):
    BLOCK = "block", "Block"
    DENY = "deny", "Deny"
    WARN = "warn", "Warn"
    GRACE = "grace", "Grace"
    SUSPEND = "suspend", "Suspend"


class RequirementDisclosure(models.TextChoices):
    VISIBLE = "visible", "Visible"
    GENERIC = "generic", "Generic"
    INTERNAL = "internal", "Internal"


class PlanEligibilityStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    CONDITIONALLY_AVAILABLE = "conditionally_available", "Conditionally available"
    NOT_ELIGIBLE = "not_eligible", "Not eligible"
    HIDDEN = "hidden", "Hidden"


class SubscriptionTransitionKind(models.TextChoices):
    BASE_SWITCH = "base_switch", "Changement de BASE"
    ADDON_ADD = "addon_add", "Ajout d’add-on"
    ADDON_REMOVE = "addon_remove", "Retrait d’add-on"


class SubscriptionTransitionStatus(models.TextChoices):
    REQUESTED = "requested", "Demandée"
    IN_PROGRESS = "in_progress", "En cours"
    READY = "ready", "Prête"
    COMPLETED = "completed", "Terminée"
    REJECTED = "rejected", "Rejetée"
    CANCELLED = "cancelled", "Annulée"
    EXPIRED = "expired", "Expirée"
    FAILED = "failed", "Échouée"


class SubscriptionTransitionRequestOrigin(models.TextChoices):
    SELF_SERVICE = "self_service", "Libre-service"
    STAFF = "staff", "Staff"
    SYSTEM = "system", "Système"
