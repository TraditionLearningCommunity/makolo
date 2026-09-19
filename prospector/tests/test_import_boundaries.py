import subprocess
import sys
from pathlib import Path
from unittest import TestCase


class FrameworkBoundaryTests(TestCase):
    def test_core_imports_without_django(self):
        repository_root = Path(__file__).resolve().parents[2]
        code = (
            "import sys; "
            "import prospector, prospector.contracts, prospector.ports; "
            "assert not any(name == 'django' or name.startswith('django.') "
            "for name in sys.modules)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
