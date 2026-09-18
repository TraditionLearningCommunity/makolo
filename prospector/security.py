from __future__ import annotations

import ipaddress
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlsplit

from .frontier import FrontierClaim
from .observation_contracts import make_handoff_key
from .policy import GateDecision, GateDisposition, ObservationPolicy


def _host_matches(hostname: str, suffix: str) -> bool:
    return hostname == suffix or hostname.endswith("." + suffix)


def _global_address(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


def _period_bounds(now: datetime, period_seconds: int):
    now = now.astimezone(timezone.utc)
    epoch = int(now.timestamp())
    start_epoch = epoch - (epoch % period_seconds)
    period_start = datetime.fromtimestamp(start_epoch, tz=timezone.utc)
    return period_start, period_start + timedelta(seconds=period_seconds)


class ObservationGate:
    """Pre-observation security, scope and budget gate.

    Discovery does not grant collection rights. This gate runs after a Frontier
    claim and before the Observateur is allowed to receive the target.
    """

    def __init__(self, *, dns_resolver, domain_scope, budget_store) -> None:
        self.dns_resolver = dns_resolver
        self.domain_scope = domain_scope
        self.budget_store = budget_store

    async def evaluate(
        self,
        claim: FrontierClaim,
        *,
        policy: ObservationPolicy,
        now: datetime,
    ) -> GateDecision:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        now = now.astimezone(timezone.utc)
        target = claim.target

        if target.kind not in policy.allowed_kinds:
            return GateDecision(
                GateDisposition.REJECT,
                "policy.unsupported_target_kind",
            )
        if policy.max_locator_length is not None and len(target.locator) > policy.max_locator_length:
            return GateDecision(
                GateDisposition.REJECT,
                "policy.locator_too_long",
            )

        try:
            parts = urlsplit(target.locator)
            hostname = (parts.hostname or "").rstrip(".").lower()
        except ValueError:
            return GateDecision(GateDisposition.REJECT, "security.malformed_locator")

        if parts.scheme not in {"http", "https"} or not hostname:
            return GateDecision(
                GateDisposition.REJECT,
                "security.unsupported_locator",
            )
        if parts.username is not None or parts.password is not None:
            return GateDecision(
                GateDisposition.REJECT,
                "security.embedded_credentials",
            )

        if hostname == "localhost" or hostname.endswith(".localhost"):
            return GateDecision(
                GateDisposition.REJECT,
                "security.localhost",
            )

        if any(_host_matches(hostname, suffix) for suffix in policy.denied_host_suffixes):
            return GateDecision(
                GateDisposition.REJECT,
                "policy.host_denied",
            )
        if policy.allowed_host_suffixes and not any(
            _host_matches(hostname, suffix)
            for suffix in policy.allowed_host_suffixes
        ):
            return GateDecision(
                GateDisposition.REJECT,
                "policy.host_out_of_scope",
            )

        if policy.denied_path_prefixes and any(
            parts.path.startswith(prefix)
            for prefix in policy.denied_path_prefixes
        ):
            return GateDecision(
                GateDisposition.REJECT,
                "policy.path_denied",
            )

        sensitive_names = set(policy.sensitive_query_names)
        for name, _value in parse_qsl(parts.query, keep_blank_values=True):
            if name.lower() in sensitive_names:
                return GateDecision(
                    GateDisposition.REJECT,
                    "security.sensitive_query",
                )

        depth = target.policy_context.get("depth", 0)
        if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0:
            return GateDecision(
                GateDisposition.REJECT,
                "policy.invalid_depth",
            )
        if policy.max_depth is not None and depth > policy.max_depth:
            return GateDecision(
                GateDisposition.REJECT,
                "policy.depth_exceeded",
            )

        try:
            literal = ipaddress.ip_address(hostname)
        except ValueError:
            literal = None

        if literal is not None:
            if not literal.is_global:
                return GateDecision(
                    GateDisposition.REJECT,
                    "security.non_global_address",
                )
            addresses = (literal.compressed,)
        else:
            try:
                addresses = tuple(await self.dns_resolver.resolve(hostname))
            except Exception:
                addresses = ()
            if not addresses:
                return GateDecision(
                    GateDisposition.DEFER,
                    "security.dns_unresolved",
                    retry_at=now + timedelta(seconds=policy.dns_retry_seconds),
                )
            if any(not _global_address(address) for address in addresses):
                return GateDecision(
                    GateDisposition.REJECT,
                    "security.non_global_address",
                )

        registrable_domain = self.domain_scope.registrable_domain(hostname)
        scopes = {
            "host": hostname,
            "domain": registrable_domain,
        }
        context_scope_fields = {
            "mission": "mission_key",
            "campaign": "campaign_key",
            "branch": "branch_key",
        }
        for scope_kind, field_name in context_scope_fields.items():
            value = target.policy_context.get(field_name)
            if isinstance(value, str) and value.strip():
                scopes[scope_kind] = value.strip()

        if policy.budget is not None:
            required = set(policy.budget.limits)
            missing = sorted(required - set(scopes))
            if missing:
                return GateDecision(
                    GateDisposition.REJECT,
                    f"policy.missing_budget_scope.{missing[0]}",
                    budget_scopes=scopes,
                )
            period_start, period_end = _period_bounds(
                now,
                policy.budget.period_seconds,
            )
            budget = await self.budget_store.reserve(
                handoff_key=make_handoff_key(
                    target_key=target.target_key,
                    handoff_generation=claim.handoff_generation,
                ),
                policy_key=policy.policy_key,
                scopes={kind: scopes[kind] for kind in policy.budget.limits},
                limits=policy.budget.limits,
                period_start=period_start,
                period_end=period_end,
                now=now,
            )
            if not budget.allowed:
                return GateDecision(
                    GateDisposition.DEFER,
                    "budget.exhausted",
                    retry_at=budget.retry_at,
                    budget_scopes=scopes,
                )

        return GateDecision(
            GateDisposition.ALLOW,
            "admissible",
            budget_scopes=scopes,
        )
