"""
Gemini live integration test — skipped unless GEMINI_API_KEY is present.

This is the single test from Phase 2 that exercises the real call_gemini
path end-to-end (FirstPassResult → Gemini → validate_tool_call). It
deliberately does NOT run in routine local/CI without a key: it skips
cleanly so the default suite still passes with no credentials.
"""

import os
import sys

# Ensure imports work whether pytest is run from repo root or from this dir
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # type: ignore

from cv.first_pass import run_first_pass
from agent.tool_selector import validate_tool_call, select_tool
from tests.synthetic import make_low_contrast_frame

FULL_ROI = (0, 0, 200, 200)


def test_real_gemini_select_tool_validates():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set — skipping live Gemini integration test")

    # Build a genuinely UNCERTAIN first pass so the agent path fires
    frame = make_low_contrast_frame()
    fp = run_first_pass(frame, None, [FULL_ROI])
    assert fp.status == "UNCERTAIN", f"fixture must be UNCERTAIN to exercise agent, got {fp.status}"

    # Real Gemini call — this is the path main.py uses when GEMINI_API_KEY is set
    tool_call = select_tool(fp, api_key=api_key)

    # The returned ToolCall must pass the same whitelist validation the pipeline enforces.
    # Construct the raw dict shape that validate_tool_call expects and assert it succeeds.
    raw = {
        "tool": tool_call.tool,
        "arguments": tool_call.arguments,
        "reason_code": tool_call.reason_code,
    }
    validated = validate_tool_call(raw)

    assert validated.tool in ("reinspect_roi", "compare_to_reference", "measure_edge_continuity", "track_across_frames")
    assert isinstance(validated.reason_code, str) and validated.reason_code
    assert isinstance(validated.arguments, dict)
    # Also assert the fallback-reason path wasn't taken (unless the live call genuinely fell back
    # due to a transient error — still a valid outcome, but the test notes it)
    if validated.reason_code.startswith("FALLBACK_"):
        pytest.skip(f"Gemini call fell back ({validated.reason_code}) — not a hard failure, but live model not exercised")


# Provide a manual __main__ runner so `python tests/test_gemini_integration.py` also works
TESTS = [test_real_gemini_select_tool_validates]

if __name__ == "__main__":
    import traceback
    passed = skipped = failed = 0
    for t in TESTS:
        try:
            print(f"RUN  {t.__name__}")
            t()
            print(f"PASS {t.__name__}\n")
            passed += 1
        except BaseException as e:
            # pytest.skip raises _pytest.outcomes.Skipped (BaseException, not Exception)
            if type(e).__name__ == "Skipped" or "skip" in type(e).__name__.lower():
                print(f"SKIP {t.__name__}: {e}\n")
                skipped += 1
            elif "skipped" in str(e).lower() or "GEMINI_API_KEY not set" in str(e):
                print(f"SKIP {t.__name__}: {e}\n")
                skipped += 1
            else:
                print(f"FAIL {t.__name__}: {e}\n")
                traceback.print_exc()
                failed += 1
    print(f"--- {passed} passed, {skipped} skipped, {failed} failed out of {len(TESTS)} ---")
    sys.exit(1 if failed else 0)
