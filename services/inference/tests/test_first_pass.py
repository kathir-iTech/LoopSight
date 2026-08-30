"""
Unit tests for cv/first_pass.py against synthetic fixtures.

Run with: python3 -m pytest tests/test_first_pass.py -v
(or: python3 tests/test_first_pass.py — has a __main__ runner too, since
pytest isn't guaranteed to be installed in every environment this repo
lands in).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cv.first_pass import measure_region, score_evidence, run_first_pass, PROFILES
from tests.synthetic import make_clean_square, make_broken_square, make_low_contrast_frame


PROFILE = PROFILES["fdm_print_surface_v1"]
FULL_ROI = (0, 0, 200, 200)


def test_clean_edge_has_high_edge_continuity():
    img = make_clean_square()
    region = measure_region(img, None, FULL_ROI)
    assert region.edge_continuity > 0.0, "a drawn square should register some edge signal"
    print(f"  clean square edge_continuity = {region.edge_continuity:.4f}")


def test_broken_edge_has_lower_edge_continuity_than_clean():
    clean = measure_region(make_clean_square(), None, FULL_ROI)
    broken = measure_region(make_broken_square(), None, FULL_ROI)
    print(f"  clean={clean.edge_continuity:.4f}  broken={broken.edge_continuity:.4f}")
    assert broken.edge_continuity < clean.edge_continuity, (
        "a square with deliberate gaps in its boundary must score lower "
        "edge continuity than a complete one — this is the core signal "
        "the whole first pass depends on"
    )


def test_low_contrast_frame_triggers_uncertain_via_contrast_gate():
    img = make_low_contrast_frame()
    result = run_first_pass(img, None, [FULL_ROI])
    print(f"  low-contrast frame status = {result.status}, evidence_gap = {result.evidence_gap}")
    assert result.status == "UNCERTAIN"
    assert "contrast" in result.evidence_gap[0]


def test_clean_square_scores_confident_pass_or_uncertain_but_never_confident_fail():
    img = make_clean_square()
    result = run_first_pass(img, None, [FULL_ROI])
    print(f"  clean square status = {result.status}")
    assert result.status != "CONFIDENT_FAIL", (
        "a genuinely clean synthetic edge must never be classified as a "
        "confident defect — a false positive here on the easiest possible "
        "case would mean the thresholds are miscalibrated"
    )


def test_broken_square_is_not_confident_pass():
    img = make_broken_square()
    result = run_first_pass(img, None, [FULL_ROI])
    print(f"  broken square status = {result.status}")
    assert result.status != "CONFIDENT_PASS", (
        "a square with real, deliberate gaps must not be waved through as "
        "a confident pass — this is the false-negative sanity check"
    )


def test_score_evidence_uncertain_case_lists_allowed_tools():
    img = make_low_contrast_frame()
    result = run_first_pass(img, None, [FULL_ROI])
    assert result.status == "UNCERTAIN"
    assert len(result.allowed_tools) > 0, "an UNCERTAIN result must always offer at least one next tool"


def test_reference_mismatch_triggers_uncertain_not_a_crash():
    """A reference frame of the wrong shape should be treated as evidence
    of misalignment (low similarity), never raise — this is exactly the
    kind of malformed-input case the demo needs to survive gracefully."""
    frame = make_clean_square(size=200)
    bad_reference = make_clean_square(size=100)  # deliberately wrong shape
    result = run_first_pass(frame, bad_reference, [FULL_ROI])
    print(f"  mismatched-reference status = {result.status}")
    assert result.status in ("UNCERTAIN",), "a shape-mismatched reference should read as low similarity, triggering UNCERTAIN, not crash or false-pass"


TESTS = [
    test_clean_edge_has_high_edge_continuity,
    test_broken_edge_has_lower_edge_continuity_than_clean,
    test_low_contrast_frame_triggers_uncertain_via_contrast_gate,
    test_clean_square_scores_confident_pass_or_uncertain_but_never_confident_fail,
    test_broken_square_is_not_confident_pass,
    test_score_evidence_uncertain_case_lists_allowed_tools,
    test_reference_mismatch_triggers_uncertain_not_a_crash,
]

if __name__ == "__main__":
    passed, failed = 0, 0
    for t in TESTS:
        try:
            print(f"RUN  {t.__name__}")
            t()
            print(f"PASS {t.__name__}\n")
            passed += 1
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}\n")
            failed += 1
    print(f"--- {passed} passed, {failed} failed out of {len(TESTS)} ---")
    sys.exit(1 if failed else 0)
