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

        max_tokens=8192 because the insights extractor emits a fat JSON
        (10 sections × multiple items) and the scoring response has nested
        per-criterion sub-scores with evidence quotes. 4096 was getting
        truncated mid-JSON on long transcripts, which then failed to parse
        and caused the background analysis worker to bail silently. The
        Sonnet 4.6 max output is 8192 by default — no extra header needed.
        """
        if not self.live:
            return mock_response
        msg = self._anthropic.messages.create(
            model=self.model,
            max_tokens=8192,
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
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # Most common cause: response was truncated at max_tokens. Surface
            # a more useful error than the cryptic JSONDecodeError so the
            # background task's error_message is actionable.
            stop_reason = getattr(msg, "stop_reason", "unknown")
            preview = text[-200:] if len(text) > 200 else text
            raise RuntimeError(
                f"Claude returned non-JSON (stop_reason={stop_reason}, "
                f"output_len={len(text)}). Likely truncated. "
                f"Last 200 chars: {preview!r}. Original error: {e}"
            )
