from django.core.exceptions import ValidationError


def validate_publication_accessibility(manifest):
    """Reject deterministic accessibility violations before global publication.

    This deliberately stays small: review remains responsible for subjective visual
    quality while the renderer enforces the contracts it can prove mechanically.
    """
    headings = []

    def walk(node):
        name = node.get("component")
        props = node.get("props", {})
        if name == "Heading":
            headings.append(int(props.get("level", 1)))
        if name in {"Image", "OrganizerMark"} and (props.get("src") or props.get("image")) and "alt" not in props:
            raise ValidationError("Une image informative doit déclarer un texte alternatif.")
        for child in node.get("children", []):
            walk(child)

    walk(manifest["layout"])
    if not headings or headings[0] != 1:
        raise ValidationError("Un modèle public doit commencer sa hiérarchie par un titre de niveau 1.")
    previous = headings[0]
    for level in headings[1:]:
        if level > previous + 1:
            raise ValidationError("La hiérarchie de titres ne doit pas sauter de niveau.")
        previous = level
    return True
