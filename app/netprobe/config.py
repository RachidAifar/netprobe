"""Loads probe targets from a YAML file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

ProbeType = Literal["http", "tcp", "dns"]
PROBE_TYPES: tuple[ProbeType, ...] = ("http", "tcp", "dns")


@dataclass(frozen=True)
class Target:
    name: str
    type: ProbeType
    address: str
    """URL for http, host:port for tcp, hostname for dns."""


@dataclass(frozen=True)
class Settings:
    targets: tuple[Target, ...]
    interval_seconds: float = 15.0
    timeout_seconds: float = 5.0


class ConfigError(ValueError):
    pass


def parse_settings(raw: dict) -> Settings:
    if not isinstance(raw, dict):
        raise ConfigError("Config must be a mapping.")

    interval = float(raw.get("interval_seconds", 15))
    timeout = float(raw.get("timeout_seconds", 5))
    if interval <= 0 or timeout <= 0:
        raise ConfigError("interval_seconds and timeout_seconds must be positive.")
    if timeout >= interval:
        raise ConfigError("timeout_seconds must be shorter than interval_seconds.")

    targets = []
    seen = set()
    for index, item in enumerate(raw.get("targets") or []):
        name, probe_type, address = item.get("name"), item.get("type"), item.get("address")
        if not name or not address:
            raise ConfigError(f"Target #{index + 1} needs a name and an address.")
        if probe_type not in PROBE_TYPES:
            raise ConfigError(f"Target '{name}' has unknown type '{probe_type}'. Use one of {PROBE_TYPES}.")
        if name in seen:
            raise ConfigError(f"Target name '{name}' is used more than once.")
        if probe_type == "tcp":
            _split_host_port(address, name)
        seen.add(name)
        targets.append(Target(name=name, type=probe_type, address=address))

    if not targets:
        raise ConfigError("At least one target is required.")
    return Settings(targets=tuple(targets), interval_seconds=interval, timeout_seconds=timeout)


def load_settings(path: str | os.PathLike[str] | None = None) -> Settings:
    path = Path(path or os.environ.get("NETPROBE_CONFIG", "config/targets.yaml"))
    with path.open(encoding="utf-8") as file:
        return parse_settings(yaml.safe_load(file))


def _split_host_port(address: str, name: str) -> tuple[str, int]:
    host, sep, port = address.rpartition(":")
    if not sep or not host or not port.isdigit() or not 0 < int(port) < 65536:
        raise ConfigError(f"Target '{name}' must use host:port for tcp, got '{address}'.")
    return host.strip("[]"), int(port)


def split_host_port(address: str) -> tuple[str, int]:
    return _split_host_port(address, address)
