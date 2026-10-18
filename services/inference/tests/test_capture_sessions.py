"""Synthetic regression checks for actual recapture transport and persistence."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

import main
from capture_sessions import CaptureSessionError, SqliteCaptureSessionStore, frame_digest, validate_capture_pair
from sample_frames import make_backlit_recovery_pair, make_structural_crack, make_glare_confounded_water
from storage import InMemoryJobStore


def png(frame):
    ok, data = cv2.imencode(".png", frame)
    assert ok
    return data.tobytes()


@pytest.fixture
def context(monkeypatch, tmp_path):
    clock = [time.time()]
    captures = SqliteCaptureSessionStore(str(tmp_path / "captures.db"), ttl_seconds=60, clock=lambda: clock[0])
    monkeypatch.setattr(main, "capture_store", captures)
    monkeypatch.setattr(main, "store", InMemoryJobStore({}, sqlite_path=str(tmp_path / "jobs.db")))
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("DEMO_MODE", "")
    with TestClient(main.app, raise_server_exceptions=False) as client:
        yield client, captures, clock, tmp_path


def inspect(client, frame, **fields):
    return client.post("/inspect", files={"image": ("capture.png", png(frame), "image/png")},
                       data={"inspection_profile": "water_turbidity_v1", **fields})


def initial(client):
    first, second = make_backlit_recovery_pair()
    response = inspect(client, first)
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]
    result = client.get("/jobs/" + job_id).json()
    assert result["final_decision"]["decision"] == "REVIEW"
    assert result["capture_session"]["can_recapture"] is True
    return job_id, result, first, second


def test_follow_up_keeps_the_original_first_pass_even_when_new_image_is_confident(context, monkeypatch):
    client, captures, _, directory = context
    parent, original, first, second = initial(client)
    # Simulate independent worker state; both stores must reload from disk.
    monkeypatch.setattr(main, "capture_store", SqliteCaptureSessionStore(captures.path))
    monkeypatch.setattr(main, "store", InMemoryJobStore({}, sqlite_path=str(directory / "jobs.db")))
    response = inspect(client, second, original_job_id=parent, lighting2="backlight")
    assert response.status_code == 200, response.text
    result = client.get("/jobs/" + response.json()["job_id"]).json()
    assert result["status"] == original["status"] == "UNCERTAIN"
    assert result["regions"] == original["regions"]
    assert result["frames"][0]["sha256"] == frame_digest(first)
    assert result["frames"][1]["sha256"] == frame_digest(second)
    assert result["frames"][0]["timestamp"] == original["frames"][0]["timestamp"]
    assert result["final_decision"]["decision"] == "PASS"
    assert result["acquisition"]["observations_used"] == 2
    assert result["acquisition"]["new_capture_used"] is True
    assert result["acquisition"]["parent_job_id"] == parent
    assert result["second_pass"]["evidence_source"] == "new_capture"
    assert result["capture_session"]["can_recapture"] is False


def test_capture_can_be_loaded_by_a_fresh_python_process(context):
    client, captures, _, _ = context
    parent, _, first, _ = initial(client)
    code = """import sys
