"""Print-first layout for one already-authorized, issued Makolo Passport.

This module owns no business fact, permission, issuance or media-selection rule.
It renders only the snapshot payload and permitted portrait/QR bytes supplied.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

from PIL import Image as PILImage, ImageOps, ImageDraw
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as canvas_module
from reportlab.platypus import (
    SimpleDocTemplate, Flowable, Paragraph, Spacer, Table, TableStyle,
    KeepTogether, Image as PDFImage,
)

VIOLET = HexColor("#5232DB")
DEEP = HexColor("#2B176E")
INK = HexColor("#0F172A")
MUTED = HexColor("#64748B")
WARM = HexColor("#FAF7F5")
LIGHT = HexColor("#F4F0FC")
BORDER = HexColor("#E8E3F1")
MARGIN = 44
CONTENT_WIDTH = A4[0] - 2 * MARGIN
FONT = "Helvetica"
BOLD = "Helvetica-Bold"


def _register_fonts():
    global FONT, BOLD
    options = (
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    )
    for regular, heavy in options:
        if Path(regular).is_file() and Path(heavy).is_file():
            pdfmetrics.registerFont(TTFont("MakoloPassportRegular", regular))
            pdfmetrics.registerFont(TTFont("MakoloPassportHeavy", heavy))
            FONT, BOLD = "MakoloPassportRegular", "MakoloPassportHeavy"
            return


def _style(size=10, leading=None, *, bold=False, color=INK):
    return ParagraphStyle(
        "passport", fontName=BOLD if bold else FONT,
        fontSize=size, leading=leading or size * 1.45,
        textColor=color, allowWidows=0, allowOrphans=0,
    )


def _paragraph(value, style=None):
    return Paragraph(escape(str(value or "")), style or _style())


def _value(value):
    result = str(value or "").strip()
    return "" if result.lower() in {"none", "null", "non renseigné", "not provided"} else result


def _country(code):
    code = _value(code)
    if code.upper() in {"CD", "RDC", "COD"}:
        return "République démocratique du Congo"
    if len(code) != 2 or not code.isascii():
        return code
    if code.upper() == "CG":
        return "République du Congo"
    try:
        from babel import Locale
        return Locale.parse("fr").territories.get(code.upper(), code)
    except ImportError:
        return {
            "FR": "France", "BE": "Belgique", "CA": "Canada",
            "US": "États-Unis", "ZA": "Afrique du Sud", "KE": "Kenya",
        }.get(code.upper(), code)


def _portrait(source_bytes):
    if not source_bytes:
        return None
    try:
        with PILImage.open(BytesIO(source_bytes)) as source:
            upright = ImageOps.exif_transpose(source)
            upright.load()
            if upright.width * upright.height > 28_000_000:
                return None
            square = ImageOps.fit(
                upright.convert("RGB"), (480, 480),
                method=PILImage.Resampling.LANCZOS, centering=(.5, .43),
            )
        mask = PILImage.new("L", (480, 480))
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, 479, 479), radius=55, fill=255,
        )
        image = PILImage.new("RGBA", (480, 480))
        image.paste(square, (0, 0), mask)
        output = BytesIO()
        image.save(output, "PNG", optimize=True)
        output.seek(0)
        return ImageReader(output)
    except (OSError, ValueError, TypeError, PILImage.DecompressionBombError):
        return None


def _blend(a, b, fraction):
    return colors.Color(
        a.red * (1 - fraction) + b.red * fraction,
        a.green * (1 - fraction) + b.green * fraction,
        a.blue * (1 - fraction) + b.blue * fraction,
    )


class PassportHero(Flowable):
    """A single scannable identity block: portrait / identity / verification QR.

    The QR has a white quiet-zone, never sits directly on the violet ink, and
    is issued for the exact document described in the final metadata block.
    """

    def __init__(self, identity, metadata, portrait_bytes, qr_png, verify_url):
        super().__init__()
        self.identity, self.meta = identity, metadata
        self.verify_url = verify_url
        self.portrait = _portrait(portrait_bytes)
        self.qr_image = ImageReader(BytesIO(qr_png))
        self.width = CONTENT_WIDTH
        self.photo_size = 102
        self.qr_box = 102
        self.qr_x = self.width - self.qr_box - 21
        self.text_x = 142
        self.text_width = self.qr_x - self.text_x - 14

        name = _value(identity.get("name")) or "Passeport Makolo"
        kind = str(metadata.get("kind", ""))
        private = identity.get("owner_details") or {}
        if metadata.get("variant_code") != "complete":
            private = {}
        profile = kind == "Profil personnel"
        profession = _value(identity.get("profession") or identity.get("headline"))
        self.lines = []
        if profession:
            self.lines.append((profession, 10.0, HexColor("#F5F0FF")))
        elif kind == "Espace":
            self.lines.append(("Espace Makolo", 10.0, HexColor("#F5F0FF")))

        location = _value(identity.get("location"))
        if location:
            self.lines.append((
                ", ".join(_country(item.strip())
                          for item in location.split(",") if item.strip()),
                9.0, HexColor("#E4DCFC"),
            ))
        # Other personal coordinates are not publicly inferred or shown.
        if profile and private:
            descriptors = [
                _value(private.get("gender")),
                _value(private.get("language")),
            ]
            descriptors = [item for item in descriptors if item]
            if descriptors:
                self.lines.append((" · ".join(descriptors), 9.0,
                                   HexColor("#E4DCFC")))

        name_size = 19
        for candidate in (19, 18, 16, 14):
            name_paragraph = _paragraph(
                name, _style(candidate, candidate * 1.24,
                             bold=True, color=colors.white),
            )
            _, name_height = name_paragraph.wrap(self.text_width, 1200)
            if name_height <= 66 or candidate == 14:
                name_size = candidate
                break
        self.name_paragraph = name_paragraph
        self.name_height = name_height
        self.line_paragraphs = []
        line_heights = 0
        for label, size, color in self.lines:
            p = _paragraph(label, _style(size, size * 1.38, color=color))
            _, ph = p.wrap(self.text_width, 1200)
            self.line_paragraphs.append((p, ph))
            line_heights += ph + 4
        self.height = max(168, self.name_height + line_heights + 77)
        self.height = min(440, self.height)

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        c.saveState()
        clip = c.beginPath()
        clip.roundRect(0, 0, w, h, 18)
        c.clipPath(clip, fill=0, stroke=0)
        for i in range(48):
            c.setFillColor(_blend(VIOLET, DEEP, i / 47))
            c.rect(w * i / 48, 0, w / 48 + 1, h, stroke=0, fill=1)
        c.restoreState()

        photo_y = (h - self.photo_size) / 2
        if self.portrait:
            c.drawImage(self.portrait, 23, photo_y,
                        self.photo_size, self.photo_size, mask="auto")
        else:
            c.setFillColor(HexColor("#F0EBFD"))
            c.roundRect(23, photo_y, self.photo_size, self.photo_size,
                        12, stroke=0, fill=1)
            name = _value(self.identity.get("name"))
            initials = "".join(item[0] for item in name.split()[:2]).upper() or "M"
            c.setFillColor(DEEP)
            c.setFont(BOLD, 25)
            c.drawCentredString(23 + self.photo_size / 2,
                                photo_y + self.photo_size / 2 - 8, initials)

        # Identity stays to the left of the QR, never under it.
        c.setFillColor(HexColor("#DBCEFD"))
        c.setFont(BOLD, 7.4)
        descriptor = (str(self.meta.get("kind", "")) + " · " +
                      str(self.meta.get("variant", ""))).upper()
        # Avoid drawing long metadata over the QR area.
        if pdfmetrics.stringWidth(descriptor, BOLD, 7.4) > self.text_width:
            descriptor = str(self.meta.get("kind", "")).upper()
        c.drawString(self.text_x, h - 24, descriptor)
        y = h - 42
        self.name_paragraph.drawOn(c, self.text_x, y - self.name_height)
        y -= self.name_height + 9
        for paragraph, height in self.line_paragraphs:
            paragraph.drawOn(c, self.text_x, y - height)
            y -= height + 4

        identifier = _value(self.meta.get("identifier"))
        if identifier:
            line = _paragraph(
                "@" + identifier.lstrip("@"),
                _style(8.6, 12, color=HexColor("#E5DDFC")),
            )
            _, line_height = line.wrap(self.text_width, 1200)
            line.drawOn(c, self.text_x, max(12, min(21, y - line_height)))

        # A true QR needs a quiet white margin and sufficient print size.
        qr_y = (h - self.qr_box) / 2 + 9
        c.setFillColor(colors.white)
        c.roundRect(self.qr_x, qr_y, self.qr_box, self.qr_box,
                    9, fill=1, stroke=0)
        inset = 6
        c.drawImage(self.qr_image, self.qr_x + inset, qr_y + inset,
                    self.qr_box - 2 * inset, self.qr_box - 2 * inset,
                    preserveAspectRatio=True, anchor="c", mask="auto")
        # Click-to-verify in PDF viewers, scan-to-verify on paper.
        c.linkURL(self.verify_url,
                  (self.qr_x, qr_y, self.qr_x + self.qr_box,
                   qr_y + self.qr_box), relative=0)
        c.setFont(BOLD, 7.2)
        c.setFillColor(HexColor("#EDE7FF"))
        c.drawCentredString(self.qr_x + self.qr_box / 2, qr_y - 14,
                            "VÉRIFIER")


class TagFlow(Flowable):
    """Wrapping print pills; splits on row boundaries across pages."""

    def __init__(self, labels):
        super().__init__()
        self.labels = [str(x) for x in labels if _value(x)]
        self.width, self.height = CONTENT_WIDTH, 0
        self.positions = []

    def wrap(self, available_width, available_height):
        self.width = min(CONTENT_WIDTH, available_width)
        x, y, row_height = 0, 0, 28
        self.positions = []
        for label in self.labels:
            text_width = pdfmetrics.stringWidth(label, FONT, 9.1)
            pill_width = min(self.width, text_width + 27)
            paragraph = _paragraph(label, _style(9.1, 13, color=DEEP))
            _, text_height = paragraph.wrap(pill_width - 23, 320)
            pill_height = max(25, text_height + 11)
            if x > 0 and x + pill_width > self.width:
                y += row_height + 7
                x, row_height = 0, 28
            self.positions.append((x, y, pill_width, pill_height, paragraph))
            x += pill_width + 7
            row_height = max(row_height, pill_height)
        self.height = y + row_height + 2 if self.labels else 0
        return self.width, self.height

    def split(self, available_width, available_height):
        self.wrap(available_width, available_height)
        if self.height <= available_height:
            return [self]
        count = 0
        for _, y, _, height, _ in self.positions:
            if y + max(height, 28) + 5 <= available_height:
                count += 1
            else:
                break
        if count == 0:
            return []
        return [TagFlow(self.labels[:count]), TagFlow(self.labels[count:])]

    def draw(self):
        c = self.canv
        for x, y, width, height, paragraph in self.positions:
            c.setFillColor(LIGHT)
            c.setStrokeColor(BORDER)
            c.roundRect(x, self.height - y - height, width, height,
                        height / 2, stroke=1, fill=1)
            paragraph.drawOn(
                c, x + 12,
                self.height - y - height + (height - paragraph.height) / 2,
            )


class NumberedCanvas(canvas_module.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages = []

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            self.saveState()
            self.setStrokeColor(BORDER)
            self.setLineWidth(.6)
            self.line(MARGIN, 34, A4[0] - MARGIN, 34)
            self.setFont(FONT, 7.6)
            self.setFillColor(MUTED)
            self.drawString(MARGIN, 21, "Document de présentation · Makolo")
            self.drawRightString(A4[0] - MARGIN, 21, f"{self._pageNumber} / {total}")
            self.restoreState()
            canvas_module.Canvas.showPage(self)
        canvas_module.Canvas.save(self)


def _brand_mark(canvas, x, y, size=19):
    """Use the existing first-party Mark geometry; never invent a substitute logo."""
    try:
        from core.branding import _load_mark_geometry

        (width, height), points = _load_mark_geometry()
        scale = min(size / width, size / height)
        offset_x = x + (size - width * scale) / 2
        offset_y = y + (size - height * scale) / 2
        shape = canvas.beginPath()
        for index, (px, py) in enumerate(points):
            xx, yy = offset_x + px * scale, offset_y + (height - py) * scale
            if index == 0:
                shape.moveTo(xx, yy)
            else:
                shape.lineTo(xx, yy)
        shape.close()
        canvas.drawPath(shape, stroke=0, fill=1)
    except (FileNotFoundError, OSError, ValueError):
        # Mark asset absent in a development install: typography stays useful.
        canvas.roundRect(x + 5, y + 1, 7, size - 2, 3, stroke=0, fill=1)


def _page_header(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(VIOLET)
    _brand_mark(canvas, MARGIN, A4[1] - 54)
    canvas.setFillColor(DEEP)
    canvas.setFont(BOLD, 12)
    canvas.drawString(MARGIN + 26, A4[1] - 45, "PASSEPORT MAKOLO")
    canvas.setFont(FONT, 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(A4[0] - MARGIN, A4[1] - 44,
                           "DOCUMENT ÉMIS PAR MAKOLO")
    canvas.setStrokeColor(BORDER)
    canvas.line(MARGIN, A4[1] - 59, A4[0] - MARGIN, A4[1] - 59)
    canvas.restoreState()


def _heading(title):
    section = Table([[_paragraph(title.upper(),
                   _style(10.2, 13, bold=True, color=DEEP))]],
                    colWidths=[CONTENT_WIDTH])
    section.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), .6, BORDER),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return section


def _details_grid(details):
    rows = []
    for i in range(0, len(details), 2):
        cells = []
        for label, value in details[i:i + 2]:
            cells.append([
                _paragraph(label, _style(8, color=MUTED)), Spacer(1, 2),
                _paragraph(value, _style(9.6, 14, bold=True)),
            ])
        if len(cells) == 1:
            cells.append("")
        rows.append(cells)
    table = Table(rows, colWidths=[CONTENT_WIDTH / 2] * 2, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WARM),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEAFTER", (0, 0), (0, -1), 3, colors.white),
        ("LINEBELOW", (0, 0), (-1, -2), .5, colors.white),
    ]))
    if len(details) % 2:
        # Avoid the empty right-hand box when only one fact is available.
        table.setStyle(TableStyle([("SPAN", (0, len(rows) - 1),
                                  (1, len(rows) - 1))]))
    return table


def _fact_row(title, note=""):
    content = [_paragraph(title, _style(9.3, 13.8, color=INK))]
    if _value(note):
        content += [Spacer(1, 2), _paragraph(note, _style(8.2, 11.8, color=MUTED))]
    table = Table([[
        _paragraph("•", _style(10, bold=True, color=VIOLET)), content,
    ]], colWidths=[17, CONTENT_WIDTH - 17], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _verification(metadata, verify_url):
    """Compact issuance details, without a second QR.

    Readers scan the QR in the identity block; the clickable domain here is
    another way to reach that exact signed verification URL.
    """
    domain = urlsplit(verify_url).netloc
    href = escape(verify_url, {'"': '&quot;'})
    domain_link = Paragraph(
        '<link href="' + href + '" color="#5232DB">' +
        escape(domain) + "</link>",
        _style(9.0, 13.5, bold=True, color=VIOLET),
    )
    title = _paragraph("VÉRIFIER CE DOCUMENT",
                       _style(10.5, 15, bold=True, color=DEEP))
    values = [
        [
            [_paragraph("Document", _style(8.4, 12, color=MUTED)),
             _paragraph(metadata["document_id"],
                        _style(9, 13.5, bold=True))],
            [_paragraph("Émis le", _style(8.4, 12, color=MUTED)),
             _paragraph(metadata["issued_at"], _style(9, 13.5))],
        ],
        [
            [_paragraph("Variante", _style(8.4, 12, color=MUTED)),
             _paragraph(metadata["variant"], _style(9, 13.5, bold=True))],
            [_paragraph("Domaine d’émission",
                        _style(8.4, 12, color=MUTED)), domain_link],
        ],
    ]
    details = Table(values, colWidths=[CONTENT_WIDTH / 2 - 14] * 2,
                    hAlign="LEFT")
    details.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    panel = Table([[title], [details]], colWidths=[CONTENT_WIDTH],
                  hAlign="LEFT")
    panel.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .75, BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), WARM),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (0, 0), 12),
        ("BOTTOMPADDING", (0, 0), (0, 0), 2),
        ("TOPPADDING", (0, 1), (0, 1), 1),
        ("BOTTOMPADDING", (0, 1), (0, 1), 10),
    ]))
    return panel


class BottomVerification(Flowable):
    """Use the remaining space to anchor issuance references above page footer.

    This placement is for the final page only; the QR itself stays in the
    identity block on page one. If too little room remains, the entire
    verification panel moves to the next page without splitting.
    """

    def __init__(self, metadata, verify_url):
        super().__init__()
        self.panel = _verification(metadata, verify_url)
        self.note = _paragraph(
            "Document de présentation émis par Makolo. La vérification "
            "confirme son émission et son intégrité, sans certifier les "
            "informations déclarées.",
            _style(7.8, 11.8, color=MUTED),
        )
        self.width = CONTENT_WIDTH
        self.height = 0
        self.panel_height = 0
        self.note_height = 0

    def wrap(self, avail_width, avail_height):
        self.width = min(CONTENT_WIDTH, avail_width)
        _, self.panel_height = self.panel.wrap(self.width, avail_height)
        _, self.note_height = self.note.wrap(self.width, avail_height)
        required = self.panel_height + self.note_height + 15
        self.height = max(required, avail_height)
        return self.width, self.height

    def split(self, avail_width, avail_height):
        # A final verification block must never break across pages.
        return []

    def draw(self):
        self.note.drawOn(self.canv, 0, 5)
        self.panel.drawOn(self.canv, 0, self.note_height + 13)


def render_passport_layout(payload, metadata, verify_url, *,
                           portrait_bytes=None, qr_png=None):
    """Generate A4 PDF solely from an authorized snapshot and permitted media."""
    _register_fonts()
    if qr_png is None:
        import qrcode
        stream = BytesIO()
        qrcode.make(verify_url).save(stream, format="PNG")
        qr_png = stream.getvalue()
    identity = payload.get("identity") or {}
    kind = "Profil personnel" if payload.get("subject_kind") == "profile" else "Espace"
    metadata = {**metadata, "kind": kind, "variant_code": payload.get("variant")}
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=75, bottomMargin=47, title="Passeport Makolo · " +
        _value(identity.get("name")), author="Makolo",
        subject="Document de présentation Makolo", pageCompression=1,
    )
    story = [Spacer(1, 5), PassportHero(identity, metadata, portrait_bytes, qr_png, verify_url),
             Spacer(1, 18)]
    bio = _value(identity.get("bio"))
    if bio:
        # Paragraphs themselves are splittable. Do not wrap an arbitrarily long
        # biography in KeepTogether or it can overflow an A4 frame.
        heading = _heading("Présentation")
        heading.keepWithNext = 1
        gap = Spacer(1, 9)
        gap.keepWithNext = 1
        story.extend([heading, gap, _paragraph(bio, _style(10.1, 16)),
                      Spacer(1, 16)])
    owner = identity.get("owner_details") or {}
    if payload.get("variant") != "complete":
        owner = {}
    # The identity header already contains the person's name, location,
    # language and declared gender. Repeat only meaningful additional facts.
    labels = (
        ("company", "Entreprise"), ("organization", "Organisation"),
        ("city", "Ville"), ("country", "Pays"),
        ("phone", "Téléphone"), ("address", "Adresse"),
        ("birth_date", "Date de naissance"),
    )
    details = []
    for field, label in labels:
        raw = _value(owner.get(field))
        value = _country(raw) if field == "country" else raw
        # Identity data already displayed in the hero should not be repeated.
        if field == "country" and raw in _value(identity.get("location")).split(", "):
            continue
        if value:
            details.append((label, value))
    if details:
        detail_title = "Informations complémentaires" if kind == "Profil personnel" else "Informations de l’Espace"
        story.extend([KeepTogether([
            _heading(detail_title), Spacer(1, 9),
            _details_grid(details),
        ]), Spacer(1, 16)])
    tags = [
        ("Centres d’intérêt", payload.get("interests") or []),
        ("Ouvert à", [
            _value(row.get("kind")) +
            (" · " + _value(row.get("topic")) if _value(row.get("topic")) else "")
            for row in payload.get("open_to") or []
        ]),
    ]
    for title, values in tags:
        values = [x for x in values if _value(x)]
        if values:
            # Keep the section title with its first tangible choices; allow
            # the remainder to wrap across pages without oversized blocks.
            first, remaining = values[:3], values[3:]
            story.append(KeepTogether([
                _heading(title), Spacer(1, 9), TagFlow(first),
            ]))
            if remaining:
                story.append(TagFlow(remaining))
            story.append(Spacer(1, 14))
    links = [
        (str(label), str(url))
        for label, url in (identity.get("links") or []) if _value(url)
    ]
    if links:
        story.extend([KeepTogether([_heading("Liens"), Spacer(1, 7)])])
        for label, url in links:
            parsed = urlsplit(url)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                # Clickable complete target, concise printed host.
                href = escape(url, {'"': '&quot;'})
                display = escape(parsed.netloc)
                line = Paragraph(
                    escape(label) + '  ·  <link href="' + href +
                    '" color="#5232DB">' + display + '</link>',
                    _style(9.1, 14, color=INK),
                )
            else:
                line = _paragraph(label + "  ·  " + url,
                                  _style(9.1, 14, color=INK))
            story.extend([line, Spacer(1, 5)])
        story.append(Spacer(1, 10))
    groups = [
        ("Activités", [
            (_value(row.get("title")), _value(row.get("status")))
            for row in payload.get("activities") or []
        ]),
        ("Faits établis", [
            (_value(row.get("label")),
             " · ".join(x for x in (_value(row.get("activity")),
                 _value(row.get("issued_at"))) if x))
            for row in payload.get("proofs") or []
        ]),
        ("Attestations délivrées", [
            (_value(row.get("title")),
             " · ".join(x for x in (_value(row.get("issuer")),
                 _value(row.get("status")), _value(row.get("issued_at"))) if x))
            for row in payload.get("credentials") or []
        ]),
        ("Vérifications", [
            (_value(row.get("label")), _value(row.get("valid_until")))
            for row in payload.get("trust_verifications") or []
        ]),
    ]
    last_rows = None
    last_title = None
    for title, items in groups:
        rows = [_fact_row(label, note) for label, note in items if label]
        if not rows:
            continue
        # Keep the last two rows of the last nonempty factual section next to
        # the verification block, avoiding an otherwise QR-only final page.
        if last_rows is not None:
            story.extend(last_rows)
            story.append(Spacer(1, 14))
        story.extend([KeepTogether([_heading(title), Spacer(1, 7),
                                    rows[0]])])
        last_title = title
        last_rows = rows[1:]
    # The issuance block sits close to the physical footer on the final
    # sheet, instead of being immediately after the last short content row.
    # Keep at least the final factual rows nearby if the page is full.
    from reportlab.platypus import CondPageBreak

    if last_rows:
        head, tail = last_rows[:-2], last_rows[-2:]
        story.extend(head)
        tail_height = sum(
            item.wrap(CONTENT_WIDTH, 10000)[1] for item in tail
        )
        story.append(CondPageBreak(tail_height + 140))
        story.extend(tail)
    story.append(Spacer(1, 12))
    story.append(BottomVerification(metadata, verify_url))
    document.build(story, onFirstPage=_page_header,
                   onLaterPages=_page_header, canvasmaker=NumberedCanvas)
    return output.getvalue()
