"""Validate deployment image selection without contacting AWS or Docker."""
import json
import os
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize("architecture,revision,success", [
    ("arm64", "a" * 40, True),
    ("amd64", "a" * 40, False),
    ("arm64", "b" * 40, False),
])
def test_ci_image_must_match_architecture_and_exact_revision_before_cloud_writes(tmp_path, architecture, revision, success):
    directory = tmp_path / "bin"
    directory.mkdir()
    log = tmp_path / "commands.jsonl"
    code = '''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
tool=Path(sys.argv[0]).name
args=sys.argv[1:]
with open(os.environ['TEST_COMMAND_LOG'],'a') as output:
    output.write(json.dumps({'tool':tool,'args':args})+'\\n')
if tool=='git' and args[0]=='rev-parse':print('a'*40)
if tool=='aws' and args[:2]==['sts','get-caller-identity']:print('123456789012')
if tool=='aws' and args[:2]==['ecr','get-login-password']:print('test-only-password')
if tool=='aws' and args[:2]==['ecr','describe-images']:print('sha256:'+'c'*64)
if tool=='docker' and args[:2]==['image','inspect']:
    print(os.environ['TEST_IMAGE_ARCH'] if 'Architecture' in args[-1] else os.environ['TEST_IMAGE_REVISION'])
if tool=='docker' and args[0]=='login':sys.stdin.read()
'''
    for tool in ["git", "aws", "docker"]:
        path = directory / tool
        path.write_text(code)
        path.chmod(0o755)
    archive = tmp_path / "verified-image.tar.gz"
    archive.write_bytes(b"mock archive; no actual Docker invocation")
    repo = Path(__file__).resolve().parents[3]
    result = subprocess.run(["bash", str(repo / "scripts/deploy_lambda.sh")], cwd=repo,
                            env={**os.environ, "PATH": str(directory) + os.pathsep + os.environ["PATH"],
                                 "CI_IMAGE_ARCHIVE": str(archive), "TEST_COMMAND_LOG": str(log),
                                 "TEST_IMAGE_ARCH": architecture, "TEST_IMAGE_REVISION": revision,
                                 "STACK_NAME": "loopsight-test"}, capture_output=True, text=True, timeout=15)
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert (result.returncode == 0) is success, result.stderr
    cloud_writes = [call for call in calls if call["tool"] == "aws" and call["args"][:2] == ["cloudformation", "deploy"]]
    pushes = [call for call in calls if call["tool"] == "docker" and call["args"][0] == "push"]
    assert bool(cloud_writes) is success
    assert bool(pushes) is success
    assert not any(call["tool"] == "docker" and call["args"][0] == "buildx" for call in calls)
