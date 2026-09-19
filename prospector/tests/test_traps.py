from unittest import TestCase

from prospector.traps import inspect_web_url


class UrlStructureTests(TestCase):
    def test_shape_collapses_calendar_and_query_values(self):
        left = inspect_web_url(
            "https://example.test/calendar/2026-09-18?page=1&lang=fr"
        )
        right = inspect_web_url(
            "https://example.test/calendar/2026-09-19?page=999&lang=en"
        )
        self.assertEqual(left.shape, right.shape)

    def test_shape_collapses_numeric_and_uuid_identifiers(self):
        numeric_a = inspect_web_url("https://example.test/items/12345")
        numeric_b = inspect_web_url("https://example.test/items/67890")
        self.assertEqual(numeric_a.shape, numeric_b.shape)

        uuid_a = inspect_web_url(
            "https://example.test/items/123e4567-e89b-12d3-a456-426614174000"
        )
        uuid_b = inspect_web_url(
            "https://example.test/items/123e4567-e89b-12d3-a456-426614174001"
        )
        self.assertEqual(uuid_a.shape, uuid_b.shape)

    def test_counts_query_pairs_and_path_segments(self):
        value = inspect_web_url("https://example.test/a/b/c?x=1&x=2&y=3")
        self.assertEqual(value.query_parameter_count, 3)
        self.assertEqual(value.path_segment_count, 3)