sys.path.insert(0, sys.argv[1])
from capture_sessions import SqliteCaptureSessionStore, frame_digest
session = SqliteCaptureSessionStore(sys.argv[2]).load(sys.argv[3])
print(frame_digest(session.frame))
"""
    result = subprocess.run([sys.executable, "-I", "-c", code,
                             str(Path(main.__file__).parent), captures.path, parent],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == frame_digest(first)


@pytest.mark.parametrize("case", ["duplicate", "unrelated", "featureless", "different_aspect_ratio"])
def test_invalid_follow_up_does_not_create_a_verdict(context, case):
    client, _, _, _ = context
    parent, original, first, second = initial(client)
    images = {
        "duplicate": first,
        "unrelated": np.random.default_rng(123).integers(0, 255, first.shape, dtype=np.uint8),
        "featureless": np.full_like(first, 80),
        "different_aspect_ratio": second[:, :100],
    }
    response = inspect(client, images[case], original_job_id=parent, lighting2="backlight")
    assert response.status_code == 422, response.text
    assert "job_id" not in response.json()
    assert client.get("/jobs/" + parent).json() == original


def test_expired_capture_requires_a_fresh_inspection(context):
    client, _, clock, _ = context
    parent, _, _, second = initial(client)
    clock[0] += 61
    response = inspect(client, second, original_job_id=parent)
    assert response.status_code == 410
    assert "expired" in response.json()["detail"]


def test_unknown_parent_never_becomes_an_independent_inspection(context):
    client, _, _, _ = context
    _, second = make_backlit_recovery_pair()
    response = inspect(client, second, original_job_id="never-created")
    assert response.status_code == 404
    assert "job_id" not in response.json()


@pytest.mark.parametrize("fields,status", [
    ({"lighting2": "ambient"}, 422),
    ({"inspection_profile": "fdm_print_surface_v1"}, 409),
])
def test_follow_up_cannot_change_profile_or_repeat_declared_lighting(context, fields, status):
    client, _, _, _ = context
    parent, _, _, second = initial(client)
    assert inspect(client, second, original_job_id=parent, **fields).status_code == status


def test_bad_second_image_is_not_silently_ignored(context):
    client, _, _, _ = context
    first, _ = make_backlit_recovery_pair()
    response = client.post("/inspect", data={"inspection_profile": "water_turbidity_v1"}, files={
        "image": ("first.png", png(first), "image/png"),
        "image2": ("bad.png", b"not an image", "image/png"),
    })
    assert response.status_code == 400
    assert "second image" in response.json()["detail"]


def test_session_storage_failure_returns_an_error_instead_of_a_nonreplayable_job(context, monkeypatch):
    client, captures, _, _ = context
    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("storage unavailable")
    monkeypatch.setattr(captures, "save", fail)
    first, _ = make_backlit_recovery_pair()
    response = inspect(client, first)
    assert response.status_code == 503
    assert "job_id" not in response.json()


@pytest.mark.parametrize("frame,profile", [
    (make_backlit_recovery_pair()[0], "water_turbidity_v1"),
    (make_structural_crack(), "structural_crack_metrology_v1"),
])
def test_api_never_exposes_uncalibrated_physical_units(context, frame, profile):
    client, _, _, _ = context
    response = inspect(client, frame, inspection_profile=profile)
    assert response.status_code == 200, response.text
    result = client.get("/jobs/" + response.json()["job_id"]).json()
    contract = result["measurement_contract"]
    assert contract["physical_units_available"] is False
    assert contract["water_unit"] == "dimensionless"
    assert contract["crack_width_unit"] == "analysis_image_pixels"
    encoded = json.dumps(result)
    for forbidden in ["estimated_ntu", "who_tier", "crack_width_mm"]:
        assert forbidden not in encoded
    if profile == "structural_crack_metrology_v1":
        assert result["regions"][0]["evidence"]["crack_width_px"] >= 4


def test_same_image_enhancement_does_not_count_as_a_second_observation(context):
    client, _, _, _ = context
    response = inspect(client, make_glare_confounded_water())
    assert response.status_code == 200
    result = client.get("/jobs/" + response.json()["job_id"]).json()
    assert result["final_decision"]["decision"] == "REVIEW"
    assert result["acquisition"]["observations_used"] == 1
    assert result["second_pass"]["evidence_source"] == "same_image_processing"
    assert result["capture_session"]["can_recapture"] is True


def test_storage_capacity_evicts_oldest_capture(tmp_path):
    clock = [time.time()]
    captures = SqliteCaptureSessionStore(str(tmp_path / "bounded.db"), max_sessions=1, clock=lambda: clock[0])
    first, _ = make_backlit_recovery_pair()
    captures.save("old", first, None, {})
    clock[0] += 1
    captures.save("new", first, None, {})
    with pytest.raises(CaptureSessionError, match="not found"):
        captures.load("old")
    assert captures.load("new").metadata["frame_sha256"] == frame_digest(first)


def test_both_retained_captures_match_the_recorded_frames_and_expire(context):
    client, _, clock, _ = context
    parent, _, first, second = initial(client)
    response = inspect(client, second, original_job_id=parent)
    assert response.status_code == 200, response.text
    child = response.json()["job_id"]
    for index, expected in enumerate([first, second]):
        image = client.get(f"/jobs/{child}/captures/{index}")
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/png"
        assert image.headers["cache-control"] == "private, no-store"
        decoded = cv2.imdecode(np.frombuffer(image.content, np.uint8), cv2.IMREAD_COLOR)
        assert np.array_equal(decoded, expected)
    assert client.get(f"/jobs/{child}/captures/2").status_code == 404
    assert inspect(client, second, original_job_id=child).status_code == 409
    clock[0] += 61
    assert client.get(f"/jobs/{child}/captures/0").status_code == 410


def test_corrupt_retained_frame_is_not_used_for_a_follow_up(context):
    client, captures, _, _ = context
    parent, _, _, second = initial(client)
    with sqlite3.connect(captures.path) as connection:
        connection.execute("UPDATE capture_sessions SET frame = ? WHERE job_id = ?", (png(second), parent))
    response = inspect(client, second, original_job_id=parent)
    assert response.status_code == 503
    assert "integrity" in response.json()["detail"]
