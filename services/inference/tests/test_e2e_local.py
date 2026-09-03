"""
Phase B verification — prove the REAL stack works locally, end to end.

Uses FastAPI's TestClient to exercise the actual /inspect and /jobs/{id}
routes (the same app uvicorn runs), uploading a real synthetic image.
Asserts the returned JSON is NOT the frozen 0.81/0.64/0.48/0.91 mock
values from apps/web/src/lib/mock-data.ts — i.e. the real CV pipeline is
answering, not a canned fallback.

Run: python -m pytest tests/test_e2e_local.py -v -s
"""

import sys
import os

# Blank the Gemini key BEFORE importing main, so _load_dotenv() (which only
# sets keys not already in os.environ) doesn't restore it. This keeps the
# UNCERTAIN path on the fast deterministic mock through the REAL CV pipeline,
# which is what Phase B is verifying end-to-end.
os.environ["GEMINI_API_KEY"] = ""

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import cv2

from fastapi.testclient import TestClient
from main import app  # noqa: F401  (imports the real app, routes, store)

client = TestClient(app)

from tests.synthetic import make_clean_square, make_broken_square


def _png_bytes(gen_fn) -> bytes:
    img = gen_fn()
    ok, buf = cv2.imencode(".png", img)
    assert ok, "failed to encode synthetic image to PNG"
    return buf.tobytes()


def test_inspect_returns_real_pipeline_values():
    """POST /inspect with a real image → response must NOT be the frozen mock."""
    files = {"image": ("clean.png", _png_bytes(make_clean_square), "image/png")}
    with client:
        resp = client.post("/inspect", files=files, data={"inspection_profile": "fdm_print_surface_v1"})
        assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "job_id" in data, "expected a job_id in response"
        job_id = data["job_id"]

    # Fetch the stored result
    with client:
        job = client.get(f"/jobs/{job_id}")
        assert job.status_code == 200, f"expected 200, got {job.status_code}"
        result = job.json()

    print("  --- real result (NOT the canned mock) ---")
    import json
    print(json.dumps(result, indent=2, default=str))

    # The whole point: this must NOT be the frozen 0.81/0.64/0.48/0.91 mock
    for region in result.get("regions", []):
        ev = region["evidence"]
        assert ev.get("edge_continuity") not in (0.81,), f"found canned mock edge_continuity 0.81: {ev}"
        assert ev.get("reference_similarity") not in (0.64,), f"found canned mock reference_similarity 0.64: {ev}"
        assert ev.get("layer_alignment_deviation") not in (0.48,), f"found canned mock layer_alignment_deviation 0.48: {ev}"
    # The final_decision must be a real decision from the policy, and the whole
    # result must be the real InspectionResult shape
    assert result["status"] in ("CONFIDENT_PASS", "CONFIDENT_FAIL", "UNCERTAIN")
    assert result["final_decision"]["decision"] in ("PASS", "REVIEW", "FAIL")


def test_inspect_works_for_a_broken_image_too():
    files = {"image": ("broken.png", _png_bytes(make_broken_square), "image/png")}
    with client:
        resp = client.post("/inspect", files=files, data={"inspection_profile": "fdm_print_surface_v1"})
        assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
        job = client.get(f"/jobs/{resp.json()['job_id']}")
        assert job.status_code == 200
        result = job.json()
    print(f"  broken result: status={result['status']} decision={result['final_decision']['decision']}")
    assert result["status"] in ("CONFIDENT_PASS", "CONFIDENT_FAIL", "UNCERTAIN")


TESTS = [test_inspect_returns_real_pipeline_values, test_inspect_works_for_a_broken_image_too]

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