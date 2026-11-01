import asyncio

import httpx

from netprobe.config import Target
from netprobe.probes import probe_dns, probe_http, probe_tcp


def run(coro):
    return asyncio.run(coro)


def mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def http_probe(status=None, exc=None):
    def handler(request):
        if exc:
            raise exc
        return httpx.Response(status)

    async with mock_client(handler) as client:
        return await probe_http(
            Target("web", "http", "https://service.test/health"), client, timeout_seconds=1
        )


def test_http_up_for_success_status():
    result = run(http_probe(status=200))

    assert result.up
    assert result.detail == "HTTP 200"
    assert result.duration_seconds >= 0


def test_http_down_for_server_error():
    result = run(http_probe(status=503))

    assert not result.up
    assert result.detail == "HTTP 503"


def test_http_down_on_timeout():
    result = run(http_probe(exc=httpx.ReadTimeout("slow")))

    assert not result.up
    assert result.detail == "timeout"


def test_http_down_on_connection_error():
    result = run(http_probe(exc=httpx.ConnectError("refused")))

    assert not result.up
    assert result.detail == "error: ConnectError"


def test_tcp_up_when_port_accepts_connections():
    async def scenario():
        server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            return await probe_tcp(Target("local", "tcp", f"127.0.0.1:{port}"), timeout_seconds=1)

    result = run(scenario())

    assert result.up
    assert result.detail == "connected"


def test_tcp_down_when_port_is_closed():
    async def scenario():
        # Bind and close a server to get a port that is free but not listening.
        server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        server.close()
        await server.wait_closed()
        return await probe_tcp(Target("closed", "tcp", f"127.0.0.1:{port}"), timeout_seconds=1)

    result = run(scenario())

    assert not result.up
    assert result.detail.startswith("error")


def test_dns_resolves_localhost():
    result = run(probe_dns(Target("lo", "dns", "localhost"), timeout_seconds=2))

    assert result.up
    assert "127.0.0.1" in result.detail or "::1" in result.detail


def test_dns_down_for_unknown_name():
    result = run(probe_dns(Target("bad", "dns", "does-not-exist.invalid"), timeout_seconds=5))

    assert not result.up
    assert result.detail.startswith("error")
