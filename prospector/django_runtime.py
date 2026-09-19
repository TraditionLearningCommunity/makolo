from __future__ import annotations

from prospector.adapters.crawlee_queue import (
    CrawleeObservationInbox,
    CrawleeQueuePolicy,
)
from prospector.adapters.domain_scope import TldExtractDomainScope
from prospector.adapters.network import SystemDnsResolver
from prospector.django_budget import DjangoBudgetStore
from prospector.django_frontier import DjangoFrontierStore
from prospector.policy import ObservationPolicy
from prospector.runtime import ProspectorRuntime, RuntimePolicy
from prospector.safe_handoff import SafeObservationHandoff
from prospector.security import ObservationGate


def build_django_crawlee_runtime(
    *,
    request_queue,
    observation_policy: ObservationPolicy,
    runtime_policy: RuntimePolicy,
    queue_policy: CrawleeQueuePolicy,
) -> ProspectorRuntime:
    """Compose PX6 without assuming deployment storage or credentials.

    The caller owns the Crawlee RequestQueue construction. This factory only
    wires Makolo's durable Frontier, policy/budget gate and Observer inbox.
    """

    frontier = DjangoFrontierStore()
    gate = ObservationGate(
        dns_resolver=SystemDnsResolver(),
        domain_scope=TldExtractDomainScope(),
        budget_store=DjangoBudgetStore(),
    )
    observer = CrawleeObservationInbox(
        request_queue=request_queue,
        policy=queue_policy,
    )
    handoff = SafeObservationHandoff(
        gate=gate,
        observer=observer,
    )
    return ProspectorRuntime(
        frontier=frontier,
        handoff=handoff,
        observation_policy=observation_policy,
        runtime_policy=runtime_policy,
    )



def build_django_adaptive_crawlee_runtime(
    *,
    request_queue,
    observation_policy: ObservationPolicy,
    runtime_policy: RuntimePolicy,
    queue_policy: CrawleeQueuePolicy,
    adaptive_policy,
) -> ProspectorRuntime:
    """Compose PX7 adaptive selection without changing PX6 boundaries."""

    from prospector.adaptive_frontier import DjangoAdaptiveFrontierStore
    from prospector.django_feedback import DjangoFeedbackStore

    feedback_store = DjangoFeedbackStore()
    frontier = DjangoAdaptiveFrontierStore(
        feedback_store=feedback_store,
        policy=adaptive_policy,
    )
    gate = ObservationGate(
        dns_resolver=SystemDnsResolver(),
        domain_scope=TldExtractDomainScope(),
        budget_store=DjangoBudgetStore(),
    )
    observer = CrawleeObservationInbox(
        request_queue=request_queue,
        policy=queue_policy,
    )
    handoff = SafeObservationHandoff(
        gate=gate,
        observer=observer,
    )
    return ProspectorRuntime(
        frontier=frontier,
        handoff=handoff,
        observation_policy=observation_policy,
        runtime_policy=runtime_policy,
    )
