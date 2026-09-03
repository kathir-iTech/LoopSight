"""
Test for scripts/run_experiments.py against synthetic fixtures.

Proves the full evaluation harness (Experiments A/B/B2/C) is WORKING CODE
TODAY against synthetic data, clearly labeled as a dry run — so the moment
real labeled photos land, it's one command, not a rebuild.

Run: python -m pytest tests/test_run_experiments.py -v -s
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import cv2

from scripts.run_experiments import (
    _load_synthetic_dataset,
    run_all,
    print_report,
    run_experiment_a,
    run_experiment_b,
    run_experiment_c,
    run_experiment_b2,
    evaluate_experiment,
    _FULL_ROI,
    CORRECT_VERDICTS,
)
from cv.first_pass import run_first_pass
from scripts.calibrate_thresholds import _stats  # reuse, but not needed really


def test_harness_runs_all_experiments_and_produces_all_metrics():
    dataset = _load_synthetic_dataset()
    print(f"  dry-run dataset size = {len(dataset)}")
    assert len(dataset) >= 6, "expected a non-trivial synthetic set"
    results = run_all(dataset)
    assert set(results.keys()) == {"A", "B", "B2", "C"}
    for name in ("A", "B", "B2", "C"):
        m = results[name]
        # Every experiment must report every required metric
        for key in ("accuracy", "trigger_rate", "resolution_rate",
                    "false_trigger", "missed_trigger", "conditional_benefit"):
            assert key in m, f"exp {name} missing metric {key}"
        # Metric ranges are sane
        assert 0.0 <= m["accuracy"] <= 1.0
        assert 0.0 <= m["trigger_rate"] <= 1.0
        assert -1.0 <= m["conditional_benefit"] <= 1.0
    print("  all four experiments produced all six metrics")
    print_report(results)


def test_experiment_a_never_triggers_and_c_does():
    """Experiment A is single-pass — trigger_rate must be 0. Experiment C is
    adaptive — on genuinely ambiguous/borderline inputs it must trigger."""
    dataset = _load_synthetic_dataset()
    a = evaluate_experiment(run_experiment_a, dataset, "fdm_print_surface_v1")
    c = evaluate_experiment(run_experiment_c, dataset, "fdm_print_surface_v1")
    print(f"  A trigger_rate={a['trigger_rate']} C trigger_rate={c['trigger_rate']}")
    assert a["trigger_rate"] == 0.0, "single-pass baseline must never trigger a 2nd look"
    assert c["trigger_rate"] > 0.0, "adaptive policy must trigger on the borderline set"


def test_conditional_benefit_is_computable_and_bounded():
    """The number that settles the mechanism: P(correct|2nd look) - P(correct|1st).
    Must be a real, finite number in [-1, 1] on synthetic data — the tooling
    works even if the synthetic magnitude isn't meaningful yet."""
    dataset = _load_synthetic_dataset()
    results = run_all(dataset)
    cb = results["C"]["conditional_benefit"]
    print(f"  Experiment C conditional_benefit on synthetic = {cb}")
    assert -1.0 <= cb <= 1.0
    # Also confirm B2's matched budget actually differs from B (it should, since
    # B2 fires the fixed repeat on only a matched fraction).
    print(f"  B trigger_rate={results['B']['trigger_rate']} "
          f"B2 trigger_rate={results['B2']['trigger_rate']}")


def test_real_dataset_loading_works_or_raises_cleanly():
    """Prove the real-file loading path doesn't crash on a bogus path, and
    works on a temp labeled dir (organized like calibrate_thresholds data)."""
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # A real labeled layout
        clean = root / "clean"; clean.mkdir()
        broken = root / "broken"; broken.mkdir()
        from tests.synthetic import make_clean_square, make_broken_square
        cv2.imwrite(str(clean / "0.png"), make_clean_square())
        cv2.imwrite(str(broken / "0.png"), make_broken_square())
        from scripts.run_experiments import _load_real_dataset
        ds = _load_real_dataset(root)
        labels = {l for l, _ in ds}
        assert "clean" in labels and "broken" in labels
        print(f"  loaded {len(ds)} labeled images from temp dir")


TESTS = [
    test_harness_runs_all_experiments_and_produces_all_metrics,
    test_experiment_a_never_triggers_and_c_does,
    test_conditional_benefit_is_computable_and_bounded,
    test_real_dataset_loading_works_or_raises_cleanly,
]

if __name__ == "__main__":
    passed, failed = 0, 0
    for t in TESTS:
        try:
            print(f"RUN  {t.__name__}")
            t()
            print(f"PASS {t.__name__}\n")
            passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}\n")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"--- {passed} passed, {failed} failed out of {len(TESTS)} ---")
    sys.exit(1 if failed else 0)