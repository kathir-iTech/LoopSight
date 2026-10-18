"""
LoopSight v2 — the deterministic final decision policy.

Per spec Section 9's design constraint: the LLM never renders the pass/fail
verdict. This function does, and it is completely deterministic and auditable.
Supports all three inspection profiles:
  - water_turbidity_v1
  - structural_crack_metrology_v1
  - fdm_print_surface_v1
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .first_pass import FirstPassResult, RegionEvidence, PROFILES


@dataclass
class FinalDecision:
    decision: str  # "PASS" | "REVIEW" | "FAIL" | "NO_PATTERN_DETECTED"
    confidence_band: str  # "high" | "medium" | "low"
    evidence_changed: bool
    human_approval_required: bool
    reasoning: list[str] = field(default_factory=list)


def decide(
    first_pass: FirstPassResult,
    second_pass_region: RegionEvidence | None,
    profile_name: str = "fdm_print_surface_v1",
    *,
    independent_capture: bool = False,
) -> FinalDecision:
    profile = PROFILES[profile_name]

    # Responsible-AI guard for water_turbidity_v1: if no reference pattern was
    # detected on either pass, return NO_PATTERN_DETECTED instead of guessing.
    if profile_name == "water_turbidity_v1":
        first_has_pattern = (
            any(getattr(r, "pattern_found", False) for r in first_pass.regions)
            if first_pass.regions
            else False
        )
        second_has_pattern = (
            bool(getattr(second_pass_region, "pattern_found", False))
            if second_pass_region is not None
            else False
        )
        pattern_missing_first = (not first_has_pattern) or any(
            "pattern not detected" in g.lower() for g in first_pass.evidence_gap
        )
        if pattern_missing_first and not second_has_pattern:
            return FinalDecision(
                decision="NO_PATTERN_DETECTED",
                confidence_band="low",
                evidence_changed=second_pass_region is not None,
                human_approval_required=True,
                reasoning=[
                    "reference pattern not detected — ensure the printed checkerboard/grid is visible behind the water sample; no turbidity verdict possible on invalid input"
                ],
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
            reasoning=["first pass confidently detected a defect/contamination signal"],
        )

    if second_pass_region is None:
        return FinalDecision(
            decision="REVIEW",
            confidence_band="low",
            evidence_changed=False,
            human_approval_required=True,
            reasoning=["first pass uncertain, no second-pass evidence available"],
        )

    # 1. Water profile: second pass resolves via pattern_visibility
    if profile_name == "water_turbidity_v1":
        pv = getattr(second_pass_region, "pattern_visibility", 0.0) or 0.0
        metric_val = pv if pv > 0 else second_pass_region.edge_continuity
        if metric_val >= profile.pattern_visibility_confident_clear:
            if not independent_capture:
                return FinalDecision(
                    decision="REVIEW", confidence_band="low", evidence_changed=False,
                    human_approval_required=True,
                    reasoning=["same-image processing raised visibility; capture a new photo under different lighting before clearing the sample"],
                )
            return FinalDecision(
                decision="PASS",
                confidence_band="medium",
                evidence_changed=True,
                human_approval_required=False,
                reasoning=[
                    f"second-pass pattern visibility {metric_val:.2f} resolved toward clear water (no visible turbidity)"
                ],
            )
        if metric_val <= profile.pattern_visibility_confident_turbid:
            return FinalDecision(
                decision="FAIL",
                confidence_band="medium",
                evidence_changed=True,
                human_approval_required=True,
                reasoning=[
                    f"second-pass pattern visibility {metric_val:.2f} resolved toward turbid water (visible turbidity)"
                ],
            )
        return FinalDecision(
            decision="REVIEW",
            confidence_band="low",
            evidence_changed=True,
            human_approval_required=True,
            reasoning=[
                f"second-pass pattern visibility {metric_val:.2f} still in borderline band — genuine REVIEW, request different lighting or lab test"
            ],
        )

    # 2. Structural crack metrology profile: resolves via crack_severity_score and crack_width_px
    if profile_name == "structural_crack_metrology_v1":
        sev = getattr(second_pass_region, "crack_severity_score", 0.0) or 0.0
        width_px = getattr(second_pass_region, "crack_width_px", 0.0) or 0.0
        if sev >= profile.crack_severity_confident_fail or width_px >= profile.crack_width_px_fail:
            return FinalDecision(
                decision="FAIL",
                confidence_band="medium",
                evidence_changed=True,
                human_approval_required=True,
                reasoning=[
                    f"second-pass image screening detected a crack-like feature (width={width_px:.2f}px, severity={sev:.2f})"
                ],
            )
        if sev <= profile.crack_severity_confident_pass and width_px < 1.5:
            return FinalDecision(
                decision="PASS",
                confidence_band="medium",
                evidence_changed=True,
                human_approval_required=False,
                reasoning=[
                    f"second-pass illumination-normalized metrology cleared shadow/surface artifact (width={width_px:.2f}px, severity={sev:.2f})"
                ],
            )
        return FinalDecision(
            decision="REVIEW",
            confidence_band="low",
            evidence_changed=True,
            human_approval_required=True,
            reasoning=[
                f"second-pass line feature (width={width_px:.2f}px, severity={sev:.2f}) remains in borderline image-score band"
            ],
        )

    # 3. FDM and generic profiles: edge continuity
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

    return FinalDecision(
        decision="REVIEW",
        confidence_band="low",
        evidence_changed=True,
        human_approval_required=True,
        reasoning=[f"second-pass edge continuity {ec:.2f} still in the ambiguous band — genuine REVIEW case"],
    )
