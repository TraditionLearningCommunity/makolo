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
            "'web_research','orchestration','projector','celery','langgraph','openai','anthropic','neo4j','redis'); "
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
            "from mayele.knowledge import Reality, Proposition, PropositionKind, PropositionConstruction, KnowledgeSupportTrace, build_proposition_construction; "
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
            "from mayele.knowledge import KnowledgeFacetStatus, KnowledgeFacetState, build_knowledge_completeness, build_knowledge_state, ResearchGapTarget, ResearchGapTargetKind, ResearchGapReason, build_research_gap; "
            "kc=build_knowledge_completeness(Reality('reality:visa'), now, facets=(KnowledgeFacetState('deadline', KnowledgeFacetStatus.UNKNOWN, now),)); "
            "ks=build_knowledge_state(Reality('reality:visa'), now, state_ref='state:x', completeness=kc); "
            "gap=build_research_gap(ks, ResearchGapTarget(ResearchGapTargetKind.FACET,'deadline'), ResearchGapReason.UNKNOWN, now, gap_ref='gap:x', basis_refs=('deadline',), trigger_ref='need:x'); "
            "assert len(p.fingerprint) == 64; assert len(c.fingerprint) == 64; assert r.reality is None; assert PropositionConstruction; assert KnowledgeSupportTrace; assert build_proposition_construction; assert gap.knowledge_state_ref == ks.state_ref"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
