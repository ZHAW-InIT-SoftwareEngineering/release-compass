"""Manage a local Phoenix collector for the CLI session."""

import subprocess
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from src.configs.trace.trace_config import TraceConfig

PHOENIX_LOG_PATH = Path("data/harness/phoenix.log")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _is_ready(url: str) -> bool:
    # Local requests must not be sent through a configured HTTP proxy.
    try:
        with build_opener(ProxyHandler({})).open(url, timeout=0.5) as response:
            return response.status == 200
    except URLError, OSError:
        return False


@contextmanager
def phoenix_server(config: TraceConfig) -> Generator[None]:
    """Reuse a ready local server or start one and stop it after spans flush."""
    endpoint = config.endpoint
    if (
        not config.enabled
        or not config.auto_start
        or endpoint.scheme != "http"
        or endpoint.host not in LOCAL_HOSTS
        or endpoint.path != "/v1/traces"
    ):
        yield
        return

    port = endpoint.port or 80
    host = "::1" if endpoint.host == "::1" else "127.0.0.1"
    origin = f"http://[{host}]:{port}" if host == "::1" else f"http://{host}:{port}"
    ready_url = f"{origin}/readyz"
    if _is_ready(ready_url):
        yield
        return

    PHOENIX_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PHOENIX_LOG_PATH.open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "phoenix.server.main",
                "serve",
                "--host",
                host,
                "--port",
                str(port),
            ],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            print(f"Starting Phoenix at {origin} (log: {PHOENIX_LOG_PATH})")
            deadline = monotonic() + config.startup_timeout_seconds
            while not _is_ready(ready_url):
                if process.poll() is not None:
                    raise RuntimeError(
                        f"Phoenix exited during startup; see {PHOENIX_LOG_PATH}"
                    )
                if monotonic() >= deadline:
                    raise RuntimeError(
                        f"Phoenix startup timed out; see {PHOENIX_LOG_PATH}"
                    )
                sleep(0.2)
            yield
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
