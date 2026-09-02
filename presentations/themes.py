import re

from django.core.exceptions import ValidationError

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
ALLOWED_FONTS = {"system", "serif", "sans", "mono"}
ALLOWED_RADIUS = {"none", "sm", "md", "lg", "pill"}
ALLOWED_DENSITY = {"compact", "normal", "airy"}
ALLOWED_BORDER = {"none", "solid", "strong"}
ALLOWED_MOTION = {"none", "fade", "reveal", "soft_scale", "stagger"}
ALLOWED_FONT_SCALE = {"sm", "md", "lg"}
ALLOWED_SPACING = {"compact", "normal", "relaxed"}
ALLOWED_HERO_RATIO = {"square", "landscape", "wide"}
ALLOWED_ALIGNMENT = {"start", "center"}
TOKEN_KEYS = {"background", "surface", "text", "muted", "accent", "font_family", "font_scale", "radius", "spacing", "border_style", "hero_ratio", "alignment", "density", "motion"}


def validate_theme_tokens(tokens):
    if not isinstance(tokens, dict):
        raise ValidationError("Les tokens du thème doivent être un objet JSON.")
    unknown = set(tokens) - TOKEN_KEYS
    if unknown:
        raise ValidationError(f"Tokens inconnus: {', '.join(sorted(unknown))}.")
    for key in ("background", "surface", "text", "muted", "accent"):
        if key in tokens and not HEX.match(str(tokens[key])):
            raise ValidationError({key: "Une couleur doit être un hexadécimal #RRGGBB."})
    registries = {
        "font_family": (ALLOWED_FONTS, "Police"),
        "font_scale": (ALLOWED_FONT_SCALE, "Échelle typographique"),
        "radius": (ALLOWED_RADIUS, "Radius"),
        "spacing": (ALLOWED_SPACING, "Espacement"),
        "border_style": (ALLOWED_BORDER, "Bordure"),
        "hero_ratio": (ALLOWED_HERO_RATIO, "Ratio hero"),
        "alignment": (ALLOWED_ALIGNMENT, "Alignement"),
        "density": (ALLOWED_DENSITY, "Densité"),
        "motion": (ALLOWED_MOTION, "Preset de mouvement"),
    }
    for key, (allowed, label) in registries.items():
        if key in tokens and tokens[key] not in allowed:
            raise ValidationError({key: f"{label} non approuvé."})


def theme_css_variables(tokens):
    validate_theme_tokens(tokens)
    return {f"--mps-{key.replace('_', '-')}": str(value) for key, value in sorted(tokens.items())}
