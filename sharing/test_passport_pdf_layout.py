"""Focused print-document contract tests; no migrations or external PDF service."""
from io import BytesIO
from unittest import TestCase

from PIL import Image, ImageDraw
from pypdf import PdfReader

from .passport_pdf_layout import _portrait, render_passport_layout


META = {
    "document_id": "PM-P-20261030-ABCDEF12",
    "issued_at": "30/10/2026 · 11:25 UTC",
    "variant": "Complet",
    "identifier": "example",
}
VERIFY = "https://example.test/passport/verification/signed-snapshot"


def _payload(variant="complete", *, subject_kind="profile"):
    return {
        "schema_version": 1,
        "subject_kind": subject_kind,
        "variant": variant,
        "identity": {
            "name": "Profil Exemple" if subject_kind == "profile" else "Espace Exemple",
            "bio": "Présentation d'un parcours réellement déclaré.",
            "profession": "Développement",
            "location": "Lubumbashi, CD",
            "links": [("Site web", "https://example.test/a")],
            "owner_details": {
                "first_name": "Profil", "last_name": "Exemple",
                "username": "example", "country": "CD",
                "language": "Français",
                "phone": "PRIVATE-PHONE-NOT-FOR-PUBLIC",
            },
        },
        "interests": ["Culture", "Recherche"],
        "open_to": [{"kind": "Collaborer", "topic": ""}],
        "activities": [], "proofs": [], "credentials": [],
        "trust_verifications": [],
    }


class PassportPdfLayoutTests(TestCase):
    def _reader(self, payload, *, portrait_bytes=None):
        data = render_passport_layout(
            payload, META, VERIFY, portrait_bytes=portrait_bytes,
        )
        self.assertTrue(data.startswith(b"%PDF-"))
        return PdfReader(BytesIO(data))

    def test_private_sparse_passport_is_single_a4_page_and_contains_verification(self):
        reader = self._reader(_payload())
        self.assertEqual(len(reader.pages), 1)
        page = reader.pages[0]
        self.assertAlmostEqual(float(page.mediabox.width), 595.3, delta=1)
        self.assertAlmostEqual(float(page.mediabox.height), 841.9, delta=1)
        content = page.extract_text()
        self.assertIn("PASSEPORT MAKOLO", content)
        # Name, country, optional language and gender belong in the identity
        # block, rather than repeated fields or an empty detail table.
        self.assertNotIn("INFORMATIONS PERSONNELLES", content)
        self.assertIn("Français", content)
        self.assertIn("Profil Exemple", content)
        self.assertIn("@example", content)
        self.assertIn("PRIVATE-PHONE-NOT-FOR-PUBLIC", content)
        self.assertIn(META["document_id"], content)
        self.assertIn("VÉRIFIER CE DOCUMENT", content)
        self.assertIn("République démocratique du Congo", content)
        self.assertEqual(content.count(META["document_id"]), 1)
        self.assertIn("DOMAINE D’ÉMISSION", content)
        self.assertGreaterEqual(len(page.images), 1)  # QR in header, even without portrait
        self.assertTrue(page.get("/Annots"))  # clickable verification link

    def test_public_variant_never_prints_owner_only_information(self):
        payload = _payload("public")
        reader = self._reader(payload)
        text = "\n".join(page.extract_text() for page in reader.pages)
        self.assertNotIn("PRIVATE-PHONE-NOT-FOR-PUBLIC", text)
        self.assertNotIn("INFORMATIONS PERSONNELLES", text)
        self.assertNotIn("INFORMATIONS COMPLÉMENTAIRES", text)
        self.assertNotIn("Français", text)
        self.assertIn("Centres d’intérêt".upper(), text)

    def test_hero_shows_optional_gender_only_for_complete_variant(self):
        complete = _payload("complete")
        complete["identity"]["owner_details"]["gender"] = "Femme"
        private_pdf = self._reader(complete)
        private_text = "\n".join(page.extract_text() for page in private_pdf.pages)
        self.assertIn("Femme", private_text)

        public_pdf = self._reader(_payload("public"))
        public_text = "\n".join(page.extract_text() for page in public_pdf.pages)
        self.assertNotIn("Femme", public_text)

    def test_qr_is_once_in_hero_not_repeated_in_bottom_metadata(self):
        reader = self._reader(_payload())
        images = reader.pages[0].images
        self.assertGreaterEqual(len(images), 1)
        text = reader.pages[0].extract_text()
        self.assertEqual(text.count("VÉRIFIER CE DOCUMENT"), 1)
        self.assertEqual(text.count(META["document_id"]), 1)

    def test_space_uses_collective_identity_not_personal_fields(self):
        reader = self._reader(_payload("public", subject_kind="space"))
        text = "\n".join(page.extract_text() for page in reader.pages)
        self.assertIn("ESPACE", text)
        self.assertIn("Espace Exemple", text)
        self.assertNotIn("PRIVATE-PHONE-NOT-FOR-PUBLIC", text)

    def test_rich_passport_paginates_without_truncating_final_verification(self):
        payload = _payload()
        payload["identity"]["bio"] = "Une présentation qui accompagne un dossier. " * 38
        payload["interests"] = [
            f"Sujet détaillé numéro {n} pour une activité réelle"
            for n in range(45)
        ]
        payload["activities"] = [
            {"title": f"Activité {n} : recherche et développement", "status": "Terminée"}
            for n in range(16)
        ]
        payload["credentials"] = [
            {
                "title": f"Attestation délivrée {n}", "issuer": "Organisateur",
                "status": "Valide", "issued_at": "2026-10-30",
            }
            for n in range(12)
        ]
        reader = self._reader(payload)
        self.assertGreaterEqual(len(reader.pages), 3)
        self.assertTrue(all(len(page.extract_text().strip()) > 60
                            for page in reader.pages))
        text = "\n".join(page.extract_text() for page in reader.pages)
        self.assertIn("Sujet détaillé numéro 44", text)
        self.assertIn("Attestation délivrée 11", text)
        self.assertIn(META["document_id"], reader.pages[-1].extract_text())
        self.assertIn("VÉRIFIER CE DOCUMENT", reader.pages[-1].extract_text())

    def test_exif_portrait_is_normalized_to_square(self):
        picture = Image.new("RGB", (200, 120), "#8C80D2")
        ImageDraw.Draw(picture).rectangle((40, 10, 75, 95), fill="#2B176E")
        exif = Image.Exif()
        exif[274] = 6
        stream = BytesIO()
        picture.save(stream, "JPEG", exif=exif)
        normalized = _portrait(stream.getvalue())
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized.getSize(), (480, 480))
        reader = self._reader(_payload(), portrait_bytes=stream.getvalue())
        self.assertGreater(len(reader.pages[0].images), 0)
