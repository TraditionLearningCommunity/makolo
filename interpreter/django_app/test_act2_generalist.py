from django.test import SimpleTestCase

from interpreter.contracts import (
    CandidateConstraint,
    CandidateEntity,
    CandidateFact,
    CandidateModality,
    CandidateRelation,
    CandidateValueKind,
    ConstraintOperator,
    LogicOperator,
)
from .tests import interpret


class GeneralistDeterministicExtractionTests(SimpleTestCase):
    def _html(self, body):
        return interpret(
            ("<html lang='en'><head><title>Guide</title></head><body>"
             + body + "</body></html>").encode(),
            media="text/html",
        )[0]

    def test_possibility_scenario_does_not_require_business_model(self):
        result = self._html(
            "<h1>Open call</h1><p>Start: 2026-11-03</p>"
            "<p>Location: Kinshasa</p>"
        )
        facts = [c for c in result.candidates if isinstance(c, CandidateFact)]
        self.assertTrue(any(c.predicate == "start_date" and c.value.kind is CandidateValueKind.DATE for c in facts))
        self.assertTrue(any(c.predicate == "location_text" for c in facts))
        self.assertFalse(any("activity" == h for c in result.candidates if isinstance(c, CandidateEntity) for h in c.type_hints if c.label == "Guide"))

    def test_requirement_scenario_preserves_or_and_modality(self):
        result = self._html(
            "<h1>Admission</h1><h2>Requirements</h2>"
            "<p>Passport OR national ID required</p>"
        )
        relations = [
            c for c in result.candidates
            if isinstance(c, CandidateRelation) and c.predicate == "requires"
        ]
        disjunction = [c for c in relations if c.logic_operator is LogicOperator.OR]
        self.assertEqual(len(disjunction), 2)
        self.assertEqual(len({c.logic_group for c in disjunction}), 1)
        self.assertTrue(all(c.modality is CandidateModality.REQUIRED for c in disjunction))

    def test_qualification_scenario_extracts_generic_threshold(self):
        result = self._html(
            "<h1>Qualification</h1><h2>Eligibility</h2>"
            "<p>Language score >= 80</p>"
        )
        constraints = [c for c in result.candidates if isinstance(c, CandidateConstraint)]
        self.assertTrue(any(
            c.operator is ConstraintOperator.GTE
            and c.value.number == 80
            for c in constraints
        ))
        self.assertTrue(any(
            isinstance(c, CandidateEntity)
            and c.label == "Language score"
            and "requirement_subject" in c.type_hints
            for c in result.candidates
        ))

    def test_actor_scenario_extracts_organization_and_person(self):
        result = self._html(
            "<h1>Contacts</h1>"
            "<p>Organization: Universite Alpha</p>"
            "<p>Contact person: Marie K.</p>"
        )
        entities = [c for c in result.candidates if isinstance(c, CandidateEntity)]
        self.assertTrue(any(c.label == "Universite Alpha" and "organization" in c.type_hints for c in entities))
        self.assertTrue(any(c.label == "Marie K." and "person" in c.type_hints for c in entities))
        predicates = {c.predicate for c in result.candidates if isinstance(c, CandidateRelation)}
        self.assertTrue({"provided_by", "contact_person"}.issubset(predicates))

    def test_spatiotemporal_scenario_types_only_complete_dates(self):
        result = self._html(
            "<h1>Session</h1>"
            "<p>Start: 2026-11-03</p>"
            "<p>End: 3 December</p>"
            "<p>Duration: 3 weeks</p>"
            "<p>Capacity: 40 seats</p>"
        )
        facts = [c for c in result.candidates if isinstance(c, CandidateFact)]
        start = next(c for c in facts if c.predicate == "start_date")
        end = next(c for c in facts if c.predicate == "end_date")
        duration = next(c for c in facts if c.predicate == "duration")
        self.assertIs(start.value.kind, CandidateValueKind.DATE)
        self.assertIs(end.value.kind, CandidateValueKind.TEXT)
        self.assertIs(duration.value.kind, CandidateValueKind.QUANTITY)
        self.assertTrue(any(c.predicate == "capacity_announced" and c.value.number == 40 for c in facts))


    def test_datetime_requires_timezone_and_named_date_requires_year(self):
        result = self._html(
            "<h1>Schedule</h1>"
            "<p>Start: 2026-11-03T09:30:00+02:00</p>"
            "<p>End: 14 October 2026</p>"
            "<p>Deadline: 14 October</p>"
        )
        facts = [c for c in result.candidates if isinstance(c, CandidateFact)]
        start = next(c for c in facts if c.predicate == "start_date")
        end = next(c for c in facts if c.predicate == "end_date")
        deadline = next(c for c in facts if c.predicate == "deadline")
        self.assertIs(start.value.kind, CandidateValueKind.DATETIME)
        self.assertEqual(start.value.datetime_value.isoformat(), "2026-11-03T07:30:00+00:00")
        self.assertIs(end.value.kind, CandidateValueKind.DATE)
        self.assertEqual(end.value.date_value.isoformat(), "2026-10-14")
        self.assertIs(deadline.value.kind, CandidateValueKind.TEXT)

    def test_procedure_scenario_extracts_links_and_form_without_fetching(self):
        result = self._html(
            "<h1>How to apply</h1>"
            "<a href='https://example.test/apply'>Apply now</a>"
            "<a href='https://example.test/register'>Registration</a>"
            "<a href='mailto:help@example.test'>Contact</a>"
            "<form action='/submit'><label>Name</label><input name='name'></form>"
        )
        facts = [c for c in result.candidates if isinstance(c, CandidateFact)]
        predicates = {c.predicate for c in facts}
        self.assertTrue({"application_url", "registration_url", "contact_email", "form_available"}.issubset(predicates))

    def test_economic_scenario_does_not_invent_currency(self):
        result = self._html(
            "<h1>Fees</h1><p>Price: 250 USD</p><p>Cost: 100</p>"
        )
        prices = [c for c in result.candidates if isinstance(c, CandidateFact) and c.predicate == "price"]
        self.assertTrue(any(c.value.kind is CandidateValueKind.MONEY and c.value.currency == "USD" for c in prices))
        self.assertTrue(any(c.value.kind is CandidateValueKind.NUMBER and c.value.currency is None for c in prices))

    def test_reference_scenario_extracts_canonical_and_guide_links(self):
        result = interpret(
            b"""<html><head><title>Official guide</title>
            <link rel='canonical' href='https://example.test/guide'></head>
            <body><h1>Official guide</h1>
            <a href='https://example.test/rules.pdf'>Rules PDF</a></body></html>""",
            media="text/html",
        )[0]
        urls = [
            c.value.text for c in result.candidates
            if isinstance(c, CandidateFact) and c.predicate == "reference_url"
        ]
        self.assertIn("https://example.test/guide", urls)
        self.assertIn("https://example.test/rules.pdf", urls)

    def test_interval_negation_contacts_and_contradictions_are_not_flattened(self):
        result = self._html(
            "<h1>Conditions</h1><h2>Requirements</h2>"
            "<p>No passport required</p>"
            "<p>Age 18-30 years</p>"
            "<p>Contact: team@example.test +243 999 111 222</p>"
            "<p>Deadline: 2026-11-01</p><p>Deadline: 2026-11-05</p>"
        )
        self.assertTrue(any(
            isinstance(c, CandidateRelation)
            and c.predicate == "requires"
            and c.modality is CandidateModality.NEGATED
            for c in result.candidates
        ))
        self.assertTrue(any(
            isinstance(c, CandidateConstraint)
            and c.operator is ConstraintOperator.BETWEEN
            for c in result.candidates
        ))
        facts = [c for c in result.candidates if isinstance(c, CandidateFact)]
        self.assertTrue(any(c.predicate == "contact_email" for c in facts))
        self.assertTrue(any(c.predicate == "contact_phone" for c in facts))
        deadlines = {c.value.raw_text for c in facts if c.predicate == "deadline"}
        self.assertEqual(deadlines, {"2026-11-01", "2026-11-05"})
