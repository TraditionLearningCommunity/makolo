"""PDF rendering of one already-authorized Makolo Passport projection.

The exact issued snapshot and its signed verification link are shared by
Web and native clients. This renderer never queries identity or bypasses the
Passport domain's disclosure decisions.
"""
from io import BytesIO
from xml.sax.saxutils import escape

import qrcode
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether

from .passport_documents import (
    issue_passport_snapshot,
    passport_verification_token,
    serialize_passport_projection,
)
from django.urls import reverse


VIOLET = colors.HexColor("#5232DB")
DEEP = colors.HexColor("#2B176E")
INK = colors.HexColor("#0F172A")


def passport_pdf_response(request, projection):
    """Issue a verifiable, dated PDF for this permitted Passport variant."""
    if not projection.has_content:
        from django.http import Http404
        raise Http404("Ce Passeport ne contient aucun élément à exporter.")
    snapshot = issue_passport_snapshot(projection)
    verify_url = request.build_absolute_uri(
        reverse("sharing:passport-verify", kwargs={
            "token": passport_verification_token(snapshot),
        })
    )
    payload = serialize_passport_projection(projection)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=19*mm, leftMargin=19*mm,
        topMargin=19*mm, bottomMargin=18*mm,
        title="Passeport Makolo", author="Makolo",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="MakoloTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=20, leading=25, textColor=DEEP, spaceAfter=9,
    ))
    styles.add(ParagraphStyle(
        name="MakoloSection", parent=styles["Heading2"], fontSize=12,
        leading=17, textColor=VIOLET, spaceBefore=15, spaceAfter=7,
    ))
    styles.add(ParagraphStyle(
        name="MakoloBody", parent=styles["BodyText"], fontSize=9.5,
        leading=15, textColor=INK, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="MakoloSmall", parent=styles["BodyText"], fontSize=8,
        leading=12, textColor=colors.HexColor("#475569"),
    ))

    def para(value, style="MakoloBody"):
        return Paragraph(escape(str(value or "")), styles[style])

    story = [para("PASSEPORT MAKOLO", "MakoloTitle")]
    # Use only an avatar admitted by this Passport projection.
    avatar = getattr(projection.subject, "avatar", None)
    if payload["subject_kind"] == "profile" and avatar and projection.identity.get("avatar_url"):
        try:
            with avatar.open("rb") as image_file:
                avatar_data = BytesIO(image_file.read(2 * 1024 * 1024))
            picture = Image(avatar_data, width=28*mm, height=28*mm)
            portrait = Table([[picture, para(payload["identity"]["name"])]],
                             colWidths=[34*mm, 133*mm])
            portrait.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
            story.append(portrait)
        except (OSError, ValueError):
            story.append(para(payload["identity"]["name"]))
    else:
        story.append(para(payload["identity"]["name"]))
    subject_kind = "Personnel" if payload["subject_kind"] == "profile" else "Espace"
    story.append(para(f"{subject_kind} · {projection.variant_label}", "MakoloSmall"))
    story.append(Spacer(1, 6*mm))

    identity = payload["identity"]
    personal = [
        ("Profession", identity.get("profession")),
        ("Localisation", identity.get("location")),
        ("Présentation", identity.get("bio")),
    ]
    visible = [(k, v) for k, v in personal if v]
    if visible:
        story.append(para("Présentation", "MakoloSection"))
        for label, value in visible:
            story.append(para(f"{label} : {value}"))
    private_details = identity.get("owner_details", {})
    if private_details:
        story.append(para("Informations personnelles", "MakoloSection"))
        labels = [
            ("first_name", "Prénom"), ("last_name", "Nom"),
            ("username", "Identifiant Makolo"), ("company", "Entreprise"),
            ("organization", "Organisation"), ("city", "Ville"),
            ("country", "Pays"), ("language", "Langue"),
            ("phone", "Téléphone"), ("address", "Adresse"),
            ("birth_date", "Date de naissance"), ("gender", "Genre"),
        ]
        for key, label in labels:
            if private_details.get(key):
                story.append(para(f"{label} : {private_details[key]}"))
    if identity.get("links"):
        story.append(para("Liens", "MakoloSection"))
        for label, url in identity["links"]:
            story.append(para(f"{label} : {url}"))
    sections = [
        ("Centres d'intérêt", payload["interests"]),
        ("Ouvert à", [
            row["kind"] + (" · " + row["topic"] if row["topic"] else "")
            for row in payload["open_to"]
        ]),
        ("Activités", [row["title"] for row in payload["activities"]]),
        ("Faits établis", [row["label"] for row in payload["proofs"]]),
        ("Attestations délivrées", [
            row["title"] + " · " + row["issuer"]
            for row in payload["credentials"]
        ]),
        ("Vérifications", [row["label"] for row in payload["trust_verifications"]]),
    ]
    for title, items in sections:
        if items:
            story.append(para(title, "MakoloSection"))
            for item in items:
                story.append(para("— " + str(item)))

    qr = qrcode.QRCode(border=1, box_size=6)
    qr.add_data(verify_url)
    qr.make(fit=True)
    qr_image = BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(qr_image, format="PNG")
    qr_image.seek(0)
    issued = snapshot.generated_at.strftime("%d/%m/%Y %H:%M UTC")
    verification = Table([
        [Image(qr_image, width=31*mm, height=31*mm),
         [
             para("Émis par Makolo", "MakoloSection"),
             para(f"Date d'émission : {issued}", "MakoloSmall"),
             para(f"Document : {snapshot.document_id}", "MakoloSmall"),
             para("Scanner le QR pour vérifier l'émission du document.", "MakoloSmall"),
         ]],
    ], colWidths=[37*mm, 130*mm])
    verification.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEABOVE", (0, 0), (-1, 0), 0.6, VIOLET),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.extend([Spacer(1, 9*mm), KeepTogether(verification)])
    story.append(Spacer(1, 5*mm))
    story.append(para(
        "Ce document présente des informations déclarées et, lorsqu'ils existent, "
        "des faits ou attestations connus de Makolo. Il ne constitue pas une pièce "
        "d'identité légale.", "MakoloSmall",
    ))
    doc.build(story)
    result = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    result["Content-Disposition"] = (
        f'attachment; filename="passeport-makolo-{snapshot.public_identifier}.pdf"'
    )
    result["Cache-Control"] = "private, no-store"
    result["X-Content-Type-Options"] = "nosniff"
    return result
