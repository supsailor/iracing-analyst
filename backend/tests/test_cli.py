import sys

from iracing_analyst import cli


def test_default_command_starts_server(monkeypatch):
    calls = {}
    monkeypatch.setattr(sys, "argv", ["iracing-analyst"])
    monkeypatch.setattr(cli, "free_port", lambda: 9123)
    monkeypatch.setattr(cli.threading, "Timer", lambda *_: type("Timer", (), {"start": lambda self: None})())
    monkeypatch.setattr(cli.uvicorn, "run", lambda app, **kwargs: calls.update(kwargs))

    cli.main()

    assert calls == {"host": "127.0.0.1", "port": 9123, "log_level": "info"}
