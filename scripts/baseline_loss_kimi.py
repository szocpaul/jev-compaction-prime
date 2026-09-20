#!/usr/bin/env python3
"""Baseline loss measurement — Kimi K3 summarizer arm (extends T002).

Same fixtures, prompts, settings and metric as scripts/baseline_loss.py,
but the summarizer is Kimi K3 via the prime-agent kimi-coding provider
(Anthropic Messages API, https://api.kimi.com/coding). No cache: every run
is a live API call. Rewrites baseline_loss.json into per-summarizer blocks:
  meta.summarizers.{qwen3.8-27b,kimi-k3}  +  "summarizer=<name>" blocks.

Usage: .venv/bin/python scripts/baseline_loss_kimi.py
"""
import importlib.util
import json
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("baseline_loss", REPO / "scripts" / "baseline_loss.py")
bl = importlib.util.module_from_spec(spec)
sys.modules["baseline_loss"] = bl
spec.loader.exec_module(bl)

KIMI_BASE = "https://api.kimi.com/coding"
KIMI_MODEL = "k3"
AUTH = json.loads(Path.home().joinpath(".prime/agent/auth.json").read_text())
KEY = AUTH["kimi-coding"]["key"]
OUT = REPO / "baseline_loss.json"
FIXTURES = REPO / "tests" / "fixtures" / "transcripts"


def kimi_summarize(system_prompt, user_prompt, max_tokens):
    body = json.dumps({
        "model": KIMI_MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }).encode()
    req = urllib.request.Request(KIMI_BASE + "/v1/messages", data=body, headers={
        "content-type": "application/json",
        "x-api-key": KEY,
        "anthropic-version": "2023-06-01",
    })
    with urllib.request.urlopen(req, timeout=1800) as r:
        data = json.loads(r.read())
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    return text, data.get("stop_reason"), data.get("usage", {}), data.get("model", KIMI_MODEL)


def main():
    old = json.loads(OUT.read_text())
    assert "transcripts" in old, "expected legacy single-summarizer baseline_loss.json"

    result = {
        "meta": {
            "purpose": old["meta"]["purpose"] + " — extended: same measurement with two summarizer models",
            "summarizers": {
                "qwen3.8-27b": old["meta"]["summarizer"],
                "kimi-k3": {
                    "base_url": KIMI_BASE, "model": KIMI_MODEL, "api": "anthropic-messages",
                    "note": "prime-agent kimi-coding provider; same prompts/settings as the qwen arm, "
                            "no cache — every run is a live API call",
                },
            },
            "prompts": old["meta"]["prompts"],
            "settings": old["meta"]["settings"],
            "runs_per_transcript": old["meta"]["runs_per_transcript"],
            "cache": old["meta"]["cache"],
            "deviation": old["meta"]["deviation"],
        },
        "summarizer=qwen3.8-27b": {"transcripts": old["transcripts"]},
        "summarizer=kimi-k3": {"transcripts": {}},
    }

    model_seen = KIMI_MODEL
    for fx in sorted(FIXTURES.glob("session-*.jsonl")):
        chain = bl.load_chain(fx)
        cut = bl.find_cut(chain)
        prefix, suffix = chain[:cut], chain[cut:]
        prefix_text = bl.serialize_conversation(prefix)
        suffix_text = bl.full_text(suffix)
        candidates = bl.extract_candidates(prefix_text + "\n" + bl.full_text(prefix), suffix_text)
        user_prompt = (f"<conversation>\n{prefix_text}\n</conversation>\n\n"
                       f"{bl.SUMMARIZATION_PROMPT}\n\n{bl.KERNEL_PERSIST_SUMMARY_NOTE}")
        runs = []
        for run in range(bl.RUNS):
            t0 = time.time()
            summary, stop_reason, usage, model_seen = kimi_summarize(
                bl.SUMMARIZATION_SYSTEM_PROMPT, user_prompt, bl.SUMMARY_MAX_TOKENS)
            lost = [{"kind": k, "value": s} for (k, s) in candidates if s not in summary]
            runs.append({"run": run, "summary_chars": len(summary),
                         "candidates": len(candidates), "kept": len(candidates) - len(lost),
                         "lost": len(lost), "lost_items": lost,
                         "stop_reason": stop_reason, "usage": usage,
                         "duration_s": round(time.time() - t0, 1)})
            print(f"{fx.name} run{run}: candidates={len(candidates)} lost={len(lost)} "
                  f"stop={stop_reason} {time.time()-t0:.0f}s", flush=True)
        lost_counts = [r["lost"] for r in runs]
        result["summarizer=kimi-k3"]["transcripts"][fx.name] = {
            "messages": len(chain), "cut_index": cut,
            "prefix_messages": len(prefix), "suffix_messages": len(suffix),
            "candidates_later_referenced": len(candidates),
            "lost_per_run": lost_counts,
            "lost_min": min(lost_counts), "lost_max": max(lost_counts),
            "lost_mean": sum(lost_counts) / len(lost_counts),
            "runs": runs,
        }
        result["meta"]["summarizers"]["kimi-k3"]["model_reported"] = model_seen
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"written: {OUT}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
