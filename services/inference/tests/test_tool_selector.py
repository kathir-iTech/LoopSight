import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.tool_selector import select_tool, validate_tool_call, InvalidToolCallError
from cv.first_pass import run_first_pass
from tests.synthetic import make_low_contrast_frame

FULL_ROI = (0, 0, 200, 200)


def test_valid_mock_response_passes_through():
    fp = run_first_pass(make_low_contrast_frame(), None, [FULL_ROI])
    fixture = {"tool": "reinspect_roi", "arguments": {"scale": 2.0}, "reason_code": "LOW_CONTRAST"}
    call = select_tool(fp, mock_fixture=fixture)
    print(f"  selected tool={call.tool} reason_code={call.reason_code}")
    assert call.tool == "reinspect_roi"
    assert call.reason_code == "LOW_CONTRAST"


def test_tool_outside_whitelist_is_rejected():
    try:
        validate_tool_call({"tool": "delete_all_evidence", "arguments": {}, "reason_code": "X"})
        assert False, "should have raised for a non-whitelisted tool"
    except InvalidToolCallError as e:
        print(f"  correctly rejected non-whitelisted tool: {e}")


def test_malformed_response_falls_back_to_default_tool_not_a_crash():
    """This is the direct test for spec Section 3.3's real finding: a
    schema-constrained model call CAN return malformed/invalid output.
    The pipeline must degrade to a deterministic default, never crash."""
    fp = run_first_pass(make_low_contrast_frame(), None, [FULL_ROI])
    bad_fixture = {"tool": "not_a_real_tool", "arguments": {}, "reason_code": "X"}
    call = select_tool(fp, mock_fixture=bad_fixture, default_tool="reinspect_roi")
    print(f"  fallback tool={call.tool} reason_code={call.reason_code}")
    assert call.tool == "reinspect_roi"
    assert call.reason_code == "FALLBACK_AFTER_INVALID_AGENT_RESPONSE"


def test_missing_reason_code_is_rejected():
    try:
        validate_tool_call({"tool": "reinspect_roi", "arguments": {}})
        assert False, "should have raised for a missing reason_code"
    except InvalidToolCallError as e:
        print(f"  correctly rejected missing reason_code: {e}")


def test_no_api_key_and_no_mock_falls_back_gracefully():
    fp = run_first_pass(make_low_contrast_frame(), None, [FULL_ROI])
    call = select_tool(fp)  # neither api_key nor mock_fixture supplied
    print(f"  no-input fallback: tool={call.tool} reason_code={call.reason_code}")
    assert call.reason_code == "FALLBACK_AFTER_INVALID_AGENT_RESPONSE"


TESTS = [
    test_valid_mock_response_passes_through,
    test_tool_outside_whitelist_is_rejected,
    test_malformed_response_falls_back_to_default_tool_not_a_crash,
    test_missing_reason_code_is_rejected,
    test_no_api_key_and_no_mock_falls_back_gracefully,
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
