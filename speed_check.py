#!/usr/bin/env python3
"""Measure download speed: 10 sequential GET requests to the given URL.

One HTTP connection (keep-alive) is reused for all requests, like a browser
or Node's default agent, so we measure transfer speed rather than repeated
DNS + TCP + TLS handshakes.
"""

import http.client
import sys
import time
from urllib.parse import urljoin, urlsplit

REQUEST_COUNT = 10
TIMEOUT_SECONDS = 30
CHUNK_SIZE = 64 * 1024
MAX_REDIRECTS = 5


def format_bytes(size: float) -> str:
    for unit in ("B", "KiB", "MiB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} GiB"


class Downloader:
    """Keeps one open connection per host and reuses it between requests."""

    def __init__(self, url: str):
        self.url = url
        self.conn: http.client.HTTPConnection | None = None
        self.origin: tuple[str, str] | None = None  # (scheme, host:port)

    def _connection_for(self, url: str):
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError(f"Invalid URL: {url}")
        origin = (parts.scheme, parts.netloc)
        if self.conn is None or origin != self.origin:
            self.close()
            cls = (http.client.HTTPSConnection if parts.scheme == "https"
                   else http.client.HTTPConnection)
            self.conn = cls(parts.netloc, timeout=TIMEOUT_SECONDS)
            self.origin = origin
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        return self.conn, path

    def _get(self, url: str) -> http.client.HTTPResponse:
        conn, path = self._connection_for(url)
        try:
            conn.request("GET", path)
            return conn.getresponse()
        except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError):
            # The server closed an idle keep-alive connection: reconnect once.
            conn.close()
            conn.request("GET", path)
            return conn.getresponse()

    def download_once(self) -> tuple[float, int]:
        """Download the full body. Returns (elapsed_seconds, bytes)."""
        started = time.perf_counter()
        url = self.url
        for _ in range(MAX_REDIRECTS + 1):
            response = self._get(url)
            if 300 <= response.status < 400 and response.getheader("Location"):
                response.read()  # drain the body so the connection can be reused
                url = urljoin(url, response.getheader("Location"))
                continue
            if not 200 <= response.status < 300:
                response.read()
                raise ValueError(f"Request failed with status {response.status}")
            total = 0
            while chunk := response.read(CHUNK_SIZE):
                total += len(chunk)
            # Remember the final URL so later requests skip the redirect.
            self.url = url
            return time.perf_counter() - started, total
        raise ValueError("Too many redirects")

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 speed_check.py <URL>", file=sys.stderr)
        return 1

    downloader = Downloader(sys.argv[1])
    times: list[float] = []
    total_bytes = 0

    try:
        for i in range(1, REQUEST_COUNT + 1):
            elapsed, size = downloader.download_once()
            times.append(elapsed)
            total_bytes += size
            print(f"#{i}: {elapsed * 1000:.2f} ms, {format_bytes(size)}")
    except (OSError, http.client.HTTPException, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    finally:
        downloader.close()

    total_time = sum(times)
    bytes_per_second = total_bytes / total_time

    print("\nSummary")
    print(f"Requests: {REQUEST_COUNT}")
    print(f"Average time: {total_time / REQUEST_COUNT * 1000:.2f} ms")
    print(f"Total downloaded: {format_bytes(total_bytes)} ({total_bytes} B)")
    print(f"Download speed: {bytes_per_second / 1024 / 1024:.3f} MiB/s")
    print(f"Download speed: {bytes_per_second * 8 / 1_000_000:.3f} Mbit/s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
