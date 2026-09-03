"""
Phase B verification — proves the REAL stack works locally, end to end.

Writes its results to a file so they're reliably inspectable regardless of
shell output-capture issues. Uses FastAPI's TestClient (the same app uvicorn
runs) to exercise the actual /inspect and /jobs/{id} routes, uploading a real
synthetic image. Asserts the returned JSON is NOT the frozen
0.81/0.64/0.48/0.91 mock values from apps/web/src/lib/mock-data.ts.

Run: python -X utf8 scripts/_verify_end_to_end.py
"""

import sys, os

os.environ["GEMINI_API_KEY"] = ""  # blank BEFORE importing main

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import numpy as np
import cv2

from fastapi.testclient import TestClient
from main import app
from tests.synthetic import make_clean_square, make_broken_square

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "reports", "_phase_b_verification.json")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

client = TestClient(app)


def _png_bytes(gen_fn) -> bytes:
    img = gen_fn()
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def main() -> int:
    results = {"phase": "B", "ok": True, "checks": []}

    def check(name, ok, detail):
        results["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            results["ok"] = False

    # --- clean image end-to-end ---
    files = {"image": ("clean.png", _png_bytes(make_clean_square), "image/png")}
    with client:
        r = client.post("/inspect", files=files, data={"inspection_profile": "fdm_print_surface_v1"})
        check("clean /inspect status 200", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
        if r.status_code == 200:
            job_id = r.json()["job_id"]
            job = client.get(f"/jobs/{job_id}")
            check("clean /jobs ok", job.status_code == 200, f"status={job.status_code}")
            result = job.json() if job.status_code == 200 else {}
        else:
            result = {}

    # Verify NOT the frozen mock values
    mock_frozen = (0.81, 0.64, 0.48, 0.91)
    regions = result.get("regions", [])
    for region in regions:
        ev = region.get("evidence", {})
        for k, v in ev.items():
            check(f"clean evidence.{k} not frozen mock {v}", v not in mock_frozen, f"{k}={v}")
    check("clean status is real enum", result.get("status") in ("CONFIDENT_PASS", "CONFIDENT_FAIL", "UNCERTAIN"), f"status={result.get('status')}")
    check("clean decision is real enum", result.get("final_decision", {}).get("decision") in ("PASS", "REVIEW", "FAIL"), f"decision={result.get('final_decision', {}).get('decision')}")

    # --- broken image end-to-end ---
    files_b = {"image": ("broken.png", _png_bytes(make_broken_square), "image/png")}
    with client:
        rb = client.post("/inspect", files=files_b, data={"inspection_profile": "fdm_print_surface_v1"})
        check("broken /inspect status 200", rb.status_code == 200, f"status={rb.status_code} body={rb.text[:200]}")
        if rb.status_code == 200:
            jb = client.get(f"/jobs/{rb.json()['job_id']}")
            rb_result = jb.json() if jb.status_code == 200 else {}
        else:
            rb_result = {}
    check("broken status is real enum", rb_result.get("status") in ("CONFIDENT_PASS", "CONFIDENT_FAIL", "UNCERTAIN"), f"status={rb_result.get('status')}")

    # Save the real result JSON as evidence
    results["clean_result"] = result
    results["broken_result"] = rb_result

    print(json.dumps(results, indent=2, default=str))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n[written] {OUT}")
    return 0 if results["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())