from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time

from django.urls import reverse

from .essential import ESSENTIAL_MANIFEST, ESSENTIAL_THEME


MPS_ARTIFACT_PROJECTION = "mps.artifact"
MPS_TEMPLATE_PROJECTION = "mps.template.version"
MPS_THEME_PROJECTION = "mps.theme.version"
MPS_RENDERER_CONTRACT = "mps.native.v1"


def _json_value(value):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def context_payload(context):
    return {
        "activity": _json_value(context.activity),
        "occurrence": _json_value(context.occurrence),
        "organizer": _json_value(context.organizer),
        "recipient": _json_value(context.recipient),
        "access": _json_value(context.access),
        "editorial": _json_value(context.editorial),
        "actions": _json_value(context.actions),
    }


def _builtin_template_ref():
    return {
        "projection": MPS_TEMPLATE_PROJECTION,
        "resource_key": "builtin:makolo-essential:1",
        "builtin": True,
        "schema_version": int(ESSENTIAL_MANIFEST["schema_version"]),
    }


def _builtin_theme_ref():
    return {
        "projection": MPS_THEME_PROJECTION,
        "resource_key": "builtin:makolo-essential-theme:1",
        "builtin": True,
        "schema_version": 1,
    }


def template_ref(resolved, *, link_name=None, link_kwargs=None):
    version = resolved.template_version
    if version is None:
        return _builtin_template_ref()
    payload = {
        "projection": MPS_TEMPLATE_PROJECTION,
        "resource_key": str(version.pk),
        "builtin": False,
        "schema_version": int(version.schema_version),
    }
    if link_name:
        payload["path"] = reverse(link_name, kwargs={**(link_kwargs or {}), "version_id": version.pk})
    return payload


def theme_ref(resolved, *, link_name=None, link_kwargs=None):
    version = resolved.theme_version
    if version is None:
        return _builtin_theme_ref()
    payload = {
        "projection": MPS_THEME_PROJECTION,
        "resource_key": str(version.pk),
        "builtin": False,
        "schema_version": int(version.schema_version),
    }
    if link_name:
        payload["path"] = reverse(link_name, kwargs={**(link_kwargs or {}), "version_id": version.pk})
    return payload


def artifact_payload(
    *,
    subject_kind,
    subject_id,
    purpose,
    resolved,
    context,
    template_link_name=None,
    theme_link_name=None,
    link_kwargs=None,
    capabilities=(),
    links=None,
):
    return {
        "identity": {
            "kind": "mps_artifact",
            "resource_key": f"{subject_kind}:{subject_id}:{purpose}",
        },
        "subject": {"kind": subject_kind, "id": str(subject_id)},
        "purpose": str(purpose),
        "renderer": {
            "contract": MPS_RENDERER_CONTRACT,
            "schema_version": 1,
            "minimum_renderer_version": 1,
        },
        "template": template_ref(
            resolved,
            link_name=template_link_name,
            link_kwargs=link_kwargs,
        ),
        "theme": theme_ref(
            resolved,
            link_name=theme_link_name,
            link_kwargs=link_kwargs,
        ),
        "context": context_payload(context),
        "capabilities": list(capabilities),
        "links": dict(links or {}),
        "fallback_reason": resolved.fallback_reason or None,
    }


def template_definition_payload(version):
    return {
        "identity": {
            "kind": MPS_TEMPLATE_PROJECTION,
            "resource_key": str(version.pk),
        },
        "schema_version": int(version.schema_version),
        "version_number": int(version.version_number),
        "template": {
            "id": str(version.template_id),
            "slug": version.template.slug,
            "name": version.template.name,
        },
        "manifest": version.manifest,
    }


def theme_definition_payload(version):
    return {
        "identity": {
            "kind": MPS_THEME_PROJECTION,
            "resource_key": str(version.pk),
        },
        "schema_version": int(version.schema_version),
        "version_number": int(version.version_number),
        "theme": {
            "id": str(version.theme_id),
            "slug": version.theme.slug,
            "name": version.theme.name,
        },
        "tokens": version.tokens,
    }
