#!/usr/bin/env python3
"""Serve Hoop Sim locally and expose a same-machine NBA catch-up action."""
from __future__ import annotations
import json
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
ALLOWED_SEASONS = {"2024-25", "2025-26", "2026-27"}


class HoopSimHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/sync", "/api/live-sync"}:
            self.send_error(404)
            return
        season = parse_qs(parsed.query).get("season", ["2026-27"])[0]
        if season not in ALLOWED_SEASONS:
            self.send_error(400, "Unsupported season")
            return
        if parsed.path == "/api/live-sync":
            command = [sys.executable, str(ROOT / "scripts" / "import_nba_data.py"), "--season", season, "--live-only"]
            timeout = 600
        else:
            command = [sys.executable, str(ROOT / "scripts" / "import_basketball_reference.py"), "--season", season, "--skip-game-logs", "--skip-draft"]
            timeout = 1800
        try:
            result = subprocess.run(
                command, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False,
            )
            payload = {"ok": result.returncode == 0, "output": (result.stdout + result.stderr)[-12000:]}
            body = json.dumps(payload).encode()
            self.send_response(200 if payload["ok"] else 502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except subprocess.TimeoutExpired:
            limit = "10 minute" if parsed.path == "/api/live-sync" else "30 minute"
            body = json.dumps({"ok": False, "output": f"NBA sync exceeded the {limit} limit."}).encode()
            self.send_response(504)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


if __name__ == "__main__":
    print("Hoop Sim running at http://localhost:8000")
    ThreadingHTTPServer(("0.0.0.0", 8000), HoopSimHandler).serve_forever()
