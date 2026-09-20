#!/usr/bin/env python3
"""Baseline recovery control arm (SC-004b, T015).

For every candidate LOST from the summary in baseline_loss.json (both summarizer
arms), simulates the agent's live recovery path: ONE search for the candidate in
the retained JSONL history (the fixture file itself — the same session artifact
the agent can grep / search programmatically via the REPL). No LLM calls, no cache.

IMPORTANT INTERPRETATION NOTE (recorded in meta): this measures UPPER-BOUND
retrievability — the search uses the exact lost string as the needle. A live
agent must first suspect the loss and formulate a query from whatever the
summary preserved. The T016 gate decision should weigh this.

Usage: .venv/bin/python scripts/baseline_recovery.py
"""
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("baseline_loss", REPO / "scripts" / "baseline_loss.py")
bl = importlib.util.module_from_spec(spec)
sys.modules["baseline_loss"] = bl
spec.loader.exec_module(bl)

FIXTURES = REPO / "tests" / "fixtures" / "transcripts"
BASELINE = REPO / "baseline_loss.json"
OUT = REPO / "baseline_recovery.json"


def search_corpus(fx_path):
    """Visible text of the full retained history (what the agent can search)."""
    chain = bl.load_chain(fx_path)
    return bl.full_text(chain) + "\n" + bl.serialize_conversation(chain)


def main():
    baseline = json.loads(BASELINE.read_text())
    arms = [k for k in baseline if k.startswith("summarizer=")]
    result = {
        "meta": {
            "purpose": "SC-004b control arm: can the agent recover what the summary lost, "
                       "with ONE search per lost candidate in the retained JSONL history?",
            "method": "exact substring search of each lost candidate in the parsed visible text "
                      "of the full fixture JSONL (the live recovery surface: REPL / grep over the "
                      "session file). One search per candidate; no summary regeneration; no LLM calls.",
            "interpretation_warning": "UPPER BOUND: the needle is the exact lost string. A live agent "
                                      "must suspect the loss and derive a query from the summary first.",
            "baseline_source": "baseline_loss.json",
            "cache": "n/a — local text search only",
        },
    }
    for arm in arms:
        arm_out = {"transcripts": {}}
        arm_lost_total = arm_rec_total = 0
        for fx_name, tr in baseline[arm]["transcripts"].items():
            corpus = search_corpus(FIXTURES / fx_name)
            runs_out = []
            for run in tr["runs"]:
                recovered, unrecovered = [], []
                for item in run["lost_items"]:
                    (recovered if item["value"] in corpus else unrecovered).append(item)
                runs_out.append({
                    "run": run["run"], "lost": run["lost"],
                    "recovered_one_search": len(recovered),
                    "unrecovered": len(unrecovered),
                    "recovery_rate": (len(recovered) / run["lost"]) if run["lost"] else None,
                    "unrecovered_items": unrecovered,
                })
                arm_lost_total += run["lost"]
                arm_rec_total += len(recovered)
                print(f"{arm} {fx_name} run{run['run']}: lost={run['lost']} "
                      f"recovered={len(recovered)}", flush=True)
            rates = [r["recovery_rate"] for r in runs_out if r["recovery_rate"] is not None]
            arm_out["transcripts"][fx_name] = {
                "runs": runs_out,
                "mean_recovery_rate": sum(rates) / len(rates) if rates else None,
            }
            result[arm] = arm_out
            OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        arm_out["totals"] = {
            "lost_total": arm_lost_total,
            "recovered_total": arm_rec_total,
            "recovery_rate": (arm_rec_total / arm_lost_total) if arm_lost_total else None,
        }
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"written: {OUT}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
