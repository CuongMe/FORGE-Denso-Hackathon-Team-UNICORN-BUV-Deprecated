import json
import os
from pathlib import Path
import subprocess
import sys


API_ROOT = Path(__file__).resolve().parents[1]


def run_isolated(code: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment['FORGE_RUNTIME_MODE'] = 'invalid-on-purpose'
    return subprocess.run(
        [sys.executable, '-c', code],
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_importing_api_does_not_construct_production_runtime():
    completed = run_isolated('import app.main; print("imported")')

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == 'imported'


def test_health_uses_cached_readiness_without_waiting_for_provider():
    code = '''
import json
import time
from fastapi.testclient import TestClient
from app import main

class SlowRuntime:
    chunks_count = 0
    reranker = type('Reranker', (), {'name': 'fake'})()
    state_store = None

    def readiness(self):
        time.sleep(1)
        return {'ready': True, 'checks': {'provider': 'ready'}}

    def document_list(self):
        return []

    def ingestion(self):
        return {'mode': 'test', 'chunker': 'fake'}

main.runtime = SlowRuntime()
started = time.perf_counter()
response = TestClient(main.app).get('/api/health')
print(json.dumps({'status': response.status_code, 'elapsed': time.perf_counter() - started}))
'''
    completed = run_isolated(code)

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout.splitlines()[-1])
    assert result['status'] == 200
    assert result['elapsed'] < 0.35
