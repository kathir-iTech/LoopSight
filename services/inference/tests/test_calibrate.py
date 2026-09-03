"""
Test for scripts/calibrate_thresholds.py against synthetic fixtures.

This proves the calibration tooling is working code TODAY, even though the
real dataset doesn't exist yet. It organizes synthetic images into temp
folders by label and runs the calibrate + suggest pipeline end-to-end.

Run with: python tests/test_calibrate.py  or  pytest tests/test_calibrate.py -v -s
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
import pathlib
import cv2

from tests.synthetic import make_clean_square, make_broken_square
from scripts.calibrate_thresholds import calibrate, compute_table, suggest_thresholds, print_report


def test_calibrate_runs_on_synthetic_fixtures():
    """Organize synthetic fixtures into temp folders per label and prove
    calibrate_thresholds.py runs end-to-end without crashing and produces
    data-driven suggestions."""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)

        def write_images(folder: str, gen_fn, count: int = 3):
            p = root / folder
            p.mkdir(parents=True, exist_ok=True)
            for i in range(count):
                img = gen_fn()
                ok = cv2.imwrite(str(p / f"{i}.png"), img)
                assert ok, f"failed to write {p / f'{i}.png'}"

        # Use all expected labels from the spec
        write_images("clean", lambda: make_clean_square())
        write_images("layer_shift", lambda: make_broken_square(gap=20))
        write_images("stringing", lambda: make_broken_square(gap=15))
        write_images("warping", lambda: make_broken_square(gap=30))
        write_images("under_extrusion", lambda: make_broken_square(gap=25))
        write_images("blob", lambda: make_broken_square(gap=22))
        write_images("elephants_foot", lambda: make_broken_square(gap=18))

        raw = calibrate(root)
        assert "clean" in raw, "clean label missing after calibrate"
        for lbl in ["clean", "layer_shift", "warping"]:
            assert lbl in raw, f"expected label '{lbl}' not found in raw"
            assert len(raw[lbl]["edge_continuity"]) == 3, f"wrong count for {lbl}"

        table = compute_table(raw)
        assert table["clean"]["edge_continuity"].mean > 0, "clean edge mean should be >0"
        # Check that stringing vs clean have different means (signal is separable)
        assert table["clean"]["edge_continuity"].mean != table["warping"]["edge_continuity"].mean

        suggestions = suggest_thresholds(raw)
        print(f"  suggestions = {suggestions}")

        # Thresholds must be data-driven and internally consistent
        assert suggestions["edge_continuity_confident_fail"] < suggestions["edge_continuity_confident_pass"], (
            "fail threshold must be < pass threshold"
        )
        assert 0.0 <= suggestions["reference_similarity_floor"] <= 1.0
        assert 0.0 <= suggestions["contrast_min_for_confidence"] <= 1.0

        # Prove print_report doesn't crash and contains expected sections
        print_report(raw, table, suggestions)

        # Also prove CLI works via subprocess
        import subprocess
        result = subprocess.run(
            [sys.executable, "scripts/calibrate_thresholds.py", str(root)],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            capture_output=True,
            text=True,
        )
        print("  CLI stdout snippet:", result.stdout[:800])
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "edge_continuity" in result.stdout
        assert "Suggested InspectionProfile" in result.stdout


def test_calibrate_handles_single_label_gracefully():
    """Even with only one label present, suggestions should still be produced
    (global percentile fallback) without crashing."""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        p = root / "clean"
        p.mkdir(parents=True, exist_ok=True)
        for i in range(2):
            cv2.imwrite(str(p / f"{i}.png"), make_clean_square())
        raw = calibrate(root)
        table = compute_table(raw)
        suggestions = suggest_thresholds(raw)
        print(f"  single-label suggestions = {suggestions}")
        assert "edge_continuity_confident_fail" in suggestions


TESTS = [test_calibrate_runs_on_synthetic_fixtures, test_calibrate_handles_single_label_gracefully]

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
            import traceback; traceback.print_exc()
            failed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}\n")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"--- {passed} passed, {failed} failed out of {len(TESTS)} ---")
    sys.exit(1 if failed else 0)
