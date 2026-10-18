"""
LoopSight v2 — comprehensive unit & integration tests for the upgraded OpenCV 5
spatial metrology tools, multi-profile active-perception loop, MCP endpoints,
benchmark sample runner, and SQLite write-through persistence.
"""

import os
import sys
import tempfile

os.environ["GEMINI_API_KEY"] = ""
os.environ["DEMO_MODE"] = ""

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app, SAMPLE_CATALOG
from cv.first_pass import run_first_pass
from cv.tools import (
    inpaint_specular_glare,
    rectify_perspective_homography,
    analyze_vertical_stratification,
    skeletonize_crack_metrology,
)
from cv.policy import decide
from storage import InMemoryJobStore
from tests.synthetic import (
    make_glare_confounded_water,
    make_stratified_turbid_water,
    make_intact_concrete,
    make_structural_crack,
    make_shadow_confounded_concrete,
    make_checkerboard,
)

client = TestClient(app)
ROI = (0, 0, 200, 200)


def test_glare_processing_cannot_clear_a_sample_without_a_new_capture():
    img = make_glare_confounded_water()
    fp = run_first_pass(img, None, [ROI], profile_name="water_turbidity_v1")
    assert fp.status == "UNCERTAIN", f"expected UNCERTAIN on glare confounder, got {fp.status}"
    assert "inpaint_specular_glare" in fp.allowed_tools
    tool_res = inpaint_specular_glare(img, ROI)
    final = decide(fp, tool_res.region, profile_name="water_turbidity_v1")
    print(f"  glare confounder: pass1_pv={fp.regions[0].pattern_visibility:.3f} -> inpaint_pv={tool_res.region.pattern_visibility:.3f} -> {final.decision}")
    assert final.decision == "REVIEW"
    assert final.human_approval_required is True
    assert "new photo" in final.reasoning[0]


def test_vertical_stratification_triggers_uncertain_and_resolves_fail():
    img = make_stratified_turbid_water()
    fp = run_first_pass(img, None, [ROI], profile_name="water_turbidity_v1")
    assert fp.status == "UNCERTAIN", f"expected UNCERTAIN on stratified water, got {fp.status}"
    assert "analyze_vertical_stratification" in fp.allowed_tools
    tool_res = analyze_vertical_stratification(img, ROI)
    final = decide(fp, tool_res.region, profile_name="water_turbidity_v1")
    print(f"  stratification: pass1_pv={fp.regions[0].pattern_visibility:.3f} (delta={fp.regions[0].stratification_delta:.3f}) -> strat_pv={tool_res.region.pattern_visibility:.3f} -> {final.decision}")
    assert final.decision == "FAIL"


def test_rectify_perspective_homography_runs_cleanly():
    img = make_checkerboard()
    res = rectify_perspective_homography(img, ROI)
    assert res.tool == "rectify_perspective_homography"
    assert res.region.pattern_visibility > 0.50


def test_structural_crack_metrology_profile_separates_intact_crack_and_confounder():
    intact = run_first_pass(make_intact_concrete(), None, [ROI], profile_name="structural_crack_metrology_v1")
    assert intact.status == "CONFIDENT_PASS", f"expected CONFIDENT_PASS for intact concrete, got {intact.status}"

    cracked = run_first_pass(make_structural_crack(thickness_px=6), None, [ROI], profile_name="structural_crack_metrology_v1")
    assert cracked.status == "CONFIDENT_FAIL", f"expected CONFIDENT_FAIL for 6px synthetic line, got {cracked.status}"
    assert cracked.regions[0].crack_width_px >= 4.0

    confounded = run_first_pass(make_shadow_confounded_concrete(), None, [ROI], profile_name="structural_crack_metrology_v1")
    assert confounded.status == "UNCERTAIN"
    skel_res = skeletonize_crack_metrology(make_shadow_confounded_concrete(), ROI)
    final = decide(confounded, skel_res.region, profile_name="structural_crack_metrology_v1")
    print(f"  crack metrology: intact={intact.status}, cracked_px={cracked.regions[0].crack_width_px:.3f}, confounded->{final.decision}")
    assert final.decision == "PASS"


