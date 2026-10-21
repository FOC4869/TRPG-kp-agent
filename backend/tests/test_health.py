"""The scaffold must work without a model SDK request or a player save."""

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from app.main import app


class TestHealth(unittest.TestCase):
    def test_health_and_openapi_contract(self):
        with TestClient(app) as client:
            response = client.get("/api/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "ok", "service": "trpg-kp-backend"})
            schema = client.get("/openapi.json").json()
            self.assertEqual(set(schema["paths"]), {"/api/health"})

    def test_app_import_does_not_load_agent_or_create_files(self):
        root = Path(__file__).resolve().parents[1]
        code = (
            "import sys; "
            f"sys.path.insert(0, {str(root)!r}); "
            "import app.main; "
            "assert 'kp_agent.graph' not in sys.modules; "
            "assert 'kp_agent.models' not in sys.modules"
        )
        with TemporaryDirectory() as directory:
            subprocess.run([sys.executable, "-B", "-c", code], cwd=directory, check=True)
            self.assertEqual(list(Path(directory).iterdir()), [])
