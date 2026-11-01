import asyncio
import time

import httpx
from fastapi.testclient import TestClient

from netprobe.config import parse_settings
from netprobe.main import create_app

SETTINGS = parse_settings(
    {
        "targets": [
            {"name": "healthy", "type": "http", "address": "https://ok.test/"},
            {"name": "broken", "type": "http", "address": "https://down.test/"},
        ]
    }
)


def fake_upstream(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200 if request.url.host == "ok.test" else 500)


def make_client() -> TestClient:
    app = create_app(
        SETTINGS,
        client=httpx.AsyncClient(transport=httpx.MockTransport(fake_upstream)),
        start_background=False,
    )
    return TestClient(app)


def run_round(client: TestClient) -> None:
    client.portal.call(client.app.state.prober.run_round)


def test_health_is_always_ok():
    with make_client() as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_not_ready_until_first_round():
    with make_client() as client:
        assert client.get("/ready").status_code == 503

        run_round(client)

        assert client.get("/ready").status_code == 200


def test_targets_show_last_result():
    with make_client() as client:
        run_round(client)
        targets = {t["name"]: t for t in client.get("/targets").json()}

    assert targets["healthy"]["last"]["up"] is True
    assert targets["broken"]["last"]["up"] is False
    assert targets["broken"]["last"]["detail"] == "HTTP 500"


def test_metrics_exposed_in_prometheus_format():
    with make_client() as client:
        run_round(client)
        run_round(client)
        body = client.get("/metrics").text

    assert 'netprobe_target_up{target="healthy",type="http"} 1.0' in body
    assert 'netprobe_target_up{target="broken",type="http"} 0.0' in body
    assert 'netprobe_probe_failures_total{target="broken",type="http"} 2.0' in body
    assert "netprobe_rounds_total 2.0" in body
    assert "netprobe_probe_duration_seconds_bucket" in body


def test_rounds_run_probes_concurrently():
    # Two probes that each take 0.2 s should finish in well under 0.4 s together.
    async def slow(request):
        await asyncio.sleep(0.2)
        return httpx.Response(200)

    client = httpx.AsyncClient(transport=httpx.MockTransport(slow))
    with TestClient(create_app(SETTINGS, client=client, start_background=False)) as test_client:
        start = time.perf_counter()
        run_round(test_client)
        elapsed = time.perf_counter() - start

    assert elapsed < 0.35
