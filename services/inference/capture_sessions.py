"""Bounded, expiring capture persistence for workers sharing a SQLite file.

SQLite survives a local worker restart. Separate cloud instances need a shared
filesystem or another session-store implementation; /tmp is not cross-instance storage.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
import time

import cv2
import numpy as np

POLICY_VERSION = "image-space-v1"
MAX_ENTRY_BYTES = 48 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024


class CaptureSessionError(ValueError):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def frame_digest(frame: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(str(frame.shape).encode("ascii"))
    digest.update(frame.tobytes())
    return digest.hexdigest()


@dataclass
class CaptureSession:
    frame: np.ndarray
    reference: np.ndarray | None
    metadata: dict
    expires_at: float
    second_frame: np.ndarray | None = None


class SqliteCaptureSessionStore:
    def __init__(self, path: str, ttl_seconds: int = 1800, max_sessions: int = 100, clock=time.time):
        if not 60 <= ttl_seconds <= 86400 or not 1 <= max_sessions <= 100:
            raise ValueError("capture session limits are outside supported bounds")
        self.path = path
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self.clock = clock
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS capture_sessions (
                job_id TEXT PRIMARY KEY, frame BLOB NOT NULL, reference BLOB,
                metadata TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL,
                second_frame BLOB
            )""")
            columns = {row[1] for row in conn.execute("PRAGMA table_info(capture_sessions)")}
            if "second_frame" not in columns:
                conn.execute("ALTER TABLE capture_sessions ADD COLUMN second_frame BLOB")

    def _connect(self):
        return sqlite3.connect(self.path, timeout=5)

    @staticmethod
    def _encode(frame):
        if frame is None:
            return None
        ok, encoded = cv2.imencode(".png", frame)
        if not ok:
            raise CaptureSessionError("could not preserve the first capture", 503)
        return encoded.tobytes()

    def save(self, job_id: str, frame: np.ndarray, reference: np.ndarray | None, metadata: dict,
             second_frame: np.ndarray | None = None) -> float:
        image = self._encode(frame)
        reference_image = self._encode(reference)
        second_image = self._encode(second_frame)
        if len(image) + len(reference_image or b"") + len(second_image or b"") > MAX_ENTRY_BYTES:
            raise CaptureSessionError("capture exceeds the session storage limit", 413)
        now = self.clock()
        expires_at = now + self.ttl_seconds
        metadata = {**metadata, "policy_version": POLICY_VERSION, "frame_sha256": frame_digest(frame)}
        if reference is not None:
            metadata["reference_sha256"] = frame_digest(reference)
        if second_frame is not None:
            metadata["second_frame_sha256"] = frame_digest(second_frame)
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM capture_sessions WHERE expires_at <= ?", (now,))
            conn.execute("INSERT OR REPLACE INTO capture_sessions "
                         "(job_id, frame, reference, metadata, created_at, expires_at, second_frame) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (job_id, image, reference_image, json.dumps(metadata), now, expires_at, second_image))
            while True:
                count, size = conn.execute(
                    "SELECT COUNT(*), COALESCE(SUM(LENGTH(frame) + COALESCE(LENGTH(reference), 0) + COALESCE(LENGTH(second_frame), 0)), 0) FROM capture_sessions"
                ).fetchone()
                if count <= self.max_sessions and size <= MAX_TOTAL_BYTES:
                    break
                conn.execute("DELETE FROM capture_sessions WHERE job_id = ("
                             "SELECT job_id FROM capture_sessions ORDER BY created_at, rowid LIMIT 1)")
        return expires_at

    def load(self, job_id: str) -> CaptureSession:
        with closing(self._connect()) as conn, conn:
            row = conn.execute("SELECT frame, reference, metadata, expires_at, second_frame FROM capture_sessions WHERE job_id = ?",
                               (job_id,)).fetchone()
            if row is None:
                raise CaptureSessionError("capture session not found; start a new inspection", 404)
            if row[3] <= self.clock():
                conn.execute("DELETE FROM capture_sessions WHERE job_id = ?", (job_id,))
                expired = True
            else:
                expired = False
        if expired:
            raise CaptureSessionError("capture session expired; start a new inspection", 410)
        metadata = json.loads(row[2])
        if metadata.get("policy_version") != POLICY_VERSION:
            raise CaptureSessionError("the inspection policy changed; start a new inspection", 409)
        frame = cv2.imdecode(np.frombuffer(row[0], np.uint8), cv2.IMREAD_COLOR)
        reference = cv2.imdecode(np.frombuffer(row[1], np.uint8), cv2.IMREAD_COLOR) if row[1] else None
        second_frame = cv2.imdecode(np.frombuffer(row[4], np.uint8), cv2.IMREAD_COLOR) if row[4] else None
        if frame is None or frame_digest(frame) != metadata["frame_sha256"]:
            raise CaptureSessionError("stored capture failed its integrity check", 503)
        if row[1] and (reference is None or frame_digest(reference) != metadata.get("reference_sha256")):
            raise CaptureSessionError("stored reference failed its integrity check", 503)
        if row[4] and (second_frame is None or frame_digest(second_frame) != metadata.get("second_frame_sha256")):
            raise CaptureSessionError("stored second capture failed its integrity check", 503)
        return CaptureSession(frame, reference, metadata, row[3], second_frame)


def validate_capture_pair(first: np.ndarray, second: np.ndarray) -> tuple[np.ndarray, dict]:
    """Check alignment/appearance, not physical sample identity or acquisition truth."""
    if frame_digest(first) == frame_digest(second):
        raise CaptureSessionError("the second image duplicates the first; capture a new photo")
    h, w = first.shape[:2]
    h2, w2 = second.shape[:2]
    if min(h, w, h2, w2) < 64:
        raise CaptureSessionError("captures must be at least 64 pixels per side")
    if abs((w2 / h2) / (w / h) - 1) > 0.05:
        raise CaptureSessionError("capture aspect ratios differ; keep the same target and framing")
    # Analyze in a bounded common coordinate space; retain the original data for storage.
    scale = min(1.0, 512 / max(h, w))
    size = (max(16, round(w * scale)), max(16, round(h * scale)))
    gray1 = cv2.resize(cv2.cvtColor(first, cv2.COLOR_BGR2GRAY), size).astype(np.float32)
    gray2 = cv2.resize(cv2.cvtColor(second, cv2.COLOR_BGR2GRAY), size).astype(np.float32)
    if min(float(gray1.std()), float(gray2.std())) < 2:
        raise CaptureSessionError("insufficient image detail to align captures; improve focus and lighting")
    gray1 = (gray1 - gray1.mean()) / gray1.std()
    gray2 = (gray2 - gray2.mean()) / gray2.std()
    window = cv2.createHanningWindow(size, cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(gray1, gray2, window)
    if not np.isfinite([dx, dy, response]).all() or response < 0.25:
        raise CaptureSessionError("captures could not be aligned; retain the same sample and target")
    if abs(dx) > size[0] * 0.15 or abs(dy) > size[1] * 0.15:
        raise CaptureSessionError("the target moved too far between captures; keep the camera steady")
    matrix = np.float32([[1, 0, -dx], [0, 1, -dy]])
    aligned = cv2.warpAffine(gray2, matrix, size)
    valid = cv2.warpAffine(np.ones(gray2.shape, np.uint8), matrix, size, flags=cv2.INTER_NEAREST) > 0
    correlation = float(np.corrcoef(gray1[valid], aligned[valid])[0, 1])
    overlap = float(valid.mean())
    if not np.isfinite(correlation) or correlation < 0.65 or overlap < 0.75:
        raise CaptureSessionError("capture appearance is inconsistent; keep the same sample and checkerboard")
    full_size_second = cv2.resize(second, (w, h))
    full_matrix = np.float32([[1, 0, -dx / scale], [0, 1, -dy / scale]])
    aligned_second = cv2.warpAffine(full_size_second, full_matrix, (w, h), borderMode=cv2.BORDER_REFLECT_101)
    # A common crop avoids treating interpolated border pixels as new evidence.
    margin_x = int(np.ceil(abs(dx / scale))) + 2
    margin_y = int(np.ceil(abs(dy / scale))) + 2
    aligned_second = aligned_second[margin_y:h-margin_y, margin_x:w-margin_x]
    return aligned_second, {
        "accepted": True, "scope": "appearance_and_translation_consistency_only",
        "translation_px": [round(dx / scale, 3), round(dy / scale, 3)],
        "correlation": round(correlation, 4), "overlap": round(overlap, 4),
        "crop": [margin_x, margin_y, w - 2 * margin_x, h - 2 * margin_y],
        "limitations": "Visual agreement does not prove physical sample identity or that a new photo was taken.",
    }
