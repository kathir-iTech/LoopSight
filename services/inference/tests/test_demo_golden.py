"""
Tests for Phase C — demo resilience.

Covers both spec-required demo paths:
  1. Golden-result fallback (DEMO_MODE=golden): pre-computed known results
     served instead of live inference, so a demo never depends on a live
     API call working.
  2. Forced-ambiguity demo mode: a way to guarantee the UNCERTAIN branch
     fires on command (demo_case=uncertain), so the adaptive loop can be
     shown deliberately, not left to chance.

Run: python -m pytest tests/test_demo_golden.py -v -s
"""

import sys
import os

# Blank the Gemini key BEFORE importing main so the live-Gemini path is not
# used in any test; demo mode must be fully offline-deterministic.
os.environ["GEMINI_API_KEY"] = ""

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json

import pytest

from fastapi.testclient import TestClient

import demo_golden
import main  # noqa: F401

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def _demo_golden_mode_isolated():
    """Activate DEMO_MODE=golden during each demo test, then restore the
    original value afterwards.

    Without the restore, the env mutation leaks into every other test module
    in the same pytest process (golden_mode_enabled() is read live from the
    environment), silently turning their /inspect calls into golden responses.
    """
    original = os.environ.get("DEMO_MODE")
    os.environ["DEMO_MODE"] = "golden"
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("DEMO_MODE", None)
        else:
            os.environ["DEMO_MODE"] = original


def _submit(case: str):
    with client:
        r = client.post(
            "/inspect",
            data={"demo_case": case, "inspection_profile": "fdm_print_surface_v1"},
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        job_id = r.json()["job_id"]
        job = client.get(f"/jobs/{job_id}")
        assert job.status_code == 200, f"expected job 200, got {job.status_code}"
        return job.json(), job_id


def test_golden_confident_pass():
    result, _ = _submit("confident_pass")
    print("  confident_pass:", json.dumps(result, indent=2, default=str))
    assert result["status"] == "CONFIDENT_PASS"
    assert result["final_decision"]["decision"] == "PASS"
    assert result["final_decision"]["human_approval_required"] is False
    assert "agent_call" not in result, "confident pass must not fire the agent"
    assert "second_pass" not in result, "confident pass must not take a second look"


def test_golden_confident_fail():
    result, _ = _submit("confident_fail")
    print("  confident_fail:", json.dumps(result, indent=2, default=str))
    assert result["status"] == "CONFIDENT_FAIL"
    assert result["final_decision"]["decision"] == "FAIL"
    assert result["final_decision"]["human_approval_required"] is True
    assert "agent_call" not in result


def test_golden_uncertain_triggers_agent():
    result, _ = _submit("uncertain")
    print("  uncertain:", json.dumps(result, indent=2, default=str))
    assert result["status"] == "UNCERTAIN"
    assert "agent_call" in result, "uncertain golden MUST fire the agent"
    assert "second_pass" in result, "uncertain golden MUST take a second look"
    assert result["final_decision"]["decision"] == "REVIEW"
    assert result["final_decision"]["human_approval_required"] is True


def test_forced_ambiguity_flag_guarantees_uncertain_branch():
    """The forced-ambiguity demo mode: ANY golden request with demo_case
    'uncertain' (or unknown case) MUST land on the UNCERTAIN+agent branch,
    never on a confident pass/fail. This is the 'rehearse the genuinely
    ambiguous case, not just the clean ones' risk from the spec."""
    result, _ = _submit("uncertain")
    assert result["status"] == "UNCERTAIN"
    assert result["agent_call"]["reason_code"] == "AMBIGUOUS_EDGE_BAND"
    print("  forced-ambiguity fired the agent on command:",
          result["agent_call"]["tool"],
          result["agent_call"]["reason_code"])


def test_unknown_demo_case_does_not_crash_and_lands_on_uncertain():
    """A bad demo_case value must never crash — fall back to the ambiguous
    fixture so the demo stays on the agent-loops-shown path."""
    result, _ = _submit("not_a_real_case")
    assert result["status"] == "UNCERTAIN"
    assert "agent_call" in result
    print("  unknown demo_case safely landed on UNCERTAIN")


def test_demo_mode_disabled_runs_real_pipeline():
    """Sanity: when DEMO_MODE is NOT golden, the real CV pipeline runs."""
    import cv2
    from tests.synthetic import make_clean_square
    os.environ["DEMO_MODE"] = ""
    # Re-import a fresh app state so golden_mode_enabled() re-reads env
    img = make_clean_square()
    ok, buf = cv2.imencode(".png", img)
    assert ok
    client2 = TestClient(main.app)
    with client2:
        r = client2.post(
            "/inspect",
            files={"image": ("c.png", buf.tobytes(), "image/png")},
            data={"inspection_profile": "fdm_print_surface_v1"},
        )
        assert r.status_code == 200
        job = client2.get(f"/jobs/{r.json()['job_id']}")
        result = job.json()
    os.environ["DEMO_MODE"] = "golden"
    print("  real-pipeline status:", result["status"],
          "decision:", result["final_decision"]["decision"])
    assert "regions" in result
    assert result["status"] in ("CONFIDENT_PASS", "CONFIDENT_FAIL", "UNCERTAIN")


TESTS = [
    test_golden_confident_pass,
    test_golden_confident_fail,
    test_golden_uncertain_triggers_agent,
    test_forced_ambiguity_flag_guarantees_uncertain_branch,
    test_unknown_demo_case_does_not_crash_and_lands_on_uncertain,
    test_demo_mode_disabled_runs_real_pipeline,
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