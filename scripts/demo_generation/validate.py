"""Isolated test runner for demo generation.

Uses Django's test runner to provision and destroy a test database. NEVER
points a generator at the user's actual demo SQLite. Full mode also executes
existing canonical domain suites, not just CLI mocks.
"""
import argparse
import os

QUICK_LABELS = (
    "scripts.demo_generation.test_cli",
    "scripts.demo_generation.test_integration",
)
DOMAIN_LABELS = (
    "funding.tests",
    "payments.tests",
    "journeys.tests",
    "access.tests",
    "scanner.tests",
    "operations.tests",
    "services.tests",
    "obtention.tests",
    "tickets.tests",
    "presentations.tests",
    "organizations.tests",
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true",
                        help="Only demo-generation CLI and integration tests")
    parser.add_argument("--failfast", action="store_true")
    parser.add_argument("--verbosity", type=int, default=1, choices=(0, 1, 2))
    args = parser.parse_args(argv)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django
    django.setup()
    from django.conf import settings
    from django.db import connections
    from django.test.utils import get_runner

    # Validate against the configured Django test runner, which creates its own
    # test database. Refuse any custom TEST.NAME that points at the source DB.
    for alias in connections:
        cfg = connections[alias].settings_dict
        configured = str(cfg.get("NAME") or "")
        test_name = str((cfg.get("TEST") or {}).get("NAME") or "")
        if test_name and test_name == configured:
            raise SystemExit(
                "Refus : TEST.NAME pointe vers la base ordinaire (" + alias + ")."
            )

    labels = QUICK_LABELS if args.quick else (*QUICK_LABELS, *DOMAIN_LABELS)
    print("VALIDATION:", "QUICK" if args.quick else "DOMAIN", len(labels),
          "test labels (Django isolated test database)", flush=True)
    runner = get_runner(settings)(
        verbosity=args.verbosity, interactive=False,
        failfast=args.failfast, keepdb=False,
    )
    failures = runner.run_tests(labels)
    if failures:
        raise SystemExit(1)
    print("VALIDATION OK: demo generation and canonical domain contracts.")
    return 0


if __name__ == "__main__":
    main()
