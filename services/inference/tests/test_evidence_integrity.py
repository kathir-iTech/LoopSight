import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from agent.tool_selector import InvalidToolCallError, call_gemini, validate_tool_call
from cv.first_pass import run_first_pass
from main import app, _execute_inspection_pipeline
from sample_frames import make_backlit_recovery_pair, make_low_contrast_frame


@pytest.mark.parametrize("tool,arguments", [
    ("reinspect_roi", {"scale": 1e9}),
    ("reinspect_roi", {"scale": float("nan")}),
    ("reinspect_roi", {"scale": True}),
    ("reinspect_roi", {"radius": 5}),
    ("inpaint_specular_glare", {"radius": -1}),
    ("measure_edge_continuity", {"low": 200, "high": 100}),
    ("measure_edge_continuity", {"low": 0.5}),
    ("skeletonize_crack_metrology", {"mm_per_px": float("inf")}),
])
def test_out_of_budget_or_invalid_tool_arguments_are_rejected(tool, arguments):
    with pytest.raises(InvalidToolCallError):
        validate_tool_call({"tool": tool, "arguments": arguments, "reason_code": "probe"})


def test_unbounded_tool_chain_is_rejected_before_execution():
    with pytest.raises(InvalidToolCallError):
        validate_tool_call({"tool_chain": ["reinspect_roi"] * 1000, "reason_code": "probe"})


def test_tools_must_be_permitted_for_this_inspection():
    with pytest.raises(InvalidToolCallError):
        validate_tool_call({"tool": "inpaint_specular_glare", "reason_code": "probe"},
                           allowed_tools={"reinspect_roi"})


def test_gemini_timeout_uses_milliseconds_and_one_attempt(monkeypatch):
    from google import genai

    calls = []
    def client(**options):
        assert options["http_options"] == {"timeout": 15000, "retry_options": {"attempts": 1}}
        def generate_content(**request):
            calls.append(request["model"])
            return SimpleNamespace(text=json.dumps({"tool": "reinspect_roi", "reason_code": "test"}))
        return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content), close=lambda: None)
    monkeypatch.setattr(genai, "Client", client)
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "15")
    frame = make_low_contrast_frame()
    fp = run_first_pass(frame, None, [(0, 0, 200, 200)])
    assert call_gemini(fp, "unit-test-placeholder", model="configured-model").tool == "reinspect_roi"
    assert calls == ["configured-model"]


def test_missing_second_capture_keeps_decision_in_review(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    frame, _ = make_backlit_recovery_pair()
    _, result = _execute_inspection_pipeline(frame, "water_turbidity_v1")
    assert result["agent_call"]["tool"] == "track_across_frames"
    assert result["agent_call"]["selector"] == "deterministic_policy"
    assert "second_pass" not in result
    assert result["final_decision"]["decision"] == "REVIEW"
    assert result["provenance"]["execution_mode"] == "live_opencv"


def test_synthetic_benchmark_provenance_survives_job_storage(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    with TestClient(app) as client:
        response = client.post("/inspect/sample/water_turbid_fail")
        assert response.status_code == 200
        job = client.get("/jobs/" + response.json()["job_id"])
        assert job.status_code == 200
        assert job.json()["provenance"]["execution_mode"] == "synthetic_benchmark"


@pytest.mark.parametrize("params", [[1], {"name": []}, {"name": "reinspect_roi", "arguments": []},
    {"name": "reinspect_roi", "arguments": {"scale": 1e9}}])
def test_mcp_rejects_malformed_or_unbounded_calls_without_server_errors(params):
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/mcp/rpc", json={"jsonrpc": "2.0", "id": 1,
                                               "method": "tools/call", "params": params})
        assert response.status_code == 200
        assert "error" in response.json()


def test_mcp_initialized_notification_has_no_json_rpc_response():
    with TestClient(app) as client:
        response = client.post("/mcp/rpc", json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        assert response.status_code == 202
        assert response.content == b""


def test_mcp_tracking_does_not_duplicate_one_frame_into_a_second_capture():
    with TestClient(app) as client:
        response = client.post("/mcp/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "track_across_frames", "arguments": {"sample_id": "water_dual_lighting"}}})
        assert response.json()["result"]["isError"] is True
        assert "second_image_base64" in response.json()["result"]["content"][0]["text"]
