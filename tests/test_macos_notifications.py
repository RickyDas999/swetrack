"""macOS notification adapter (Job Radar Checkpoint 4)."""

from __future__ import annotations

import subprocess

import pytest

from swetrack.infrastructure.notifications import macos as macos_module
from swetrack.infrastructure.notifications.macos import send_macos_notification


def test_returns_false_on_non_darwin_without_calling_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(macos_module.platform, "system", lambda: "Linux")
    calls = []
    monkeypatch.setattr(macos_module.subprocess, "run", lambda *a, **k: calls.append((a, k)))

    result = send_macos_notification(title="T", subtitle="S", message="M")

    assert result is False
    assert calls == []


def test_returns_true_when_osascript_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(macos_module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(macos_module.subprocess, "run", lambda *a, **k: None)

    assert send_macos_notification(title="T", subtitle="S", message="M") is True


def test_returns_false_when_osascript_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "osascript")

    monkeypatch.setattr(macos_module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(macos_module.subprocess, "run", _raise)

    assert send_macos_notification(title="T", subtitle="S", message="M") is False


def test_returns_false_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args, **kwargs):
        raise subprocess.TimeoutExpired("osascript", 5)

    monkeypatch.setattr(macos_module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(macos_module.subprocess, "run", _raise)

    assert send_macos_notification(title="T", subtitle="S", message="M") is False


def test_message_with_quotes_is_safely_embedded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(macos_module.platform, "system", lambda: "Darwin")
    captured = {}

    def _capture_run(args, **kwargs):
        captured["script"] = args[2]

    monkeypatch.setattr(macos_module.subprocess, "run", _capture_run)

    send_macos_notification(title='Say "hi"', subtitle="S", message="M")

    assert '\\"hi\\"' in captured["script"]
