"""Exercise the packaged Lambda handler through AWS's runtime emulator.

Requires an already running container on a native ARM64 host. This is not an
AWS account deployment or S3 test. Uses only generated inspection fixtures.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import time
import urllib.error
import urllib.request
import uuid


def invoke(endpoint, method, path):
    event = {"version": "2.0", "routeKey": "$default", "rawPath": path, "rawQueryString": "",
             "headers": {"host": "lambda-emulator.local"},
             "requestContext": {"accountId": "local-emulator", "apiId": "local", "domainName": "lambda-emulator.local",
                                "requestId": uuid.uuid4().hex, "routeKey": "$default", "stage": "$default",
                                "http": {"method": method, "path": path, "protocol": "HTTP/1.1",
                                         "sourceIp": "127.0.0.1", "userAgent": "loopsight-arm64-smoke"}},
             "isBase64Encoded": False}
    request = urllib.request.Request(endpoint, data=json.dumps(event).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=35) as response:
        result = json.load(response)
    if "statusCode" not in result:
        raise RuntimeError("Lambda handler failed: " + json.dumps(result)[:5000])
    return result["statusCode"], json.loads(result["body"])


def smoke(endpoint, revision):
    assert platform.machine() in {"aarch64", "arm64"}, "this verification requires a native ARM64 host"
    for attempt in range(20):
        try:
            status, version = invoke(endpoint, "GET", "/version")
            break
        except (urllib.error.URLError, ConnectionError):
            if attempt == 19:
                raise
            time.sleep(1)
    assert status == 200, version
    assert version["runtime_architecture"] in {"aarch64", "arm64"}, version
    assert version["opencv_version"].startswith("5."), version
    assert version["python_version"].startswith("3.13."), version
    assert version["measurement_contract"]["physical_units_available"] is False
    assert version["build_revision"] == revision
    assert invoke(endpoint, "GET", "/ready")[0] == 200
    status, created = invoke(endpoint, "POST", "/inspect/sample/water_turbid_fail")
    assert status == 200, created
    status, result = invoke(endpoint, "GET", "/jobs/" + created["job_id"])
    assert status == 200, result
    assert result["final_decision"]["decision"] == "FAIL", result["final_decision"]
    assert result["provenance"]["execution_mode"] == "synthetic_benchmark"
    assert invoke(endpoint, "GET", "/jobs/never-created-arm64-smoke")[0] == 404
    return {"status": "passed", "scope": "native_arm64_lambda_container_emulator",
            "host_architecture": platform.machine(), "image_runtime_architecture": version["runtime_architecture"],
            "python_version": version["python_version"], "opencv_version": version["opencv_version"],
            "build_revision": revision, "synthetic_inspection_decision": "FAIL", "unknown_job_status": 404,
            "aws_account_deployed": False, "s3_runtime_verified": False, "physical_accuracy_validated": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:9000/2015-03-31/functions/function/invocations")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = smoke(args.endpoint, args.revision)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
    except Exception as error:
        if os.environ.get("GITHUB_ACTIONS"):
            message = f"{type(error).__name__}: {error}".replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            print("::error title=Native ARM64 Lambda smoke::" + message[:6000])
        raise
