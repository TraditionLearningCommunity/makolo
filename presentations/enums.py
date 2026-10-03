from django.db import models


class PresentationPurpose(models.TextChoices):
    PUBLIC_PAGE = "public_page", "Page publique"
    INVITATION = "invitation", "Invitation"
    ACCESS_PASS = "access_pass", "Billet / Access"
    CONFIRMATION = "confirmation", "Confirmation"
    PROGRAM = "program", "Programme"
    BADGE = "badge", "Badge"


class PresentationSurface(models.TextChoices):
    WEB = "web", "Web"
    PRINT = "print", "Impression"


class Provenance(models.TextChoices):
    MAKOLO = "makolo", "Makolo"
    USER = "user", "Utilisateur"
    SPACE = "space", "Espace"


class Visibility(models.TextChoices):
    PRIVATE = "private", "Privé"
    SPACE = "space", "Espace"
    PUBLIC = "public", "Public"


class VersionStatus(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    SUBMITTED = "submitted", "Soumis"
    PUBLISHED = "published", "Publié"
    RETIRED = "retired", "Retiré"
    SUSPENDED = "suspended", "Suspendu"


class PresentationState(models.TextChoices):
    DRAFT = "draft", "Brouillon"
    PUBLISHED = "published", "Publié"
    ARCHIVED = "archived", "Archivé"
