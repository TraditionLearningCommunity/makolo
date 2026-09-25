import hashlib
from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from interpreter.benchmark import BenchmarkExpectation, benchmark_interpretation
from interpreter.contracts import CandidateEntity, CandidateFact, InterpretationOutcome
from interpreter.extraction import DeterministicInterpreter
from resolver.ports import EntityLookup, FactHistoryComparison
from resolver.strategy import DeterministicResolver

from .tests import MemoryReader, descriptor, material, interpret


def _minimal_pdf(lines):
    commands = ["BT", "/F1 12 Tf", "72 720 Td"]
    for index, line in enumerate(lines):
        if index:
            commands.append("0 -18 Td")
        commands.append(f"({line}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects)+1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(pdf)


class EmptyCatalog:
    def lookup_entity(self, material, entity, context):
        return EntityLookup(
            families=tuple(context["families"]),
            alternatives=(),
            basis_codes=("act4_empty_catalog",),
        )


class EmptyHistory:
    def compare_fact(self, **kwargs):
        return FactHistoryComparison()


class Actor3ClosureBenchmarkTests(SimpleTestCase):
    def test_generalist_fixture_matrix(self):
        cases = [
            (
                "scholarship",
                b"""<html><head><title>Scholarship guide</title></head><body>
                <h1>Scholarship 2027</h1><p>Organization: Alpha Foundation</p>
                <p>Deadline: 2026-11-30</p><p>Fee: 0 USD</p>
                <a href='https://example.test/apply'>Apply</a></body></html>""",
                {"deadline", "price", "application_url", "provided_by"},
            ),
            (
                "visa",
                b"""<html><head><title>Visa guide</title></head><body>
                <h1>Visa procedure</h1><h2>Requirements</h2>
                <p>Passport required</p><p>Fee: 50 USD</p>
                <a href='https://example.test/visa-form.pdf'>Official form PDF</a></body></html>""",
                {"requires", "price", "reference_url"},
            ),
            (
                "transport",
                b"""<html><head><title>Transport</title></head><body>
                <h1>Route A</h1><p>Origin: Lubumbashi</p><p>Destination: Kolwezi</p>
                <p>Duration: 4 hours</p><p>Price: 30 USD</p><p>Capacity: 50 seats</p>
                </body></html>""",
                {"origin_text", "destination_text", "duration", "price", "capacity_announced"},
            ),
            (
                "requirements",
                b"""<html><head><title>Admission</title></head><body>
                <h1>Admission</h1><h2>Eligibility</h2>
                <p>Language score >= 80</p><p>Passport OR national ID required</p>
                </body></html>""",
                {"requires", "score"},
            ),
            (
                "organization-place",
                b"""<html><head><title>Contact</title></head><body>
                <h1>Contact</h1><p>Organization: University Alpha</p>
                <p>Place: Kinshasa</p></body></html>""",
                {"provided_by", "located_at"},
            ),
            (
                "json-ld",
                b"""<html><head><title>Catalog</title>
                <script type='application/ld+json'>
                {"@type":"Course","name":"Course Alpha","startDate":"2026-12-02","price":"250","priceCurrency":"USD"}
                </script></head><body><h1>Catalog</h1><p>Course Alpha</p></body></html>""",
                {"start_date", "price"},
            ),
        ]
        for name, payload, expected in cases:
            with self.subTest(name=name):
                result, stats = interpret(payload, media="text/html")
                predicates = {
                    c.predicate for c in result.candidates
                    if hasattr(c, "predicate")
                }
                self.assertTrue(expected.issubset(predicates), (name, expected - predicates))
                self.assertEqual(stats["ocr_calls"], 0)

    def test_article_title_about_training_is_not_itself_training(self):
        payload = b"""<html lang='fr'><head>
        <title>Le Recteur inaugure un centre de formation</title>
        <meta property='og:type' content='article'>
        <meta name='datePublished' content='2026-09-24'>
        </head><body><article>
        <h1>Le Recteur inaugure un centre de formation</h1>
        <p>Organization: Universite Alpha</p></article></body></html>"""
        result, _ = interpret(payload, media="text/html")
        document = next(
            c for c in result.candidates
            if isinstance(c, CandidateEntity) and "document" in c.type_hints
        )
        self.assertNotIn("training", document.type_hints)
        self.assertNotIn("activity", document.type_hints)
        publications = [
            c for c in result.candidates
            if isinstance(c, CandidateFact) and c.predicate == "publication_date"
        ]
        self.assertEqual(len(publications), 1)
        self.assertEqual(publications[0].subject_ref, document.candidate_ref)

    def test_pdf_and_rendered_dom_paths(self):
        pdf = _minimal_pdf([
            "Official guide",
            "Deadline: 2026-12-15",
            "Price: 25 USD",
            "Capacity: 40 seats",
        ])
        result, stats = interpret(pdf, media="application/pdf")
        self.assertIn(result.outcome, {InterpretationOutcome.INTERPRETED, InterpretationOutcome.PARTIAL})
        self.assertEqual(stats["pdf_pages"], 1)
        self.assertEqual(stats["ocr_calls"], 0)
        self.assertTrue(all(
            evidence.page_number == 1
            for candidate in result.candidates
            for evidence in candidate.evidence
        ))

        shell = b"<html><body><p>Loading...</p></body></html>"
        dom = b"""<html><body><h1>Rendered offer</h1>
        <p>Price: 45 USD</p><p>Capacity: 12 seats</p></body></html>"""
        a = descriptor(shell, ref="observer:artifact:v1:act4-shell", media="text/html")
        b = descriptor(dom, ref="observer:artifact:v1:act4-dom", role="rendered_dom", media="text/html")
        reader = MemoryReader({a.artifact_ref: shell, b.artifact_ref: dom})
        now = datetime(2026, 9, 25, 8, tzinfo=timezone.utc)
        rendered, _ = DeterministicInterpreter().interpret(
            material(a, b), reader,
            started_at=now, clock=lambda: now + timedelta(milliseconds=5),
        )
        labels = [c.label for c in rendered.candidates if isinstance(c, CandidateEntity)]
        self.assertIn("Rendered offer", labels)
        self.assertNotIn("Loading...", labels)

    def test_benchmark_reports_semantics_evidence_and_cost_not_just_count(self):
        payload = b"""<html><head><title>Guide</title></head><body>
        <h1>Program Alpha</h1><p>Deadline: 2026-11-20</p>
        <p>Price: 250 USD</p><p>Capacity: 20 seats</p></body></html>"""
        item = descriptor(payload, media="text/html")
        reader = MemoryReader({item.artifact_ref: payload})
        now = datetime(2026, 9, 25, 8, tzinfo=timezone.utc)
        output, report = benchmark_interpretation(
            DeterministicInterpreter(),
            material(item),
            reader,
            BenchmarkExpectation(
                predicates=frozenset({"deadline", "price", "capacity_announced"}),
                forbidden_entity_hints=frozenset({"training"}),
            ),
            started_at=now,
            clock=lambda: now + timedelta(milliseconds=5),
        )
        self.assertFalse(report["false_negative_predicates"])
        self.assertFalse(report["forbidden_hints_present"])
        self.assertEqual(report["missing_evidence_count"], 0)
        self.assertEqual(report["duplicate_semantic_count"], 0)
        self.assertEqual(report["intelligence_calls"], 0)
        self.assertGreater(report["bytes_read"], 0)
        self.assertTrue(output.candidates)

    def test_actor4_accepts_generalist_actor3_material_without_refactor(self):
        payload = b"""<html><head><title>Transport</title></head><body>
        <h1>Route A</h1><p>Origin: Lubumbashi</p><p>Destination: Kolwezi</p>
        <p>Price: 30 USD</p><p>Capacity: 50 seats</p></body></html>"""
        interpreted, _ = interpret(payload, media="text/html")
        now = datetime(2026, 9, 25, 8, tzinfo=timezone.utc)
        resolved, stats = DeterministicResolver().resolve(
            interpreted,
            EmptyCatalog(),
            EmptyHistory(),
            started_at=now,
            clock=lambda: now + timedelta(milliseconds=5),
        )
        self.assertTrue(resolved.assertions)
        self.assertGreater(stats["fact_count"], 0)
        self.assertEqual(stats["model_calls"], 0)
        self.assertEqual(stats["network_calls"], 0)
