"""Shared, bounded S3 job/session persistence. No local fallback on cloud errors."""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
import time
import zipfile

import cv2
import numpy as np

from capture_sessions import CaptureSession, CaptureSessionError, MAX_ENTRY_BYTES, POLICY_VERSION, frame_digest

MAX_OBJECT_BYTES = MAX_ENTRY_BYTES + 128 * 1024
MAX_JOB_BYTES = 6 * 1024 * 1024
JOB_ID = re.compile(r"[0-9a-f]{32}")


class StorageUnavailable(RuntimeError):
    """A result is not durably available; callers must return a service error."""


class S3Objects:
    def __init__(self, bucket: str, client=None, prefix="loopsight/v1"):
        if not bucket or not re.fullmatch(r"[A-Za-z0-9/_-]+", prefix) or ".." in prefix:
            raise ValueError("invalid evidence bucket or object prefix")
        if client is None:
            import boto3
            from botocore.config import Config
            client = boto3.client("s3", config=Config(connect_timeout=3, read_timeout=5,
                                                      retries={"mode": "standard", "total_max_attempts": 2}))
        self.client, self.bucket, self.prefix = client, bucket, prefix.strip("/")

    def key(self, kind, job_id):
        if not JOB_ID.fullmatch(job_id):
            raise ValueError("invalid job identifier")
        return f"{self.prefix}/{kind}/{job_id}"

    def put(self, key, body, content_type, expires_at):
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type,
                                   CacheControl="private, no-store", ServerSideEncryption="AES256",
                                   Metadata={"expires-at": str(expires_at), "sha256": hashlib.sha256(body).hexdigest()})
        except Exception as error:
            raise StorageUnavailable("evidence storage write failed") from error

    def get(self, key, maximum, now):
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except Exception as error:
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if code in {"NoSuchKey", "NotFound", "404"}:
                return None
            raise StorageUnavailable("evidence storage read failed") from error
        stream = response["Body"]
        try:
            metadata = response.get("Metadata", {})
            expiry = float(metadata["expires-at"])
            if not math.isfinite(expiry):
                raise ValueError("invalid expiry")
            if expiry <= now:
                # Application access expires immediately; S3 lifecycle deletes later.
                raise CaptureSessionError("evidence expired; start a new inspection", 410)
            if response.get("ContentLength", maximum + 1) > maximum:
                raise ValueError("oversized stored object")
            body = stream.read(maximum + 1)
            if len(body) > maximum or hashlib.sha256(body).hexdigest() != metadata.get("sha256"):
                raise ValueError("object integrity check failed")
            return body, expiry
        except CaptureSessionError:
            raise
        except Exception as error:
            raise StorageUnavailable("stored evidence failed its integrity check") from error
        finally:
            stream.close()


