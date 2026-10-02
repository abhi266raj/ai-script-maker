import unittest
import os
import sys
from core.server_manager import get_server_info, get_current_port, get_current_host, _resolve_launch_command
from core.version import __version__


class TestServerManager(unittest.TestCase):
    def test_version_bump(self):
        self.assertEqual(__version__, "1.7.0")

    def test_get_current_port_default(self):
        # When HRS_PORT is unset
        old_port = os.environ.pop("HRS_PORT", None)
        try:
            port = get_current_port()
            self.assertIn(port, [80, 8501])
        finally:
            if old_port is not None:
                os.environ["HRS_PORT"] = old_port

    def test_get_current_port_env(self):
        old_port = os.environ.get("HRS_PORT")
        try:
            os.environ["HRS_PORT"] = "8080"
            self.assertEqual(get_current_port(), 8080)
        finally:
            if old_port is not None:
                os.environ["HRS_PORT"] = old_port
            else:
                os.environ.pop("HRS_PORT", None)

    def test_get_server_info(self):
        info = get_server_info()
        self.assertEqual(info["status"], "running")
        self.assertIsInstance(info["pid"], int)
        self.assertIsInstance(info["port"], int)
        self.assertIsInstance(info["host"], str)
        self.assertIsInstance(info["is_frozen"], bool)

    def test_resolve_launch_command(self):
        cmd = _resolve_launch_command()
        self.assertIsInstance(cmd, list)
        self.assertGreaterEqual(len(cmd), 1)


if __name__ == "__main__":
    unittest.main()
