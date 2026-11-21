"""Django integration contracts for demo_generation Objectives scenarios."""
from unittest.mock import patch
from collections import Counter

from django.db.utils import OperationalError
from django.test import TestCase

from accounts.models import User
from activities.models import Activity
from journeys.models import Journey, JourneyStatus, WorkflowKind
from objectives.models import (
    Dossier, DossierJourneyDependency, DossierJourneyLink,
    Project, ProjectDossierLink,
)
from objectives.organizer import build_organizer_page
from scripts.demo_generation.objectives import generate, planned_titles


class ObjectivesDemoGeneratorTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="world_objectives_test", email="world_objectives_test@makolo.test",
            password="Example-only-test-password",
        )
        self.other = User.objects.create_user(
            username="world_other_test", email="world_other_test@makolo.test",
            password="Example-only-test-password",
        )
        for index in range(3):
            activity = Activity.objects.create(
                title=f"Activité de démonstration {index}",
                slug=f"demo-objectives-test-{index}",
                owner_profile=self.owner,
                created_by=self.owner,
            )
            Journey.objects.create(
                beneficiary=self.owner, initiated_by=self.owner, activity=activity,
                workflow=WorkflowKind.SERVICE, status=JourneyStatus.DRAFT,
            )

    def _generate(self, apply=False):
        return generate(
            [self.owner], count=1,
            projects_per_profile=3, dossiers_per_project=2,
            independent_dossiers=2, journeys_per_dossier=2, apply=apply,
        )

    def test_plan_is_read_only_and_reports_desired_coverage(self):
        result = self._generate()
        self.assertEqual(result["projects_planned"], 3)
        self.assertEqual(result["dossiers_planned"], 8)
        self.assertFalse(Project.objects.exists())
        self.assertFalse(Dossier.objects.exists())

    def test_repeat_preserves_identifiers_and_real_journey_links(self):
        self._generate(apply=True)
        first = {
            "projects": set(Project.objects.values_list("pk", flat=True)),
            "dossiers": set(Dossier.objects.values_list("pk", flat=True)),
            "project_links": set(ProjectDossierLink.objects.values_list("pk", flat=True)),
            "journey_links": set(DossierJourneyLink.objects.values_list("pk", flat=True)),
            "dependencies": set(DossierJourneyDependency.objects.values_list("pk", flat=True)),
        }
        self.assertEqual(len(first["projects"]), 3)
        self.assertEqual(len(first["dossiers"]), 8)
        self.assertEqual(len(first["project_links"]), 6)
        self.assertTrue(first["journey_links"])
        self.assertTrue(first["dependencies"])
        self._generate(apply=True)
        after = {
            "projects": set(Project.objects.values_list("pk", flat=True)),
            "dossiers": set(Dossier.objects.values_list("pk", flat=True)),
            "project_links": set(ProjectDossierLink.objects.values_list("pk", flat=True)),
            "journey_links": set(DossierJourneyLink.objects.values_list("pk", flat=True)),
            "dependencies": set(DossierJourneyDependency.objects.values_list("pk", flat=True)),
        }
        self.assertEqual(first, after)
        self.assertEqual(Journey.objects.count(), 3)
        self.assertEqual(Dossier.objects.filter(
            owner_profile=self.owner, project_links__is_active=True,
        ).distinct().count(), 6)

    def test_organizer_presents_real_parents_without_disclosing_another_person(self):
        self._generate(apply=True)
        page = build_organizer_page(self.owner, limit=50)
        kinds = {entry["kind"] for entry in page["items"]}
        self.assertEqual(kinds, {"project", "dossier", "journey"})
        self.assertEqual(sum(bool(e.get("project_id")) for e in page["items"]), 6)
        self.assertTrue(any(e.get("dossier_ids") for e in page["items"]))
        stranger = build_organizer_page(self.other, limit=50)
        self.assertFalse(stranger["items"])

    def test_mobile_mature_persona_links_its_existing_journeys(self):
        mobile = User.objects.create_user(
            username="beta_synthetic_mobile",
            email="beta_synthetic_mobile@makolo.test",
            password="Example-only-test-password",
            metadata={"seed": "mobile-mature-universe", "persona": "primary"},
        )
        for index in range(4):
            activity = Activity.objects.create(
                title=f"Activité mobile synthétique {index}",
                slug=f"mobile-mature-objectives-contract-{index}",
                owner_profile=mobile,
                created_by=mobile,
            )
            Journey.objects.create(
                beneficiary=mobile, initiated_by=mobile, activity=activity,
                workflow=WorkflowKind.SERVICE, status=JourneyStatus.DRAFT,
            )
        before = Journey.objects.count()
        result = generate(
            [mobile], count=1,
            projects_per_profile=2, dossiers_per_project=2,
            independent_dossiers=1, journeys_per_dossier=2, apply=True,
        )
        self.assertEqual(result["eligible_journeys"], 4)
        self.assertGreater(result["journey_links_created"], 0)
        self.assertEqual(Journey.objects.count(), before)
        page = build_organizer_page(mobile, limit=50)
        self.assertEqual(
            {row["kind"] for row in page["items"]},
            {"project", "dossier", "journey"},
        )
        self.assertTrue(
            any(row.get("dossier_ids") for row in page["items"]
                if row["kind"] == "journey")
        )

    def test_synthetic_activity_scope_does_not_include_other_namespaces(self):
        from scripts.demo_generation.scope import synthetic_journey_activity_prefixes
        self.assertEqual(
            synthetic_journey_activity_prefixes(self.owner), ("demo-",),
        )
        ordinary = User.objects.create_user(
            username="ordinary_beta_user", email="ordinary_beta@makolo.test",
            password="Example-only-test-password",
        )
        self.assertEqual(synthetic_journey_activity_prefixes(ordinary), ())

    def test_explicit_non_demo_profile_refused(self):
        ordinary = User.objects.create_user(
            username="normal_account", email="ordinary@makolo.test",
            password="Example-only-test-password",
        )
        with self.assertRaisesRegex(ValueError, "n'est pas un Profil de démonstration"):
            generate([ordinary], count=1, apply=True)
        self.assertFalse(Project.objects.exists())

    def test_journey_link_count_is_forwarded_to_atomic_generator(self):
        # Regression: the extracted helper previously referenced an unbound
        # journeys_per_dossier local variable, raising NameError on generate.
        with patch(
            "scripts.demo_generation.objectives._apply_one_profile",
            return_value=Counter({"profiles_completed": 1}),
        ) as apply_one:
            result = generate(
                [self.owner], count=1, projects_per_profile=2,
                dossiers_per_project=2, independent_dossiers=1,
                journeys_per_dossier=3, apply=True,
            )
        apply_one.assert_called_once()
        self.assertEqual(apply_one.call_args.args[3], 3)
        self.assertEqual(result["profiles_completed"], 1)

    def test_sqlite_lock_retries_whole_owner_transaction_without_duplicate_counts(self):
        # The mocked first attempt must fail before any transaction commits;
        # the retry contributes exactly one successful owner's counts.
        with patch(
            "scripts.demo_generation.objectives._apply_one_profile",
            side_effect=[
                OperationalError("database is locked"),
                Counter({"projects_created": 3, "dossiers_created": 8}),
            ],
        ) as apply_one, patch(
            "scripts.demo_generation.objectives.connections.close_all"
        ) as close, patch(
            "scripts.demo_generation.objectives.sleep"
        ) as pause:
            result = self._generate(apply=True)
        self.assertEqual(apply_one.call_count, 2)
        close.assert_called_once()
        pause.assert_called_once()
        self.assertEqual(result["projects_created"], 3)
        self.assertEqual(result["dossiers_created"], 8)

    def test_sqlite_lock_stops_after_bounded_attempts(self):
        with patch(
            "scripts.demo_generation.objectives._apply_one_profile",
            side_effect=OperationalError("database is locked"),
        ) as apply_one, patch(
            "scripts.demo_generation.objectives.connections.close_all"
        ), patch("scripts.demo_generation.objectives.sleep"):
            with self.assertRaisesRegex(RuntimeError, "toujours occupée"):
                self._generate(apply=True)
        self.assertEqual(apply_one.call_count, 3)

    def test_non_lock_database_error_is_never_retried(self):
        with patch(
            "scripts.demo_generation.objectives._apply_one_profile",
            side_effect=OperationalError("no such table"),
        ) as apply_one:
            with self.assertRaisesRegex(OperationalError, "no such table"):
                self._generate(apply=True)
        apply_one.assert_called_once()

    def test_names_are_unique_even_when_themes_repeat_common_words(self):
        pairs = list(planned_titles(
            self.owner, projects=8, per_project=6, independent=6,
        ))
        titles = [project for project, _ in pairs if project]
        dossiers = [title for _, titles in pairs for title in titles]
        self.assertEqual(len(titles), len(set(titles)))
        self.assertEqual(len(dossiers), len(set(dossiers)))
