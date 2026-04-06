"""Ingest pipeline: ELMS poll → normalize → (optional) document sync → PDF extract → embed jobs.

CLI and :mod:`citycouncil.pipeline` call the ``*_standalone`` helpers; the API uses
:func:`citycouncil.ingest.poller.run_poll_cycle` with a shared session. Shared HTTP download
logic lives in :mod:`citycouncil.ingest.http_download`.
"""

from citycouncil.ingest.poller import run_poll_cycle

__all__ = ["run_poll_cycle"]
