"""S3 adapter contract tests. These do not claim a real AWS deployment."""
import io
import json
from types import SimpleNamespace

from botocore.exceptions import ClientError
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

import main
import storage
from capture_sessions import CaptureSessionError
from cloud_storage import S3Objects, S3CaptureSessionStore, S3JobStore, StorageUnavailable
from sample_frames import make_backlit_recovery_pair

ID = "a" * 32


class ObjectService:
    """Shared service state; clients/stores have no in-process job/frame cache."""
    def __init__(self):
        self.objects = {}
        self.fail_reads = self.fail_writes = False
        self.bodies = []

    def put_object(self, **request):
        if self.fail_writes:
            raise ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject")
        assert request["ServerSideEncryption"] == "AES256"
        assert request["CacheControl"] == "private, no-store"
        self.objects[request["Bucket"], request["Key"]] = dict(request)

    def get_object(self, **request):
        if self.fail_reads:
            raise ClientError({"Error": {"Code": "AccessDenied"}}, "GetObject")
        stored = self.objects.get((request["Bucket"], request["Key"]))
        if stored is None:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        stream = io.BytesIO(stored["Body"])
        self.bodies.append(stream)
        return {"Body": stream, "ContentLength": len(stored["Body"]), "Metadata": dict(stored["Metadata"])}


@pytest.fixture
def objects():
    service = ObjectService()
    return service, S3Objects("test-private-bucket", client=service)


def test_s3_capture_round_trip_across_store_instances_preserves_pixels(objects):
    service, first_client = objects
    frame, second = make_backlit_recovery_pair()
    original = S3CaptureSessionStore(first_client, clock=lambda: 100)
    original.save(ID, frame, second, {"profile": "water_turbidity_v1"}, second_frame=second)
    fresh = S3CaptureSessionStore(S3Objects("test-private-bucket", client=service), clock=lambda: 101)
    session = fresh.load(ID)
    assert np.array_equal(frame, session.frame)
    assert np.array_equal(second, session.reference)
    assert np.array_equal(second, session.second_frame)
    assert session.metadata["profile"] == "water_turbidity_v1"
    assert all(body.closed for body in service.bodies)


def test_s3_job_round_trip_and_unknown_id(objects):
    service, client = objects
    S3JobStore(client, clock=lambda: 100).save(ID, {"decision": "REVIEW", "score": 0.14})
    new = S3JobStore(S3Objects("test-private-bucket", client=service), clock=lambda: 101)
    assert new.get(ID) == {"decision": "REVIEW", "score": 0.14}
    assert new.get("b" * 32) is None
    assert new.get("../captures/" + ID) is None


def test_s3_expiry_is_enforced_before_lifecycle_deletion(objects):
    service, client = objects
    frame, _ = make_backlit_recovery_pair()
    S3CaptureSessionStore(client, ttl_seconds=60, clock=lambda: 100).save(ID, frame, None, {})
    with pytest.raises(CaptureSessionError) as error:
        S3CaptureSessionStore(client, clock=lambda: 160).load(ID)
    assert error.value.status_code == 410
    assert service.objects  # Lifecycle deletion may lag, but access is blocked.
    assert all(body.closed for body in service.bodies)


@pytest.mark.parametrize("fault", ["bytes", "digest", "expiry", "length"])
def test_s3_corrupt_metadata_or_content_never_returns_evidence(objects, fault):
    service, client = objects
    S3JobStore(client).save(ID, {"decision": "PASS"})
    stored = next(iter(service.objects.values()))
    if fault == "bytes": stored["Body"] = b'{}'
    if fault == "digest": stored["Metadata"]["sha256"] = "wrong"
    if fault == "expiry": stored["Metadata"]["expires-at"] = "nan"
    if fault == "length": stored["Body"] = b"x" * (7 * 1024 * 1024)
    with pytest.raises(StorageUnavailable):
        S3JobStore(client).get(ID)
    assert all(body.closed for body in service.bodies)


def test_s3_outage_is_not_mistaken_for_unknown_job(objects):
    service, client = objects
    service.fail_reads = True
    with pytest.raises(StorageUnavailable): S3JobStore(client).get(ID)
    service.fail_writes = True
    with pytest.raises(StorageUnavailable): S3JobStore(client).save(ID, {})


def test_configured_dynamo_outage_cannot_select_local_fallback(monkeypatch):
    monkeypatch.setenv("DYNAMO_TABLE_NAME", "configured-table")
    monkeypatch.delenv("LOOPSIGHT_EVIDENCE_BUCKET", raising=False)
    def unavailable(*args): raise StorageUnavailable("unavailable")
    monkeypatch.setattr(storage, "DynamoJobStore", unavailable)
    with pytest.raises(StorageUnavailable): storage.create_job_store({})


def test_cloud_recapture_uses_fresh_stores_and_no_local_cache(objects, monkeypatch):
    service, client = objects
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("DEMO_MODE", "")
    def new_worker():
        other = S3Objects("test-private-bucket", client=service)
        monkeypatch.setattr(main, "store", S3JobStore(other))
        monkeypatch.setattr(main, "capture_store", S3CaptureSessionStore(other))
    def upload(api, image, **fields):
        ok, data = cv2.imencode(".png", image)
        assert ok
        return api.post("/inspect", files={"image": ("capture.png", data.tobytes(), "image/png")},
                        data={"inspection_profile": "water_turbidity_v1", **fields})
    first, second = make_backlit_recovery_pair()
    with TestClient(main.app) as api:
        new_worker()
        parent = upload(api, first).json()["job_id"]
        original = api.get("/jobs/" + parent).json()
        new_worker()
        result = upload(api, second, original_job_id=parent)
        assert result.status_code == 200, result.text
        child = result.json()["job_id"]
        new_worker()
        result = api.get("/jobs/" + child).json()
        assert result["regions"] == original["regions"]
        assert result["final_decision"]["decision"] == "PASS"
        assert result["acquisition"]["observations_used"] == 2
        assert api.get(f"/jobs/{child}/captures/1").status_code == 200
        service.fail_reads = True
        assert api.get("/jobs/" + child).status_code == 503


def test_failed_job_write_returns_no_successful_job_id(objects, monkeypatch, tmp_path):
    service, client = objects
    service.fail_writes = True
    monkeypatch.setattr(main, "store", S3JobStore(client))
    monkeypatch.setattr(main, "capture_store", SimpleNamespace(save=lambda *a, **kw: 9999999999))
    monkeypatch.setenv("GEMINI_API_KEY", "")
    with TestClient(main.app, raise_server_exceptions=False) as api:
        response = api.post("/inspect/sample/water_turbid_fail")
        assert response.status_code == 503
        assert "job_id" not in response.json()


def test_local_results_expire_and_cache_cannot_bypass_expiry(tmp_path):
    clock = [100.0]
    local = storage.InMemoryJobStore({ID: {"decision": "PASS"}}, sqlite_path=str(tmp_path / "jobs.db"),
                                     ttl_seconds=60, clock=lambda: clock[0])
    local.save(ID, {"decision": "REVIEW"})
    assert local.get(ID)["decision"] == "REVIEW"
    clock[0] = 160
    with pytest.raises(CaptureSessionError) as error:
        local.get(ID)
    assert error.value.status_code == 410


def test_local_job_capacity_evicts_oldest_without_stale_cache(tmp_path):
    local = storage.InMemoryJobStore({}, sqlite_path=str(tmp_path / "jobs.db"), max_jobs=2)
    for i in range(3): local.save(str(i), {"decision": "REVIEW"})
    assert local.get("0") is None
    assert local.get("2") == {"decision": "REVIEW"}
