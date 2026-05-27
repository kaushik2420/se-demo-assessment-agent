"""
Thin Claude wrapper. Falls back to deterministic mock responses when no API key
is set, so the prototype runs end-to-end for demos.
"""

from __future__ import annotations

import json
import os
from typing import Optional


class LLMClient:
    def __init__(self, model: Optional[str] = None, live: Optional[bool] = None):
        self.model = model or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
        if live is None:
            live = bool(os.getenv("ANTHROPIC_API_KEY"))
        self.live = live
        self._anthropic = None
        if self.live:
            try:
                import anthropic
                self._anthropic = anthropic.Anthropic()
            except Exception as e:
                print(f"[LLMClient] Falling back to mock — anthropic init failed: {e}")
                self.live = False

    def chat_json(self, system: str, user: str, mock_response: dict) -> dict:
        """
        Call Claude and parse JSON output. If not live, return mock_response.
        mock_response is the deterministic fallback so the demo always runs.
        """
        if not self.live:
            return mock_response
        msg = self._anthropic.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = msg.content[0].text.strip()
        # strip ```json fences if Claude added them
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        return json.loads(text)
