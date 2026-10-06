"""
Operational Health Checks (Module 13)
Implements the Three Production Health Concepts:
1. Liveness: "Is the process alive and execution loop running?"
2. Readiness: "Can this worker accept work? Is SQLite reachable and config loaded?"
3. Dependency Health: "Can external systems (Reddit client/auth) currently be reached?"
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import sqlite3
import threading
from typing import Any, Callable

from ..reddit import RedditClient


class HealthStatus:
    UP = "UP"
    DOWN = "DOWN"


class HealthCheckHandler:
    """Core health check evaluator decoupled from network transport."""

    def __init__(
        self,
        db_path: str,
        reddit_client: RedditClient,
        is_worker_alive: Callable[[], bool] | None = None,
    ) -> None:
        self.db_path = db_path
        self.reddit_client = reddit_client
        self._is_worker_alive = is_worker_alive or (lambda: True)

    def check_liveness(self) -> tuple[int, dict[str, Any]]:
        alive = self._is_worker_alive()
        status = HealthStatus.UP if alive else HealthStatus.DOWN
        code = 200 if alive else 503
        return code, {"status": status, "check": "liveness", "process_alive": alive}

    def check_readiness(self) -> tuple[int, dict[str, Any]]:
        # Check SQLite connectivity
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("SELECT 1")
            conn.close()
            db_ok = True
        except Exception as exc:
            return 503, {"status": HealthStatus.DOWN, "check": "readiness", "error": f"DatabaseUnreachable: {str(exc)}"}

        return 200, {"status": HealthStatus.UP, "check": "readiness", "db_connected": db_ok}

    def check_dependencies(self) -> tuple[int, dict[str, Any]]:
        # Check Reddit API connectivity by fetching rules
        try:
            rules = self.reddit_client.get_subreddit_rules("r/Python")
            reddit_ok = isinstance(rules, list)
        except Exception as exc:
            return 503, {"status": HealthStatus.DOWN, "check": "dependencies", "error": f"RedditApiUnreachable: {str(exc)}"}

        return 200, {"status": HealthStatus.UP, "check": "dependencies", "reddit_api": reddit_ok}


class ProductionHTTPHealthHandler(BaseHTTPRequestHandler):
    """Minimal HTTP Request Handler dispatching health probes."""

    health_evaluator: HealthCheckHandler | None = None

    def do_GET(self) -> None:
        evaluator = ProductionHTTPHealthHandler.health_evaluator
        if not evaluator:
            self._send(500, {"error": "HealthEvaluatorNotConfigured"})
            return

        if self.path == "/health/live":
            code, payload = evaluator.check_liveness()
        elif self.path == "/health/ready":
            code, payload = evaluator.check_readiness()
        elif self.path == "/health/deps":
            code, payload = evaluator.check_dependencies()
        else:
            code, payload = 404, {"error": "NotFound"}

        self._send(code, payload)

    def _send(self, status_code: int, body: dict[str, Any]) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard stdout logs during health tests
        pass


class HealthServer:
    """Lightweight built-in HTTP health probe server."""

    def __init__(self, evaluator: HealthCheckHandler, port: int = 8089) -> None:
        self.evaluator = evaluator
        self.port = port
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        ProductionHTTPHealthHandler.health_evaluator = self.evaluator
        self.server = HTTPServer(("127.0.0.1", self.port), ProductionHTTPHealthHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