def test_mcp_tools_and_benchmark_samples_endpoints():
    with client:
        mcp_resp = client.get("/mcp/tools")
        assert mcp_resp.status_code == 200
        mcp_body = mcp_resp.json()
        assert mcp_body["protocol"] == "mcp/1.0"
        assert len(mcp_body["tools"]) == 8

        samples_resp = client.get("/samples")
        assert samples_resp.status_code == 200
        samples = samples_resp.json()["samples"]
        assert len(samples) == len(SAMPLE_CATALOG)

        for item in samples:
            sid = item["id"]
            run_resp = client.post(f"/inspect/sample/{sid}")
            assert run_resp.status_code == 200, f"sample {sid} failed: {run_resp.text}"
            jid = run_resp.json()["job_id"]
            job_resp = client.get(f"/jobs/{jid}")
            assert job_resp.status_code == 200
            job_data = job_resp.json()
            assert job_data.get("overlay_data_url", "").startswith("data:image/png;base64,")
            print(f"  sample {sid:26s} -> status={job_data['status']:14s} tool={job_data.get('agent_call', {}).get('tool')} decision={job_data['final_decision']['decision']}")


def test_sqlite_write_through_persistence():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_file = os.path.join(tmp, "test_jobs.sqlite3")
        store1 = InMemoryJobStore(backing={}, sqlite_path=db_file)
        store1.save("job123", {"status": "CONFIDENT_PASS", "final_decision": {"decision": "PASS"}})
        # Simulate new worker process with empty RAM dict reading from same SQLite file
        store2 = InMemoryJobStore(backing={}, sqlite_path=db_file)
        loaded = store2.get("job123")
        assert loaded is not None
        assert loaded["final_decision"]["decision"] == "PASS"


def test_water_evidence_is_dimensionless_without_physical_conversion():
    from dataclasses import asdict
    from cv.first_pass import measure_pattern_visibility
    from sample_frames import make_clear_water, make_turbid_water, make_checkerboard
    clear = measure_pattern_visibility(make_clear_water(), ROI)
    turbid = measure_pattern_visibility(make_turbid_water(make_checkerboard()), ROI)
    assert 0 <= turbid.pattern_visibility < clear.pattern_visibility <= 1
    assert "estimated_ntu" not in asdict(clear)
    assert "who_tier" not in asdict(clear)


def test_multi_tool_chaining_execution():
    from cv.tools import execute_tool_chain
    from tests.synthetic import make_glare_confounded_water
    frame = make_glare_confounded_water()
    roi = (0, 0, frame.shape[1], frame.shape[0])

    chain = ["inpaint_specular_glare", "rectify_perspective_homography"]
    res = execute_tool_chain(chain, frame, roi, radius=5.0)
    assert res.tool == "inpaint_specular_glare -> rectify_perspective_homography"
    assert "Step 1 (inpaint_specular_glare)" in res.notes
    assert "Step 2 (rectify_perspective_homography)" in res.notes
    assert res.region.pattern_found is True
    assert res.region.pattern_visibility > 0.20
    assert not hasattr(res.region, "estimated_ntu")


def test_mcp_json_rpc_2_protocol():
    from fastapi.testclient import TestClient
    from main import app
    with TestClient(app) as client:
        # 1. Initialize
        r_init = client.post("/mcp/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert r_init.status_code == 200
        d_init = r_init.json()
        assert d_init["jsonrpc"] == "2.0"
        assert d_init["result"]["serverInfo"]["name"] == "loopsight-opencv5-mcp"

        # 2. Ping
        r_ping = client.post("/mcp/rpc", json={"jsonrpc": "2.0", "id": 2, "method": "ping"})
        assert r_ping.status_code == 200
        assert r_ping.json()["result"] == {}

        # 3. tools/list
        r_list = client.post("/mcp/rpc", json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
        assert r_list.status_code == 200
        tools = r_list.json()["result"]["tools"]
        assert len(tools) == 8

        # 4. tools/call
        r_call = client.post(
            "/mcp/rpc",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "inpaint_specular_glare", "arguments": {"sample_id": "water_glare_confounded", "radius": 5.0}},
            },
        )
        assert r_call.status_code == 200
        res_call = r_call.json()["result"]
        assert not res_call["isError"]
        assert "pattern_visibility" in res_call["content"][0]["text"]


TESTS = [
    test_glare_processing_cannot_clear_a_sample_without_a_new_capture,
    test_vertical_stratification_triggers_uncertain_and_resolves_fail,
    test_rectify_perspective_homography_runs_cleanly,
    test_structural_crack_metrology_profile_separates_intact_crack_and_confounder,
    test_mcp_tools_and_benchmark_samples_endpoints,
    test_sqlite_write_through_persistence,
    test_water_evidence_is_dimensionless_without_physical_conversion,
    test_multi_tool_chaining_execution,
    test_mcp_json_rpc_2_protocol,
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
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"--- {passed} passed, {failed} failed out of {len(TESTS)} ---")
    sys.exit(1 if failed else 0)

