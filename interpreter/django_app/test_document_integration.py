"""ACT1 end-to-end checks through the existing Actor 3 contract/runtime."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from interpreter.contracts import CandidateEntity, CandidateFact, EvidenceLocatorKind, InterpretationOutcome
from interpreter.documents import parse_html_document
from interpreter.extraction import DeterministicInterpreter, strategy_fingerprint
from .tests import MemoryReader, descriptor, interpret, material


class DocumentInterpreterTests(SimpleTestCase):
    def test_article_title_is_not_a_training_and_mentioned_org_stays_separate(self):
        source = b'''<html lang="fr"><head><title>Le Recteur inaugure un centre de formation</title>
        <meta property="og:type" content="article"><meta name="datePublished" content="2026-09-24">
        <script type="application/ld+json">{"@type":"NewsArticle","headline":"Inauguration",
        "about":{"@type":"Organization","name":"Centre Alpha"}}</script></head>
        <body><article><h1>Le Recteur inaugure un centre de formation</h1><p>Un centre a ouvert.</p></article></body></html>'''
        with patch("socket.socket", side_effect=AssertionError("Actor 3 must not fetch")):
            result, stats = interpret(source, media="text/html")
        entities = [c for c in result.candidates if isinstance(c, CandidateEntity)]
        docs = {c.candidate_ref for c in entities if "document" in c.type_hints}
        self.assertTrue(docs)
        self.assertTrue(any(c.label == "Centre Alpha" and "organization" in c.type_hints for c in entities))
        self.assertFalse(any(set(c.type_hints) & {"training", "activity", "opportunity"} for c in entities))
        publication = next(c for c in result.candidates if isinstance(c, CandidateFact) and c.predicate == "publication_date")
        self.assertIn(publication.subject_ref, docs)
        self.assertEqual(publication.value.date_value.isoformat(), "2026-09-24")
        self.assertEqual(stats["llm_calls"], 0)

    def test_even_an_untyped_html_headline_does_not_classify_a_training(self):
        result, _ = interpret(b'<h1>A report about training</h1><p>The rector visited a centre.</p>', media="text/html")
        self.assertFalse(any(isinstance(c, CandidateEntity) and "training" in c.type_hints for c in result.candidates))

    def test_all_html_evidence_resolves_to_a_real_semantic_block(self):
        source = b'''<html><head><meta name="description" content="Guide"><title>Guide</title>
        <script type="application/ld+json">{"@type":"Course","name":"Course Alpha","startDate":"2026-10-14"}</script></head>
        <body><h1>Guide</h1><p>Price: <strong>250</strong> USD</p><dl><dt>Duration</dt><dd>3 weeks</dd></dl></body></html>'''
        item = descriptor(source, media="text/html")
        doc = parse_html_document(source.decode(), item)
        locators = {b.locator for b in doc.blocks}
        result, _ = interpret(source, media="text/html")
        self.assertTrue(result.candidates)
        for candidate in result.candidates:
            for evidence in candidate.evidence:
                self.assertEqual(evidence.locator_kind, EvidenceLocatorKind.HTML_PATH)
                self.assertIn(evidence.locator, locators)
                self.assertEqual(evidence.artifact_ref, item.artifact_ref)
        self.assertTrue(any(isinstance(c, CandidateFact) and c.predicate == "price" and c.value.currency == "USD" for c in result.candidates))

    def test_replay_html_uses_old_owner_and_strategy_changes_identity(self):
        from observer.contracts import ObservationOutcome
        source = b'<html><head><title>Guide</title></head><body><p>Price: 250 USD</p></body></html>'
        item = descriptor(source, media="text/html", owner="observer:observation:v1:historical")
        observed = material(outcome=ObservationOutcome.NOT_MODIFIED, revalidated=(item,))
        reader = MemoryReader({item.artifact_ref: source})
        now = datetime(2026, 9, 24, tzinfo=timezone.utc)
        first, _ = DeterministicInterpreter().interpret(observed, reader, started_at=now, clock=lambda: now)
        second, _ = DeterministicInterpreter().interpret(observed, reader, started_at=now, clock=lambda: now)
        self.assertEqual(first.candidates, second.candidates)
        self.assertTrue(all(e.artifact_observation_ref == item.observation_ref for c in first.candidates for e in c.evidence))
        old = strategy_fingerprint({"html": "1", "json": "1", "xml": "1", "text": "1", "pdf_text": "1", "semantic_rules": "1"})
        self.assertNotEqual(first.strategy_fingerprint, old)

    def test_pdf_page_number_and_empty_pdf_diagnostic(self):
        page = SimpleNamespace(extract_text=lambda: "Guide\nPrice: 250 USD")
        with patch("interpreter.extraction.PdfReader", return_value=SimpleNamespace(pages=[page])):
            result, _ = interpret(b"pdf-test", media="application/pdf")
        self.assertTrue(result.candidates)
        self.assertTrue(all(e.page_number == 1 for c in result.candidates for e in c.evidence))
        with patch("interpreter.extraction.PdfReader", return_value=SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: "")])):
            result, stats = interpret(b"pdf-test", media="application/pdf")
        self.assertEqual(result.outcome, InterpretationOutcome.FAILED)
        self.assertEqual(result.failure_code, "malformed_content")
        self.assertEqual(stats["ocr_calls"], 0)

    def test_html_resource_error_stays_distinct_from_success(self):
        result, _ = interpret(("<div>" * 70 + "x" + "</div>" * 70).encode(), media="text/html")
        self.assertEqual(result.outcome, InterpretationOutcome.FAILED)
        self.assertEqual(result.failure_code, "resource_limit")

    def test_content_meta_is_retained_without_becoming_document_metadata(self):
        result, _ = interpret(b'<head><title>Guide</title><meta itemprop="startDate" content="2026-10-14"></head><body><h1>Guide</h1></body>', media="text/html")
        start = next(c for c in result.candidates if isinstance(c, CandidateFact) and c.predicate == "start_date")
        self.assertIsNone(start.subject_ref)
        self.assertEqual(start.value.date_value.isoformat(), "2026-10-14")
