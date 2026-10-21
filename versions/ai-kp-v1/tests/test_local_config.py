"""Configuration checks only read temporary fake .env files, never local keys."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from kp_agent.config import LocalConfigurationError, load_local_env


class LocalConfigTests(unittest.TestCase):
    def test_missing_local_file_does_not_search_parent_directories(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "missing.env"
            with patch("kp_agent.config.LOCAL_ENV_FILE", path):
                self.assertFalse(load_local_env())

    def test_shell_environment_wins_and_values_are_not_interpolated(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / ".env"
            path.write_text("KP_MODEL_MODE=demo\nKP_CONFIG_LITERAL=${OTHER}\n", encoding="utf-8")
            with patch("kp_agent.config.LOCAL_ENV_FILE", path), patch.dict(os.environ, {"KP_MODEL_MODE": "deepseek", "OTHER": "not-expanded"}, clear=True):
                load_local_env()
                self.assertEqual(os.environ["KP_MODEL_MODE"], "deepseek")
                self.assertEqual(os.environ["KP_CONFIG_LITERAL"], "${OTHER}")

    def test_malformed_file_error_does_not_echo_its_private_contents(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / ".env"
            path.write_text('DEEPSEEK_API_KEY="fake-private-secret\n', encoding="utf-8")
            with patch("kp_agent.config.LOCAL_ENV_FILE", path), self.assertRaises(LocalConfigurationError) as caught:
                load_local_env()
            self.assertNotIn("fake-private-secret", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
