import os
import pytest
from hpyx import config


def test_defaults_present():
    assert config.DEFAULTS == {
        "os_threads": None,
        "cfg": [],
        "autoinit": True,
        "trace_path": None,
        "async_mode": "async",
    }


def test_from_env_empty(monkeypatch):
    for k in ("HPYX_OS_THREADS", "HPYX_CFG", "HPYX_AUTOINIT", "HPYX_TRACE_PATH", "HPYX_ASYNC_MODE"):
        monkeypatch.delenv(k, raising=False)
    assert config.from_env() == config.DEFAULTS


def test_from_env_os_threads(monkeypatch):
    monkeypatch.setenv("HPYX_OS_THREADS", "4")
    assert config.from_env()["os_threads"] == 4


def test_from_env_os_threads_invalid_raises(monkeypatch):
    monkeypatch.setenv("HPYX_OS_THREADS", "not-a-number")
    with pytest.raises(ValueError, match="HPYX_OS_THREADS"):
        config.from_env()


def test_from_env_cfg_semicolon_split(monkeypatch):
    monkeypatch.setenv(
        "HPYX_CFG",
        "hpx.stacks.small_size=0x20000;hpx.os_threads!=2",
    )
    assert config.from_env()["cfg"] == [
        "hpx.stacks.small_size=0x20000",
        "hpx.os_threads!=2",
    ]


def test_from_env_cfg_empty_entries_stripped(monkeypatch):
    monkeypatch.setenv("HPYX_CFG", "a=1;;b=2;")
    assert config.from_env()["cfg"] == ["a=1", "b=2"]


@pytest.mark.parametrize("value,expected", [
    ("0", False), ("false", False), ("FALSE", False), ("no", False),
    ("1", True), ("true", True), ("TRUE", True), ("yes", True),
])
def test_from_env_autoinit(monkeypatch, value, expected):
    monkeypatch.setenv("HPYX_AUTOINIT", value)
    assert config.from_env()["autoinit"] is expected


def test_from_env_trace_path(monkeypatch):
    monkeypatch.setenv("HPYX_TRACE_PATH", "/tmp/hpyx.jsonl")
    assert config.from_env()["trace_path"] == "/tmp/hpyx.jsonl"


def test_defaults_include_async_mode():
    assert config.DEFAULTS["async_mode"] == "async"


def test_from_env_async_mode(monkeypatch):
    monkeypatch.setenv("HPYX_ASYNC_MODE", "deferred")
    assert config.from_env()["async_mode"] == "deferred"


def test_from_env_async_mode_default(monkeypatch):
    monkeypatch.delenv("HPYX_ASYNC_MODE", raising=False)
    assert config.from_env()["async_mode"] == "async"


def test_from_env_async_mode_invalid(monkeypatch):
    monkeypatch.setenv("HPYX_ASYNC_MODE", "bogus")
    with pytest.raises(ValueError, match="HPYX_ASYNC_MODE"):
        config.from_env()


@pytest.mark.parametrize("value,expected", [
    ("ASYNC", "async"),
    ("DEFERRED", "deferred"),
    ("  Deferred  ", "deferred"),
])
def test_from_env_async_mode_case_insensitive(monkeypatch, value, expected):
    monkeypatch.setenv("HPYX_ASYNC_MODE", value)
    assert config.from_env()["async_mode"] == expected
