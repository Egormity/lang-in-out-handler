"""System proxy discovery stays deterministic and shared by HTTP and speech."""

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from websocket._url import get_proxy_info

from lang_handler import network, system_proxy
from lang_handler.errors import ServiceError


@pytest.fixture(autouse=True)
def clear_proxy_environment(monkeypatch):
    for key in list(os.environ):
        if key.lower().endswith("_proxy"):
            monkeypatch.delenv(key)


def system_result(monkeypatch, value):
    calls = []

    def resolve():
        calls.append(True)
        return value

    monkeypatch.setattr(system_proxy, "desktop_proxy", resolve)
    monkeypatch.setattr(network, "desktop_proxy", resolve, raising=False)
    return calls


def helper_result(monkeypatch, payload, *, code=0):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=code, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(system_proxy.subprocess, "run", run)
    return calls


def test_explicit_override_wins_even_when_environment_excludes_openai(monkeypatch):
    calls = system_result(monkeypatch, "http://desktop.invalid:7897")
    monkeypatch.setenv("HTTPS_PROXY", "http://environment.invalid:8080")
    monkeypatch.setenv("NO_PROXY", "api.openai.com")
    assert network.proxy_url("  socks://override.invalid:1080  ") == "socks5://override.invalid:1080"
    options = network.websocket_proxy("http://override.invalid:8181")
    assert options["http_proxy_host"] == "override.invalid"
    assert options["http_no_proxy"] == ["__lang_handler_no_bypass__"]
    # websocket-client otherwise independently reapplies NO_PROXY ahead of a
    # supplied proxy host, making its connection differ from httpx trust_env=False.
    selected = get_proxy_info(
        "api.openai.com", True,
        proxy_host=options["http_proxy_host"], proxy_port=options["http_proxy_port"],
        no_proxy=options["http_no_proxy"],
    )
    assert selected[:2] == ("override.invalid", 8181)
    assert calls == []


def test_environment_precedence_and_blank_override(monkeypatch):
    calls = system_result(monkeypatch, "http://desktop.invalid:7897")
    monkeypatch.setenv("ALL_PROXY", "socks5://fallback.invalid:1080")
    monkeypatch.setenv("HTTPS_PROXY", "http://uppercase.invalid:8080")
    monkeypatch.setenv("https_proxy", "http://lowercase.invalid:8081")
    assert network.proxy_url("   ") == "http://lowercase.invalid:8081"
    monkeypatch.delenv("https_proxy")
    assert network.proxy_url() == "http://uppercase.invalid:8080"
    monkeypatch.delenv("HTTPS_PROXY")
    assert network.proxy_url() == "socks5://fallback.invalid:1080"
    assert calls == []


@pytest.mark.parametrize("excluded", ["*", "api.openai.com", ".openai.com"])
def test_environment_exclusions_select_direct_for_both_transports(monkeypatch, excluded):
    calls = system_result(monkeypatch, "http://desktop.invalid:7897")
    monkeypatch.setenv("https_proxy", "http://environment.invalid:8080")
    monkeypatch.setenv("no_proxy", excluded)
    assert network.proxy_url() is None
    assert network.websocket_proxy() == {"http_no_proxy": ["*"]}
    assert calls == []


def test_desktop_launch_uses_system_proxy_and_realtime_auth(monkeypatch):
    calls = system_result(monkeypatch, "http://user%40name:p%3Ass@desktop.invalid:7897")
    selected = network.proxy_url()
    assert selected == "http://user%40name:p%3Ass@desktop.invalid:7897"
    options = network.websocket_proxy()
    assert options["http_proxy_host"] == "desktop.invalid"
    assert options["http_proxy_port"] == 7897
    assert options["http_proxy_auth"] == ("user@name", "p:ss")
    assert options["proxy_type"] == "http"
    assert options["http_no_proxy"] == ["__lang_handler_no_bypass__"]
    assert len(calls) == 2


def test_automatic_resolution_rechecks_changed_desktop_settings(monkeypatch):
    values = iter(["http://first.invalid:7897", "socks5://second.invalid:1080", None])
    resolve = lambda: next(values)
    monkeypatch.setattr(system_proxy, "desktop_proxy", resolve)
    monkeypatch.setattr(network, "desktop_proxy", resolve, raising=False)
    assert network.proxy_url() == "http://first.invalid:7897"
    assert network.proxy_url() == "socks5://second.invalid:1080"
    assert network.websocket_proxy() == {"http_no_proxy": ["*"]}


