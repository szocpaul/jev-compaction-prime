#!/usr/bin/env python3
"""Baseline loss measurement (SC-004, T002).

Runs the EXISTING Prime Agent summarization-based compaction (read-only
replica of the prompts/serialization from prime-agent dist/core/compaction,
nothing modified) on each fixture transcript and counts how many
later-referenced file paths / error messages are lost from the summary.

Per-transcript breakdown, 3 repeated runs (noise interval), no caching.

Usage:
    .venv/bin/python scripts/baseline_loss.py

Requires: local summarizer endpoint (OpenAI-compatible), see --base-url.
"""
import argparse
import json
import math
import re
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "tests" / "fixtures" / "transcripts"
OUT = REPO / "baseline_loss.json"

DEFAULT_BASE_URL = "http://desktop-c5ikame-1.tailee6bc1.ts.net:8033/v1"
KEEP_RECENT_TOKENS = 20000          # prime-agent default (compaction.js)
RESERVE_TOKENS = 16384              # prime-agent default
SUMMARY_MAX_TOKENS = math.floor(0.8 * RESERVE_TOKENS)  # generateSummary()
RUNS = 3                            # noise measurement repeats (T002)

# --- prompts copied verbatim from prime-agent dist/core/compaction/ (read-only replica) ---
SUMMARIZATION_SYSTEM_PROMPT = """You are a context summarization assistant. Your task is to read a conversation between a user and an AI coding assistant, then produce a structured summary following the exact format specified.

Do NOT continue the conversation. Do NOT respond to any questions in the conversation. ONLY output the structured summary."""

SUMMARIZATION_PROMPT = """The messages above are a conversation to summarize. Create a structured context checkpoint summary that another LLM will use to continue the work.

Use this EXACT format:

## Goal
[What is the user trying to accomplish? Can be multiple items if the session covers different tasks.]

## Constraints & Preferences
- [Any constraints, preferences, or requirements mentioned by user]
- [Or "(none)" if none were mentioned]

## Progress
### Done
- [x] [Completed tasks/changes]

### In Progress
- [ ] [Current work]

### Blocked
- [Issues preventing progress, if any]

## Key Decisions
- **[Decision]**: [Brief rationale]

## Next Steps
1. [Ordered list of what should happen next]

## Critical Context
- [Any data, examples, or references needed to continue]
- [Or "(none)" if not applicable]

Keep each section concise. Preserve exact file paths, function names, and error messages."""

KERNEL_PERSIST_SUMMARY_NOTE = ("Note: the Python kernel keeps running after this summary — every Python variable, "
    "import, and helper you defined stays available. The cells that defined them won't appear above, so record "
    "in the summary any names worth remembering so you reuse them instead of redefining them.")

TOOL_RESULT_MAX_CHARS = 2000
TOOL_RESULT_TAIL_CHARS = 500


def truncate_for_summary(text, max_chars=TOOL_RESULT_MAX_CHARS):
    if len(text) <= max_chars:
        return text
    marker_max = len(f"[... {len(text)} characters truncated; first {max_chars} and last {TOOL_RESULT_TAIL_CHARS} kept ...]")
    head = max_chars - TOOL_RESULT_TAIL_CHARS - marker_max - 4
    elided = len(text) - head - TOOL_RESULT_TAIL_CHARS
    return (f"{text[:head]}\n\n[... {elided} characters truncated; first {head} and last "
            f"{TOOL_RESULT_TAIL_CHARS} kept ...]\n\n{text[len(text) - TOOL_RESULT_TAIL_CHARS:]}")


def serialize_conversation(msgs):
    """Read-only replica of serializeConversation() from compaction/utils.js."""
    nl = chr(10)
    parts = []
    for msg in msgs:
        role = msg["role"]
        c = msg.get("content")
        if role == "user":
            content = c if isinstance(c, str) else "".join(b.get("text", "") for b in c if b.get("type") == "text")
            if content:
                parts.append(f"[User]: {content}")
        elif role == "assistant":
            texts, thinks, calls = [], [], []
            for b in (c if isinstance(c, list) else []):
                if b.get("type") == "text":
                    texts.append(b.get("text", ""))
                elif b.get("type") == "thinking":
                    thinks.append(b.get("thinking", ""))
                elif b.get("type") == "toolCall":
                    args = b.get("arguments") or {}
                    args_str = ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in args.items())
                    calls.append(f"{b.get('name')}({args_str})")
            if thinks:
                parts.append("[Assistant thinking]: " + nl.join(thinks))
            if texts:
                parts.append("[Assistant]: " + nl.join(texts))
            if calls:
                parts.append("[Assistant tool calls]: " + "; ".join(calls))
        elif role == "toolResult":
            content = "".join(b.get("text", "") for b in (c if isinstance(c, list) else []) if b.get("type") == "text")
            if content:
                parts.append(f"[Tool result]: {truncate_for_summary(content)}")
    return (nl + nl).join(parts)


