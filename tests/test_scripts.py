"""Runs both scripts against a local HTTP server with a file of known size."""

import re
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD_SIZE = 200_000  # bytes
EXPECTED_REQUESTS = 10


class Handler(BaseHTTPRequestHandler):
    hits = 0

    def do_GET(self):
        if self.path == "/missing":
            self.send_response(404)
            self.end_headers()
            return
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/file")
            self.end_headers()
            return
        Handler.hits += 1
        self.send_response(200)
        self.send_header("Content-Length", str(PAYLOAD_SIZE))
        self.end_headers()
        self.wfile.write(b"x" * PAYLOAD_SIZE)

    def log_message(self, *args):
        pass


class SpeedScriptsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        Handler.hits = 0

    def run_script(self, command, path):
        return subprocess.run(
            command + [self.base + path], capture_output=True, text=True, timeout=60
        )

    def check_success(self, command, path="/file"):
        result = self.run_script(command, path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Handler.hits, EXPECTED_REQUESTS)
        total = int(re.search(r"\((\d+) B\)", result.stdout).group(1))
        self.assertEqual(total, PAYLOAD_SIZE * EXPECTED_REQUESTS)
        self.assertIn("MiB/s", result.stdout)
        self.assertIn("Mbit/s", result.stdout)

    def check_errors(self, command):
        self.assertEqual(self.run_script(command, "/missing").returncode, 1)
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)

    def test_python_success(self):
        self.check_success([sys.executable, str(ROOT / "speed_check.py")])

    def test_node_success(self):
        self.check_success(["node", str(ROOT / "src" / "speed-check.js")])

    def test_node_follows_redirect(self):
        self.check_success(["node", str(ROOT / "src" / "speed-check.js")], "/redirect")

    def test_python_follows_redirect(self):
        self.check_success([sys.executable, str(ROOT / "speed_check.py")], "/redirect")

    def test_python_errors(self):
        self.check_errors([sys.executable, str(ROOT / "speed_check.py")])

    def test_node_errors(self):
        self.check_errors(["node", str(ROOT / "src" / "speed-check.js")])


if __name__ == "__main__":
    unittest.main()
