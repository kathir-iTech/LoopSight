"""Verify the web-to-inference transport and retained evidence on an actual URL.

Inputs are generated fixtures. A passing report is not physical validation.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import httpx
import numpy as np
from sample_frames import make_backlit_recovery_pair


def verify(base, expected_revision=None, allow_local=False):
    parsed = urlsplit(base)
    local = parsed.hostname in {"localhost", "127.0.0.1"}
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("use a base URL without embedded credentials, query or fragment")
    if parsed.scheme != "https" and not (allow_local and local and parsed.scheme == "http"):
        raise ValueError("deployed verification requires HTTPS; --allow-local permits local HTTP only")
    base = base.rstrip("/")
    first, second = make_backlit_recovery_pair()
    def encoded(frame):
        ok, image = cv2.imencode(".png", frame)
        assert ok
        return image.tobytes()
    with httpx.Client(timeout=30, trust_env=not local) as client:
        version = client.get(base + "/api/version")
        version.raise_for_status()
        version = version.json()
        assert version["opencv_version"].startswith("5."), "OpenCV 5 runtime required"
        assert version["measurement_contract"]["physical_units_available"] is False
        if not allow_local:
            assert version["runtime_architecture"] in {"aarch64", "arm64"}, "actual ARM64 runtime required"
            assert version["storage"]["shared_across_instances"] is True, "shared S3 adapters required"
            assert re.fullmatch(r"[a-f0-9]{40}", version["build_revision"]), "deployed revision required"
        if expected_revision:
            assert version["build_revision"] == expected_revision, "deployed revision mismatch"
        ready = client.get(base + "/api/readiness")
        ready.raise_for_status()
        assert ready.json()["available"] is True
        def upload(image, **fields):
            response = client.post(base + "/api/inspect", files={"image": ("synthetic.png", encoded(image), "image/png")},
                                   data={"inspection_profile": "water_turbidity_v1", **fields})
            response.raise_for_status()
            job_id = response.json()["job_id"]
            response = client.get(base + "/api/jobs/" + job_id)
            response.raise_for_status()
            return job_id, response.json()
        parent, original = upload(first)
        assert original["final_decision"]["decision"] == "REVIEW"
        child, result = upload(second, original_job_id=parent, lighting2="backlight")
        assert result["provenance"]["execution_mode"] == "live_opencv"
        assert result["regions"] == original["regions"]
        assert result["acquisition"]["new_capture_used"] is True
        assert result["acquisition"]["observations_used"] == 2
        assert result["final_decision"]["decision"] == "PASS"
        archive = client.get(base + f"/api/jobs/{child}/evidence")
        archive.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
            manifest = json.loads(bundle.read("manifest.json"))
            assert manifest["job_id"] == child
            for name, entry in manifest["files"].items():
                assert hashlib.sha256(bundle.read(name)).hexdigest() == entry["sha256"]
            for name, expected in [("first.png", first), ("second.png", second)]:
                decoded = cv2.imdecode(np.frombuffer(bundle.read(name), np.uint8), cv2.IMREAD_COLOR)
                assert np.array_equal(decoded, expected)
        assert client.get(base + "/api/jobs/never-created-deployed-smoke").status_code == 404
        corrupt = client.post(base + "/api/inspect", files={"image": ("bad.png", b"invalid", "image/png")})
        assert corrupt.status_code == 400
        duplicate = client.post(base + "/api/inspect", files={"image": ("duplicate.png", encoded(first), "image/png")},
                                data={"original_job_id": parent, "inspection_profile": "water_turbidity_v1"})
        assert duplicate.status_code == 422
        assert client.get(base + "/evaluation").status_code == 200
    return {"status": "passed", "scope": "local_transport_check" if local else "deployed_transport_check",
            "inputs": "generated synthetic fixtures uploaded through real web proxy",
            "physical_validation": False, "build_revision": version["build_revision"],
            "runtime_architecture": version["runtime_architecture"], "storage": version["storage"],
            "different_runtime_instances_observed": original["provenance"]["runtime_instance_id"] != result["provenance"]["runtime_instance_id"],
            "retained_pixels_verified": True, "evidence_file_hashes_verified": True,
            "first_decision": "REVIEW", "second_decision": "PASS", "observations_used": 2,
            "unknown_job_status": 404, "corrupt_upload_status": 400, "duplicate_status": 422}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web-base", required=True)
    parser.add_argument("--expected-revision")
    parser.add_argument("--allow-local", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.web_base, args.expected_revision, args.allow_local)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print("PASS:", report["scope"], "— original evidence, recapture, archive hashes and error statuses verified")
