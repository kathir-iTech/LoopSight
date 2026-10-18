"""Check evaluation budgets, independent inputs and leakage boundaries."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import cv2
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sample_frames import make_backlit_recovery_pair
from scripts.evaluate_captures import Sample, acquisition_plans, evaluate, load_manifest


def test_matched_budget_is_exact_and_reorder_stable():
    first, second = make_backlit_recovery_pair()
    samples = [Sample(str(i), str(i), "synthetic", "PASS", first, second) for i in range(12)]
    passes = [SimpleNamespace(status="UNCERTAIN" if i < 4 else "CONFIDENT_PASS") for i in range(12)]
    plans = acquisition_plans(samples, passes, seed=2026)
    assert len(plans["matched_capture"]) == len(plans["adaptive_capture"]) == 4
    assert len(plans["fixed_capture"]) == 12
    # The control can spend its budget on confident cases, unlike adaptive.
    assert plans["matched_capture"] != plans["adaptive_capture"]
    reverse = acquisition_plans(samples[::-1], passes[::-1], seed=2026)
    assert {samples[i].sample_id for i in plans["matched_capture"]} == {
        samples[::-1][i].sample_id for i in reverse["matched_capture"]}


def test_actual_pair_can_resolve_uncertainty_but_missing_image_cannot():
    first, second = make_backlit_recovery_pair()
    samples = [Sample("paired", "one", "synthetic", "PASS", first, second),
               Sample("unpaired", "two", "synthetic", "PASS", first, None)]
    report = evaluate(samples)
    assert report["evidence_scope"] == "synthetic_regression_only"
    assert report["physical_calibration_validated"] is False
    assert report["confidence_intervals"] is None
    assert report["results"]["single"]["correct"] == 0
    adaptive = report["results"]["adaptive_capture"]
    assert adaptive["correct"] == 1
    assert adaptive["additional_inputs_requested"] == 1
    assert adaptive["cases"][1]["decision"] == "REVIEW"
    assert adaptive["cases"][1]["second_frame_sha256"] is None


def test_rejected_pair_still_costs_an_input_without_creating_a_verdict():
    first, _ = make_backlit_recovery_pair()
    report = evaluate([Sample("duplicate", "one", "synthetic", "PASS", first, first.copy())])
    adaptive = report["results"]["adaptive_capture"]
    assert adaptive["additional_inputs_requested"] == adaptive["rejected_pairs"] == 1
    assert adaptive["valid_new_captures_used"] == 0
    assert adaptive["cases"][0]["decision"] == "REVIEW"


def write_manifest(directory, rows):
    first, second = make_backlit_recovery_pair()
    cv2.imwrite(str(directory / "first.png"), first)
    cv2.imwrite(str(directory / "second.png"), second)
    path = directory / "manifest.json"
    path.write_text(json.dumps({"schema_version": 1, "label_scope": "relative_image_screening", "samples": rows}))
    return path


def row(identifier="one", group="one", split="test", image="first.png"):
    return {"id": identifier, "group_id": group, "split": split, "source_kind": "synthetic",
            "expected_outcome": "PASS", "primary_image": image}


def test_loader_rejects_session_group_leakage(tmp_path):
    path = write_manifest(tmp_path, [row(), row("two", split="validation", image="second.png")])
    with pytest.raises(ValueError, match="group leakage"):
        load_manifest(path, "test")


def test_loader_rejects_image_leakage_even_with_different_groups(tmp_path):
    path = write_manifest(tmp_path, [row(), row("two", "two", "validation")])
    with pytest.raises(ValueError, match="image leakage"):
        load_manifest(path, "test")


def test_loader_rejects_path_escape_and_empty_selected_split(tmp_path):
    path = write_manifest(tmp_path, [row(image="../outside.png")])
    with pytest.raises(ValueError, match="stay inside"):
        load_manifest(path, "test")
    path = write_manifest(tmp_path, [row(split="calibration")])
    with pytest.raises(ValueError, match="no samples"):
        load_manifest(path, "test")


def test_loader_validates_duplicate_identifiers_and_physical_declarations(tmp_path):
    path = write_manifest(tmp_path, [row(), row()])
    with pytest.raises(ValueError, match="unique"):
        load_manifest(path, "test")
    declared = row()
    declared["source_kind"] = "physical"
    path = write_manifest(tmp_path, [declared])
    report = evaluate(load_manifest(path, "test"))
    assert report["evidence_scope"] == "declared_physical_captures"
    assert report["physical_calibration_validated"] is False
