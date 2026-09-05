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

    # Responsible-AI guard: if no reference pattern was detected at all, do not
    # return a confident turbidity verdict on invalid input. This prevents a
    # non-water photo (wall, person, random object) from being scored as PASS/FAIL/REVIEW
    # when the checkerboard was never visible. See Part 3.3 audit.
    if profile_name == "water_turbidity_v1":
        first_has_pattern = any(getattr(r, "pattern_found", False) for r in first_pass.regions) if first_pass.regions else False
        second_has_pattern = bool(getattr(second_pass_region, "pattern_found", False)) if second_pass_region is not None else False
        # Evidence gap explicitly says pattern not detected, or no region found it, and second look also didn't find it
        pattern_missing_first = (not first_has_pattern) or any("pattern not detected" in g.lower() for g in first_pass.evidence_gap)
        if pattern_missing_first and not second_has_pattern:
            return FinalDecision(
                decision="NO_PATTERN_DETECTED",
                confidence_band="low",
                evidence_changed=second_pass_region is not None,
                human_approval_required=True,
                reasoning=["reference pattern not detected — ensure the printed checkerboard/grid is visible behind the water sample; no turbidity verdict possible on invalid input"],
            )

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

    # Water profile: second pass resolves via pattern visibility, not edge continuity
    if profile_name == "water_turbidity_v1":
        # Prefer pattern_visibility when available; fallback to edge_continuity (aliased)
        pv = getattr(second_pass_region, "pattern_visibility", 0.0) or 0.0
        # If pattern_visibility is 0 but edge_continuity has signal, use edge as fallback
        metric_val = pv if pv > 0 else second_pass_region.edge_continuity
        if metric_val >= profile.pattern_visibility_confident_clear:
            return FinalDecision(
                decision="PASS",
                confidence_band="medium",
                evidence_changed=True,
                human_approval_required=False,
                reasoning=[f"second-pass pattern visibility {metric_val:.2f} resolved toward clear water (no visible turbidity)"],
            )
        if metric_val <= profile.pattern_visibility_confident_turbid:
            return FinalDecision(
                decision="FAIL",
                confidence_band="medium",
                evidence_changed=True,
                human_approval_required=True,
                reasoning=[f"second-pass pattern visibility {metric_val:.2f} resolved toward turbid water (visible turbidity)"],
            )
        return FinalDecision(
            decision="REVIEW",
            confidence_band="low",
            evidence_changed=True,
            human_approval_required=True,
            reasoning=[f"second-pass pattern visibility {metric_val:.2f} still in borderline band — genuine REVIEW, request different lighting or lab test"],
        )

    # FDM and generic profiles: edge continuity
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
