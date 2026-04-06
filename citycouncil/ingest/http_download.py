"""Bounded HTTP downloads shared by document sync and extract."""

from __future__ import annotations

import httpx


async def download_bytes_limited(client: httpx.AsyncClient, url: str, max_bytes: int) -> bytes:
    """Stream a GET response and cap total size (raises if ``max_bytes`` exceeded)."""
    async with client.stream("GET", url, follow_redirects=True) as r:
        r.raise_for_status()
        chunks: list[bytes] = []
        total = 0
        async for chunk in r.aiter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"download exceeds max_bytes={max_bytes}")
            chunks.append(chunk)
    return b"".join(chunks)
