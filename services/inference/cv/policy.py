"""
LoopSight — the final decision policy.

This is deliberately the smallest, most boring file in the codebase. Per
spec Section 9's design constraint: the LLM never renders the pass/fail
verdict. This function does, and it's plain enough for a judge to read
top to bottom in under a minute.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .first_pass import FirstPassResult, RegionEvidence, PROFILES


@dataclass
class FinalDecision:
    decision: str  # "PASS" | "REVIEW" | "FAIL"
    confidence_band: str  # "high" | "medium" | "low"
    evidence_changed: bool
    human_approval_required: bool
    reasoning: list[str] = field(default_factory=list)


def decide(
    first_pass: FirstPassResult,
    second_pass_region: RegionEvidence | None,
    profile_name: str = "fdm_print_surface_v1",
) -> FinalDecision:
    profile = PROFILES[profile_name]

    if first_pass.status == "CONFIDENT_PASS":
        return FinalDecision(
            decision="PASS",
            confidence_band="high",
            evidence_changed=False,
            human_approval_required=False,
            reasoning=["first pass confident, no second look triggered"],
        )

    if first_pass.status == "CONFIDENT_FAIL":
        return FinalDecision(
            decision="FAIL",
            confidence_band="high",
            evidence_changed=False,
            human_approval_required=True,
            reasoning=["first pass confidently detected a defect signal"],
        )

    # UNCERTAIN with no second-pass evidence yet — shouldn't normally reach
    # the policy in this state, but fail safe rather than raise.
    if second_pass_region is None:
        return FinalDecision(
            decision="REVIEW",
            confidence_band="low",
            evidence_changed=False,
            human_approval_required=True,
            reasoning=["first pass uncertain, no second-pass evidence available"],
        )

    # Second pass ran — did it actually resolve the ambiguity?
    ec = second_pass_region.edge_continuity
    if ec >= profile.edge_continuity_confident_pass:
        return FinalDecision(
            decision="PASS",
            confidence_band="medium",
            evidence_changed=True,
            human_approval_required=False,
            reasoning=[f"second-pass edge continuity {ec:.2f} resolved the ambiguity toward PASS"],
        )
    if ec <= profile.edge_continuity_confident_fail:
        return FinalDecision(
            decision="FAIL",
            confidence_band="medium",
            evidence_changed=True,
            human_approval_required=True,
            reasoning=[f"second-pass edge continuity {ec:.2f} resolved the ambiguity toward FAIL"],
        )

    # Still ambiguous after a genuine second look — this is a legitimate,
    # expected outcome (spec Section 9), not a bug to eliminate.
    return FinalDecision(
        decision="REVIEW",
        confidence_band="low",
        evidence_changed=True,
        human_approval_required=True,
        reasoning=[f"second-pass edge continuity {ec:.2f} still in the ambiguous band — genuine REVIEW case"],
    )
