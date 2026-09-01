"""Presentation-only Makolo brand helpers.

This module must never become a source of business truth. In particular, QR
payloads are supplied by the owning domain (for Access, via
``render_access_credential``); this module only renders those opaque payloads.
"""

from base64 import b64encode
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import re
from xml.etree import ElementTree

from django.contrib.staticfiles import finders
from PIL import ImageDraw
import qrcode


MAKOLO_MARK_INK = "brand/makolo-mark-ink.svg"
MAKOLO_QR_INK = "#0F172A"
MAKOLO_QR_MARK_WIDTH_RATIO = 0.15
MAKOLO_QR_PLATE_WIDTH_RATIO = 0.21

_POINT_RE = re.compile(r"[ML]\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)")


@lru_cache(maxsize=1)
def _load_mark_geometry():
    """Read the official monochrome Makolo Mark as polygon geometry."""
    asset_path = finders.find(MAKOLO_MARK_INK)
    if not asset_path:
        raise FileNotFoundError(MAKOLO_MARK_INK)

    root = ElementTree.fromstring(Path(asset_path).read_text(encoding="utf-8"))
    view_box = root.attrib.get("viewBox", "").split()
    if len(view_box) != 4:
        raise ValueError("The Makolo Mark SVG must define a four-value viewBox.")
    _, _, width, height = (float(value) for value in view_box)
    if width <= 0 or height <= 0:
        raise ValueError("The Makolo Mark SVG has invalid dimensions.")

    path = next((element for element in root.iter() if element.tag.endswith("path")), None)
    if path is None:
        raise ValueError("The Makolo Mark SVG must contain a path.")
    points = [(float(x), float(y)) for x, y in _POINT_RE.findall(path.attrib.get("d", ""))]
    if len(points) < 3:
        raise ValueError("The Makolo Mark SVG path could not be reduced to polygon points.")
    return (width, height), tuple(points)


def _base_qr(payload, *, box_size):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    return qr.make_image(fill_color=MAKOLO_QR_INK, back_color="white").convert("RGB")


def _overlay_official_mark(image):
    (mark_width, mark_height), points = _load_mark_geometry()
    target_width = max(16, int(image.width * MAKOLO_QR_MARK_WIDTH_RATIO))
    target_height = max(12, int(target_width * mark_height / mark_width))
    plate_width = max(target_width + 12, int(image.width * MAKOLO_QR_PLATE_WIDTH_RATIO))
    plate_height = max(target_height + 12, int(plate_width * mark_height / mark_width))

    left = (image.width - plate_width) // 2
    top = (image.height - plate_height) // 2
    right = left + plate_width
    bottom = top + plate_height

    drawing = ImageDraw.Draw(image)
    drawing.rounded_rectangle(
        (left, top, right, bottom),
        radius=max(4, int(plate_width * 0.08)),
        fill="white",
    )

    mark_left = (image.width - target_width) / 2
    mark_top = (image.height - target_height) / 2
    scaled = [
        (
            mark_left + (x / mark_width) * target_width,
            mark_top + (y / mark_height) * target_height,
        )
        for x, y in points
    ]
    drawing.polygon(scaled, fill=MAKOLO_QR_INK)
    return image


def render_makolo_qr_png(payload, *, branded=True, box_size=8):
    """Render an opaque payload as a robust Makolo QR PNG.

    Branding is best-effort and presentation-only. If the official Mark cannot
    be loaded or rendered, the function returns the same high-correction QR
    without an overlay rather than risking an unusable credential.
    """
    if not payload:
        raise ValueError("A non-empty QR payload is required.")
    if box_size < 4:
        raise ValueError("Makolo QR box_size must be at least 4 for reliable presentation.")

    image = _base_qr(payload, box_size=box_size)
    if branded:
        try:
            _overlay_official_mark(image)
        except (FileNotFoundError, OSError, ValueError, ElementTree.ParseError):
            # Branding must never make a valid credential unavailable.
            image = _base_qr(payload, box_size=box_size)

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def render_makolo_qr_data_uri(payload, *, branded=True, box_size=8):
    png = render_makolo_qr_png(payload, branded=branded, box_size=box_size)
    return "data:image/png;base64," + b64encode(png).decode("ascii")
