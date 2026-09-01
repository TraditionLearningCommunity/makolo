from copy import deepcopy

from django.db import transaction

from .enums import Provenance, VersionStatus, Visibility
from .essential import ESSENTIAL_MANIFEST, ESSENTIAL_THEME
from .models import PresentationTemplate, PresentationTemplateVersion, PresentationTheme, PresentationThemeVersion


TEMPLATE_DEFINITIONS = (
    ("makolo-essential", "Makolo Essential", "Universel", "Sobre Makolo, très lisible", "essential"),
    ("formal", "Formal", "Élégant", "Invitation officielle, cérémonie et institution", "formal"),
    ("professional", "Professional", "Professionnel", "Conférence, séminaire et formation", "professional"),
    ("celebration", "Celebration", "Festif", "Chaleureux, expressif et adulte", "celebration"),
    ("stage", "Stage", "Soirée", "Visuel contrasté pour scène et spectacle", "stage"),
    ("heritage", "Heritage", "Culturel", "Éditorial contemporain pour culture et patrimoine", "heritage"),
    ("mono", "Mono", "Minimal", "Fort contraste et économique à imprimer", "mono"),
    ("journey", "Journey", "Professionnel", "Rapide à lire, orienté horaires et déplacement", "journey"),
)

THEME_DEFINITIONS = {
    "makolo-violet": ("Makolo Violet", {**ESSENTIAL_THEME, "accent": "#5232DB", "background": "#FAF7F5"}),
    "makolo-ink": ("Makolo Ink", {**ESSENTIAL_THEME, "accent": "#2B176E", "background": "#FAF7F5"}),
    "ivory": ("Ivory", {**ESSENTIAL_THEME, "accent": "#2B176E", "background": "#FFFDF7", "surface": "#FAF7F5"}),
    "midnight": ("Midnight", {**ESSENTIAL_THEME, "accent": "#FF704D", "background": "#0F172A", "surface": "#1E293B", "text": "#FAF7F5", "muted": "#CBD5E1"}),
    "warm": ("Warm", {**ESSENTIAL_THEME, "accent": "#FF704D", "background": "#FFF7ED", "surface": "#FAF7F5"}),
    "corporate-blue": ("Corporate Blue", {**ESSENTIAL_THEME, "accent": "#1D4ED8", "background": "#F8FAFC"}),
    "mono": ("Mono", {**ESSENTIAL_THEME, "accent": "#0F172A", "background": "#FFFFFF", "surface": "#FFFFFF", "text": "#000000", "muted": "#334155", "font_family": "mono", "radius": "none", "motion": "none"}),
}


def _manifest_for(slug):
    manifest = deepcopy(ESSENTIAL_MANIFEST)
    manifest["catalog_slug"] = slug
    children = manifest["layout"]["children"]
    if slug in {"formal", "heritage"}:
        children.insert(2, {"component": "Organizer", "props": {}})
    elif slug in {"professional", "journey"}:
        children.insert(3, {"component": "Divider", "props": {}})
    elif slug in {"celebration", "stage"}:
        children.insert(1, {"component": "Hero", "props": {"image": {"binding": "editorial.hero_image"}, "alt": ""}})
    elif slug == "mono":
        children.insert(1, {"component": "Divider", "props": {}})
    return manifest


def catalog_entries():
    return [
        {"slug": slug, "name": name, "category": category, "description": description, "style": style}
        for slug, name, category, description, style in TEMPLATE_DEFINITIONS
    ]


@transaction.atomic
def ensure_builtin_catalog(*, actor):
    templates = {}
    themes = {}
    for slug, name, category, description, style in TEMPLATE_DEFINITIONS:
        template, _ = PresentationTemplate.objects.get_or_create(
            slug=slug,
            provenance=Provenance.MAKOLO,
            defaults={"name": name, "description": description, "visibility": Visibility.PUBLIC, "created_by": actor},
        )
        version, _ = PresentationTemplateVersion.objects.get_or_create(
            template=template,
            version_number=1,
            defaults={"status": VersionStatus.PUBLISHED, "schema_version": 1, "manifest": _manifest_for(slug), "created_by": actor},
        )
        templates[slug] = version
    for slug, (name, tokens) in THEME_DEFINITIONS.items():
        theme, _ = PresentationTheme.objects.get_or_create(
            slug=slug,
            provenance=Provenance.MAKOLO,
            defaults={"name": name, "visibility": Visibility.PUBLIC, "created_by": actor},
        )
        version, _ = PresentationThemeVersion.objects.get_or_create(
            theme=theme,
            version_number=1,
            defaults={"status": VersionStatus.PUBLISHED, "schema_version": 1, "tokens": tokens, "created_by": actor},
        )
        themes[slug] = version
    return templates, themes
