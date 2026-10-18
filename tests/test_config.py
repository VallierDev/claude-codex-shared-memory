import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from configure import render, validate, private_write
from serve import build_env, read_settings


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.settings = dict(api_key="test-placeholder", base_url="https://api.evermind.ai",
                             user_id="alice", app_id="shared-memory", project_id="demo",
                             assistant_sender_id="assistant-alice")

    def test_both_clients_launch_identical_config_even_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="memory config ") as folder:
            path = Path(folder) / "settings.json"
            claude, codex = render(path, "/opt/Python with space/python")
            cc = claude["mcpServers"]["everos-shared"]
            cx = tomllib.loads(codex)["mcp_servers"]["everos-shared"]
            self.assertEqual(cc["args"], cx["args"])
            self.assertEqual(cc["command"], cx["command"])
            self.assertNotIn("api_key", json.dumps(claude) + codex)

    def test_inherited_identity_and_session_do_not_leak(self):
        env = build_env(self.settings, {"PATH": "/bin", "EVEROS_SESSION_ID": "old-shared", "EVEROS_USER_ID": "bob", "EVER_OS_BASE_URL": "http://old", "EVEROS_MCP_TRANSPORT": "http"})
        self.assertEqual(env["EVEROS_USER_ID"], "alice")
        self.assertNotIn("EVEROS_SESSION_ID", env)
        self.assertNotIn("EVEROS_MCP_TRANSPORT", env)
        self.assertNotIn("EVER_OS_BASE_URL", env)
        self.assertEqual(env["PATH"], "/bin")

    @unittest.skipUnless(os.name == "posix", "POSIX virtualenv symlink regression")
    def test_virtualenv_executable_symlink_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            executable = Path(folder) / "venv-python"
            executable.symlink_to(sys.executable)
            claude, codex = render(Path(folder) / "settings.json", str(executable))
            self.assertEqual(claude["mcpServers"]["everos-shared"]["command"], str(executable))
            self.assertEqual(tomllib.loads(codex)["mcp_servers"]["everos-shared"]["command"], str(executable))

    def test_secret_file_is_private_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            private_write(path, json.dumps(self.settings))
            self.assertEqual(read_settings(path), self.settings)
            with self.assertRaises(FileExistsError):
                private_write(path, "overwrite")

    def test_invalid_scope_and_credential_url_rejected(self):
        for patch in ({"user_id": "../bob"}, {"base_url": "https://user:secret@example.com"}, {"api_key": ""}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                validate(dict(self.settings, **patch))

    def test_self_hosted_without_cloud_key(self):
        self.assertTrue(validate(dict(self.settings, api_key="", base_url="http://127.0.0.1:8000")))


if __name__ == "__main__":
    unittest.main()
