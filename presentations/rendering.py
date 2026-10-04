from html import escape

from django.core.exceptions import ValidationError

from .bindings import binding_allowed
from .manifests.validation import validate_manifest
from .themes import theme_css_variables, validate_theme_tokens


PRINT_SIZES = {"A4", "A5", "A6", "badge", "card"}


def _value(raw, context):
    if isinstance(raw, dict) and "binding" in raw:
        binding = raw["binding"]
        if not binding_allowed(binding):
            raise ValidationError("Binding interdit.")
        value = context.binding_value(binding)
        return "" if value is None else str(value)
    return "" if raw is None else str(raw)


def _render_node(node, context):
    name = node["component"]
    props = node.get("props", {})
    children = "".join(_render_node(child, context) for child in node.get("children", []))
    if name == "Page":
        return f'<main class="mps-page">{children}</main>'
    if name in {"Section", "Stack", "Grid"}:
        return f'<section class="mps-{name.lower()}">{children}</section>'
    if name == "MakoloMark":
        return '<span class="mps-mark" aria-hidden="true">M</span>'
    if name in {"Heading", "Subheading"}:
        level = 2 if name == "Subheading" else int(props.get("level", 1))
        level = min(max(level, 1), 6)
        return f'<h{level}>{escape(_value(props.get("value"), context))}</h{level}>'
    if name in {"Text", "Footer"}:
        tag = "footer" if name == "Footer" else "p"
        return f'<{tag}>{escape(_value(props.get("value"), context))}</{tag}>'
    if name == "OccurrenceDetails":
        starts = context.occurrence.get("starts_at") or ""
        place = context.occurrence.get("place") or ""
        return f'<section class="mps-occurrence"><time>{escape(str(starts))}</time><p>{escape(str(place))}</p></section>'
    if name == "Organizer":
        return f'<p class="mps-organizer">{escape(str(context.organizer.get("display_name", "")))}</p>'
    if name == "AccessSummary":
        if not context.access.get("display_type"):
            return ""
        return '<section class="mps-access"><strong>{}</strong><span>{}</span><span>{}</span></section>'.format(
            escape(str(context.access.get("display_type", ""))),
            escape(str(context.access.get("beneficiary", ""))),
            escape(str(context.access.get("display_status", ""))),
        )
    if name == "QRCode":
        image = context.render_assets.get("canonical_qr_data_uri", "")
        if not image:
            return ""
        alt = escape(str(props.get("alt", "QR Makolo")))
        return f'<img class="mps-qr" src="{escape(image)}" alt="{alt}">'
    if name == "CallToAction":
        url = escape(_value(props.get("url"), context), quote=True)
        label = escape(_value(props.get("label"), context))
        return f'<a class="mps-cta" href="{url}">{label}</a>' if url and label else ""
    if name in {"Hero", "Image", "OrganizerMark"}:
        src = _value(props.get("image") or props.get("src"), context)
        if not src:
            return ""
        return f'<img class="mps-image" src="{escape(src, quote=True)}" alt="{escape(str(props.get("alt", "")))}">'
    if name == "Divider":
        return '<hr class="mps-divider">'
    if name in {"DateTime", "Place"}:
        key = "starts_at" if name == "DateTime" else "place"
        return f'<span>{escape(str(context.occurrence.get(key, "") or ""))}</span>'
    raise ValidationError(f"Composant non rendu: {name}.")


def render_presentation(*, manifest, theme_tokens, context, surface="web", print_size="A4"):
    validate_manifest(manifest)
    validate_theme_tokens(theme_tokens)
    if surface not in manifest["surfaces"]:
        raise ValidationError("Surface non supportée par ce modèle.")
    if surface == "print" and print_size not in PRINT_SIZES:
        raise ValidationError("Format d'impression non supporté.")
    css_vars = ";".join(f"{key}:{escape(value, quote=True)}" for key, value in theme_css_variables(theme_tokens).items())
    body = _render_node(manifest["layout"], context)
    surface_class = "mps-print" if surface == "print" else "mps-web"
    return f'<div class="mps-root {surface_class}" data-mps-surface="{surface}" style="{css_vars}">{body}</div>'
