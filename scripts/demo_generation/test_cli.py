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

    def test_objectives_plan_routes_volume_and_username_to_existing_domain(self):
        args = build_parser().parse_args([
            "plan", "--domains", "objectives", "--count", "8",
            "--profiles", "100", "--profile-username", "world_011_divine",
            "--objectives-projects", "6",
            "--objectives-dossiers-per-project", "4",
            "--objectives-independent", "3",
            "--objectives-journeys-per-dossier", "2",
        ])
        with patch("scripts.demo_generation.community.main") as community:
            run(args)
        argv = community.call_args.args[0]
        self.assertIn("--profile-username", argv)
        self.assertIn("world_011_divine", argv)
        for token in ("--objectives-projects", "--objectives-dossiers-per-project",
                      "--objectives-independent", "--objectives-journeys-per-dossier"):
            self.assertIn(token, argv)
        self.assertNotIn("--apply", argv)

    def test_objectives_generate_applies_only_with_explicit_generate(self):
        args = build_parser().parse_args([
            "generate", "--domains", "objectives", "--count", "1",
            "--profile-username", "world_011_divine",
        ])
        with patch("scripts.demo_generation.community.main") as community:
            run(args)
        self.assertIn("--apply", community.call_args.args[0])

    def test_objectives_reject_unbounded_generation_parameters(self):
        args = build_parser().parse_args([
            "generate", "--domains", "objectives",
            "--objectives-projects", "100",
        ])
        with self.assertRaises(SystemExit):
            run(args)

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


    def test_named_beneficiary_routes_without_world_distribution(self):
        args = build_parser().parse_args([
            "plan", "--domains", "discovery,goals,journeys,access",
            "--profile-username", "beta_alain", "--profiles", "1",
        ])
        with patch("scripts.demo_generation.personal.main") as personal, \
             patch("scripts.demo_generation.scale.main") as scale:
            run(args)
        self.assertEqual(
            personal.call_args.args[0][personal.call_args.args[0].index("--profile-username") + 1],
            "beta_alain",
        )
        self.assertEqual(
            scale.call_args.args[0][scale.call_args.args[0].index("--profile-username") + 1],
            "beta_alain",
        )
        self.assertNotIn("--apply", personal.call_args.args[0])
        self.assertNotIn("--apply", scale.call_args.args[0])

    def test_generic_paid_subscription_preview(self):
        args = build_parser().parse_args(["plan", "--domains", "subscriptions"])
        with patch("scripts.demo_generation.subscriptions.main") as seeded:
            run(args)
        self.assertEqual(seeded.call_args.args[0],
                         ["--count", "50", "--profiles", "30"])

    def test_named_all_is_accepted_for_contextual_routing(self):
        args = build_parser().parse_args([
            "plan", "--domains", "all", "--profile-username", "beta_alain",
        ])
        with patch("scripts.demo_generation.personal.main") as personal, \
             patch("scripts.demo_generation.ecosystem.main") as ecosystem, \
             patch("scripts.demo_generation.transport.main"), \
             patch("scripts.demo_generation.mandates.main"), \
             patch("scripts.demo_generation.foundations.main"), \
             patch("scripts.demo_generation.verticals.main"), \
             patch("scripts.demo_generation.scale.main"), \
             patch("scripts.demo_generation.aftercare.main"), \
             patch("scripts.demo_generation.live.main"), \
             patch("scripts.demo_generation.community.main"), \
             patch("scripts.demo_generation.engagement.main"), \
             patch("scripts.demo_generation.media.main"), \
             patch("scripts.demo_generation.conversations.main") as conversations:
            run(args)
        self.assertIn("--profile-username", conversations.call_args.args[0])
        self.assertIn("--profile-username", personal.call_args.args[0])
        self.assertIn("--profile-username", ecosystem.call_args.args[0])

    def test_named_paid_subscription_preview_is_read_only(self):
        args = build_parser().parse_args([
            "plan", "--domains", "subscriptions",
            "--profile-username", "beta_alain", "--count", "4",
        ])
        with patch("scripts.demo_generation.subscriptions.main") as seeded:
            run(args)
        self.assertEqual(seeded.call_args.args[0],
                         ["--count", "4", "--profiles", "30", "--profile-username", "beta_alain"])

    def test_named_paid_subscription_generate_is_explicit(self):
        args = build_parser().parse_args([
            "generate", "--domains", "subscriptions",
            "--profile-username", "beta_alain",
        ])
        with patch("scripts.demo_generation.subscriptions.main") as seeded:
            run(args)
        self.assertIn("--apply", seeded.call_args.args[0])

    def test_all_never_charges_subscriptions_implicitly(self):
        self.assertNotIn("subscriptions", parse_domains("all"))



    def test_demo_subscription_catalog_is_opt_in(self):
        self.assertNotIn("subscription-catalog", parse_domains("all"))
        args = build_parser().parse_args(["plan", "--domains", "subscription-catalog"])
        with patch("scripts.demo_generation.subscription_catalog.main") as catalog:
            run(args)
        catalog.assert_called_once_with([])

    def test_demo_subscription_catalog_generate(self):
        args = build_parser().parse_args(["generate", "--domains", "subscription-catalog"])
        with patch("scripts.demo_generation.subscription_catalog.main") as catalog:
            run(args)
        catalog.assert_called_once_with(["--apply"])



    def test_connections_catalog_is_in_all_without_fake_credentials(self):
        self.assertIn("connections", parse_domains("all"))
        args = build_parser().parse_args(["plan", "--domains", "connections"])
        with patch("scripts.demo_generation.connections.main") as connected:
            run(args)
        connected.assert_called_once_with(["--count", "50", "--profiles", "30"])

    def test_connections_generate_does_not_claim_credentials(self):
        args = build_parser().parse_args(["generate", "--domains", "connections"])
        with patch("scripts.demo_generation.connections.main") as connected:
            run(args)
        connected.assert_called_once_with(["--apply", "--count", "50", "--profiles", "30"])



    def test_conversation_generation_follows_context_foundations(self):
        args = build_parser().parse_args([
            "plan", "--domains", "services,conversations", "--count", "3",
        ])
        calls = []
        with (
            patch("scripts.demo_generation.foundations.main",
                  side_effect=lambda _args: calls.append("foundations")),
            patch("scripts.demo_generation.verticals.main",
                  side_effect=lambda _args: calls.append("verticals")),
            patch("scripts.demo_generation.conversations.main",
                  side_effect=lambda _args: calls.append("conversations")),
        ):
            run(args)
        self.assertEqual(calls, ["foundations", "verticals", "conversations"])

    def test_conversation_generator_plan_routes_target_and_seed(self):
        self.assertIn("conversations", parse_domains("all"))
        args = build_parser().parse_args([
            "plan", "--domains", "conversations", "--count", "500",
            "--profiles", "20", "--profile-username", "world_011_divine",
            "--seed", "7", "--conversation-points", "3",
        ])
        with patch("scripts.demo_generation.conversations.main") as seeded:
            run(args)
        self.assertEqual(seeded.call_args.args[0], [
            "--count", "500", "--profiles", "20", "--seed", "7",
            "--points", "3", "--profile-username", "world_011_divine",
        ])

    def test_conversations_generate_explicit_apply(self):
        args = build_parser().parse_args([
            "generate", "--domains", "conversations", "--count", "500",
        ])
        with patch("scripts.demo_generation.conversations.main") as seeded:
            run(args)
        self.assertIn("--apply", seeded.call_args.args[0])

    def test_conversation_phase_and_point_story_are_grounded(self):
        from datetime import datetime, timedelta, timezone
        from scripts.demo_generation.conversations import (
            phase_for_dates, point_blueprints, scenario_reference,
        )
        now = datetime(2026, 11, 4, tzinfo=timezone.utc)
        self.assertEqual(phase_for_dates(now - timedelta(days=3),
                                         now - timedelta(days=2), now), "past")
        self.assertEqual(phase_for_dates(now - timedelta(minutes=5),
                                         now + timedelta(minutes=30), now), "live")
        self.assertEqual(phase_for_dates(now + timedelta(days=2),
                                         now + timedelta(days=3), now), "future")
        self.assertEqual(len(point_blueprints("live", "Atelier")), 4)
        self.assertTrue(all(mode == "free_text" for kind, _, _, mode, _ in point_blueprints("live", "Atelier") if kind == "exchange"))
        self.assertEqual(scenario_reference("activity", "123", "live", 2),
                         scenario_reference("activity", "123", "live", 2))



    def test_conversations_accept_existing_beta_test_accounts(self):
        args = build_parser().parse_args([
            "generate", "--domains", "conversations",
            "--count", "500", "--conversation-include-test-users",
        ])
        with patch("scripts.demo_generation.conversations.main") as seeded:
            run(args)
        self.assertIn("--include-test-users", seeded.call_args.args[0])
        self.assertIn("--apply", seeded.call_args.args[0])



    def test_timeline_moves_occurrence_with_atomic_date_window(self):
        import sqlite3
        from scripts.demo_generation.clock import update_occurrence
        from datetime import timedelta
        db = sqlite3.connect(":memory:")
        db.execute(
            "CREATE TABLE activities_occurrence ("
            "id TEXT PRIMARY KEY, start_at TEXT, end_at TEXT,"
            "start_date TEXT, end_date TEXT, start_time TEXT, end_time TEXT,"
            "schedule_local_date TEXT, timezone TEXT, schedule_id TEXT,"
            "CONSTRAINT activities_occ_date_window CHECK "
            "(end_date IS NULL OR start_date IS NULL OR end_date >= start_date))"
        )
        db.execute(
            "INSERT INTO activities_occurrence VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("one", "2026-10-10 09:00:00", "2026-10-11 10:00:00",
             "2026-10-10", "2026-10-11", "10:00:00", "11:00:00",
             None, "Africa/Kinshasa", None),
        )
        self.assertEqual(update_occurrence(db, "one", timedelta(days=60)), 1)
        result = db.execute(
            "SELECT start_date,end_date FROM activities_occurrence WHERE id='one'"
        ).fetchone()
        self.assertEqual(result, ("2026-12-09", "2026-12-10"))
        self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        db.close()

    def test_timeline_preserves_schedule_generated_slots(self):
        import sqlite3
        from scripts.demo_generation.clock import update_occurrence
        from datetime import timedelta
        db = sqlite3.connect(":memory:")
        db.execute(
            "CREATE TABLE activities_occurrence ("
            "id TEXT, start_at TEXT, end_at TEXT, start_date TEXT, end_date TEXT,"
            "start_time TEXT, end_time TEXT, schedule_local_date TEXT,"
            "timezone TEXT, schedule_id TEXT)"
        )
        row = ("one", "2026-10-10 09:00:00", "2026-10-10 10:00:00",
               "2026-10-10", "2026-10-10", "10:00:00", "11:00:00",
               "2026-10-10", "Africa/Kinshasa", "schedule-1")
        db.execute("INSERT INTO activities_occurrence VALUES (?,?,?,?,?,?,?,?,?,?)", row)
        self.assertEqual(update_occurrence(db, "one", timedelta(days=20)), 0)
        self.assertEqual(
            db.execute("SELECT * FROM activities_occurrence").fetchone(), row
        )
        db.close()


    def test_subscription_offers_have_natural_visible_names(self):
        from scripts.demo_generation.subscription_catalog import DEMO_OFFERS
        self.assertTrue(all("demo" not in item[3].lower() for item in DEMO_OFFERS))

    def test_editorial_titles_are_natural_and_repeatable(self):
        from types import SimpleNamespace
        from scripts.demo_generation.editorial import (
            space_name, group_name, objective_titles, activity_title,
            space_activity_title,
        )
        owner = SimpleNamespace(pk="10000000-0000-0000-0000-000000000011",
                                username="world_011_divine")
        values = [
            space_name(owner), group_name(owner), *objective_titles(owner),
            activity_title("funding", 0), activity_title("services", 7),
            activity_title("obtention", 20), space_activity_title(owner),
        ]
        self.assertEqual(space_name(owner), space_name(owner))
        self.assertEqual(group_name(owner), group_name(owner))
        self.assertTrue(all(value and "demo" not in value.lower()
                            and "world_" not in value.lower() for value in values))

    def test_conversation_reply_stays_contextual_and_deterministic(self):
        from scripts.demo_generation.conversations import coherent_reply, exchange_dialogue
        response = coherent_reply("future", "Atelier des familles", "reference-123")
        self.assertEqual(response, coherent_reply("future", "Atelier des familles", "reference-123"))
        self.assertNotIn("demo", response.lower())
        self.assertEqual(len(exchange_dialogue("live", "reference-123")), 2)



    def test_connection_rotation_covers_50_choices_for_each_profile(self):
        from scripts.demo_generation.connections import offer_index
        for profile_position in range(2):
            values = {
                offer_index(slot, 2, 50)
                for slot in range(profile_position, 100, 2)
            }
            self.assertEqual(values, set(range(50)))
        self.assertEqual(offer_index(50, 1, 50), 0)

    def test_foundations_username_is_forwarded(self):
        args = build_parser().parse_args([
            "plan", "--domains", "services", "--count", "8",
            "--profile-username", "world_011_divine",
        ])
        with patch("scripts.demo_generation.foundations.main") as foundations, \
             patch("scripts.demo_generation.verticals.main"):
            run(args)
        self.assertIn("--profile-username", foundations.call_args.args[0])
        self.assertIn("world_011_divine", foundations.call_args.args[0])


    def test_timeline_exposes_scoped_safety_and_backup(self):
        args = build_parser().parse_args([
            "timeline", "--activity-prefix", "demo-generation-",
            "--mode", "safe", "--backup", "--demo-slots", "8",
            "--now", "2026-11-09T09:00:00+01:00",
        ])
        with patch("scripts.demo_generation.clock.main") as timeline:
            run(args)
        options = timeline.call_args.args[0]
        self.assertEqual(options[options.index("--activity-prefix") + 1],
                         "demo-generation-")
        self.assertIn("--backup", options)
        self.assertIn("--mode", options)
        self.assertNotIn("--apply", options)

    def test_rebalance_routes_profile_and_space_modes_without_writes(self):
        for target in ("profiles", "spaces"):
            args = build_parser().parse_args([
                "rebalance", "--target", target, "--per-profile", "4",
                "--count", "12", "--profile-username", "world_demo",
            ])
            with patch("scripts.demo_generation.rebalance.main") as balance:
                run(args)
            options = balance.call_args.args[0]
            self.assertIn(target, options)
            self.assertIn("world_demo", options)
            self.assertNotIn("--apply", options)

    def test_period_rebalance_reuses_timeline_code(self):
        args = build_parser().parse_args([
            "rebalance", "--target", "periods", "--limit", "6",
            "--mode", "full", "--demo-live",
        ])
        with patch("scripts.demo_generation.clock.main") as timeline:
            run(args)
        options = timeline.call_args.args[0]
        self.assertIn("--mode", options)
        self.assertIn("full", options)
        self.assertIn("--demo-live", options)
        self.assertNotIn("--apply", options)

    def test_maintenance_routes_all_manual_operations(self):
        for action in ("complete", "refresh", "retire", "restore"):
            args = build_parser().parse_args([
                "maintain", "--action", action, "--count", "7",
            ])
            with patch("scripts.demo_generation.maintenance.main") as maintenance:
                run(args)
            options = maintenance.call_args.args[0]
            self.assertIn(action, options)
            self.assertNotIn("--apply", options)

    def test_demo_editorial_refresh_is_deterministic(self):
        from scripts.demo_generation.maintenance import editorial_text
        self.assertEqual(editorial_text(4, "my-demo-id"),
                         editorial_text(4, "my-demo-id"))
        self.assertTrue(editorial_text(4, "my-demo-id"))

    def test_rebalance_rotation_is_stable(self):
        from types import SimpleNamespace
        from scripts.demo_generation.rebalance import rank_items
        profile = SimpleNamespace(pk="one")
        items = [SimpleNamespace(pk=str(i)) for i in range(7)]
        self.assertEqual(
            [v.pk for v in rank_items(profile, items, 42)],
            [v.pk for v in rank_items(profile, list(reversed(items)), 42)],
        )

    def test_safe_timeline_refuses_consumed_or_completed_scenarios(self):
        import sqlite3
        from datetime import timedelta
        from scripts.demo_generation.clock import safe_eligible, move_occurrence
        db = sqlite3.connect(":memory:")
        db.execute(
            "CREATE TABLE activities_occurrence (id TEXT PRIMARY KEY, "
            "start_at TEXT, end_at TEXT, start_date TEXT, end_date TEXT, "
            "start_time TEXT, end_time TEXT, schedule_local_date TEXT, "
            "timezone TEXT, schedule_id TEXT, status TEXT)"
        )
        db.execute(
            "INSERT INTO activities_occurrence VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("one", "2026-10-10 09:00:00", "2026-10-10 10:00:00",
             "2026-10-10", "2026-10-10", "09:00:00", "10:00:00",
             None, "Africa/Kinshasa", None, "completed"),
        )
        self.assertFalse(safe_eligible(db, "one"))
        moved = move_occurrence(db, "one", timedelta(days=5), mode="safe")
        self.assertEqual(moved["activities_occurrence"], 0)
        db.execute("UPDATE activities_occurrence SET status='scheduled'")
        db.execute(
            "CREATE TABLE access_accessuse "
            "(id TEXT, occurrence_id TEXT, access_id TEXT, used_at TEXT)"
        )
        db.execute(
            "INSERT INTO access_accessuse VALUES (?,?,?,?)",
            ("use-1", "one", None, "2026-10-10 09:30:00"),
        )
        self.assertFalse(safe_eligible(db, "one"))
        moved = move_occurrence(db, "one", timedelta(days=5), mode="safe")
        self.assertEqual(moved["activities_occurrence"], 0)
        self.assertEqual(
            db.execute("SELECT used_at FROM access_accessuse").fetchone()[0],
            "2026-10-10 09:30:00",
        )
        db.close()


    def test_rebalance_trim_is_explicit_and_forwards_backup(self):
        args = build_parser().parse_args([
            "rebalance", "--target", "profiles", "--direction", "trim",
            "--per-profile", "2", "--activity-prefix", "demo-generation-",
            "--apply", "--backup",
        ])
        with patch("scripts.demo_generation.rebalance.main") as rebalance:
            run(args)
        options = rebalance.call_args.args[0]
        self.assertIn("trim", options)
        self.assertIn("--apply", options)
        self.assertIn("--backup", options)
        self.assertIn("demo-generation-", options)

    def test_relationship_rebalance_rejects_ignored_timeline_options(self):
        args = build_parser().parse_args([
            "rebalance", "--target", "profiles", "--mode", "full",
        ])
        with self.assertRaises(SystemExit):
            run(args)

    def test_maintenance_forwards_scope_and_backup(self):
        args = build_parser().parse_args([
            "maintain", "--action", "refresh",
            "--activity-prefix", "demo-generation-services-",
            "--edition", "3", "--apply", "--backup",
        ])
        with patch("scripts.demo_generation.maintenance.main") as maintenance:
            run(args)
        options = maintenance.call_args.args[0]
        self.assertIn("demo-generation-services-", options)
        self.assertIn("--apply", options)
        self.assertIn("--backup", options)


    def test_full_timeline_applies_in_place_without_implicit_backup(self):
        args = build_parser().parse_args([
            "timeline", "--mode", "full", "--apply",
        ])
        with patch("scripts.demo_generation.clock.main") as timeline:
            run(args)
        options = timeline.call_args.args[0]
        self.assertIn("--apply", options)
        self.assertIn("full", options)
        self.assertNotIn("--backup", options)
        self.assertNotIn("--output", options)

    def test_trim_applies_without_implicit_backup(self):
        args = build_parser().parse_args([
            "rebalance", "--target", "profiles", "--direction", "trim",
            "--apply",
        ])
        with patch("scripts.demo_generation.rebalance.main") as rebalance:
            run(args)
        options = rebalance.call_args.args[0]
        self.assertIn("trim", options)
        self.assertIn("--apply", options)
        self.assertNotIn("--backup", options)

    def test_include_existing_has_no_implicit_backup(self):
        args = build_parser().parse_args([
            "timeline", "--include-existing", "--mode", "safe", "--apply",
        ])
        with patch("scripts.demo_generation.clock.main") as timeline:
            run(args)
        options = timeline.call_args.args[0]
        self.assertIn("--include-existing", options)
        self.assertIn("--apply", options)
        self.assertNotIn("--backup", options)

    def test_rebalance_refuses_non_demo_profiles(self):
        from scripts.demo_generation.rebalance import main as rebalance
        with self.assertRaises(SystemExit):
            rebalance(["--target", "profiles", "--profile-username", "real-person"])


    def test_resources_preview_routes_target_without_backup_or_apply(self):
        args = build_parser().parse_args([
            "resources", "--domains", "documents,proofs,credentials",
            "--profile-username", "beta_alain", "--count", "4",
        ])
        with patch("scripts.demo_generation.resources.main") as resources:
            run(args)
        values = resources.call_args.args[0]
        self.assertIn("beta_alain", values)
        self.assertIn("--reuse-avatar", values)
        self.assertNotIn("--apply", values)
        self.assertNotIn("--backup", values)

    def test_resources_apply_is_explicit_and_no_backup_by_default(self):
        args = build_parser().parse_args([
            "resources", "--domains", "documents", "--count", "3",
            "--apply", "--no-reuse-avatar",
        ])
        with patch("scripts.demo_generation.resources.main") as resources:
            run(args)
        values = resources.call_args.args[0]
        self.assertIn("--apply", values)
        self.assertIn("--no-reuse-avatar", values)
        self.assertNotIn("--backup", values)

    def test_resources_backup_only_when_requested(self):
        args = build_parser().parse_args([
            "resources", "--domains", "documents",
            "--apply", "--backup",
        ])
        with patch("scripts.demo_generation.resources.main") as resources:
            run(args)
        self.assertIn("--backup", resources.call_args.args[0])

    def test_resources_fallback_content_is_user_specific_and_not_a_certificate(self):
        from scripts.demo_generation.resources import demo_text, DOCUMENT_TITLES
        text = demo_text("beta_alain", 0).decode("utf-8")
        self.assertIn("@beta_alain", text)
        self.assertIn(DOCUMENT_TITLES[0], text)
        self.assertIn("ne constitue ni une piece d'identite", text)
        self.assertEqual(text, demo_text("beta_alain", 0).decode("utf-8"))


    def test_resources_local_avatar_is_copied_not_linked(self):
        from types import SimpleNamespace
        from django.core.files.uploadedfile import SimpleUploadedFile
        from scripts.demo_generation.resources import avatar_upload, document_slots
        png = b"\\x89PNG\\r\\n\\x1a\\n" + b"demo-image-bytes"
        class FakeStorage:
            def exists(self, name):
                return name == "avatars/own.png"
        class FakeAvatar:
            name = "avatars/own.png"
            storage = FakeStorage()
            def open(self, mode):
                from io import BytesIO
                return BytesIO(png)
        user = SimpleNamespace(username="beta_alain", avatar=FakeAvatar())
        copy = avatar_upload(user)
        self.assertIsInstance(copy, SimpleUploadedFile)
        self.assertEqual(copy.read(), png)
        docs = list(document_slots(user, include_avatar=True))
        self.assertEqual(docs[0][0], "Copie de ma photo de profil")
        self.assertEqual(docs[0][1].read(), png)

    def test_resources_missing_avatar_falls_back_to_text_documents(self):
        from types import SimpleNamespace
        from scripts.demo_generation.resources import document_slots
        user = SimpleNamespace(username="world_demo", avatar=None)
        docs = list(document_slots(user, include_avatar=True))
        self.assertEqual(len(docs), 4)
        for _title, upload in docs:
            self.assertEqual(upload.content_type, "text/plain")
            self.assertIn(b"Makolo", upload.read())


    def test_conversation_multi_principal_cli_routes_explicit_usernames(self):
        args = build_parser().parse_args([
            "plan", "--domains", "conversations", "--count", "25",
            "--conversation-usernames", "beta_alain,world_002_grace,world_003_sarah",
            "--conversation-max-participants", "8",
            "--conversation-context-types", "space,group,journey",
            "--conversation-selection", "random",
        ])
        with patch("scripts.demo_generation.conversations.main") as conversations:
            run(args)
        options = conversations.call_args.args[0]
        self.assertIn("beta_alain,world_002_grace,world_003_sarah", options)
        self.assertIn("--profile-usernames", options)
        self.assertIn("--max-participants", options)
        self.assertIn("space,group,journey", options)
        self.assertNotIn("--apply", options)

    def test_conversation_selection_uses_all_explicit_main_profiles(self):
        from scripts.demo_generation.conversations import (
            parse_usernames, ordered_principals, ordered_participants,
        )
        from types import SimpleNamespace
        self.assertEqual(
            parse_usernames(single="beta_alain",
                            multiple="world_002_grace,beta_alain,world_003_sarah"),
            ("beta_alain", "world_002_grace", "world_003_sarah"),
        )
        people = [SimpleNamespace(pk=str(i)) for i in range(8)]
        self.assertEqual(
            [p.pk for p in ordered_principals(people, 27)],
            [p.pk for p in ordered_principals(people, 27)],
        )
        selected = ordered_participants(people, seed=27, reference="demo", limit=5)
        self.assertEqual(len({p.pk for p in selected}), 5)

    def test_conversation_context_selection_fairness_and_collective_priority(self):
        from types import SimpleNamespace
        from scripts.demo_generation.conversations import select_contexts
        owners = [SimpleNamespace(pk="first"), SimpleNamespace(pk="second")]
        pools = {
            "activity": [("activity", "activity", SimpleNamespace(pk=str(i)),
                          owners[0], "Act", "ongoing") for i in range(12)],
            "space": [("space", "space", SimpleNamespace(pk="s1"),
                       owners[1], "Space", "ongoing")],
            "group": [("group", "group", SimpleNamespace(pk="g1"),
                       owners[0], "Group", "ongoing")],
        }
        chosen = select_contexts(
            pools, count=4, seed=17, kinds={"activity", "space", "group"}
        )
        self.assertEqual(len(chosen), 4)
        self.assertEqual({x[3].pk for x in chosen},
                         {"first", "second"})
        self.assertEqual({x[0] for x in chosen[:2]}, {"space", "group"})
        self.assertEqual(
            [(x[0], x[2].pk) for x in chosen],
            [(x[0], x[2].pk) for x in select_contexts(
                pools, count=4, seed=17,
                kinds={"activity", "space", "group"},
            )],
        )

if __name__ == "__main__":
    unittest.main()
