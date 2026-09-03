"""
LoopSight — golden-result demo fixtures.

Per spec Section 10's hard requirement: "Fallback if AWS is unreachable
mid-demo: a small set of pre-computed 'golden' results keyed to the exact
rehearsed demo objects, so a live AWS hiccup in front of judges never
fully breaks the demo — this is not optional polish, build it as a real
fallback path, not an afterthought."

These are static JSON-shaped InspectionResults (matching
apps/web/src/lib/types.ts exactly) covering the three cases a demo needs:

  1. confident_pass     — first pass is confident, agent never fires
  2. confident_fail     — first pass confidently flags a defect
  3. uncertain          — genuinely ambiguous, agent fires + second look runs

When DEMO_MODE=golden is set, /inspect serves these instead of calling
the live pipeline, so a demo never depends on a live API call (Gemini or
the CV runtime) working in front of judges.

The uncertain fixture is the golden "rehearse the genuinely ambiguous
case, not just the clean ones" object: it has status=UNCERTAIN, an
agent_call, and a second_pass that the policy resolves to REVIEW (human
approval required) — proving the adaptive loop is real, not a canned
pass/fail.
"""

import json
import os
from typing import Dict

# The pre-computed golden results. Values are at rest, treated as the
# recorded ground truth for the corresponding rehearsed demo object.
# Note: these are DEMO fixtures, not real measurements. They're shaped to
# exercise every UI branch (pass/fail/review + agent evidence trace).
GOLDEN_RESULTS: Dict[str, dict] = {
    "confident_pass": {
        "status": "CONFIDENT_PASS",
        "regions": [
            {
                "x": 0,
                "y": 0,
                "w": 200,
                "h": 200,
                "evidence": {
                    "edge_continuity": 0.97,
                    "reference_similarity": 1.0,
                    "layer_alignment_deviation": 0.02,
                },
            }
        ],
        "evidence_gap": [],
        "final_decision": {
            "decision": "PASS",
            "confidence_band": "high",
            "human_approval_required": False,
        },
        "measurements": {
            "decode_ms": 2.1,
            "first_pass_ms": 5.4,
            "agent_ms": None,
            "second_pass_ms": None,
            "total_ms": 7.8,
        },
    },
    "confident_fail": {
        "status": "CONFIDENT_FAIL",
        "regions": [
            {
                "x": 0,
                "y": 0,
                "w": 200,
                "h": 200,
                "evidence": {
                    "edge_continuity": 0.08,
                    "reference_similarity": 0.47,
                    "layer_alignment_deviation": 0.61,
                },
            }
        ],
        "evidence_gap": [],
        "final_decision": {
            "decision": "FAIL",
            "confidence_band": "high",
            "human_approval_required": True,
        },
        "measurements": {
            "decode_ms": 1.9,
            "first_pass_ms": 4.8,
            "agent_ms": None,
            "second_pass_ms": None,
            "total_ms": 7.1,
        },
    },
    "uncertain": {
        "status": "UNCERTAIN",
        "regions": [
            {
                "x": 0,
                "y": 0,
                "w": 200,
                "h": 200,
                "evidence": {
                    "edge_continuity": 0.52,
                    "reference_similarity": 0.73,
                    "layer_alignment_deviation": 0.31,
                },
            }
        ],
        "evidence_gap": [
            "edge continuity 0.52 in ambiguous middle band (0.35-0.85)",
        ],
        "agent_call": {
            "tool": "measure_edge_continuity",
            "reason_code": "AMBIGUOUS_EDGE_BAND",
        },
        "second_pass": {
            "regions": [
                {
                    "edge_continuity": 0.58,
                    "reference_similarity": 0.74,
                    "layer_alignment_deviation": 0.29,
                    "local_contrast": 0.42,
                }
            ]
        },
        "final_decision": {
            "decision": "REVIEW",
            "confidence_band": "low",
            "human_approval_required": True,
        },
        "measurements": {
            "decode_ms": 1.7,
            "first_pass_ms": 5.1,
            "agent_ms": 0.4,
            "second_pass_ms": 4.2,
            "total_ms": 11.2,
        },
    },
}

# Alias for the forced-ambiguity demo path.
FORCED_AMBIGUOUS_FIXTURE_KEY = "uncertain"

# Text sentinel used by the frontend to pick a golden case by name.
GOLDEN_KEYS = sorted(GOLDEN_RESULTS.keys())


def load_golden(key: str) -> dict:
    """Return a deep copy of the golden result for `key` (or the uncertain
    fixture if `key` is unknown, so the demo never errors on a bad param)."""
    import copy

    k = key if key in GOLDEN_RESULTS else FORCED_AMBIGUOUS_FIXTURE_KEY
    return copy.deepcopy(GOLDEN_RESULTS[k])


def golden_mode_enabled() -> bool:
    """True when the demo should bypass live inference and serve goldens."""
    return os.environ.get("DEMO_MODE", "").strip().lower() == "golden"


def resolve_golden_from_request(form: dict) -> dict | None:
    """
    Decide which golden fixture (if any) a request should get, based on
    DEMO_MODE=golden plus an optional `demo_case` field.

    Returns None if demo mode is not active (caller should run the real
    pipeline). `demo_case` may be "confident_pass", "confident_fail",
    "uncertain", or "auto" (pick by uploaded filename/content).
    """
    if not golden_mode_enabled():
        return None

    case = str(form.get("demo_case") or form.get("inspection_profile") or "").strip()
    if case in GOLDEN_RESULTS:
        return load_golden(case)

    # Auto: let the rustler pick a case based on the demo_case value. For
    # the standalone forced-ambiguity path, `demo_case=uncertain` (or the
    # unknown case default) lands on the ambiguous fixture.
    if case:
        return load_golden(case)
    return load_golden(FORCED_AMBIGUOUS_FIXTURE_KEY)