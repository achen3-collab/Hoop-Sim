"""PythonAnywhere WSGI entry point for the public, read-only Hoop Sim site."""
from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent
STATIC_SUFFIXES = {".css", ".html", ".js", ".json"}


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = unquote(environ.get("PATH_INFO", "/"))

    if path in {"/api/sync", "/api/live-sync"}:
        body = json.dumps({
            "ok": False,
            "output": "Sync requests are disabled on public hosting. Run the importer as a private scheduled task.",
        }).encode()
        status = "503 Service Unavailable"
        content_type = "application/json; charset=utf-8"
    elif method not in {"GET", "HEAD"}:
        body = b"Method not allowed"
        status = "405 Method Not Allowed"
        content_type = "text/plain; charset=utf-8"
    else:
        requested = "/index.html" if path == "/" else path
        candidate = (ROOT / requested.lstrip("/")).resolve()
        allowed = (
            candidate.is_relative_to(ROOT)
            and candidate.is_file()
            and candidate.suffix.lower() in STATIC_SUFFIXES
        )
        if not allowed:
            body = b"Not found"
            status = "404 Not Found"
            content_type = "text/plain; charset=utf-8"
        else:
            body = candidate.read_bytes()
            status = "200 OK"
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            if content_type.startswith("text/") or content_type in {
                "application/javascript", "application/json",
            }:
                content_type += "; charset=utf-8"

    headers = [
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
        ("Referrer-Policy", "strict-origin-when-cross-origin"),
    ]
    start_response(status, headers)
    return [b"" if method == "HEAD" else body]
