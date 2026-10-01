import subprocess
import sys
from pathlib import Path
from unittest import TestCase


class MayeleImportBoundaryTests(TestCase):
    def test_mayele_imports_without_django_or_legacy_actors(self):
        repository_root = Path(__file__).resolve().parents[2]
        code = (
            "import sys; "
            "import mayele, mayele.common, mayele.knowledge, mayele.acquisition, mayele.observation, mayele.cognition, mayele.identity; "
            "forbidden=('django','prospector','observer','interpreter','resolver',"
            "'web_research','orchestration','projector'); "
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
            "from datetime import datetime, timezone; "
            "from mayele.knowledge import Reality, Proposition, PropositionKind; "
            "from mayele.acquisition import DiscoveryResult; "
            "from mayele.observation import Source, SourceKind, ObservationAttempt, ObservationAttemptOutcome, Observation, ObservedArtifact, Passage, ObservedStatement, Mention; "
            "from mayele.cognition import Interpretation, InterpretationMode, RealityCandidate, InterpretationReferent, ReferentKind; "
            "from mayele.identity import IdentityResolution, IdentityResolutionBasis, IdentityResolutionBasisKind, IdentityResolutionStatus, validate_identity_resolution; "
            "p=Proposition(PropositionKind.REALITY_EXISTS, Reality('reality:visa')); "
            "s=Source('source:x', SourceKind.WEB_PAGE); "
            "now=datetime.now(timezone.utc); "
            "a=ObservationAttempt('attempt:x', s, now, ObservationAttemptOutcome.SUCCESS); "
            "o=Observation('observation:x', a, now); "
            "art=ObservedArtifact('artifact:x', o, 'text/plain'); "
            "st=ObservedStatement('statement:x', Passage('passage:x', art, 'line=1'), 'Observed text'); "
            "m=Mention('mention:x', st, 'Observed', start=0, end=8); "
            "i=Interpretation('interpretation:x', st, now, InterpretationMode.EXPLICIT, mentions=(m,)); "
            "c=RealityCandidate('candidate:x', i); "
            "r=IdentityResolution('resolution:x', InterpretationReferent(ReferentKind.MENTION, m.mention_ref), m.scope, now, IdentityResolutionStatus.UNRESOLVED, basis=(IdentityResolutionBasis(IdentityResolutionBasisKind.MENTION, m.mention_ref),)); "
            "validate_identity_resolution(r, m); "
            "assert len(p.fingerprint) == 64; assert len(c.fingerprint) == 64; assert r.reality is None"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
