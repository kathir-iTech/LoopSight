"""Evaluate relative image screening on declared, grouped capture manifests.

All strategies use the same vision policy. They differ only in allocation of
additional image inputs. No transformed image is counted as a new capture.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np

from capture_sessions import CaptureSessionError, frame_digest, validate_capture_pair
from cv.first_pass import PROFILES, run_first_pass
from cv.policy import decide

PROFILE = "water_turbidity_v1"


@dataclass
class Sample:
    sample_id: str
    group_id: str
    source_kind: str
    expected: str
    first: np.ndarray
    second: np.ndarray | None


def load_manifest(path: Path, split: str) -> list[Sample]:
    document = json.loads(path.read_text())
    if document.get("schema_version") != 1 or document.get("label_scope") != "relative_image_screening":
        raise ValueError("expected schema_version=1 and label_scope=relative_image_screening")
    root = path.resolve().parent
    groups, hashes, identifiers = {}, {}, set()
    samples = []
    for row in document["samples"]:
        sample_id, group = row["id"], row["group_id"]
        if not isinstance(sample_id, str) or not sample_id.strip() or sample_id in identifiers:
            raise ValueError("sample IDs must be unique, nonempty strings")
        identifiers.add(sample_id)
        if not isinstance(group, str) or not group.strip():
            raise ValueError("each sample requires a nonempty preparation/session group_id")
        if row["split"] not in {"calibration", "validation", "test"}:
            raise ValueError("unsupported split")
        if group in groups and groups[group] != row["split"]:
            raise ValueError(f"group leakage across splits: {group}")
        groups[group] = row["split"]
        if row["source_kind"] not in {"synthetic", "physical"} or row["expected_outcome"] not in {"PASS", "FAIL"}:
            raise ValueError("source kind or binary screening label is invalid")
        images = []
        for field in ["primary_image", "secondary_image"]:
            relative = row.get(field)
            if relative is None and field == "secondary_image":
                images.append(None)
                continue
            image_path = (root / relative).resolve()
            if not image_path.is_relative_to(root):
                raise ValueError("image paths must stay inside the manifest directory")
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"could not decode {field} for {sample_id}")
            if min(image.shape[:2]) < 64 or max(image.shape[:2]) > 2048:
                raise ValueError("evaluation images must be 64..2048 pixels per side")
            digest = frame_digest(image)
            if digest in hashes and hashes[digest] != row["split"]:
                raise ValueError(f"image leakage across splits: {sample_id}")
            hashes[digest] = row["split"]
            images.append(image)
        if row["split"] == split:
            samples.append(Sample(sample_id, group, row["source_kind"], row["expected_outcome"], *images))
    if not samples:
        raise ValueError("the selected split has no samples; zero-case evaluation is invalid")
    return samples


def first_pass(sample: Sample):
    h, w = sample.first.shape[:2]
    return run_first_pass(sample.first, None, [(0, 0, w, h)], profile_name=PROFILE)


def acquisition_plans(samples: list[Sample], first_passes: list, seed: int):
    eligible = {index for index, sample in enumerate(samples) if sample.second is not None}
    adaptive = {index for index in eligible if first_passes[index].status == "UNCERTAIN"}
    # Select exactly the adaptive budget over all eligible cases using full image
    # hashes and stable IDs. Do not gate the control a second time on uncertainty.
    ranked = sorted(eligible, key=lambda index: hashlib.sha256(
        f"{seed}:{samples[index].sample_id}:{frame_digest(samples[index].first)}".encode()
    ).digest())
    return {"single": set(), "fixed_capture": eligible,
            "matched_capture": set(ranked[:len(adaptive)]), "adaptive_capture": adaptive}


def evaluate(samples: list[Sample], seed: int = 2026) -> dict:
    started = time.perf_counter()
    passes = [first_pass(sample) for sample in samples]
    plans = acquisition_plans(samples, passes, seed)
    assert len(plans["matched_capture"]) == len(plans["adaptive_capture"])
    strategy_results = {}
    for name, acquisitions in plans.items():
        cases = []
        for index, (sample, first) in enumerate(zip(samples, passes)):
            initial = decide(first, None, profile_name=PROFILE)
            final = initial
            used = False
            rejection = None
            if index in acquisitions:
                try:
                    aligned, _ = validate_capture_pair(sample.first, sample.second)
                    h, w = aligned.shape[:2]
                    quality = run_first_pass(aligned, None, [(0, 0, w, h)], profile_name=PROFILE)
                    used = first.status == "UNCERTAIN"
                    if used and quality.status != "UNCERTAIN":
                        final = decide(first, quality.regions[0], profile_name=PROFILE, independent_capture=True)
                except CaptureSessionError as error:
                    rejection = str(error)
            cases.append({"id": sample.sample_id, "group_id": sample.group_id, "source_kind": sample.source_kind,
                          "expected": sample.expected, "decision": final.decision,
                          "additional_input_requested": index in acquisitions, "new_capture_used": used,
                          "pair_rejection": rejection, "first_frame_sha256": frame_digest(sample.first),
                          "second_frame_sha256": frame_digest(sample.second) if sample.second is not None else None})
        decided = [case for case in cases if case["decision"] in {"PASS", "FAIL"}]
        negatives = [case for case in cases if case["expected"] == "FAIL"]
        correct = sum(case["decision"] == case["expected"] for case in cases)
        strategy_results[name] = {
            "samples": len(cases), "correct": correct,
            "accuracy_including_abstentions": correct / len(cases),
            "coverage": len(decided) / len(cases),
            "selective_accuracy": sum(case["decision"] == case["expected"] for case in decided) / len(decided) if decided else None,
            "false_clear_rate": sum(case["decision"] == "PASS" for case in negatives) / len(negatives) if negatives else None,
            "additional_inputs_requested": len(acquisitions),
            "observations_received": len(cases) + len(acquisitions),
            "valid_new_captures_used": sum(case["new_capture_used"] for case in cases),
            "rejected_pairs": sum(case["pair_rejection"] is not None for case in cases),
            "cases": cases,
        }
    return {
        "schema_version": 1, "profile": PROFILE, "seed": seed,
        "runtime": {"opencv": cv2.__version__, "numpy": np.__version__, "python": platform.python_version()},
        "policy_thresholds": asdict(PROFILES[PROFILE]),
        "source_sha256": {
            name: hashlib.sha256((Path(__file__).resolve().parents[1] / name).read_bytes()).hexdigest()
            for name in ["scripts/evaluate_captures.py", "cv/first_pass.py", "cv/policy.py", "capture_sessions.py"]
        },
        "evidence_scope": "synthetic_regression_only" if any(s.source_kind == "synthetic" for s in samples) else "declared_physical_captures",
        "groups": len({sample.group_id for sample in samples}),
        "budget_unit": "additional_capture_inputs_requested; not compute time, cost, or verified acquisition authenticity",
        "matched_budget_verified": True,
        "physical_calibration_validated": False,
        "confidence_intervals": None,
        "limitations": ["Capture provenance and labels are declarations, not independently certified ground truth.",
                        "No statistical significance or field accuracy is established by this report.",
                        "Missing second images cannot be simulated and are unavailable to every strategy.",
                        "All strategies use the same image policy; this tests capture allocation, not LLM superiority."],
        "evaluation_wall_seconds": round(time.perf_counter() - started, 3),
        "results": strategy_results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--split", choices=["calibration", "validation", "test"], default="test")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(load_manifest(args.manifest, args.split), args.seed)
    report["manifest_sha256"] = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    report["split"] = args.split
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2) + "\n")
    for name, result in report["results"].items():
        print(f"{name}: accuracy={result['accuracy_including_abstentions']:.3f} coverage={result['coverage']:.3f} additional_inputs={result['additional_inputs_requested']}")
    print("Exact requested-input budgets verified; scope:", report["evidence_scope"])


if __name__ == "__main__":
    main()
