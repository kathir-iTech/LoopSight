import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cv.tools import reinspect_roi, compare_to_reference, measure_edge_continuity, track_across_frames
from tests.synthetic import make_clean_square, make_broken_square

FULL_ROI = (0, 0, 200, 200)


def test_reinspect_roi_returns_a_measurement_without_crashing():
    img = make_broken_square()
    result = reinspect_roi(img, None, FULL_ROI, scale=2.0)
    print(f"  reinspect_roi edge_continuity={result.region.edge_continuity:.4f} notes={result.notes}")
    assert result.tool == "reinspect_roi"
    assert result.region.edge_continuity >= 0.0


def test_reinspect_roi_upsampling_changes_the_pixel_count_measured():
    """Proves the 'materially different observation' requirement from spec
    Section 9's Revision 2 note isn't just a docstring claim — the
    upsampled region actually has more pixels than a naive re-crop would."""
    img = make_broken_square()
    x, y, w, h = FULL_ROI
    result = reinspect_roi(img, None, FULL_ROI, scale=2.0)
    original_pixels = w * h
    # region.w/h reflect the fake_roi built from the upsampled crop
    upsampled_pixels = result.region.w * result.region.h
    print(f"  original_pixels={original_pixels} upsampled_pixels={upsampled_pixels}")
    assert upsampled_pixels > original_pixels, "reinspect_roi must genuinely change the observation, not just relabel the same pixels"


def test_measure_edge_continuity_uses_different_thresholds_than_first_pass():
    img = make_broken_square()
    result = measure_edge_continuity(img, FULL_ROI, low=30, high=100)
    print(f"  measure_edge_continuity (30,100) edge_continuity={result.region.edge_continuity:.4f}")
    assert result.tool == "measure_edge_continuity"
    assert result.region.reference_similarity == -1.0, "this tool doesn't measure reference similarity — must be clearly marked, not defaulted to a misleading value"


def test_track_across_frames_low_persistence_std_for_identical_frames():
    """Two IDENTICAL frames should show near-zero persistence std — i.e.
    if the capture layer ever fed this function two stale duplicate
    frames, it would (correctly) look like a 'persistent, likely real'
    signal even though nothing new was observed. This test exists to make
    that exact silent-failure mode from spec Section 9's Revision 2 note
    visible and provable, not to claim this function alone fixes it —
    the fix has to be upstream frame-freshness enforcement."""
    img = make_broken_square()
    result = track_across_frames([img, img, img], FULL_ROI)
    print(f"  identical-frames track: {result.notes}")
    assert "persistence_std=0.000" in result.notes, "confirms: duplicate frames are indistinguishable from a genuinely persistent defect at this layer — freshness MUST be enforced before this function, not after"


def test_track_across_frames_requires_at_least_two_frames():
    img = make_clean_square()
    try:
        track_across_frames([img], FULL_ROI)
        assert False, "should have raised ValueError for a single frame"
    except ValueError as e:
        print(f"  correctly rejected single-frame call: {e}")


TESTS = [
    test_reinspect_roi_returns_a_measurement_without_crashing,
    test_reinspect_roi_upsampling_changes_the_pixel_count_measured,
    test_measure_edge_continuity_uses_different_thresholds_than_first_pass,
    test_track_across_frames_low_persistence_std_for_identical_frames,
    test_track_across_frames_requires_at_least_two_frames,
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
