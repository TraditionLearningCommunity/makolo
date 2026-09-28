from __future__ import annotations

from intelligence.interoperability import project_provider_connection, provider_connections_for_profile

from .projections import build_interoperability_payload


def build_profile_interoperability_payload(actor):
    """Return the canonical Z16 Profile projection for API or Web consumers."""

    connections = [
        project_provider_connection(connection, manageable=True)
        for connection in provider_connections_for_profile(actor)
    ]
    return build_interoperability_payload(
        context="profile",
        connections=connections,
        self_link="/api/v1/me/interoperability/",
        actor=actor,
        authority_context=actor,
    )
