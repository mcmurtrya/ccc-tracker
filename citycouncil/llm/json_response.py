"""Parse JSON from LLM chat text (optional markdown fences)."""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json_object(text: str) -> dict[str, Any]:
    """Load a JSON object from a model response, stripping a single ``` / ```json fence if present."""
    t = text.strip()
    fence = re.match(r"^```(?:json)?\s*([\s\S]*?)```\s*$", t)
    if fence:
        t = fence.group(1).strip()
    return json.loads(t)
