"""
LoopSight — JobStore abstraction.

Phase 3: stop depending directly on the in-memory JOBS dict.
Two implementations:
  - InMemoryJobStore — wraps an in-memory dict (the existing JOBS dict),
    used whenever AWS credentials aren't configured. This stays the default.
  - DynamoJobStore — uses boto3 + DYNAMO_TABLE_NAME, only instantiated if
    AWS credentials are actually resolvable. Runtime DynamoDB failures are
    caught and logged rather than crashing the request.
"""

from __future__ import annotations

import os
import logging
from typing import Dict, Optional, Protocol

logger = logging.getLogger(__name__)


class JobStore(Protocol):
    def save(self, job_id: str, result: dict) -> None:
        ...

    def get(self, job_id: str) -> Optional[dict]:
        ...


class InMemoryJobStore:
    """Wraps the existing JOBS dict — the default when no AWS credentials."""

    def __init__(self, backing: Optional[Dict[str, dict]] = None):
        # Allow wrapping the existing global JOBS dict so behaviour is identical
        self._store: Dict[str, dict] = backing if backing is not None else {}

    def save(self, job_id: str, result: dict) -> None:
        self._store[job_id] = result

    def get(self, job_id: str) -> Optional[dict]:
        return self._store.get(job_id)

    @property
    def store(self) -> Dict[str, dict]:
        """Expose backing dict for health checks / legacy access (e.g., len)."""
        return self._store


class DynamoJobStore:
    """DynamoDB-backed store. Only constructed when credentials are resolvable.

    Table schema expectation (minimal):
      - partition key: job_id (String)
      - attribute: result (Map / JSON-serialised dict)
      - attribute: created_at (String, ISO timestamp, optional)

    If table doesn't exist or permissions are missing, calls are caught and
    logged rather than crashing the caller — the request still succeeds via
    the in-memory fallback path if the caller chooses to handle None.
    """

    def __init__(self, table_name: str):
        self.table_name = table_name
        # Lazy import so the module remains importable when boto3 isn't installed (local dev without AWS)
        import boto3  # type: ignore

        # Use resource for simpler put/get; fallback to client if resource not available
        self._dynamo = boto3.resource("dynamodb")
        self._table = self._dynamo.Table(table_name)
        # Quick liveness check: ensure table exists (describe). Don't fail constructor on error — just log.
        try:
            self._table.load()
        except Exception as e:
            logger.warning(f"[DynamoJobStore] table '{table_name}' not accessible at startup: {e} — runtime saves will log and degrade gracefully")

    def save(self, job_id: str, result: dict) -> None:
        try:
            # DynamoDB doesn't natively store arbitrary nested floats cleanly via resource's type serializer,
            # but boto3's resource does handle dicts with numbers/strings. Use a simple wrapper.
            import datetime

            self._table.put_item(
                Item={
                    "job_id": job_id,
                    "result": result,
                    "created_at": datetime.datetime.utcnow().isoformat() + "Z",
                }
            )
        except Exception as e:
            logger.error(f"[DynamoJobStore] save failed for job_id={job_id} table={self.table_name}: {e} — request will not crash, but job will not persist")
            # Do not raise — caller (main.py) will still have the in-memory copy only if we fallback.
            # For pure Dynamo mode, this means the GET will miss; the caller should handle that.
            # We intentionally don't re-raise so the POST can still return job_id (degraded).

    def get(self, job_id: str) -> Optional[dict]:
        try:
            resp = self._table.get_item(Key={"job_id": job_id})
            item = resp.get("Item")
            if item is None:
                return None
            # result was stored as a Map
            return item.get("result")  # type: ignore
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
    """
    Factory used by main.py at startup. Chooses Dynamo if and only if:
      - DYNAMO_TABLE_NAME is set, and
      - boto3.Session().get_credentials() is not None
    Otherwise returns InMemoryJobStore wrapping the provided backing dict.
    """
    table_name = os.environ.get("DYNAMO_TABLE_NAME")
    if table_name and _credentials_available():
        try:
            logger.info(f"[storage] using DynamoJobStore table={table_name}")
            return DynamoJobStore(table_name)
        except Exception as e:
            logger.warning(f"[storage] failed to init DynamoJobStore table={table_name}: {e} — falling back to InMemoryJobStore")
            return InMemoryJobStore(backing_dict)
    else:
        if table_name and not _credentials_available():
            logger.info("[storage] DYNAMO_TABLE_NAME set but no AWS credentials resolvable — using InMemoryJobStore")
        else:
            logger.info("[storage] using InMemoryJobStore (default, no AWS credentials required)")
        return InMemoryJobStore(backing_dict)
