"""The three probe types. Each returns a ProbeResult and never raises."""

from __future__ import annotations

import asyncio
import socket
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from .config import Target, split_host_port


@dataclass(frozen=True)
class ProbeResult:
    target: str
    type: str
    up: bool
    duration_seconds: float
    detail: str
    """Status code, resolved addresses or the reason for a failure."""
    checked_at: float


async def probe_http(target: Target, client: httpx.AsyncClient, timeout_seconds: float) -> ProbeResult:
    start = time.perf_counter()
    try:
        response = await client.get(target.address, timeout=timeout_seconds, follow_redirects=True)
        up = response.status_code < 400
        detail = f"HTTP {response.status_code}"
    except httpx.TimeoutException:
        up, detail = False, "timeout"
    except httpx.HTTPError as error:
        up, detail = False, f"error: {type(error).__name__}"
    return _result(target, up, start, detail)


async def probe_tcp(target: Target, timeout_seconds: float) -> ProbeResult:
    host, port = split_host_port(target.address)
    start = time.perf_counter()
    try:
        async with asyncio.timeout(timeout_seconds):
            _, writer = await asyncio.open_connection(host, port)
        writer.close()
        await writer.wait_closed()
        up, detail = True, "connected"
    except TimeoutError:
        up, detail = False, "timeout"
    except OSError as error:
        up, detail = False, f"error: {error.strerror or type(error).__name__}"
    return _result(target, up, start, detail)


async def probe_dns(target: Target, timeout_seconds: float) -> ProbeResult:
    host = urlsplit(target.address).hostname if "://" in target.address else target.address
    loop = asyncio.get_running_loop()
    start = time.perf_counter()
    try:
        async with asyncio.timeout(timeout_seconds):
            infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        addresses = sorted({info[4][0] for info in infos})
        up, detail = True, ", ".join(addresses)
    except TimeoutError:
        up, detail = False, "timeout"
    except socket.gaierror as error:
        up, detail = False, f"error: {error.strerror}"
    return _result(target, up, start, detail)


async def run_probe(target: Target, client: httpx.AsyncClient, timeout_seconds: float) -> ProbeResult:
    if target.type == "http":
        return await probe_http(target, client, timeout_seconds)
    if target.type == "tcp":
        return await probe_tcp(target, timeout_seconds)
    return await probe_dns(target, timeout_seconds)


def _result(target: Target, up: bool, start: float, detail: str) -> ProbeResult:
    return ProbeResult(
        target=target.name,
        type=target.type,
        up=up,
        duration_seconds=time.perf_counter() - start,
        detail=detail,
        checked_at=time.time(),
    )
