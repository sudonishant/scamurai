"""Bounded, policy-enforced investigation agent (master prompt section 16).

The deterministic loop mirrors the required cycle:

    read scoped state -> propose one bounded action -> validate arguments and
    policy -> execute tool -> save evidence -> validate structured result ->
    continue or stop with an explicit reason

There is no LLM dependency: planning is a deterministic mapping from an
investigation goal to registered, case-scoped tools. When an LLM provider is
configured later, it may *propose* actions, but every action still passes
through the same policy layer — the model never gets shell, SQL, unrestricted
network access, or cross-case retrieval. All material under analysis is
treated as untrusted data (prompt injection can never become a tool call).
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from ..registry import TRANSFORMS

# Allowlisted typed tools. External providers stay disabled until configured;
# the policy reports that honestly instead of mocking evidence.
TOOL_SPECS = {
    "fetch_permitted_source": {"external": False, "needs_case": True},
    "search_case_evidence": {"external": False, "needs_case": True},
    "extract_ocr": {"external": True, "needs_case": True},
    "compare_images": {"external": False, "needs_case": True},
    "find_location_candidates": {"external": True, "needs_case": True},
    "analyze_comment": {"external": False, "needs_case": True},
    "compute_coordination_features": {"external": False, "needs_case": True},
    "extract_claims": {"external": False, "needs_case": True},
    "draft_finding": {"external": False, "needs_case": True},
    "search_public_sources": {"external": True, "needs_case": True},
}

# Deterministic goal -> ordered bounded plan (each entry matches a Transform).
GOAL_PLANS: dict[str, list[str]] = {
    "image_source": ["find_exact_duplicates", "find_visual_variants", "extract_ocr"],
    "photo_location": ["estimate_capture_location"],
    "comments": ["analyze_comment"],
    "coordination": ["compute_coordination_features"],
    "check_post": ["extract_claims", "plan_claim_searches"],
}

STOP_REASONS = (
    "completed", "step_budget_exhausted", "deadline_exceeded",
    "tool_not_allowlisted", "cross_case_access_denied", "external_provider_disabled",
    "unknown_goal", "tool_error",
)


class PolicyViolation(RuntimeError):
    """Raised outside the model layer; an agent proposal can never bypass it."""


@dataclass
class ToolCall:
    tool: str
    arguments: dict
    case_id: str


@dataclass
class ToolResult:
    ok: bool
    output: dict
    evidence_ids: list[str] = field(default_factory=list)
    limitation: str | None = None


@dataclass
class AgentStep:
    seq: int
    tool: str
    arguments: dict
    ok: bool
    stop_reason: str | None
    evidence_ids: list[str]
    limitation: str | None


ToolExecutor = Callable[[ToolCall], ToolResult]


class BoundedAgent:
    """Runs approved tools inside step, time and provider budgets."""

    def __init__(self, case_id: str, *, step_budget: int = 8,
                 elapsed_budget_seconds: float = 300.0,
                 external_providers_enabled: bool = False):
        self.case_id = case_id
        self.step_budget = step_budget
        self.elapsed_budget_seconds = elapsed_budget_seconds
        self.external_providers_enabled = external_providers_enabled
        self.steps: list[AgentStep] = []
        self._start = time.monotonic()

    # ------------------------------------------------------------------ policy
    def _validate(self, call: ToolCall) -> None:
        if call.tool not in TOOL_SPECS:
            raise PolicyViolation(f"tool_not_allowlisted: {call.tool}")
        if TOOL_SPECS[call.tool]["needs_case"] and call.arguments.get("case_id") != self.case_id:
            raise PolicyViolation("cross_case_access_denied: tool arguments reference another case")
        if TOOL_SPECS[call.tool]["external"] and not self.external_providers_enabled:
            raise PolicyViolation(
                f"external_provider_disabled: {call.tool} (no approved provider configured)")

    def propose_plan(self, goal: str) -> list[str]:
        return list(GOAL_PLANS.get(goal, []))

    # ------------------------------------------------------------------ run
    def run(self, goal: str, executor: ToolExecutor) -> dict:
        plan = self.propose_plan(goal)
        if not plan:
            return {"status": "stopped", "stop_reason": "unknown_goal", "steps": self.steps,
                    "evidence_ids": self._collected_evidence()}

        for seq, transform_name in enumerate(plan, start=1):
            if len(self.steps) >= self.step_budget:
                return self._stop("step_budget_exhausted")
            if time.monotonic() - self._start > self.elapsed_budget_seconds:
                return self._stop("deadline_exceeded")

            # A Transform name maps to its allowlisted tool; unknown transforms
            # are refused rather than guessed.
            spec = TRANSFORMS.get(transform_name)
            tool = self._tool_for_transform(transform_name)
            if spec is None or tool is None:
                self.steps.append(AgentStep(seq, transform_name, {}, False,
                                            "tool_not_allowlisted", [], None))
                return self._stop("tool_not_allowlisted")

            call = ToolCall(tool=tool,
                            arguments={"case_id": self.case_id, "transform": transform_name},
                            case_id=self.case_id)
            try:
                self._validate(call)
                result = executor(call)
            except PolicyViolation as exc:
                reason = str(exc).split(":", 1)[0]
                self.steps.append(AgentStep(seq, call.tool, call.arguments, False,
                                            reason, [], str(exc)))
                return self._stop(reason)
            except Exception as exc:
                self.steps.append(AgentStep(seq, call.tool, call.arguments, False,
                                            "tool_error", [], str(exc)))
                return self._stop("tool_error")

            self.steps.append(AgentStep(
                seq, call.tool, call.arguments, result.ok, None,
                result.evidence_ids, result.limitation))
            if not result.ok and result.limitation:
                # Honest abstention: a disabled/empty tool ends the plan cleanly.
                return self._stop("external_provider_disabled"
                                  if "provider" in result.limitation.lower() else "tool_error")

        return self._stop("completed")

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _tool_for_transform(transform_name: str) -> str | None:
        mapping = {
            "import_authorized_posts": "search_case_evidence",
            "import_comments": "search_case_evidence",
            "extract_ocr": "extract_ocr",
            "find_exact_duplicates": "compare_images",
            "find_visual_variants": "compare_images",
            "estimate_capture_location": "find_location_candidates",
            "analyze_comment": "analyze_comment",
            "compute_coordination_features": "compute_coordination_features",
            "extract_claims": "extract_claims",
            "plan_claim_searches": "search_public_sources",
            "reverse_image_search": "search_public_sources",
        }
        return mapping.get(transform_name)

    def _stop(self, reason: str) -> dict:
        return {"status": "stopped", "stop_reason": reason, "steps": self.steps,
                "evidence_ids": self._collected_evidence()}

    def _collected_evidence(self) -> list[str]:
        seen: list[str] = []
        for step in self.steps:
            for evidence_id in step.evidence_ids:
                if evidence_id not in seen:
                    seen.append(evidence_id)
        return seen