class S3CaptureSessionStore:
    def __init__(self, objects: S3Objects, ttl_seconds=1800, clock=time.time):
        if not 60 <= ttl_seconds <= 86400:
            raise ValueError("unsupported capture TTL")
        self.objects, self.ttl_seconds, self.clock = objects, ttl_seconds, clock

    def save(self, job_id, frame, reference, metadata, second_frame=None):
        metadata = {**metadata, "policy_version": POLICY_VERSION}
        output = io.BytesIO()
        total = 0
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as bundle:
            for name, image, digest_name in [("first.png", frame, "frame_sha256"),
                                              ("reference.png", reference, "reference_sha256"),
                                              ("second.png", second_frame, "second_frame_sha256")]:
                if image is None:
                    continue
                ok, encoded = cv2.imencode(".png", image)
                if not ok:
                    raise StorageUnavailable("capture encoding failed")
                total += len(encoded)
                if total > MAX_ENTRY_BYTES:
                    raise CaptureSessionError("capture exceeds the storage limit", 413)
                bundle.writestr(name, encoded.tobytes())
                metadata[digest_name] = frame_digest(image)
            encoded_metadata = json.dumps(metadata, allow_nan=False).encode()
            if len(encoded_metadata) > 64 * 1024:
                raise StorageUnavailable("capture metadata exceeds its limit")
            bundle.writestr("session.json", encoded_metadata)
        expires_at = self.clock() + self.ttl_seconds
        self.objects.put(self.objects.key("captures", job_id), output.getvalue(), "application/zip", expires_at)
        return expires_at

    def load(self, job_id):
        if not JOB_ID.fullmatch(job_id):
            raise CaptureSessionError("capture session not found", 404)
        stored = self.objects.get(self.objects.key("captures", job_id), MAX_OBJECT_BYTES, self.clock())
        if stored is None:
            raise CaptureSessionError("capture session not found; start a new inspection", 404)
        body, expires_at = stored
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as bundle:
                names = bundle.namelist()
                if len(names) != len(set(names)) or not {"first.png", "session.json"} <= set(names):
                    raise ValueError("invalid capture manifest")
                if set(names) - {"first.png", "reference.png", "second.png", "session.json"}:
                    raise ValueError("unexpected bundle contents")
                if sum(item.file_size for item in bundle.infolist()) > MAX_OBJECT_BYTES:
                    raise ValueError("capture expansion exceeds its limit")
                metadata = json.loads(bundle.read("session.json"))
                if metadata["policy_version"] != POLICY_VERSION:
                    raise CaptureSessionError("the inspection policy changed; start a new inspection", 409)
                frames = []
                for name, digest_name in [("first.png", "frame_sha256"), ("reference.png", "reference_sha256"),
                                          ("second.png", "second_frame_sha256")]:
                    if name not in names:
                        frames.append(None)
                        continue
                    frame = cv2.imdecode(np.frombuffer(bundle.read(name), np.uint8), cv2.IMREAD_COLOR)
                    if frame is None or max(frame.shape[:2]) > 2048 or frame_digest(frame) != metadata[digest_name]:
                        raise ValueError("capture pixel integrity check failed")
                    frames.append(frame)
            return CaptureSession(frames[0], frames[1], metadata, expires_at, frames[2])
        except CaptureSessionError:
            raise
        except Exception as error:
            raise StorageUnavailable("stored capture bundle failed its integrity check") from error


class S3JobStore:
    def __init__(self, objects: S3Objects, ttl_seconds=86400, clock=time.time):
        if not 60 <= ttl_seconds <= 86400:
            raise ValueError("unsupported job TTL")
        self.objects, self.ttl_seconds, self.clock = objects, ttl_seconds, clock

    def save(self, job_id, result):
        body = json.dumps(result, allow_nan=False, separators=(",", ":")).encode()
        if len(body) > MAX_JOB_BYTES:
            raise StorageUnavailable("inspection result exceeds its storage limit")
        self.objects.put(self.objects.key("jobs", job_id), body, "application/json", self.clock() + self.ttl_seconds)

    def get(self, job_id):
        if not JOB_ID.fullmatch(job_id):
            return None
        stored = self.objects.get(self.objects.key("jobs", job_id), MAX_JOB_BYTES, self.clock())
        if stored is None:
            return None
        try:
            return json.loads(stored[0])
        except Exception as error:
            raise StorageUnavailable("stored result is invalid") from error


def create_capture_store():
    import os
    from capture_sessions import SqliteCaptureSessionStore
    ttl = int(os.environ.get("LOOPSIGHT_CAPTURE_TTL_SECONDS", "1800"))
    bucket = os.environ.get("LOOPSIGHT_EVIDENCE_BUCKET", "").strip()
    if bucket:
        return S3CaptureSessionStore(S3Objects(bucket), ttl_seconds=ttl)
    path = os.environ.get("LOOPSIGHT_CAPTURE_DB_PATH") or os.environ.get("LOOPSIGHT_SQLITE_PATH") or "/tmp/loopsight_jobs.sqlite3"
    return SqliteCaptureSessionStore(path, ttl_seconds=ttl)
