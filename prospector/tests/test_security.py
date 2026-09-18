from datetime import datetime, timedelta, timezone
from unittest import IsolatedAsyncioTestCase

from prospector.budget import BudgetReservationDecision
from prospector.contracts import ProspectingEvidence, ProspectingTarget
from prospector.frontier import FrontierClaim
from prospector.policy import BudgetPolicy, GateDisposition, ObservationPolicy
from prospector.security import ObservationGate


class FakeDnsResolver:
    def __init__(self, values=(), error=None):
        self.values = tuple(values)
        self.error = error

    async def resolve(self, hostname):
        if self.error:
            raise self.error
        return self.values


class FakeDomainScope:
    def registrable_domain(self, hostname):
        if hostname.endswith(".example.co.uk"):
            return "example.co.uk"
        return hostname


class FakeBudgetStore:
    def __init__(self, allowed=True, retry_at=None):
        self.allowed = allowed
        self.retry_at = retry_at
        self.calls = []

    async def reserve(self, **kwargs):
        self.calls.append(kwargs)
        return BudgetReservationDecision(
            allowed=self.allowed,
            retry_at=None if self.allowed else self.retry_at,
            scopes=kwargs["scopes"],
        )


class ObservationGateTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)

    def claim(self, locator, *, policy_context=None):
        evidence = ProspectingEvidence(
            method="external_index",
            discovered_at=self.now,
            provider="test-index",
        )
        target = ProspectingTarget(
            target_key="web_url:v1:" + ("a" * 64),
            locator=locator,
            kind="web_url",
            first_discovered_at=self.now,
            evidence=(evidence,),
            policy_context=policy_context or {},
        )
        return FrontierClaim(
            claim_token="claim-1",
            worker_id="worker-a",
            leased_until=self.now + timedelta(minutes=5),
            target=target,
            handoff_generation=1,
        )

    def policy(self, **kwargs):
        return ObservationPolicy(
            policy_key="test-v1",
            dns_retry_seconds=60,
            **kwargs,
        )

    async def evaluate(self, claim, policy, *, dns=("93.184.216.34",), budget=None):
        gate = ObservationGate(
            dns_resolver=FakeDnsResolver(dns),
            domain_scope=FakeDomainScope(),
            budget_store=budget or FakeBudgetStore(),
        )
        return await gate.evaluate(claim, policy=policy, now=self.now)

    async def test_rejects_localhost_private_literal_and_private_dns_answer(self):
        local = await self.evaluate(
            self.claim("https://localhost/path"),
            self.policy(),
            dns=(),
        )
        self.assertEqual(local.disposition, GateDisposition.REJECT)

        private_literal = await self.evaluate(
            self.claim("https://127.0.0.1/path"),
            self.policy(),
            dns=(),
        )
        self.assertEqual(private_literal.reason_code, "security.non_global_address")

        private_dns = await self.evaluate(
            self.claim("https://example.test/path"),
            self.policy(),
            dns=("93.184.216.34", "10.0.0.5"),
        )
        self.assertEqual(private_dns.reason_code, "security.non_global_address")

    async def test_dns_failure_defers_instead_of_permanently_suppressing(self):
        gate = ObservationGate(
            dns_resolver=FakeDnsResolver(error=OSError("temporary")),
            domain_scope=FakeDomainScope(),
            budget_store=FakeBudgetStore(),
        )
        decision = await gate.evaluate(
            self.claim("https://example.test/path"),
            policy=self.policy(),
            now=self.now,
        )
        self.assertEqual(decision.disposition, GateDisposition.DEFER)
        self.assertEqual(decision.reason_code, "security.dns_unresolved")
        self.assertEqual(decision.retry_at, self.now + timedelta(seconds=60))

    async def test_rejects_sensitive_query_denied_host_path_and_excess_depth(self):
        sensitive = await self.evaluate(
            self.claim("https://example.test/path?access_token=secret"),
            self.policy(),
        )
        self.assertEqual(sensitive.reason_code, "security.sensitive_query")

        denied_host = await self.evaluate(
            self.claim("https://api.example.test/path"),
            self.policy(denied_host_suffixes=("example.test",)),
        )
        self.assertEqual(denied_host.reason_code, "policy.host_denied")

        denied_path = await self.evaluate(
            self.claim("https://example.test/logout"),
            self.policy(denied_path_prefixes=("/logout",)),
        )
        self.assertEqual(denied_path.reason_code, "policy.path_denied")

        depth = await self.evaluate(
            self.claim("https://example.test/path", policy_context={"depth": 4}),
            self.policy(max_depth=3),
        )
        self.assertEqual(depth.reason_code, "policy.depth_exceeded")

    async def test_host_allow_scope_uses_label_boundary(self):
        allowed = await self.evaluate(
            self.claim("https://api.example.test/path"),
            self.policy(allowed_host_suffixes=("example.test",)),
        )
        self.assertEqual(allowed.disposition, GateDisposition.ALLOW)

        outside = await self.evaluate(
            self.claim("https://evil-example.test/path"),
            self.policy(allowed_host_suffixes=("example.test",)),
        )
        self.assertEqual(outside.reason_code, "policy.host_out_of_scope")

    async def test_budget_scopes_and_exhaustion(self):
        retry = self.now + timedelta(hours=1)
        budget_store = FakeBudgetStore(allowed=False, retry_at=retry)
        policy = self.policy(
            budget=BudgetPolicy(
                period_seconds=3600,
                limits={"host": 2, "domain": 4, "mission": 10},
            )
        )
        decision = await self.evaluate(
            self.claim(
                "https://sub.example.co.uk/path",
                policy_context={"mission_key": "rdc", "depth": 0},
            ),
            policy,
            budget=budget_store,
        )
        self.assertEqual(decision.disposition, GateDisposition.DEFER)
        self.assertEqual(decision.reason_code, "budget.exhausted")
        call = budget_store.calls[0]
        self.assertEqual(call["scopes"]["host"], "sub.example.co.uk")
        self.assertEqual(call["scopes"]["domain"], "example.co.uk")
        self.assertEqual(call["scopes"]["mission"], "rdc")

    async def test_missing_required_budget_scope_fails_closed(self):
        policy = self.policy(
            budget=BudgetPolicy(
                period_seconds=3600,
                limits={"campaign": 3},
            )
        )
        decision = await self.evaluate(
            self.claim("https://example.test/path"),
            policy,
        )
        self.assertEqual(decision.disposition, GateDisposition.REJECT)
        self.assertEqual(
            decision.reason_code,
            "policy.missing_budget_scope.campaign",
        )
