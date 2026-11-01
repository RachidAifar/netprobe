"""HTTP API: health and readiness endpoints, current status and Prometheus metrics."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import sys
import time
from collections.abc import AsyncIterator
from dataclasses import asdict

import httpx
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from . import __version__
from .config import Settings, load_settings
from .metrics import ProbeMetrics
from .probes import ProbeResult, run_probe

logger = logging.getLogger("netprobe")


class JsonFormatter(logging.Formatter):
    """One JSON object per line, ready for Filebeat / Elasticsearch."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "@timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + "Z",
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        entry.update(getattr(record, "fields", {}))
        return json.dumps(entry)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


class Prober:
    def __init__(self, settings: Settings, metrics: ProbeMetrics, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.metrics = metrics
        self.client = client
        self.results: dict[str, ProbeResult] = {}

    @property
    def ready(self) -> bool:
        return len(self.results) == len(self.settings.targets)

    async def run_round(self) -> list[ProbeResult]:
        results = await asyncio.gather(
            *(run_probe(t, self.client, self.settings.timeout_seconds) for t in self.settings.targets)
        )
        for result in results:
            self.results[result.target] = result
            self.metrics.record(result)
            level = logging.INFO if result.up else logging.WARNING
            logger.log(
                level,
                "probe finished",
                extra={
                    "fields": {
                        "target": result.target,
                        "type": result.type,
                        "up": result.up,
                        "duration_ms": round(result.duration_seconds * 1000, 1),
                        "detail": result.detail,
                    }
                },
            )
        self.metrics.rounds.inc()
        return results

    async def run_forever(self) -> None:
        while True:
            await self.run_round()
            await asyncio.sleep(self.settings.interval_seconds)


def create_app(
    settings: Settings | None = None, client: httpx.AsyncClient | None = None, start_background: bool = True
) -> FastAPI:
    settings = settings or load_settings()
    metrics = ProbeMetrics()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with contextlib.AsyncExitStack() as stack:
            http = client or await stack.enter_async_context(httpx.AsyncClient())
            app.state.prober = Prober(settings, metrics, http)
            task = asyncio.create_task(app.state.prober.run_forever()) if start_background else None
            logger.info("netprobe started", extra={"fields": {"targets": len(settings.targets)}})
            yield
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="NetProbe", version=__version__, lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> JSONResponse:
        is_ready = app.state.prober.ready
        return JSONResponse({"ready": is_ready}, status_code=200 if is_ready else 503)

    @app.get("/targets")
    async def targets() -> list[dict]:
        prober: Prober = app.state.prober
        return [
            {
                "name": t.name,
                "type": t.type,
                "address": t.address,
                "last": asdict(prober.results[t.name]) if t.name in prober.results else None,
            }
            for t in settings.targets
        ]

    @app.get("/metrics")
    async def prometheus_metrics() -> Response:
        return Response(generate_latest(metrics.registry), media_type=CONTENT_TYPE_LATEST)

    return app


def main() -> None:
    import uvicorn

    configure_logging()
    uvicorn.run(create_app(), host="0.0.0.0", port=8080, log_config=None, access_log=False)


if __name__ == "__main__":
    main()
