"""Tests pure-Python de l'interface demo_generation, sans toucher a la BDD."""
import unittest
from unittest.mock import patch

from scripts.demo_generation.__main__ import build_parser, parse_domains, run


class DemoGenerationCLITests(unittest.TestCase):
    def test_funding_is_a_domain_not_a_synonym(self):
        self.assertEqual(parse_domains("funding,obtention"), {"funding", "obtention"})
        with self.assertRaises(ValueError):
            parse_domains("financement")

    def test_all_excludes_readonly_content(self):
        self.assertNotIn("content", parse_domains("all"))
        self.assertIn("funding", parse_domains("all"))

    def test_mandates_require_explicit_opt_in_on_generate(self):
        args = build_parser().parse_args(["generate", "--domains", "mandates"])
        with self.assertRaises(SystemExit):
            run(args)

    def test_plan_is_a_preview_and_targets_only_funding(self):
        args = build_parser().parse_args(["plan", "--domains", "funding", "--count", "7"])
        with patch("scripts.demo_generation.verticals.main") as verticals, \
             patch("scripts.demo_generation.scale.main") as scale, \
             patch("scripts.demo_generation.transport.main") as transport, \
             patch("scripts.demo_generation.mandates.main") as mandates:
            run(args)
        called = verticals.call_args.args[0]
        self.assertIn("funding", called)
        self.assertIn("7", called)
        self.assertNotIn("--apply", called)
        scale.assert_not_called()
        transport.assert_not_called()
        mandates.assert_not_called()

    def test_timeline_no_write_by_default(self):
        args = build_parser().parse_args(["timeline", "--demo-live"])
        with patch("scripts.demo_generation.clock.main") as clock:
            run(args)
        self.assertNotIn("--apply", clock.call_args.args[0])


    def test_new_business_domains_are_selectable(self):
        self.assertEqual(
            parse_domains("media,groups,objectives,trust,notifications,contributions,forms,crm"),
            {"media", "groups", "objectives", "trust", "notifications",
             "contributions", "forms", "crm"},
        )

    def test_media_plan_uses_dry_run_only(self):
        args = build_parser().parse_args(["plan", "--domains", "media", "--count", "9"])
        with patch("scripts.demo_generation.media.main") as media:
            run(args)
        argv = media.call_args.args[0]
        self.assertIn("9", argv)
        self.assertNotIn("--apply", argv)

    def test_community_and_engagement_are_routed_independently(self):
        args = build_parser().parse_args([
            "plan", "--domains", "groups,forms", "--count", "4",
        ])
        with patch("scripts.demo_generation.community.main") as community, \
             patch("scripts.demo_generation.engagement.main") as engagement:
            run(args)
        self.assertIn("groups", community.call_args.args[0])
        self.assertIn("forms", engagement.call_args.args[0])
        self.assertNotIn("--apply", community.call_args.args[0])
        self.assertNotIn("--apply", engagement.call_args.args[0])

    def test_audit_supports_explicit_reference_date(self):
        args = build_parser().parse_args([
            "audit", "--at", "2026-10-30T18:00:00+02:00",
        ])
        with patch("scripts.demo_generation.audit.main") as audit:
            run(args)
        audit.assert_called_once_with(["--at", "2026-10-30T18:00:00+02:00"])


if __name__ == "__main__":
    unittest.main()
