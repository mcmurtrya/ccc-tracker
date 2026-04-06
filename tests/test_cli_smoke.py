"""Smoke tests for :mod:`citycouncil.cli` (argparse paths)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from citycouncil.cli import ROOT, main


def test_cli_help_exits_zero() -> None:
    with patch.object(sys, "argv", ["citycouncil", "--help"]):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code == 0


def test_cli_missing_subcommand_exits_nonzero() -> None:
    with patch.object(sys, "argv", ["citycouncil"]):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code != 0


def test_cli_embed_run_rejects_both_enqueue_and_process_only() -> None:
    with patch.object(
        sys,
        "argv",
        ["citycouncil", "embed-run", "--enqueue-only", "--process-only"],
    ):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code != 0


def test_cli_pipeline_rejects_both_embed_enqueue_and_process_only() -> None:
    with patch.object(
        sys,
        "argv",
        ["citycouncil", "pipeline", "--embed-enqueue-only", "--embed-process-only"],
    ):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code != 0


@patch("citycouncil.cli.subprocess.check_call")
def test_cli_migrate_invokes_alembic(mock_check: MagicMock) -> None:
    with patch.object(sys, "argv", ["citycouncil", "migrate"]):
        main()
    mock_check.assert_called_once()
    call = mock_check.call_args[0][0]
    assert "-m" in call and "alembic" in call
    assert mock_check.call_args[1]["cwd"] == ROOT


@patch("citycouncil.cli.run_poll_standalone", new_callable=AsyncMock)
def test_cli_poll_runs_standalone(mock_poll: AsyncMock) -> None:
    mock_poll.return_value = {"ok": True}
    with patch.object(sys, "argv", ["citycouncil", "poll"]):
        main()
    mock_poll.assert_awaited_once()


@patch("citycouncil.cli.load_csv_standalone", new_callable=AsyncMock)
def test_cli_load_csv(mock_load: AsyncMock, tmp_path: Path) -> None:
    csv_path = tmp_path / "rows.csv"
    csv_path.write_text("h\nv\n", encoding="utf-8")
    mock_load.return_value = SimpleNamespace(
        batch_id="b",
        file_sha256="s",
        row_count=1,
        accepted_count=1,
        duplicate_file_count=0,
        duplicate_db_count=0,
        invalid_count=0,
    )
    with patch.object(sys, "argv", ["citycouncil", "load-csv", str(csv_path)]):
        main()
    mock_load.assert_awaited_once()
