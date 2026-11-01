import pytest

from netprobe.config import ConfigError, load_settings, parse_settings, split_host_port

DUPLICATE = {"name": "a", "type": "dns", "address": "x"}


def valid(**overrides):
    raw = {"targets": [{"name": "web", "type": "http", "address": "https://example.com"}]}
    raw.update(overrides)
    return raw


def test_parses_targets_and_defaults():
    settings = parse_settings(valid())

    assert settings.interval_seconds == 15
    assert settings.timeout_seconds == 5
    assert settings.targets[0].name == "web"


@pytest.mark.parametrize(
    "raw, message",
    [
        ({"targets": []}, "At least one target"),
        (valid(targets=[{"name": "x", "type": "ftp", "address": "a"}]), "unknown type"),
        (valid(targets=[{"type": "http", "address": "a"}]), "needs a name"),
        (valid(targets=[{"name": "db", "type": "tcp", "address": "db.local"}]), "host:port"),
        (valid(targets=[{"name": "db", "type": "tcp", "address": "db.local:99999"}]), "host:port"),
        (valid(interval_seconds=5, timeout_seconds=5), "shorter than"),
        (valid(interval_seconds=0), "positive"),
        (valid(targets=[DUPLICATE, DUPLICATE]), "more than once"),
    ],
)
def test_rejects_invalid_config(raw, message):
    with pytest.raises(ConfigError, match=message):
        parse_settings(raw)


@pytest.mark.parametrize(
    "address, expected",
    [("db.local:5432", ("db.local", 5432)), ("[::1]:8080", ("::1", 8080)), ("10.0.0.1:22", ("10.0.0.1", 22))],
)
def test_split_host_port(address, expected):
    assert split_host_port(address) == expected


def test_shipped_config_is_valid():
    settings = load_settings("config/targets.yaml")

    assert {t.type for t in settings.targets} == {"http", "tcp", "dns"}
