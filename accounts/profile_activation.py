from dataclasses import dataclass

from accounts.models import UserProfile
from topics.models import ProfileInterest, ProfileOpenTo


@dataclass(frozen=True)
class ProfileActivationStep:
    key: str
    label: str
    complete: bool
    applicable: bool
    reason: str
    next_copy: str = ""
    action_url: str = ""


@dataclass(frozen=True)
class ProfileActivationSummary:
    percentage: int
    completed_steps: int
    available_steps: int
    steps: tuple[ProfileActivationStep, ...]
    next_step: ProfileActivationStep | None
    reasons: tuple[str, ...]

    @property
    def is_complete(self):
        return self.available_steps > 0 and self.completed_steps == self.available_steps


def _has_useful_identity(user):
    return bool((user.full_name or "").strip() or (user.username or "").strip())


def _has_presentation_context(user, profile):
    facts = [bool((user.bio or "").strip()), bool((profile.profession or "").strip()), bool(user.avatar)]
    return sum(facts) >= 2


def build_profile_activation_summary(user, *, profile=None):
    """Build the private, derived Profile activation read model.

    This projection is the G8 UX truth. ``UserProfile.profile_completed`` remains
    a historical compatibility marker and is deliberately not used as an input.
    Sensitive or operational data (phone, address, birth date, coordinates,
    payment/access data, social links, etc.) never contributes to activation.
    """
    if not getattr(user, "is_authenticated", False):
        raise ValueError("Profile activation requires an authenticated user.")

    if profile is None:
        profile, _ = UserProfile.objects.get_or_create(user=user)

    has_interests = ProfileInterest.objects.filter(profile=user, topic__is_active=True).exists()
    has_open_to = ProfileOpenTo.objects.filter(profile=user, is_active=True).exists()
    has_searchable_open_to = ProfileOpenTo.objects.filter(
        profile=user,
        is_active=True,
        is_searchable=True,
    ).exists()

    presentation_complete = _has_presentation_context(user, profile)
    public_applicable = bool(profile.public_profile)
    network_applicable = bool(profile.searchable or has_open_to)

    steps = (
        ProfileActivationStep(
            key="identity",
            label="Identité",
            complete=_has_useful_identity(user),
            applicable=True,
            reason="Votre identité permet à Makolo de vous reconnaître dans votre espace personnel.",
            next_copy="Ajoutez un nom d’affichage exploitable.",
            action_url="/account/profile/#personal",
        ),
        ProfileActivationStep(
            key="presentation",
            label="Présentation",
            complete=presentation_complete,
            applicable=True,
            reason="Une courte présentation aide à comprendre qui vous êtes sans demander toutes vos données personnelles.",
            next_copy=(
                "Ajoutez une courte présentation pour que votre Profil public soit compréhensible."
                if public_applicable
                else "Ajoutez un peu de contexte léger à votre Profil : bio, profession ou avatar."
            ),
            action_url="/account/profile/#presentation",
        ),
        ProfileActivationStep(
            key="interests",
            label="Centres d’intérêt",
            complete=has_interests,
            applicable=True,
            reason="Des centres d’intérêt explicites rendent Discover plus pertinent. Ils ne sont jamais déduits de votre historique.",
            next_copy="Choisissez quelques centres d’intérêt pour améliorer Discover.",
            action_url="/account/interests/",
        ),
        ProfileActivationStep(
            key="public_presence",
            label="Présence publique",
            complete=bool(public_applicable and (user.bio or "").strip()),
            applicable=public_applicable,
            reason="Ce jalon n’existe que si vous avez choisi d’activer votre Profil public.",
            next_copy="Ajoutez une courte bio pour que votre Profil public soit compréhensible.",
            action_url="/account/profile/#presentation",
        ),
        ProfileActivationStep(
            key="network",
            label="Ouvert à",
            complete=bool(network_applicable and has_searchable_open_to),
            applicable=network_applicable,
            reason="Ce jalon n’existe que si vous choisissez d’être trouvable ou de déclarer pour quoi vous êtes ouvert à être sollicité.",
            next_copy="Indiquez pour quoi vous acceptez d’être sollicité.",
            action_url="/account/open-to/",
        ),
    )

    applicable = tuple(step for step in steps if step.applicable)
    completed = sum(1 for step in applicable if step.complete)
    percentage = round((completed / len(applicable)) * 100) if applicable else 100

    # Prioritize useful missing context. Privacy choices are never suggested as
    # activation work: non-applicable public/network milestones simply vanish.
    priority = ("identity", "presentation", "interests", "public_presence", "network")
    next_step = next(
        (step for key in priority for step in applicable if step.key == key and not step.complete),
        None,
    )

    return ProfileActivationSummary(
        percentage=percentage,
        completed_steps=completed,
        available_steps=len(applicable),
        steps=steps,
        next_step=next_step,
        reasons=tuple(step.reason for step in applicable),
    )
