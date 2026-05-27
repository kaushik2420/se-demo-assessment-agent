"""
Manual upload path: SE drops a .vtt / .srt / .txt transcript or .mp4 / .mp3
recording into S3 (`s3://ss-se-uploads/{se_email}/`). A trigger Lambda
calls into our pipeline.

For audio/video files, we run AWS Transcribe (or push to Recall.ai's
async transcription endpoint).
"""

from __future__ import annotations

import os
import re
from pathlib import Path


def load_transcript_file(path: str | Path) -> str:
    """Load a .txt / .vtt / .srt transcript and normalize to 'Speaker: text' lines."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".txt":
        return text
    if p.suffix.lower() in (".vtt", ".srt"):
        # crude WEBVTT/SRT cleanup; in prod use webvtt-py / pysrt
        lines = [l for l in text.splitlines() if l and "-->" not in l and not l.isdigit() and l != "WEBVTT"]
        return "\n".join(lines)
    raise ValueError(f"Unsupported transcript format: {p.suffix}")
