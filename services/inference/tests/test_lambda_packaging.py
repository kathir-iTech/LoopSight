"""Check the code shipped by the Lambda Dockerfile, outside the checkout."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def test_lambda_copy_contents_start_without_test_packages():
    repo = Path(__file__).resolve().parents[3]
    dockerfile = repo / "services/inference/Dockerfile.lambda"
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory)
        for line in dockerfile.read_text().splitlines():
            if not line.startswith("COPY "):
                continue
            _, source, destination = line.split()
            relative = destination.removeprefix("${LAMBDA_TASK_ROOT}/")
            output = target / relative
            source_path = repo / source
            if source_path.is_dir():
                shutil.copytree(source_path, output)
            else:
                shutil.copy2(source_path, output)
        # Isolated mode prevents the checkout/PYTHONPATH from hiding missing files.
        code = """
import sys
sys.path.insert(0, '.')
import main
assert main.handler is not None
assert 'tests.synthetic' not in sys.modules
frame, _, profile = main._generate_sample_frames('water_turbid_fail')
job_id, result = main._execute_inspection_pipeline(frame, profile)
assert result['final_decision']['decision'] == 'FAIL'
assert main.store.get(job_id) == result
"""
        result = subprocess.run(
            [sys.executable, "-I", "-c", code],
            cwd=target,
            env={**os.environ, "GEMINI_API_KEY": "", "DYNAMO_TABLE_NAME": "",
                 "LOOPSIGHT_SQLITE_PATH": str(target / "jobs.sqlite3")},
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
