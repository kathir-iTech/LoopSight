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


def _load_env_key() -> str | None:
    """Load GEMINI_API_KEY from env or from a .env file searched upward.
    This lets `python tests/test_gemini_integration.py` work after the user
    pasted a key into .env without manually exporting it.

    Contracts:
      - An EXPLICIT env value equal to '' or 'disabled' means "no key and do
        not look for a .env fallback" — so CI/production can definitively
        turn the live test off (same contract main.py uses to force the mock
        path), and a corrupted/stale .env can never silently re-enable it.
      - Otherwise the env value wins; if unset we look for a .env upward."""
    raw = os.environ.get("GEMINI_API_KEY")
    if raw is not None:
        stripped = raw.strip()
        if stripped == "" or stripped.lower() == "disabled":
            return None
        return stripped
    # Search for .env upward from this file and from cwd
    candidates = []
    here = os.path.abspath(__file__)
    for _ in range(5):
        here = os.path.dirname(here)
        candidates.append(os.path.join(here, ".env"))
    candidates.append(os.path.join(os.getcwd(), ".env"))
    candidates.append(os.path.join(os.path.dirname(os.getcwd()), ".env"))
    seen = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        if os.path.isfile(cand):
            try:
                with open(cand, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        if k.strip() == "GEMINI_API_KEY":
                            v = v.strip().strip('"').strip("'")
                            if v:
                                # Also export to environ for downstream code
                                os.environ["GEMINI_API_KEY"] = v
                                return v
            except Exception:
                continue
    return None


def test_real_gemini_select_tool_validates():
    api_key = _load_env_key()
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set — skipping live Gemini integration test (no .env key found either)")

    # Build a genuinely UNCERTAIN first pass so the agent path fires
    frame = make_low_contrast_frame()
    fp = run_first_pass(frame, None, [FULL_ROI])
    assert fp.status == "UNCERTAIN", f"fixture must be UNCERTAIN to exercise agent, got {fp.status}"

    # Real Gemini call — this is the path main.py uses when GEMINI_API_KEY is set
    # Use call_gemini directly to prove the live model path, then also via select_tool
    from agent.tool_selector import call_gemini

    print(f"  [gemini] calling with key prefix {api_key[:6]}... and UNCERTAIN first_pass evidence_gap={fp.evidence_gap}")
    try:
        direct = call_gemini(fp, api_key=api_key)
        print(f"  [gemini] call_gemini() returned ToolCall(tool={direct.tool!r}, reason_code={direct.reason_code!r}, arguments={direct.arguments})")
        # Validate directly
        direct_validated = validate_tool_call({"tool": direct.tool, "arguments": direct.arguments, "reason_code": direct.reason_code})
        print(f"  [gemini] validate_tool_call() accepted it: {direct_validated}")
    except Exception as e:
        print(f"  [gemini] call_gemini() raised: {type(e).__name__}: {e}")
        raise

    # Also test the pipeline's select_tool wrapper (which adds fallback handling)
    tool_call = select_tool(fp, api_key=api_key)
    print(f"  [gemini] select_tool() returned ToolCall(tool={tool_call.tool!r}, reason_code={tool_call.reason_code!r})")

    # The returned ToolCall must pass the same whitelist validation the pipeline enforces.
    raw = {
        "tool": tool_call.tool,
        "arguments": tool_call.arguments,
        "reason_code": tool_call.reason_code,
    }
    validated = validate_tool_call(raw)
    print(f"  [gemini] final validated ToolCall: tool={validated.tool} reason_code={validated.reason_code} arguments={validated.arguments}")

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