def load_chain(path):
    """Main branch of the session tree: walk parentIds from the latest leaf."""
    entries = {}
    for line in open(path):
        e = json.loads(line)
        if "id" in e:
            entries[e["id"]] = e
    msg_ids = {i for i, e in entries.items() if e.get("type") == "message"}
    # parentIds of message entries only — agent_status/session_state entries also
    # carry parentId and would falsely disqualify real leaves
    parents = {e.get("parentId") for e in entries.values() if e.get("type") == "message"}
    leaves = [i for i in msg_ids if i not in parents]
    if not leaves:
        leaves = [list(msg_ids)[-1]] if msg_ids else []
    leaf = max(leaves, key=lambda i: entries[i].get("timestamp", ""))
    chain = []
    cur = leaf
    while cur and cur in entries:
        e = entries[cur]
        if e.get("type") == "message":
            chain.append(e["message"])
        cur = e.get("parentId")
    return list(reversed(chain))


def estimate_tokens(msg):
    """chars/4 heuristic, replica of estimateTokens() in compaction.js."""
    chars = 0
    c = msg.get("content")
    role = msg["role"]
    if role == "user":
        if isinstance(c, str):
            chars = len(c)
        elif isinstance(c, list):
            chars = sum(len(b["text"]) for b in c if b.get("type") == "text" and b.get("text"))
    elif role == "assistant":
        for b in (c if isinstance(c, list) else []):
            if b.get("type") == "text":
                chars += len(b.get("text") or "")
            elif b.get("type") == "thinking":
                chars += len(b.get("thinking") or "")
            elif b.get("type") == "toolCall":
                chars += len(b.get("name", "")) + len(json.dumps(b.get("arguments") or {}))
    else:
        if isinstance(c, str):
            chars = len(c)
        elif isinstance(c, list):
            chars = sum(len(b["text"]) for b in c if b.get("type") == "text" and b.get("text"))
    return math.ceil(chars / 4)


def find_cut(msgs, keep_recent_tokens=KEEP_RECENT_TOKENS):
    """Prefix/suffix split. Real code cuts at a user-message boundary after
    accumulating keepRecentTokens from the end; autonomous fixtures often have
    a single user turn, so fall back to the raw token-accumulation index."""
    acc = 0
    cut = None
    for i in range(len(msgs) - 1, -1, -1):
        acc += estimate_tokens(msgs[i])
        if acc >= keep_recent_tokens:
            cut = i
            break
    if cut is None:
        cut = int(0.7 * len(msgs))
    # prefer a user boundary if one exists within the kept window
    user_cut = cut
    while user_cut < len(msgs) and msgs[user_cut]["role"] != "user":
        user_cut += 1
    if user_cut < len(msgs) - 1:
        cut = user_cut
    # keep cut inside [10%, 90%] so both prefix and suffix are non-trivial
    lo, hi = max(1, int(0.1 * len(msgs))), max(2, int(0.9 * len(msgs)))
    return max(lo, min(cut, hi))


ABS_PATH_RE = re.compile(r"/[\w.\-@+]+(?:/[\w.\-@+]+)+/?")
REL_PATH_RE = re.compile(r"\b[\w.\-]+(?:/[\w.\-]+)+\.(?:py|js|mjs|cjs|ts|json|jsonl|md|toml|ya?ml|tgz|sh|txt|log|lock|csv|html|css)\b")
ERROR_LINE_RE = re.compile(r"(?i)\b(error|exception|traceback|failed|failure|errno|denied|not found|cannot |can't |exit code [1-9]|E[A-Z]{4,}|timed out|refused)\b")


