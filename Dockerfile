# syntax=docker/dockerfile:1

# Build stage: install dependencies into a virtual environment.
FROM python:3.13-slim AS build
WORKDIR /src
RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH
COPY app/pyproject.toml ./
COPY app/netprobe ./netprobe
RUN pip install --no-cache-dir . \
 && pip uninstall --yes pip

# Runtime stage: only the virtual environment and config, running as a non-root user.
# pip is removed: it is not needed at runtime and its vendored libraries add vulnerabilities.
FROM python:3.13-slim
LABEL org.opencontainers.image.source="https://github.com/RachidAifar/netprobe" \
      org.opencontainers.image.description="Network uptime probe with Prometheus metrics"
RUN python -m pip uninstall --yes pip \
 && rm -rf /usr/local/lib/python3.13/ensurepip \
 && useradd --system --uid 10001 --no-create-home netprobe
COPY --from=build /venv /venv
COPY app/config /app/config
WORKDIR /app
ENV PATH=/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    NETPROBE_CONFIG=/app/config/targets.yaml
USER 10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"
ENTRYPOINT ["python", "-m", "netprobe.main"]
