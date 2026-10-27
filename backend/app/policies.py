"""Server-side enforcement for per-case and per-run resource limits."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException


def configured_limits(settings: Any) -> dict[str, int]:
    """Return the deployment's hard ceilings for every supported policy field."""
    return {
        "max_seed_urls": settings.max_seed_urls,
        "max_depth": settings.max_depth,
        "max_new_entities": settings.max_new_entities,
        "max_source_fetches": settings.max_source_fetches,
        "run_deadline_seconds": settings.run_deadline_seconds,
    }


def _validated_limits(requested: Mapping[str, Any] | None,
                      ceilings: Mapping[str, int]) -> dict[str, int]:
    if requested is None:
        requested = {}
    if not isinstance(requested, Mapping):
        raise HTTPException(422, "Limits must be an object")

    unknown = sorted(set(requested) - set(ceilings))
    if unknown:
        raise HTTPException(422, f"Unsupported limit field(s): {', '.join(unknown)}")

    limits: dict[str, int] = {}
    for name, ceiling in ceilings.items():
        value = requested.get(name, ceiling)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise HTTPException(422, f"Limit '{name}' must be a non-negative integer")
        limits[name] = min(value, ceiling)
    return limits


def clamp_case_limits(requested: Mapping[str, Any] | None,
                      settings: Any) -> dict[str, int]:
    """Allow a case to tighten, never exceed, deployment-configured ceilings."""
    return _validated_limits(requested, configured_limits(settings))


def clamp_run_limits(case_limits: Mapping[str, Any] | None,
                     requested: Mapping[str, Any] | None,
                     settings: Any) -> dict[str, int]:
    """Allow a run to tighten, never exceed, its case's effective limits."""
    deployment_ceiling = configured_limits(settings)
    stored_case_limits = case_limits if isinstance(case_limits, Mapping) else {}
    case_ceiling: dict[str, int] = {}
    for name, ceiling in deployment_ceiling.items():
        value = stored_case_limits.get(name, ceiling)
        # Earlier versions persisted arbitrary values from the client. Invalid
        # legacy values fall back to the deployment ceiling, never to no limit.
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            value = ceiling
        case_ceiling[name] = min(value, ceiling)
    return _validated_limits(requested, case_ceiling)
