"""
LoopSight — full evaluation harness.

Implements Experiments A, B, B2, and C from spec Section 14's evaluation
plan, following the same pattern as calibrate_thresholds.py: tooling first,
data later. This runs TODAY against synthetic fixtures (the same
tests/synthetic.py generators the test suite uses), clearly labeled as a
DRY RUN, so the moment real labeled photos exist, this is ONE command, not
a rebuild.

Experiments:
  A  — single-pass baseline accuracy. First pass only; UNCERTAIN is left
       unresolved (a REVIEW guess). No second look, no adaptive loop.
  B  — fixed two-pass. Every UNCERTAIN gets the same fixed reinspect_roi
       (scale=2.0), regardless of what's actually ambiguous.
  B2 — matched observation budget. Always-repeat baseline, but only spends
       the SAME AVERAGE number of observations LoopSight (Experiment C)
       actually used — the fair fight: same total sensing cost, different
       policy for spending it.
  C  — adaptive (LoopSight's actual mechanic). Agent-selected second pass
       based on the specific evidence gap (via the same mock fixture the
       live path uses in main.py).

Output metrics (all cheap to compare across experiments):
  accuracy        — fraction of verdicts that match ground truth
  trigger_rate    — fraction of cases that took a second look
  resolution_rate — of trigger cases, fraction where the 2nd look CHANGED
                    the verdict vs. what a 1st-look-only decision gave
  false_trigger   — of PASS/FAIL-correct cases (confident ones), fraction
                    that unnecessarily fired the second look
  missed_trigger  — of cases that SHOULD have triggered a 2nd look
                    (genuinely ambiguous / borderline) but didn't

The number the spec flags as the one that settles the mechanism question:
  conditional_benefit =
      P(correct | 2nd look, was UNCERTAIN) − P(correct | 1st look only, was UNCERTAIN)

Dry-run dataset (synthetic, labeled):
  clean      -> correct verdict PASS   (first pass should be confident)
  broken     -> correct verdict FAIL   (first pass should be confident)
  borderline -> correct verdict REVIEW (a human would also hesitate)
  low_contrast -> correct verdict REVIEW (system must say UNCERTAIN, not guess)

Usage:
    python scripts/run_experiments.py            # dry-run on synthetic
    python scripts/run_experiments.py /path/to/labeled_dirs   # real data
    python -m scripts.run_experiments
    python -m pytest tests/test_run_experiments.py -v -s     # prove it runs
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

from cv.first_pass import run_first_pass, PROFILES, FirstPassResult
from cv.tools import TOOL_REGISTRY
from cv.policy import decide, FinalDecision
from agent.tool_selector import select_tool

GT_PASS = "PASS"
GT_FAIL = "FAIL"
GT_REVIEW = "REVIEW"

# Verdicts that count as "correct" for each ground-truth label.
# Phase 4 fix: borderline must require REVIEW specifically — accepting any verdict artificial zeroes conditional_benefit (audit §4).
CORRECT_VERDICTS: Dict[str, set] = {
    "clean": {GT_PASS},
    "broken": {GT_FAIL},
    # fdm borderline / water borderline: genuinely ambiguous must be REVIEW
    "borderline": {GT_REVIEW},
    "low_contrast": {GT_REVIEW},
    # water profile labels
    "clear": {GT_PASS},
    "turbid": {GT_FAIL},
}

_FULL_ROI = (0, 0, 200, 200)


# ---------------------------------------------------------------------------
# Synthetic fixture dataset (dry-run)
# ---------------------------------------------------------------------------
def _load_synthetic_dataset(profile: str = "water_turbidity_v1") -> List[Tuple[str, np.ndarray]]:
    """Build a labeled synthetic set: (label, frame). Stand-in for the real
    self-captured set until it exists (spec Section 13). Supports both profiles."""
    if profile == "water_turbidity_v1":
        from tests.synthetic import make_checkerboard, make_turbid_water, make_clear_water, make_borderline_water
        # Water: Secchi-disk checkerboard through clear vs turbid vs borderline
        samples: List[Tuple[str, Callable[[], np.ndarray]]] = [
            ("clear", make_clear_water),
            ("clear", lambda: make_checkerboard(squares=8)),
            ("turbid", lambda: make_turbid_water(make_checkerboard(), blur_ks=11, alpha=0.6, beta=20)),
            ("turbid", lambda: make_turbid_water(make_checkerboard(), blur_ks=13, alpha=0.55, beta=25)),
            ("borderline", make_borderline_water),
            ("borderline", lambda: make_turbid_water(make_checkerboard(), blur_ks=7, alpha=0.80, beta=10)),
            ("borderline", lambda: make_turbid_water(make_checkerboard(), blur_ks=9, alpha=0.70, beta=15)),
            ("clear", make_clear_water),
        ]
        return [(label, gen()) for label, gen in samples]

    from tests.synthetic import make_clean_square, make_broken_square, make_low_contrast_frame

    def make_borderline() -> np.ndarray:
        img = make_clean_square()
        faded = img.copy()
        faded[35:45, :, :] = cv2.addWeighted(
            faded[35:45, :, :], 0.15,
            np.full_like(faded[35:45, :, :], 40), 0.85, 0,
        )
        return faded

    samples = [
        ("clean", make_clean_square),
        ("clean", make_clean_square),
        ("broken", lambda: make_broken_square(gap=20)),
        ("broken", lambda: make_broken_square(gap=25)),
        ("borderline", make_borderline),
        ("borderline", make_borderline),
        ("low_contrast", make_low_contrast_frame),
        ("low_contrast", make_low_contrast_frame),
    ]
    return [(label, gen()) for label, gen in samples]


def _load_real_dataset(dataset_root: Path) -> List[Tuple[str, np.ndarray]]:
    """Load a labeled real dataset from folders: <root>/<label>/*.png|jpg..."""
    if not dataset_root.is_dir():
        raise FileNotFoundError(f"dataset root not found: {dataset_root}")
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    out: List[Tuple[str, np.ndarray]] = []
    for label_dir in sorted(dataset_root.iterdir()):
        if not label_dir.is_dir():
            continue
        label = label_dir.name
        if label not in CORRECT_VERDICTS:
            continue
        for f in sorted(label_dir.iterdir()):
            if f.suffix.lower() in exts and f.is_file():
                img = cv2.imread(str(f), cv2.IMREAD_COLOR)
                if img is not None and img.shape[0] and img.shape[1]:
                    out.append((label, img))
    if not out:
        raise ValueError(f"no supported labeled images found under {dataset_root}")
    return out


# ---------------------------------------------------------------------------
# Policy / loop implementations per experiment
# ---------------------------------------------------------------------------
def _mock_fixture_for(first_pass: FirstPassResult) -> dict:
    """Same mock-fixture selection the live /inspect path uses in main.py,
    so Experiment C exercises the real adaptive wiring, not a test-only one."""
    from main import _fixture_for_first_pass  # type: ignore

    return _fixture_for_first_pass(first_pass)


def _decide_from_first_pass(first_pass: FirstPassResult, profile: str) -> FinalDecision:
    return decide(first_pass, None, profile_name=profile)


def run_experiment_a(first_pass: FirstPassResult, profile: str, frame: np.ndarray = None, reference=None) -> Tuple[dict, FinalDecision, bool]:
    """A — single-pass baseline. UncertaIN left as a REVIEW guess."""
    _ = frame, reference
    final = _decide_from_first_pass(first_pass, profile)
    # No second look ever
    return {"triggered": False, "tool": None}, final, False


def run_experiment_b(first_pass: FirstPassResult, profile: str, frame: np.ndarray, reference=None) -> Tuple[dict, FinalDecision, bool]:
    """B — fixed two-pass. Every UNCERTAIN gets reinspect_roi(scale=2.0)."""
    if first_pass.status != "UNCERTAIN":
        final = decide(first_pass, None, profile_name=profile)
        return {"triggered": False, "tool": None}, final, False

    fn = TOOL_REGISTRY["reinspect_roi"]
    result = fn(frame, reference, _FULL_ROI, scale=2.0)
    final = decide(first_pass, result.region, profile_name=profile)
    return {"triggered": True, "tool": "reinspect_roi", "edge_continuity": result.region.edge_continuity}, final, True


def run_experiment_b2(
    first_pass: FirstPassResult,
    profile: str,
    frame: np.ndarray,
    seed: int = 0,
    adaptive_trigger_rate: float = 0.5,
    reference=None,
) -> Tuple[dict, FinalDecision, bool]:
    """B2 — matched observation budget. Spends the same AVERAGE number of
    observations LoopSight (Experiment C) did, by only repeating on a matched
    fraction of cases. The fair fight: same total sensing cost, different
    policy for spending it."""
    if first_pass.status != "UNCERTAIN":
        final = decide(first_pass, None, profile_name=profile)
        return {"triggered": False, "tool": None}, final, False

    # Deterministically decide whether THIS case gets the (always-fixed) repeat,
    # proportionally to Experiment C's real trigger rate. Seeded by the image
    # content + rate so the matched fraction is stable across runs and per-case.
    probe = int(frame.tobytes().hex(), 16) if frame.size else 0
    budget_used = ((probe ^ round(adaptive_trigger_rate * 10**6)) % 1000) < (adaptive_trigger_rate * 1000)
    if first_pass.status == "UNCERTAIN" and budget_used:
        fn = TOOL_REGISTRY["reinspect_roi"]
        result = fn(frame, reference, _FULL_ROI, scale=2.0)
        final = decide(first_pass, result.region, profile_name=profile)
        return (
            {"triggered": True, "tool": "reinspect_roi", "edge_continuity": result.region.edge_continuity},
            final, True,
        )
    # Matched budget: this case DOESN'T get a repeat (burns its share of the
    # average elsewhere / is the fraction the budget doesn't cover).
    final = decide(first_pass, None, profile_name=profile)
    return {"triggered": False, "tool": None}, final, False


def run_experiment_c(
    first_pass: FirstPassResult,
    profile: str,
    frame: np.ndarray,
    reference=None,
) -> Tuple[dict, FinalDecision, bool]:
    """C — adaptive (LoopSight's actual mechanic). Agent-selected second pass
    based on the specific evidence gap, exactly as /inspect does.
    Phase 4: now wires track_across_frames for real — simulates second lighting
    by creating a lightly different exposure of the same frame and calling
    track_across_frames([frame, frame2])."""
    if first_pass.status != "UNCERTAIN":
        final = decide(first_pass, None, profile_name=profile)
        return {"triggered": False, "tool": None}, final, False

    fixture = _mock_fixture_for(first_pass)
    tool_call = select_tool(first_pass, mock_fixture=fixture)
    fn = TOOL_REGISTRY[tool_call.tool]
    if tool_call.tool == "reinspect_roi":
        result = fn(frame, reference, _FULL_ROI, scale=float(tool_call.arguments.get("scale", 2.0)))
    elif tool_call.tool == "measure_edge_continuity":
        result = fn(frame, _FULL_ROI, low=int(tool_call.arguments.get("low", 30)), high=int(tool_call.arguments.get("high", 100)))
    elif tool_call.tool == "compare_to_reference":
        result = fn(frame, reference if reference is not None else frame, _FULL_ROI)
    elif tool_call.tool == "track_across_frames":
        # Simulate second lighting: slightly different exposure/blur of same frame
        # This exercises the real track_across_frames path (pattern_visibility persistence)
        try:
            frame2 = cv2.convertScaleAbs(frame, alpha=0.95, beta=5)
            frame2 = cv2.GaussianBlur(frame2, (3, 3), 0)
        except Exception:
            frame2 = frame.copy() if hasattr(frame, "copy") else frame
        result = fn([frame, frame2], _FULL_ROI)
    else:
        raise NotImplementedError(f"exp C not wired for {tool_call.tool}")
    final = decide(first_pass, result.region, profile_name=profile)
    # Return whichever metric is relevant for the profile
    pv = getattr(result.region, "pattern_visibility", 0.0) or 0.0
    metric = float(pv) if profile == "water_turbidity_v1" and pv else float(result.region.edge_continuity)
    return {"triggered": True, "tool": tool_call.tool, "edge_continuity": float(result.region.edge_continuity), "pattern_visibility": float(pv), "metric": metric}, final, True


# ---------------------------------------------------------------------------
# Evaluation: run an experiment over the dataset, collect metrics
# ---------------------------------------------------------------------------
def _correct(ground_truth: str, decision: str) -> bool:
    return decision in CORRECT_VERDICTS[ground_truth]


def evaluate_experiment(
    experiment_run: Callable,
    dataset: List[Tuple[str, np.ndarray]],
    profile: str,
    extra_kwargs: Optional[dict] = None,
) -> Dict[str, float]:
    """Run one experiment policy over the labeled dataset and compute its
    metrics. `experiment_run` is the per-first-pass loop for that experiment;
    `extra_kwargs` lets callers pass common params (e.g. adaptive_trigger_rate
    for B2)."""
    extra_kwargs = extra_kwargs or {}
    n = len(dataset)
    correct = 0
    triggered = 0
    resolved = 0
    false_trigger = 0
    missed_trigger = 0
    # For conditional_benefit, we need, across UNCERTAIN cases, the correct
    # verdict under a 1st-look-only decision vs. under a 2nd-look decision.
    uncertain_1look_correct = 0
    uncertain_2look_correct = 0
    uncertain_count = 0

    for label, frame in dataset:
        first_pass = run_first_pass(frame, None, [_FULL_ROI], profile_name=profile)
        _, final, did_trigger = experiment_run(first_pass, profile, frame, **extra_kwargs)
        verdict = final.decision
        this_correct = _correct(label, verdict)
        if this_correct:
            correct += 1

        if did_trigger:
            triggered += 1
            # For triggered cases, compare the verdict vs. what a
            # 1st-look-only decision would have given: did the 2nd look change it?
            one_look = _decide_from_first_pass(first_pass, profile).decision
            if verdict != one_look:
                resolved += 1
                # false_trigger: the 2nd look fired on a case that was already
                # correct on the first pass (a confident clean/fail that
                # shouldn't have taken a second look at all). Only count when
                # the first-pass decision was already correct AND confident.
                if _correct(label, one_look) and first_pass.status != "UNCERTAIN":
                    false_trigger += 1
            # conditional_benefit accumulation over UNCERTAIN cases
            if first_pass.status == "UNCERTAIN":
                uncertain_count += 1
                if _correct(label, _decide_from_first_pass(first_pass, profile).decision):
                    uncertain_1look_correct += 1
                if verdict in CORRECT_VERDICTS[label]:
                    uncertain_2look_correct += 1
        else:
            # Not triggered. Was this a case that SHOULD have (genuinely
            # ambiguous / borderline first pass)? Missed/doesn't-reach-agent.
            if first_pass.status == "UNCERTAIN":
                missed_trigger += 1
            if first_pass.status == "UNCERTAIN":
                uncertain_count += 1
                if _correct(label, _decide_from_first_pass(first_pass, profile).decision):
                    uncertain_1look_correct += 1
                if verdict in CORRECT_VERDICTS[label]:
                    uncertain_2look_correct += 1

    metrics = {
        "accuracy": round(correct / n, 4) if n else 0.0,
        "trigger_rate": round(triggered / n, 4) if n else 0.0,
        "resolution_rate": round(resolved / triggered, 4) if triggered else 0.0,
        "false_trigger": round(false_trigger / triggered, 4) if triggered else 0.0,
        "missed_trigger": round(missed_trigger / n, 4) if n else 0.0,
        "conditional_benefit": round(
            (uncertain_2look_correct / uncertain_count if uncertain_count else 0.0)
            - (uncertain_1look_correct / uncertain_count if uncertain_count else 0.0),
            4,
        ),
    }
    return metrics


# ---------------------------------------------------------------------------
# Runner / report
# ---------------------------------------------------------------------------
def run_all(dataset: List[Tuple[str, np.ndarray]], profile: str = "water_turbidity_v1") -> Dict[str, Dict[str, float]]:
    """Run all four experiments and return {name: metrics}."""
    c_metrics = evaluate_experiment(run_experiment_c, dataset, profile)
    b2_kwargs = {"adaptive_trigger_rate": c_metrics["trigger_rate"]}
    return {
        "A": evaluate_experiment(run_experiment_a, dataset, profile),
        "B": evaluate_experiment(run_experiment_b, dataset, profile),
        "B2": evaluate_experiment(run_experiment_b2, dataset, profile, extra_kwargs=b2_kwargs),
        "C": c_metrics,
    }


def print_report(results: Dict[str, Dict[str, float]]) -> None:
    print("\n" + "=" * 88)
    print("LoopSight evaluation harness — Experiment A/B/B2/C")
    print("=" * 88)
    print("DRY RUN against synthetic fixtures (not real photos). Once real")
    print("label-backed images land in data/, this is one command, not a rebuild.")
    print("-" * 88)

    metrics_order = [
        "accuracy", "trigger_rate", "resolution_rate",
        "false_trigger", "missed_trigger", "conditional_benefit",
    ]
    header = f"{'exp':<4} " + " ".join(f"{m:>18}" for m in metrics_order)
    print(header)
    print("-" * 88)
    for name in ["A", "B", "B2", "C"]:
        m = results[name]
        row = f"{name:<4} "
        row += " ".join(f"{m.get(k, 0.0):>18.4f}" for k in metrics_order)
        print(row)
    print("-" * 88)

    print("\nThe number that settles whether adaptive is worth its complexity:")
    print(f"  conditional_benefit = P(correct|2nd look, was UNCERTAIN) - P(correct|1st look, was UNCERTAIN)")
    print(f"  Experiment C conditional_benefit = {results['C']['conditional_benefit']:.4f}")
    print(f"  Experiment B conditional_benefit  = {results['B']['conditional_benefit']:.4f}")
    if results["C"]["conditional_benefit"] < 0.001:
        print("  [clue] ~zero: adaptive isn't earning its complexity; the spec's")
        print("         fallback applies — use the best deterministic policy and")
        print("         pivot the pitch to technical execution + evidence trace.")
    else:
        print("  [info] positive: a genuinely ambiguous second look is changing")
        print("         verdicts more often than a first-look-only guess.")

    print("\nInterpretation notes:")
    print("  - Resolution_rate > 0 with positive conditional_benefit: the 2nd look")
    print("    changes verdicts and does so correctly — the loop earns its cost.")
    print("  - false_trigger is confidence cases that waste a second look;")
    print("    kept low by only triggering on UNCERTAIN (never on confident).")
    print("  - These numbers are SYNTHETIC. Re-run against real photos before")
    print("    trusting them for the submission's Innovation claim.")
    print("=" * 88 + "\n")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="LoopSight evaluation harness (Experiments A/B/B2/C). "
        "Default: dry run on synthetic fixtures. Pass a real labeled dir to "
        "evaluate against real photos.",
    )
    parser.add_argument(
        "dataset", nargs="?", default=None,
        help="optional path to labeled dataset (subfolders: clean/, broken/, borderlines/, low_contrast/)",
    )
    parser.add_argument("--profile", default="water_turbidity_v1", help="InspectionProfile name")
    args = parser.parse_args()

    if args.dataset:
        dataset = _load_real_dataset(Path(args.dataset))
        print("[info] evaluating real dataset from", args.dataset)
    else:
        dataset = _load_synthetic_dataset(profile=args.profile)
        print("[info] DRY RUN: evaluating synthetic fixtures (no real photos yet) — profile", args.profile)

    print(f"[info] {len(dataset)} labeled images, profile={args.profile}")
    results = run_all(dataset, profile=args.profile)
    print_report(results)


if __name__ == "__main__":
    main()