from urllib.parse import urlparse

from django.core.exceptions import ValidationError

from presentations.bindings import binding_allowed
from presentations.components import component_contract

MAX_DEPTH = 12
MAX_COMPONENTS = 120
ALLOWED_SURFACES = {"web", "print"}
ALLOWED_PURPOSES = {"public_page", "invitation", "access_pass", "confirmation", "program", "badge"}
FORBIDDEN_KEYS = {"raw_html", "html", "javascript", "js", "script", "css", "style", "raw_css"}
FORBIDDEN_SCHEMES = {"javascript", "data", "file"}


def _safe_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return (parsed.scheme or "").lower() not in FORBIDDEN_SCHEMES


def _walk(node, *, depth=1, counter=None):
    counter = counter if counter is not None else [0]
    if depth > MAX_DEPTH:
        raise ValidationError("Manifest trop profond.")
    if not isinstance(node, dict):
        raise ValidationError("Chaque composant doit être un objet.")
    counter[0] += 1
    if counter[0] > MAX_COMPONENTS:
        raise ValidationError("Manifest trop volumineux.")
    if FORBIDDEN_KEYS.intersection(node):
        raise ValidationError("HTML, JavaScript et CSS arbitraires sont interdits.")
    name = node.get("component")
    contract = component_contract(name)
    if contract is None:
        raise ValidationError(f"Composant inconnu: {name}.")
    props = node.get("props", {})
    if not isinstance(props, dict):
        raise ValidationError("props doit être un objet.")
    unknown = set(props) - contract["props"]
    if unknown:
        raise ValidationError(f"Props non autorisées pour {name}: {', '.join(sorted(unknown))}.")
    for key, value in props.items():
        if isinstance(value, dict) and "binding" in value:
            if not binding_allowed(value["binding"]):
                raise ValidationError(f"Binding interdit: {value['binding']}.")
        elif key in {"url", "src", "image"} and isinstance(value, str) and not _safe_url(value):
            raise ValidationError("URL dangereuse interdite.")
    children = node.get("children", [])
    if children and not contract["children"]:
        raise ValidationError(f"{name} n'accepte pas d'enfants.")
    if not isinstance(children, list):
        raise ValidationError("children doit être une liste.")
    for child in children:
        _walk(child, depth=depth + 1, counter=counter)
    return counter[0]


def validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise ValidationError("Le manifest doit être un objet JSON.")
    if manifest.get("schema_version") != 1:
        raise ValidationError("schema_version=1 est requis.")
    purposes = manifest.get("purposes")
    surfaces = manifest.get("surfaces")
    if not isinstance(purposes, list) or not purposes or not set(purposes) <= ALLOWED_PURPOSES:
        raise ValidationError("Purposes invalides.")
    if not isinstance(surfaces, list) or not surfaces or not set(surfaces) <= ALLOWED_SURFACES:
        raise ValidationError("Surfaces invalides.")
    if FORBIDDEN_KEYS.intersection(manifest):
        raise ValidationError("Code ou style arbitraire interdit.")
    if "layout" not in manifest:
        raise ValidationError("layout est requis.")
    _walk(manifest["layout"])
    return manifest
