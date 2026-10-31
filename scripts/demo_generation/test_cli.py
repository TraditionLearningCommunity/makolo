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
             patch("scripts.demo_generation.mandates.main") as mandates, \
             patch("scripts.demo_generation.foundations.main") as foundations:
            run(args)
        called = verticals.call_args.args[0]
        self.assertIn("funding", called)
        self.assertIn("7", called)
        self.assertNotIn("--apply", called)
        scale.assert_not_called()
        transport.assert_not_called()
        mandates.assert_not_called()
        self.assertIn("funding", foundations.call_args.args[0])
        self.assertNotIn("--apply", foundations.call_args.args[0])

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

    def test_model_inventory_uses_complete_catalog(self):
        args = build_parser().parse_args(["inventory"])
        with patch("scripts.demo_generation.catalog.main") as catalog:
            run(args)
        catalog.assert_called_once_with([])

    def test_audit_supports_explicit_reference_date(self):
        args = build_parser().parse_args([
            "audit", "--at", "2026-10-30T18:00:00+02:00",
        ])
        with patch("scripts.demo_generation.audit.main") as audit:
            run(args)
        audit.assert_called_once_with(["--at", "2026-10-30T18:00:00+02:00"])



    def test_sharing_is_in_default_domain_coverage(self):
        self.assertIn("sharing", parse_domains("all"))

    def test_live_placement_routes_without_generating_other_domains(self):
        args = build_parser().parse_args([
            "plan", "--domains", "placement", "--count", "3",
        ])
        with patch("scripts.demo_generation.live.main") as live, \
             patch("scripts.demo_generation.scale.main") as scale:
            run(args)
        self.assertIn("placement", live.call_args.args[0])
        self.assertNotIn("--apply", live.call_args.args[0])
        scale.assert_not_called()

    def test_generate_media_routes_explicit_write(self):
        args = build_parser().parse_args([
            "generate", "--domains", "media", "--count", "3",
        ])
        with patch("scripts.demo_generation.media.main") as media:
            run(args)
        self.assertIn("--apply", media.call_args.args[0])



    def test_live_journey_pairs_cover_occurrences_before_repeating(self):
        from scripts.demo_generation.scale import distributed_pairs
        pairs = list(distributed_pairs(["o1", "o2", "o3"], ["u1", "u2"], 6))
        self.assertEqual([occ for occ, _ in pairs], [
            "o1", "o2", "o3", "o1", "o2", "o3"])
        self.assertEqual(len(set(pairs)), 6)

    def test_live_journey_pairs_handle_missing_candidates(self):
        from scripts.demo_generation.scale import distributed_pairs
        self.assertEqual(list(distributed_pairs([], ["u1"], 100)), [])
        self.assertEqual(list(distributed_pairs(["o1"], [], 100)), [])

    def test_model_policy_classifies_secrets_without_seeding(self):
        from types import SimpleNamespace
        from scripts.demo_generation.catalog import policy_for
        credential = SimpleNamespace(
            __name__="ProviderCredential",
            _meta=SimpleNamespace(label="intelligence.ProviderCredential",
                                  app_label="intelligence"))
        # Storage/engine observation policy also prevents generic seeding.
        self.assertIn(policy_for(credential)[0], {"observed", "protected"})



    def test_personal_ecosystem_domains_are_supported(self):
        domains = {"spaces", "loyalty", "automation", "discovery",
                   "goals", "space", "funding", "commerce"}
        self.assertTrue(domains.issubset(parse_domains("all")))

    def test_personal_and_ecosystem_preview_do_not_write(self):
        args = build_parser().parse_args([
            "plan", "--domains", "spaces,loyalty,automation,discovery,goals,space",
            "--count", "6", "--profiles", "6",
        ])
        with patch("scripts.demo_generation.ecosystem.main") as ecosystem, \
             patch("scripts.demo_generation.personal.main") as personal:
            run(args)
        self.assertNotIn("--apply", ecosystem.call_args.args[0])
        self.assertNotIn("--apply", personal.call_args.args[0])
        ecosystem_argv = ecosystem.call_args.args[0]
        personal_argv = personal.call_args.args[0]
        self.assertEqual(
            set(ecosystem_argv[ecosystem_argv.index("--domains") + 1].split(",")),
            {"spaces", "loyalty", "automation"},
        )
        self.assertEqual(
            set(personal_argv[personal_argv.index("--domains") + 1].split(",")),
            {"discovery", "goals", "space"},
        )

    def test_personal_domain_can_be_generated_without_global_mandates(self):
        args = build_parser().parse_args(["generate", "--domains", "goals"])
        with patch("scripts.demo_generation.personal.main") as personal:
            run(args)
        self.assertIn("--apply", personal.call_args.args[0])



    def test_accepted_access_outcomes_are_in_all(self):
        self.assertIn("outcomes", parse_domains("all"))

    def test_outcomes_are_previewed_without_write(self):
        args = build_parser().parse_args([
            "plan", "--domains", "outcomes", "--count", "8",
        ])
        with patch("scripts.demo_generation.aftercare.main") as aftercare:
            run(args)
        self.assertNotIn("--apply", aftercare.call_args.args[0])
        self.assertIn("8", aftercare.call_args.args[0])

    def test_completed_outcomes_use_explicit_generate(self):
        args = build_parser().parse_args([
            "generate", "--domains", "outcomes", "--count", "8",
        ])
        with patch("scripts.demo_generation.aftercare.main") as aftercare:
            run(args)
        self.assertIn("--apply", aftercare.call_args.args[0])



    def test_validate_routes_quick_to_isolated_runner(self):
        args = build_parser().parse_args(["validate", "--quick", "--failfast"])
        with patch("scripts.demo_generation.validate.main", return_value=0) as validator:
            run(args)
        self.assertEqual(
            validator.call_args.args[0],
            ["--verbosity", "1", "--quick", "--failfast"],
        )

    def test_validate_defaults_to_full_contract_suite(self):
        args = build_parser().parse_args(["validate"])
        with patch("scripts.demo_generation.validate.main", return_value=0) as validator:
            run(args)
        self.assertEqual(validator.call_args.args[0], ["--verbosity", "1"])

    def test_validate_refuses_source_db_as_test_db(self):
        from unittest.mock import MagicMock
        from scripts.demo_generation.validate import main
        fake = MagicMock()
        fake.settings_dict = {"NAME": "db.sqlite3", "TEST": {"NAME": "db.sqlite3"}}
        with patch("django.db.connections", {"default": fake}):
            with self.assertRaises(SystemExit):
                main(["--quick"])

if __name__ == "__main__":
    unittest.main()
