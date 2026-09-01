import re

from django.core.exceptions import ValidationError


HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
ALLOWED_FONTS = {"system", "serif", "sans", "mono"}
ALLOWED_RADIUS = {"none", "sm", "md", "lg", "pill"}
ALLOWED_DENSITY = {"compact", "normal", "airy"}
ALLOWED_BORDER = {"none", "solid", "strong"}
ALLOWED_MOTION = {"none", "fade", "reveal", "soft_scale", "stagger"}
TOKEN_KEYS = {
    "background", "surface", "text", "muted", "accent", "font_family", "font_scale",
    "radius", "spacing", "border_style", "hero_ratio", "alignment", "density", "motion",
}


def validate_theme_tokens(tokens):
    if not isinstance(tokens, dict):
        raise ValidationError("Les tokens du thème doivent être un objet JSON.")
    unknown = set(tokens) - TOKEN_KEYS
    if unknown:
        raise ValidationError(f"Tokens inconnus: {', '.join(sorted(unknown))}.")
    for key in ("background", "surface", "text", "muted", "accent"):
        if key in tokens and not HEX.match(str(tokens[key])):
            raise ValidationError({key: "Une couleur doit être un hexadécimal #RRGGBB."})
    if "font_family" in tokens and tokens["font_family"] not in ALLOWED_FONTS:
        raise ValidationError({"font_family": "Police non approuvée."})
    if "radius" in tokens and tokens["radius"] not in ALLOWED_RADIUS:
        raise ValidationError({"radius": "Radius non approuvé."})
    if "density" in tokens and tokens["density"] not in ALLOWED_DENSITY:
        raise ValidationError({"density": "Densité non approuvée."})
    if "border_style" in tokens and tokens["border_style"] not in ALLOWED_BORDER:
        raise ValidationError({"border_style": "Bordure non approuvée."})
    if "motion" in tokens and tokens["motion"] not in ALLOWED_MOTION:
        raise ValidationError({"motion": "Preset de mouvement non approuvé."})


def theme_css_variables(tokens):
    validate_theme_tokens(tokens)
    return {f"--mps-{key.replace('_', '-')}": str(value) for key, value in sorted(tokens.items())}
