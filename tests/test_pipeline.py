from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from citycouncil.pipeline import run_pipeline_standalone


async def test_pipeline_all_skipped() -> None:
    out = await run_pipeline_standalone(
        run_migrate=False,
        run_poll=False,
        run_sync_documents=False,
        run_extract_documents=False,
        run_embed_run=False,
    )
    assert [s["step"] for s in out["steps"]] == [
        "migrate",
        "poll",
        "sync-documents",
        "extract-documents",
        "embed-run",
    ]
    assert all(s["result"] == "skipped" for s in out["steps"])


def test_pipeline_rejects_embed_enqueue_and_process() -> None:
    import asyncio

    with pytest.raises(ValueError, match="enqueue-only and process-only"):
        asyncio.run(
            run_pipeline_standalone(
                run_migrate=False,
                run_poll=False,
                run_sync_documents=False,
                run_extract_documents=False,
                run_embed_run=True,
                embed_enqueue_only=True,
                embed_process_only=True,
            )
        )


@pytest.mark.asyncio
@patch("citycouncil.pipeline.embed_run_standalone", new_callable=AsyncMock)
@patch("citycouncil.pipeline.extract_documents_standalone", new_callable=AsyncMock)
@patch("citycouncil.pipeline.sync_documents_standalone", new_callable=AsyncMock)
@patch("citycouncil.pipeline.run_poll_standalone", new_callable=AsyncMock)
@patch("citycouncil.pipeline.subprocess.check_call")
async def test_pipeline_executes_each_step_when_enabled(
    mock_check: MagicMock,
    mock_poll: AsyncMock,
    mock_sync: AsyncMock,
    mock_extract: AsyncMock,
    mock_embed: AsyncMock,
) -> None:
    mock_poll.return_value = {"p": 1}
    mock_sync.return_value = {"s": 1}
    mock_extract.return_value = {"e": 1}
    mock_embed.return_value = {"m": 1}
    out = await run_pipeline_standalone(
        settings=MagicMock(),
        run_migrate=True,
        run_poll=True,
        run_sync_documents=True,
        run_extract_documents=True,
        run_embed_run=True,
    )
    mock_check.assert_called_once()
    names = [s["step"] for s in out["steps"]]
    assert names == [
        "migrate",
        "poll",
        "sync-documents",
        "extract-documents",
        "embed-run",
    ]
    assert out["steps"][0]["result"] == {"status": "ok"}
    assert out["steps"][1]["result"] == {"p": 1}
