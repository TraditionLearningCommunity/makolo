COMPONENTS = {
    "Page": {"children": True, "props": {"surface", "size"}},
    "Section": {"children": True, "props": {"variant"}},
    "Stack": {"children": True, "props": {"gap", "align"}},
    "Grid": {"children": True, "props": {"columns", "gap"}},
    "Hero": {"children": False, "props": {"image", "alt"}},
    "Image": {"children": False, "props": {"src", "alt"}},
    "MakoloMark": {"children": False, "props": set()},
    "OrganizerMark": {"children": False, "props": {"src", "alt"}},
    "Heading": {"children": False, "props": {"value", "level"}},
    "Subheading": {"children": False, "props": {"value"}},
    "Text": {"children": False, "props": {"value"}},
    "OccurrenceDetails": {"children": False, "props": set()},
    "DateTime": {"children": False, "props": set()},
    "Place": {"children": False, "props": set()},
    "Organizer": {"children": False, "props": set()},
    "CallToAction": {"children": False, "props": {"url", "label"}},
    "AccessSummary": {"children": False, "props": set()},
    "QRCode": {"children": False, "props": {"alt"}},
    "Divider": {"children": False, "props": set()},
    "Footer": {"children": False, "props": {"value"}},
}


def component_contract(name):
    return COMPONENTS.get(name)
