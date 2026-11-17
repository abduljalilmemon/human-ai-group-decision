#!/usr/bin/env python3
"""Append a prompt to ai_logs/prompts.md (works as a Claude Code hook or by hand)."""
import argparse, json, os, sys
from datetime import datetime
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "ai_logs" / "prompts.md"

def model_from_transcript(path):
    """Best effort: last 'model' value found in the session transcript."""
    try:
        model = None
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            m = obj.get("model") or (obj.get("message") or {}).get("model")
            if m:
                model = m
        return model
    except Exception:
        return None

p = argparse.ArgumentParser()
p.add_argument("prompt", nargs="?")
p.add_argument("--tool", default=os.getenv("AI_TOOL", "Claude Code (VS Code extension)"))
p.add_argument("--model", default=os.getenv("AI_MODEL"))
args = p.parse_args()

text, model = args.prompt, args.model
if text is None:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
        text = data.get("prompt") or data.get("user_prompt") or raw
        model = model or model_from_transcript(data.get("transcript_path", ""))
    except (json.JSONDecodeError, AttributeError):
        text = raw

n = (LOG.read_text(encoding="utf-8").count("## Prompt ") + 1) if LOG.exists() else 1
entry = (
    f"\n## Prompt {n} - {datetime.now():%Y-%m-%d %H:%M}\n"
    f"- Tool: {args.tool}\n- Model: {model or 'UNKNOWN - fill in'}\n\n"
    f"```text\n{text.strip()}\n```\n"
)
LOG.parent.mkdir(exist_ok=True)
with LOG.open("a", encoding="utf-8") as f:
    f.write(entry)