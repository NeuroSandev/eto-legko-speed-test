#!/usr/bin/env python3
"""Measure download speed: 10 sequential GET requests to the given URL."""

import sys
import time
import urllib.error
import urllib.request

REQUEST_COUNT = 10
TIMEOUT_SECONDS = 30
CHUNK_SIZE = 64 * 1024


def format_bytes(size: float) -> str:
    for unit in ("B", "KiB", "MiB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} GiB"


def download_once(url: str) -> tuple[float, int]:
    """Download the full response body. Returns (elapsed_seconds, bytes)."""
    started = time.perf_counter()
    # urlopen follows redirects and raises HTTPError for 4xx/5xx
    with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
        total = 0
        while chunk := response.read(CHUNK_SIZE):
            total += len(chunk)
    return time.perf_counter() - started, total


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 speed_check.py <URL>", file=sys.stderr)
        return 1

    url = sys.argv[1]
    times: list[float] = []
    total_bytes = 0

    try:
        for i in range(1, REQUEST_COUNT + 1):
            elapsed, size = download_once(url)
            times.append(elapsed)
            total_bytes += size
            print(f"#{i}: {elapsed * 1000:.2f} ms, {format_bytes(size)}")
    except (urllib.error.URLError, ValueError, TimeoutError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

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