def full_text(msgs):
    """All visible text of the messages (text blocks, tool-call args, tool results)."""
    parts = []
    for msg in msgs:
        c = msg.get("content")
        if isinstance(c, str):
            parts.append(c)
        elif isinstance(c, list):
            for b in c:
                if b.get("type") == "text":
                    parts.append(b.get("text", ""))
                elif b.get("type") == "toolCall":
                    parts.append(json.dumps(b.get("arguments") or {}, ensure_ascii=False))
    return "\n".join(parts)


def extract_candidates(prefix_text, suffix_text):
    """Strings present in BOTH prefix and suffix (= referenced again later)."""
    cands = set()
    for m in ABS_PATH_RE.finditer(prefix_text):
        s = m.group(0).rstrip("/")
        if len(s) >= 10:
            cands.add(("path", s))
    for m in REL_PATH_RE.finditer(prefix_text):
        s = m.group(0)
        if len(s) >= 10:
            cands.add(("path", s))
    seen_lines = set()
    for line in prefix_text.splitlines():
        s = line.strip()
        if 15 <= len(s) <= 300 and ERROR_LINE_RE.search(s) and s not in seen_lines:
            seen_lines.add(s)
            cands.add(("error", s))
    return sorted([(k, s) for (k, s) in cands if s in suffix_text])


def chat_complete(base_url, model, system_prompt, user_prompt, max_tokens):
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions",
                                 data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--runs", type=int, default=RUNS)
    args = ap.parse_args()

    with urllib.request.urlopen(args.base_url.rstrip("/") + "/models", timeout=15) as r:
        models = json.loads(r.read())
    model = models["data"][0]["id"]
    print(f"summarizer endpoint: {args.base_url} model: {model}", flush=True)

    result = {
        "meta": {
            "purpose": "SC-004 baseline: loss of later-referenced file paths / error messages "
                       "under the EXISTING summarization-based compaction",
            "summarizer": {"base_url": args.base_url, "model": model,
                           "note": "prime-agent compaction uses the session model; the configured "
                                   "local-tailscale provider endpoint serves the measurement"},
            "prompts": "verbatim replica of SUMMARIZATION_SYSTEM_PROMPT / SUMMARIZATION_PROMPT / "
                       "KERNEL_PERSIST_SUMMARY_NOTE + serializeConversation from prime-agent dist",
            "settings": {"keepRecentTokens": KEEP_RECENT_TOKENS, "reserveTokens": RESERVE_TOKENS,
                         "summaryMaxTokens": SUMMARY_MAX_TOKENS},
            "runs_per_transcript": args.runs,
            "cache": "none — every run calls the summarizer live",
            "deviation": "T001 asked for 80-150 tool-call transcripts; only 1 of 48 real sessions "
                         "qualifies, so the 6 largest real sessions were used (34-98 tool calls).",
        },
        "transcripts": {},
    }

    for fx in sorted(FIXTURES.glob("session-*.jsonl")):
        chain = load_chain(fx)
        cut = find_cut(chain)
        prefix, suffix = chain[:cut], chain[cut:]
        prefix_text = serialize_conversation(prefix)
        suffix_text = full_text(suffix)
        candidates = extract_candidates(prefix_text + "\n" + full_text(prefix), suffix_text)
        user_prompt = f"<conversation>\n{prefix_text}\n</conversation>\n\n{SUMMARIZATION_PROMPT}\n\n{KERNEL_PERSIST_SUMMARY_NOTE}"
        runs = []
        for run in range(args.runs):
            summary = chat_complete(args.base_url, model, SUMMARIZATION_SYSTEM_PROMPT,
                                    user_prompt, SUMMARY_MAX_TOKENS)
            lost = [{"kind": k, "value": s} for (k, s) in candidates if s not in summary]
            kept = len(candidates) - len(lost)
            runs.append({"run": run, "summary_chars": len(summary),
                         "candidates": len(candidates), "kept": kept, "lost": len(lost),
                         "lost_items": lost})
            print(f"{fx.name} run{run}: candidates={len(candidates)} lost={len(lost)}", flush=True)
        lost_counts = [r["lost"] for r in runs]
        result["transcripts"][fx.name] = {
            "messages": len(chain), "cut_index": cut,
            "prefix_messages": len(prefix), "suffix_messages": len(suffix),
            "candidates_later_referenced": len(candidates),
            "lost_per_run": lost_counts,
            "lost_min": min(lost_counts), "lost_max": max(lost_counts),
            "lost_mean": sum(lost_counts) / len(lost_counts),
            "runs": runs,
        }
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"written: {OUT}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
