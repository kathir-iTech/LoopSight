"""
LoopSight v2 — JobStore abstraction with InMemory, SQLite persistent fallback, and DynamoDB.

Implementations:
  - InMemoryJobStore — wraps the in-memory JOBS dict (fast, zero-config default
    with optional SQLite write-through when LOOP_SQLITE_PATH is set).
  - SqliteJobStore   — lightweight persistent store using Python's built-in
    sqlite3 so jobs survive worker restarts even without AWS credentials.
  - DynamoJobStore   — uses boto3 + DYNAMO_TABLE_NAME when AWS credentials are
    resolvable.
"""

from __future__ import annotations

import json
import os
import logging
import contextlib
import sqlite3
from pathlib import Path
from typing import Dict, Optional, Protocol

logger = logging.getLogger(__name__)


class JobStore(Protocol):
    def save(self, job_id: str, result: dict) -> None:
        ...

    def get(self, job_id: str) -> Optional[dict]:
        ...


class InMemoryJobStore:
    """Wraps the existing JOBS dict, with optional SQLite write-through so
    multi-worker local or container runs never lose jobs."""

    def __init__(self, backing: Optional[Dict[str, dict]] = None, sqlite_path: Optional[str] = None):
        self._store: Dict[str, dict] = backing if backing is not None else {}
        self._sqlite_path = sqlite_path or os.environ.get("LOOPSIGHT_SQLITE_PATH", "/tmp/loopsight_jobs.sqlite3")
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        if not self._sqlite_path:
            return
        try:
            Path(self._sqlite_path).parent.mkdir(parents=True, exist_ok=True)
            with contextlib.closing(sqlite3.connect(self._sqlite_path, timeout=5.0)) as conn, conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
                )
        except Exception as e:
            logger.debug(f"[InMemoryJobStore] sqlite write-through disabled: {e}")
            self._sqlite_path = ""

    def save(self, job_id: str, result: dict) -> None:
        self._store[job_id] = result
        if self._sqlite_path:
            try:
                payload = json.dumps(result, default=str)
                with contextlib.closing(sqlite3.connect(self._sqlite_path, timeout=5.0)) as conn, conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO jobs (job_id, payload) VALUES (?, ?)",
                        (job_id, payload),
                    )
            except Exception as e:
                logger.debug(f"[InMemoryJobStore] sqlite write-through save failed: {e}")

    def get(self, job_id: str) -> Optional[dict]:
        if job_id in self._store:
            return self._store[job_id]
        if self._sqlite_path:
            try:
                with contextlib.closing(sqlite3.connect(self._sqlite_path, timeout=5.0)) as conn, conn:
                    row = conn.execute("SELECT payload FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
                    if row and row[0]:
                        loaded = json.loads(row[0])
                        self._store[job_id] = loaded
                        return loaded
            except Exception as e:
                logger.debug(f"[InMemoryJobStore] sqlite read failed: {e}")
        return None

    @property
    def store(self) -> Dict[str, dict]:
        """Expose backing dict for health checks / legacy access (e.g., len)."""
        return self._store


class DynamoJobStore:
    """DynamoDB-backed store. Only constructed when credentials are resolvable."""

    def __init__(self, table_name: str):
        self.table_name = table_name
        import boto3  # type: ignore

        self._dynamo = boto3.resource("dynamodb")
        self._table = self._dynamo.Table(table_name)
        try:
            self._table.load()
        except Exception as e:
            logger.warning(
                f"[DynamoJobStore] table '{table_name}' not accessible at startup: {e} — runtime saves will log and degrade gracefully"
            )

    def save(self, job_id: str, result: dict) -> None:
        try:
            import datetime
            from decimal import Decimal

            # Convert floats to Decimal for DynamoDB resource compatibility
            clean_payload = json.loads(json.dumps(result, default=str), parse_float=Decimal)
            self._table.put_item(
                Item={
                    "job_id": job_id,
                    "result": clean_payload,
                    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }
            )
        except Exception as e:
            logger.error(
                f"[DynamoJobStore] save failed for job_id={job_id} table={self.table_name}: {e} — request will not crash"
            )

    def get(self, job_id: str) -> Optional[dict]:
        try:
            resp = self._table.get_item(Key={"job_id": job_id})
            item = resp.get("Item")
            if item is None:
                return None
            raw = item.get("result")
            return json.loads(json.dumps(raw, default=float))
        except Exception as e:
            logger.error(f"[DynamoJobStore] get failed for job_id={job_id} table={self.table_name}: {e}")
            return None


def _credentials_available() -> bool:
    """Return True only if boto3 can resolve AWS credentials in this environment."""
    try:
        import boto3  # type: ignore

        session = boto3.Session()
        creds = session.get_credentials()
        return creds is not None
    except Exception as e:
        logger.debug(f"[storage] boto3 credential check failed: {e}")
        return False


def create_job_store(backing_dict: Optional[Dict[str, dict]] = None) -> JobStore:
    """Factory used by main.py at startup."""
    table_name = os.environ.get("DYNAMO_TABLE_NAME")
    if table_name and _credentials_available():
        try:
            logger.info(f"[storage] using DynamoJobStore table={table_name}")
            return DynamoJobStore(table_name)
        except Exception as e:
            logger.warning(
                f"[storage] failed to init DynamoJobStore table={table_name}: {e} — falling back to InMemoryJobStore"
            )
            return InMemoryJobStore(backing_dict)
    else:
        if table_name and not _credentials_available():
            logger.info("[storage] DYNAMO_TABLE_NAME set but no AWS credentials resolvable — using InMemoryJobStore")
        else:
            logger.info("[storage] using InMemoryJobStore (with SQLite write-through)")
        return InMemoryJobStore(backing_dict)
