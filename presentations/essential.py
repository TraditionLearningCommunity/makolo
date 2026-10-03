ESSENTIAL_MANIFEST = {
    "schema_version": 1,
    "purposes": ["public_page", "invitation", "access_pass", "confirmation", "program", "badge"],
    "surfaces": ["web", "print"],
    "layout": {
        "component": "Page",
        "props": {"surface": "web"},
        "children": [
            {"component": "MakoloMark", "props": {}},
            {"component": "Heading", "props": {"value": {"binding": "activity.display_title"}, "level": 1}},
            {"component": "OccurrenceDetails", "props": {}},
            {"component": "Text", "props": {"value": {"binding": "editorial.intro"}}},
            {"component": "AccessSummary", "props": {}},
            {"component": "QRCode", "props": {"alt": "QR d’accès Makolo"}},
            {"component": "Footer", "props": {"value": {"binding": "editorial.footer_note"}}},
        ],
    },
}

ESSENTIAL_THEME = {
    "background": "#FAF7F5",
    "surface": "#FFFFFF",
    "text": "#0F172A",
    "muted": "#475569",
    "accent": "#5232DB",
    "font_family": "system",
    "radius": "md",
    "density": "normal",
    "border_style": "solid",
    "motion": "none",
}
