#!/usr/bin/env python3
"""Real HTTP smoke test for the FastAPI demo; isolated SQLite and fictional data.

Run: python scripts/smoke_http.py (after pip install -r backend/requirements-dev.txt)
Never points at a deployed service or a production DB.
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parents[1]


def request(base: str, path: str, method: str = "GET", payload=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(base + path, data=json.dumps(payload).encode() if payload is not None else None,
                  headers=headers, method=method)
    try:
        with urlopen(req, timeout=3) as response:
            body = response.read()
            text = body.decode("utf-8")
            return response.status, json.loads(text) if text.startswith(("{", "[")) else text
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="courtmate-http-smoke-") as tmp:
        token = secrets.token_urlsafe(48)
        env = os.environ.copy()
        env.update(COURTMATE_DB=str(Path(tmp) / "smoke.db"),
                   COURTMATE_ADMIN_TOKEN=token, COURTMATE_PUBLIC_BOOKING="true")
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app",
                                    "--host", "127.0.0.1", "--port", str(port)],
                                   cwd=str(BASE / "backend"), env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            for _ in range(60):
                if process.poll() is not None:
                    raise RuntimeError("Server exited before accepting requests")
                try:
                    if request(url, "/health")[0] == 200:
                        break
                except (URLError, TimeoutError, ConnectionError):
                    time.sleep(0.2)
            else:
                raise RuntimeError("Server failed health check")
            code, html = request(url, "/")
            assert code == 200 and "CourtMate" in html
            assert request(url, "/v1/admin/courts")[0] == 401
            code, court = request(url, "/v1/admin/courts", "POST", {"name": "Sân thử nghiệm", "price_hour": 120000}, token)
            assert code == 201, (code, court)
            code, courts = request(url, "/v1/public/courts")
            assert code == 200 and len(courts) == 1, (code, courts)
            tomorrow = (datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")) + timedelta(days=1)).date().isoformat()
            booking = {"court_id": court["id"], "date": tomorrow, "start": "10:00", "end": "11:00",
                       "customer_name": "Khach Demo", "customer_phone": "0900000000"}
            code, created = request(url, "/v1/public/bookings", "POST", booking)
            assert code == 201 and created["access_token"], (code, created)
            assert request(url, "/v1/public/bookings", "POST", booking)[0] == 409
            code, status = request(url, "/v1/public/booking-status", "POST", {"id": created["id"], "access_token": created["access_token"]})
            assert code == 200 and status["status"] == "PENDING", (code, status)
            code, cancelled = request(url, "/v1/public/bookings/cancel", "POST", {"id": created["id"], "access_token": created["access_token"]})
            assert code == 200 and cancelled["status"] == "CANCELLED", (code, cancelled)
            assert request(url, "/v1/public/bookings", "POST", booking)[0] == 201
            print("HTTP smoke OK: /health, website, access control, courts, booking, conflict, status, cancel, slot reuse")
        finally:
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()


if __name__ == "__main__":
    main()
