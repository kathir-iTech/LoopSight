"""
Phase E — input hardening. Prove every malformed/malicious `/inspect` request
returns a STRUCTURED 4xx error, never a 500, and that concurrent requests to
the same /inspect route don't crash or corrupt results.

Covers: corrupt bytes, truncated image, non-image bytes with an image
extension, empty upload, oversized upload (> MAX_UPLOAD_BYTES), missing image
field, and concurrent submissions.

Run: python -m pytest tests/test_input_hardening.py -v -s
"""

import sys
import os

# Blank the Gemini key BEFORE importing main (keeps UNCERTAIN path on the fast
# deterministic mock through the REAL CV pipeline).
os.environ["GEMINI_API_KEY"] = ""

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import cv2

from fastapi.testclient import TestClient
from main import app, MAX_UPLOAD_BYTES  # noqa: F401

from tests.synthetic import make_clean_square

# Keep the TestClient's server running for the whole module so the concurrent
# test can fire requests through the same live client without per-request
# enter/exit (which is not thread-safe and hangs under contention).
client = TestClient(app)
client.__enter__()


def _png_bytes() -> bytes:
    ok, buf = cv2.imencode(".png", make_clean_square())
    assert ok
    return buf.tobytes()


def _post(files, data=None):
    """Return the raw response for a /inspect upload (default profile)."""
    if data is None:
        data = {"inspection_profile": "fdm_print_surface_v1"}
    return client.post("/inspect", files=files, data=data)


def _assert_structured_error(resp, expected_status, detail_substring):
    """The error is structured (JSON body with a 'detail'), not a bare 500."""
    assert resp.status_code == expected_status, (
        f"expected {expected_status}, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert "detail" in body, f"expected structured error, got {body}"
    if detail_substring:
        assert detail_substring in body["detail"], f"detail={body['detail']!r}"


def test_corrupt_bytes_reject_with_400():
    resp = _post({"image": ("corrupt.png", b"\x00\x01\x02\xff\xfe garbage", "image/png")})
    _assert_structured_error(resp, 400, "decode")


def test_truncated_image_reject_with_400():
    full = _png_bytes()
    resp = _post({"image": ("trunc.png", full[: len(full) // 2], "image/png")})
    _assert_structured_error(resp, 400, "decode")


def test_non_image_with_image_extension_reject_with_400():
    # Valid non-image bytes (e.g. a text file) smuggled under a .png name.
    resp = _post({"image": ("fake.png", "this is not an image at all".encode(), "image/png")})
    _assert_structured_error(resp, 400, "decode")


def test_empty_upload_reject_with_400():
    resp = _post({"image": ("empty.png", b"", "image/png")})
    _assert_structured_error(resp, 400, "empty")


def test_missing_image_field_reject_with_400():
    # No 'image'/'file' field at all.
    resp = client.post(
        "/inspect",
        data={"inspection_profile": "fdm_print_surface_v1"},
    )
    _assert_structured_error(resp, 400, "missing image file")


def test_oversized_upload_reject_with_413():
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (MAX_UPLOAD_BYTES + 1)
    resp = _post({"image": ("huge.png", big, "image/png")})
    _assert_structured_error(resp, 413, "too large")


def test_unknown_profile_reject_with_400():
    resp = _post(
        {"image": ("clean.png", _png_bytes(), "image/png")},
        data={"inspection_profile": "does_not_exist"},
    )
    _assert_structured_error(resp, 400, "unknown inspection_profile")


def test_valid_image_still_succeeds():
    # Control: the hardening didn't break the happy path.
    resp = _post({"image": ("clean.png", _png_bytes(), "image/png")})
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    assert "job_id" in resp.json()
    job = client.get(f"/jobs/{resp.json()['job_id']}")
    assert job.status_code == 200


def test_concurrent_requests_all_succeed_and_are_independent():
    """Fire several /inspect calls through one shared TestClient concurrently;
    every one must return a real job_id and each job must be retrievable — no
    cross-contamination or crash."""
    import threading

    results = [None] * 6
    errors = [None] * 6

    def worker(i):
        try:
            files = {"image": ("c.png", _png_bytes(), "image/png")}
            r = client.post(
                "/inspect",
                files=files,
                data={"inspection_profile": "fdm_print_surface_v1"},
            )
            results[i] = r
        except Exception as e:  # pragma: no cover
            errors[i] = e

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    # Join with a timeout so a regression fails cleanly instead of hanging.
    for t in threads:
        t.join(timeout=30)
    assert all(not t.is_alive() for t in threads), "a concurrent request thread did not finish"

    for i, r in enumerate(results):
        assert errors[i] is None, f"thread {i} raised: {errors[i]}"
        assert r is not None and r.status_code == 200, f"thread {i}: {r!r}"
        job_id = r.json()["job_id"]
        job = client.get(f"/jobs/{job_id}")
        assert job.status_code == 200, f"job {job_id} not retrievable: {job.text}"


TESTS = [
    test_corrupt_bytes_reject_with_400,
    test_truncated_image_reject_with_400,
    test_non_image_with_image_extension_reject_with_400,
    test_empty_upload_reject_with_400,
    test_missing_image_field_reject_with_400,
    test_oversized_upload_reject_with_413,
    test_unknown_profile_reject_with_400,
    test_valid_image_still_succeeds,
    test_concurrent_requests_all_succeed_and_are_independent,
]

if __name__ == "__main__":
    passed, failed = 0, 0
    for t in TESTS:
        try:
            print(f"RUN  {t.__name__}")
            t()
            print(f"PASS {t.__name__}\n")
            passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}\n")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"--- {passed} passed, {failed} failed out of {len(TESTS)} ---")
    sys.exit(1 if failed else 0)