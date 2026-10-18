"""
LoopSight job storage: explicit S3 or DynamoDB, otherwise local SQLite.

Implementations:
  - InMemoryJobStore — wraps the in-memory JOBS dict (fast, zero-config default
    with SQLite write-through at LOOPSIGHT_SQLITE_PATH).
  - S3JobStore — shared encrypted objects, size limits and application TTL.
  - DynamoJobStore   — uses boto3 + DYNAMO_TABLE_NAME when AWS credentials are
    resolvable.
"""

from __future__ import annotations

import json
import os
import logging
import contextlib
import sqlite3
import time
from capture_sessions import CaptureSessionError
from pathlib import Path
from typing import Dict, Optional, Protocol

from cloud_storage import S3JobStore, S3Objects, StorageUnavailable

logger = logging.getLogger(__name__)


class JobStore(Protocol):
    def save(self, job_id: str, result: dict) -> None:
        ...

    def get(self, job_id: str) -> Optional[dict]:
        ...


class InMemoryJobStore:
    """Legacy name for bounded SQLite persistence; disk is authoritative on reads."""
    def __init__(self, backing=None, sqlite_path=None, *, ttl_seconds=86400, max_jobs=100, clock=time.time):
        self._store = backing if backing is not None else {}
        self._sqlite_path = sqlite_path or os.environ.get("LOOPSIGHT_SQLITE_PATH", "/tmp/loopsight_jobs.sqlite3")
        if not 60 <= ttl_seconds <= 86400 or not 1 <= max_jobs <= 100:
            raise ValueError("invalid local job retention limits")
        self.ttl_seconds, self.max_jobs, self.clock = ttl_seconds, max_jobs, clock
        try:
            Path(self._sqlite_path).parent.mkdir(parents=True, exist_ok=True)
            with contextlib.closing(sqlite3.connect(self._sqlite_path, timeout=5)) as conn, conn:
                conn.execute("CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, expires_at REAL)")
                columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
                if "expires_at" not in columns:
                    conn.execute("ALTER TABLE jobs ADD COLUMN expires_at REAL")
                conn.execute("UPDATE jobs SET expires_at = COALESCE(CAST(strftime('%s', created_at) AS REAL), ?) + ? WHERE expires_at IS NULL",
                             (self.clock(), self.ttl_seconds))
        except (sqlite3.Error, OSError) as error:
            raise StorageUnavailable("local job storage is unavailable") from error

    def save(self, job_id, result):
        try:
            payload = json.dumps(result, allow_nan=False)
            if len(payload.encode()) > 6 * 1024 * 1024:
                raise StorageUnavailable("inspection result exceeds the storage limit")
            now = self.clock()
            with contextlib.closing(sqlite3.connect(self._sqlite_path, timeout=5)) as conn, conn:
                conn.execute("DELETE FROM jobs WHERE expires_at <= ?", (now,))
                conn.execute("INSERT OR REPLACE INTO jobs (job_id, payload, expires_at) VALUES (?, ?, ?)",
                             (job_id, payload, now + self.ttl_seconds))
                while True:
                    count, size = conn.execute("SELECT COUNT(*), COALESCE(SUM(LENGTH(payload)), 0) FROM jobs").fetchone()
                    if count <= self.max_jobs and size <= 128 * 1024 * 1024:
                        break
                    conn.execute("DELETE FROM jobs WHERE job_id = (SELECT job_id FROM jobs ORDER BY created_at, rowid LIMIT 1)")
        except StorageUnavailable:
            raise
        except Exception as error:
            raise StorageUnavailable("local job storage write failed") from error

    def get(self, job_id):
        try:
            expired = False
            with contextlib.closing(sqlite3.connect(self._sqlite_path, timeout=5)) as conn, conn:
                row = conn.execute("SELECT payload, expires_at FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
                if row is None:
                    return None
                if row[1] <= self.clock():
                    expired = True
                    conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            if expired:
                raise CaptureSessionError("inspection result expired; start a new inspection", 410)
            return json.loads(row[0])
        except CaptureSessionError:
            raise
        except Exception as error:
            raise StorageUnavailable("local job storage read failed") from error

    @property
    def store(self):
        # Compatibility only. Results are intentionally not duplicated in RAM.
        return self._store


class DynamoJobStore:
    """DynamoDB-backed store. Explicitly selected; outages are surfaced without local fallback."""

    def __init__(self, table_name: str):
        self.table_name = table_name
        import boto3  # type: ignore

        self._dynamo = boto3.resource("dynamodb")
        self._table = self._dynamo.Table(table_name)
        try:
            self._table.load()
        except Exception as e:
            raise StorageUnavailable("configured DynamoDB table is unavailable") from e

    def save(self, job_id: str, result: dict) -> None:
        try:
            import datetime
            from decimal import Decimal

            # Convert floats to Decimal for DynamoDB resource compatibility
            serialized = json.dumps(result, allow_nan=False)
            if len(serialized.encode()) > 350 * 1024:
                raise StorageUnavailable("DynamoDB result too large; configure S3 job storage")
            clean_payload = json.loads(serialized, parse_float=Decimal)
            self._table.put_item(
                Item={
                    "job_id": job_id,
                    "result": clean_payload,
                    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }
            )
        except Exception as e:
            raise StorageUnavailable("DynamoDB job storage write failed") from e

    def get(self, job_id: str) -> Optional[dict]:
        try:
            resp = self._table.get_item(Key={"job_id": job_id})
            item = resp.get("Item")
            if item is None:
                return None
            raw = item.get("result")
            return json.loads(json.dumps(raw, default=float))
        except Exception as e:
            raise StorageUnavailable("DynamoDB job storage read failed") from e


def create_job_store(backing_dict: Optional[Dict[str, dict]] = None) -> JobStore:
    """Explicit cloud configuration never silently falls back to local storage."""
    bucket = os.environ.get("LOOPSIGHT_EVIDENCE_BUCKET", "").strip()
    if bucket:
        return S3JobStore(S3Objects(bucket), ttl_seconds=int(os.environ.get("LOOPSIGHT_JOB_TTL_SECONDS", "86400")))
    table_name = os.environ.get("DYNAMO_TABLE_NAME", "").strip()
    if table_name:
        try:
            return DynamoJobStore(table_name)
        except StorageUnavailable:
            raise
        except Exception as error:
            raise StorageUnavailable("configured DynamoDB is unavailable") from error
    return InMemoryJobStore(backing_dict)