@pytest.mark.parametrize(
    ("proxies", "expected"),
    [
        (["http://desktop.invalid:7897", "direct://"], "http://desktop.invalid:7897"),
        (["direct://", "http://desktop.invalid:7897"], None),
        (["socks4://old.invalid:1080", "socks5://new.invalid:1080"], "socks5://new.invalid:1080"),
        (["https://secure.invalid:443"], "https://secure.invalid:443"),
        (["socks5h://dns.invalid:1080"], "socks5h://dns.invalid:1080"),
    ],
)
def test_system_candidates_keep_resolver_order(monkeypatch, proxies, expected):
    helper_result(monkeypatch, {"ok": True, "proxies": proxies})
    assert system_proxy.desktop_proxy() == expected


def test_helper_uses_system_python_and_isolates_terminal_environment(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://terminal.invalid:8080")
    monkeypatch.setenv("custom_proxy", "unused")
    monkeypatch.setenv("PYTHONPATH", "/tmp/not-system-python")
    monkeypatch.setenv("PYTHONHOME", "/tmp/not-system-python")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "ubuntu:GNOME")
    calls = helper_result(monkeypatch, {"ok": True, "proxies": ["direct://"]})
    assert system_proxy.desktop_proxy() is None
    command, options = calls[0]
    assert command[0] == "/usr/bin/python3"
    assert Path(command[1]).name == "gnome_proxy.py"
    assert command[2] == "https://api.openai.com/v1"
    assert options["timeout"] == 5
    assert options["stderr"] == subprocess.DEVNULL
    assert options["stdout"] == subprocess.PIPE
    assert options["text"]
    assert not any(key.lower().endswith("_proxy") for key in options["env"])
    assert "PYTHONPATH" not in options["env"]
    assert "PYTHONHOME" not in options["env"]
    assert options["env"]["XDG_CURRENT_DESKTOP"] == "ubuntu:GNOME"
    assert os.environ["HTTPS_PROXY"] == "http://terminal.invalid:8080"


@pytest.mark.parametrize(
    "payload",
    [
        {"ok": True, "proxies": []},
        {"ok": True, "proxies": "http://invalid-shape.invalid"},
        {"ok": True, "proxies": None},
        {"ok": True, "proxies": [None]},
        {"ok": True, "proxies": ["socks4://unsupported.invalid:1080"]},
        {"ok": False, "message": "private-proxy-password"},
    ],
)
def test_invalid_or_failed_system_resolution_never_silently_goes_direct(monkeypatch, payload):
    helper_result(monkeypatch, payload)
    with pytest.raises(ServiceError) as caught:
        system_proxy.desktop_proxy()
    assert "private-proxy-password" not in str(caught.value)


def test_malformed_helper_output_is_sanitized(monkeypatch):
    monkeypatch.setattr(
        system_proxy.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="private-proxy-password", stderr=""),
    )
    with pytest.raises(ServiceError) as caught:
        system_proxy.desktop_proxy()
    assert "private-proxy-password" not in str(caught.value)


def test_helper_timeout_does_not_expose_subprocess_output(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            "helper", 5, output="private-proxy-password", stderr="private-proxy-password"
        )

    monkeypatch.setattr(system_proxy.subprocess, "run", timeout)
    with pytest.raises(ServiceError) as caught:
        system_proxy.desktop_proxy()
    assert "private-proxy-password" not in str(caught.value)


def test_unavailable_gio_can_use_direct_on_minimal_linux(monkeypatch):
    helper_result(monkeypatch, {"ok": False, "unavailable": True})
    assert system_proxy.desktop_proxy() is None


def test_non_linux_does_not_spawn_the_gnome_helper(monkeypatch):
    monkeypatch.setattr(system_proxy.sys, "platform", "win32")
    calls = helper_result(monkeypatch, {"ok": True, "proxies": ["http://must-not-read.invalid"]})
    assert system_proxy.desktop_proxy() is None
    assert calls == []
