"""Verify downloadable evidence and failures at the HTTP boundary."""
import asyncio
import hashlib
import io
import json
import struct
import threading
import zipfile
import zlib

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

import main
from capture_sessions import SqliteCaptureSessionStore
from storage import InMemoryJobStore
from request_limits import BodyLimitMiddleware
from sample_frames import make_backlit_recovery_pair


@pytest.fixture
def api(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("DEMO_MODE", "")
    monkeypatch.setenv("LOOPSIGHT_API_TOKEN", "")
    monkeypatch.setattr(main, "store", InMemoryJobStore({}, sqlite_path=str(tmp_path / "jobs.db")))
    clock = [100.0]
    monkeypatch.setattr(main, "capture_store", SqliteCaptureSessionStore(str(tmp_path / "captures.db"),
                                                                       ttl_seconds=60, clock=lambda: clock[0]))
    with TestClient(main.app, raise_server_exceptions=False) as client:
        yield client, clock


def upload(client, image, **fields):
    ok, data = cv2.imencode(".png", image)
    assert ok
    return client.post("/inspect", files={"image": ("frame.png", data.tobytes(), "image/png")},
                       data={"inspection_profile": "water_turbidity_v1", **fields})


def test_bundle_contains_real_images_policy_and_verifiable_file_hashes(api):
    client, _ = api
    first, second = make_backlit_recovery_pair()
    parent = upload(client, first).json()["job_id"]
    child = upload(client, second, original_job_id=parent).json()["job_id"]
    response = client.get(f"/jobs/{child}/evidence")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["cache-control"] == "private, no-store"
    with zipfile.ZipFile(io.BytesIO(response.content)) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
        assert manifest["job_id"] == child
        for name, entry in manifest["files"].items():
            body = bundle.read(name)
            assert len(body) == entry["bytes"]
            assert hashlib.sha256(body).hexdigest() == entry["sha256"]
        for name, expected in [("first.png", first), ("second.png", second)]:
            decoded = cv2.imdecode(np.frombuffer(bundle.read(name), np.uint8), cv2.IMREAD_COLOR)
            assert np.array_equal(decoded, expected)
        result = json.loads(bundle.read("result.json"))
        policy = json.loads(bundle.read("policy.json"))
        assert result["acquisition"]["observations_used"] == 2
        assert policy["snapshot"]["fingerprint"] == main.POLICY_FINGERPRINT
        assert policy["measurement_contract"]["physical_units_available"] is False


def test_evidence_unknown_and_expired_returns_error_not_partial_archive(api):
    client, clock = api
    first, _ = make_backlit_recovery_pair()
    parent = upload(client, first).json()["job_id"]
    assert client.get("/jobs/never-created/evidence").status_code == 404
    clock[0] += 61
    assert client.get(f"/jobs/{parent}/evidence").status_code == 410


def test_changed_policy_cannot_reinterpret_an_old_recapture(api, monkeypatch):
    client, _ = api
    first, second = make_backlit_recovery_pair()
    parent = upload(client, first).json()["job_id"]
    monkeypatch.setattr(main, "POLICY_FINGERPRINT", "new-policy-version")
    response = upload(client, second, original_job_id=parent)
    assert response.status_code == 409
    assert "policy changed" in response.json()["detail"]


def test_backend_token_protects_compute_and_evidence_but_not_liveness(api, monkeypatch):
    client, _ = api
    monkeypatch.setenv("LOOPSIGHT_API_TOKEN", "test-only-secret")
    assert client.get("/health").status_code == 200
    assert client.get("/version").status_code == 200
    assert client.get("/ready").status_code == 401
    assert client.post("/inspect/sample/water_turbid_fail").status_code == 401
    assert client.get("/jobs/unknown/evidence").status_code == 401
    response = client.post("/inspect/sample/water_turbid_fail", headers={"Authorization": "Bearer test-only-secret"})
    assert response.status_code == 200


def test_busy_work_budget_returns_retryable_error_and_health_stays_available(api, monkeypatch):
    client, _ = api
    slots = threading.BoundedSemaphore(1)
    slots.acquire()
    monkeypatch.setattr(main, "_work_slots", slots)
    response = client.post("/inspect/sample/water_turbid_fail")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "2"
    assert "job_id" not in response.json()
    assert client.get("/health").status_code == 200


def test_pixel_bomb_header_is_rejected_before_opencv_decode(api, monkeypatch):
    client, _ = api
    def png_chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
    image = b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", struct.pack("!IIBBBBB", 6000, 6000, 8, 2, 0, 0, 0))
    image += png_chunk(b"IDAT", zlib.compress(b"")) + png_chunk(b"IEND", b"")
    def forbidden(*args): raise AssertionError("OpenCV must not decode the oversized image")
    monkeypatch.setattr(main.cv2, "imdecode", forbidden)
    response = client.post("/inspect", files={"image": ("bomb.png", image, "image/png")})
    assert response.status_code == 400
    assert "pixel budget" in response.json()["detail"]


def test_chunked_body_is_bounded_before_application_or_multipart_parser(monkeypatch):
    monkeypatch.setenv("LOOPSIGHT_MAX_REQUEST_BYTES", "1024")
    called = []
    async def application(*args): called.append(True)
    middleware = BodyLimitMiddleware(application)
    messages = iter([{"type": "http.request", "body": b"x" * 700, "more_body": True},
                     {"type": "http.request", "body": b"x" * 700, "more_body": False}])
    sent = []
    async def receive(): return next(messages)
    async def send(message): sent.append(message)
    asyncio.run(middleware({"type": "http", "method": "POST", "headers": []}, receive, send))
    assert not called
    assert sent[0]["status"] == 413
    assert "1024" in json.loads(sent[1]["body"])["detail"]


def test_invalid_reference_is_not_silently_ignored(api):
    client, _ = api
    first, _ = make_backlit_recovery_pair()
    ok, image = cv2.imencode(".png", first)
    response = client.post("/inspect", files={"image": ("first.png", image.tobytes(), "image/png"),
                                             "reference_image": ("reference.png", b"corrupt", "image/png")})
    assert response.status_code == 400
    assert "invalid reference" in response.json()["detail"]
    assert "job_id" not in response.json()


def test_file_in_text_field_cannot_silently_reset_recapture_identity(api):
    client, _ = api
    first, _ = make_backlit_recovery_pair()
    ok, image = cv2.imencode(".png", first)
    response = client.post("/inspect", files={"image": ("first.png", image.tobytes(), "image/png"),
                                             "original_job_id": ("id.txt", b"invalid", "text/plain")})
    assert response.status_code == 400
    assert "must be text" in response.json()["detail"]
