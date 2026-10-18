"""Exercise synthetic uploads through the real web proxy across a backend restart.

Run prepare with both services running, restart only the backend you started,
then run verify with the same --state path. This checks transport/persistence,
not physical accuracy. Requires the test dependency httpx.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import httpx
import numpy as np

from capture_sessions import frame_digest
from sample_frames import make_backlit_recovery_pair


def encode(frame):
    ok, data = cv2.imencode(".png", frame)
    assert ok
    return data.tobytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "verify"])
    parser.add_argument("--state", type=Path, default=Path("/tmp/loopsight-recapture-smoke.json"))
    parser.add_argument("--web-base", default="http://127.0.0.1:3000")
    args = parser.parse_args()
    base = args.web_base.rstrip("/")
    first, second = make_backlit_recovery_pair()
    with httpx.Client(timeout=30, trust_env=False) as client:
        if args.phase == "prepare":
            response = client.post(base + "/api/inspect", files={"image": ("synthetic-first.png", encode(first), "image/png")},
                                   data={"inspection_profile": "water_turbidity_v1"})
            response.raise_for_status()
            parent = response.json()["job_id"]
            response = client.get(base + "/api/jobs/" + parent)
            response.raise_for_status()
            result = response.json()
            assert result["final_decision"]["decision"] == "REVIEW"
            assert result["capture_session"]["can_recapture"] is True
            assert result["acquisition"]["observations_used"] == 1
            assert result["measurement_contract"]["physical_units_available"] is False
            assert result["provenance"]["runtime_instance_id"]
            args.state.write_text(json.dumps({"parent": parent, "result": result}, indent=2))
            print("PASS first synthetic upload remains REVIEW; restart the backend, then run verify")
            return

        state = json.loads(args.state.read_text())
        response = client.post(base + "/api/inspect", files={"image": ("synthetic-second.png", encode(second), "image/png")},
                               data={"inspection_profile": "water_turbidity_v1", "original_job_id": state["parent"], "lighting2": "backlight"})
        response.raise_for_status()
        child = response.json()["job_id"]
        response = client.get(base + "/api/jobs/" + child)
        response.raise_for_status()
        result = response.json()
        assert result["regions"] == state["result"]["regions"]
        assert result["status"] == state["result"]["status"] == "UNCERTAIN"
        assert result["final_decision"]["decision"] == "PASS"
        assert result["acquisition"]["observations_used"] == 2
        assert result["acquisition"]["new_capture_used"] is True
        assert result["acquisition"]["parent_job_id"] == state["parent"]
        assert result["second_pass"]["evidence_source"] == "new_capture"
        assert result["measurement_contract"]["physical_units_available"] is False
        assert result["provenance"]["runtime_instance_id"] != state["result"]["provenance"]["runtime_instance_id"], "restart the backend between prepare and verify"
        for index, frame in enumerate([first, second]):
            image = client.get(base + f"/api/jobs/{child}/captures/{index}")
            image.raise_for_status()
            assert image.headers["content-type"] == "image/png"
            assert image.headers["cache-control"] == "private, no-store"
            decoded = cv2.imdecode(np.frombuffer(image.content, np.uint8), cv2.IMREAD_COLOR)
            assert np.array_equal(frame, decoded)
            assert result["frames"][index]["sha256"] == frame_digest(decoded)
        duplicate = client.post(base + "/api/inspect", files={"image": ("duplicate.png", encode(first), "image/png")},
                                data={"inspection_profile": "water_turbidity_v1", "original_job_id": state["parent"]})
        assert duplicate.status_code == 422
        assert client.get(base + "/api/jobs/never-created-recapture-smoke").status_code == 404
        assert client.get(base).status_code == 200
        summary = {"synthetic_transport_check": "passed", "new_backend_instance_verified": True,
                   "first_decision": "REVIEW", "follow_up_decision": "PASS", "observations_used": 2,
                   "raw_capture_round_trip": "pixel_identical", "duplicate_status": duplicate.status_code,
                   "physical_accuracy_validated": False}
        args.state.with_suffix(".result.json").write_text(json.dumps(summary, indent=2) + "\n")
        print("PASS recapture across backend restart; original first pass retained; both raw captures verified; duplicate rejected")


if __name__ == "__main__":
    main()
