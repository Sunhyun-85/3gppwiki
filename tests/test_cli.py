from pathlib import Path

from ran2wiki.cli import build_parser, main
from ran2wiki import cli


def test_init_and_status(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "config.yaml"
    config.write_text(f"paths:\n  data_dir: {tmp_path / 'data'}\n  database: {tmp_path / 'data/db/wiki.db'}\n")
    assert main(["--config", str(config), "init"]) == 0
    assert main(["--config", str(config), "status"]) == 0
    assert "Meetings indexed: 0" in capsys.readouterr().out


def test_ingestion_commands_are_wired() -> None:
    parser = build_parser()
    assert parser.parse_args(["sync", "131bis"]).func.__name__ == "cmd_sync"
    assert parser.parse_args(["update", "131bis"]).func.__name__ == "cmd_update"
    assert parser.parse_args(["extract"]).func.__name__ == "cmd_extract"
    assert parser.parse_args(["index"]).func.__name__ == "cmd_index"


def test_update_indexes_safe_downloads_after_sync_failure(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(cli, "cmd_sync_range", lambda args: calls.append("sync") or 1)
    monkeypatch.setattr(cli, "cmd_extract", lambda args: calls.append("extract") or 0)
    monkeypatch.setattr(cli, "cmd_index", lambda args: calls.append("index") or 0)
    args = type("Args", (), {"value": None})()
    assert cli._run_update(args) == 1
    assert calls == ["sync", "extract", "index"]
