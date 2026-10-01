import subprocess
import sys
from pathlib import Path
from unittest import TestCase


class MayeleImportBoundaryTests(TestCase):
    def test_mayele_imports_without_django_or_legacy_actors(self):
        repository_root = Path(__file__).resolve().parents[2]
        code = (
            "import sys; "
            "import mayele, mayele.common, mayele.knowledge, mayele.acquisition, mayele.observation; "
            "forbidden=('django','prospector','observer','interpreter','resolver',"
            "'web_research','orchestration'); "
            "assert not any(name == prefix or name.startswith(prefix + '.') "
            "for prefix in forbidden for name in sys.modules)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)

    def test_contracts_work_in_fresh_python_process(self):
        repository_root = Path(__file__).resolve().parents[2]
        code = (
            "from mayele.knowledge import Reality, Proposition, PropositionKind; from mayele.acquisition import DiscoveryResult; from mayele.observation import Source, SourceKind; "
            "p=Proposition(PropositionKind.REALITY_EXISTS, Reality('reality:visa')); "
            "assert len(p.fingerprint) == 64; assert Source('source:x', SourceKind.WEB_PAGE).source_ref == 'source:x'"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
