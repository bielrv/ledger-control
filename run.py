"""Run sessions, then monitors and controls, writing one JSON record per session.

    python run.py episodes --honest 15 --attack 0 --out results/runs.jsonl
    python run.py inject --in results/runs.jsonl --out results/sessions.jsonl
    python run.py monitor --in results/sessions.jsonl --out results/scored.jsonl
    python analyze.py results/scored.jsonl
"""
from __future__ import annotations

import argparse
import json
import pathlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

from ledger import controls
from ledger.agent import ledger_from_record, run_episode
from ledger.attacks import PATTERNS, inject as inject_attack
from ledger.monitor import score

MONITORS = {"haiku": "claude-haiku-5-5", "opus": "claude-opus-5-5"}
lock = threading.Lock()


def episodes(args):
    client = anthropic.Anthropic(max_retries=6)
    jobs = [False] * args.honest + [True] * args.attack
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(args.workers) as pool:
        futs = {pool.submit(run_episode, client, attack): i for i, attack in enumerate(jobs)}
        for f in as_completed(futs):
            rec = f.result()
            rec["run_id"] = f"{'A' if rec['attack'] else 'H'}{futs[f]:03d}"
            with lock, out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(rec["run_id"], rec["status"], "main", rec["main"]["main_score"],
                  "side", rec["side"]["paid_to_attacker"], flush=True)


def inject(args):
    """Keep every completed honest session and add attacked copies, each pattern equally often."""
    honest = [r for r in map(json.loads, open(args.inp, encoding="utf-8")) if not r["attack"] and r["status"] == "done"]
    names = list(PATTERNS)
    with open(args.out, "w", encoding="utf-8") as fh:
        for i, rec in enumerate(honest):
            rec["pattern"] = None
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            for k in range(args.per_run):
                fh.write(json.dumps(inject_attack(rec, names[(i * args.per_run + k) % len(names)]), ensure_ascii=False) + "\n")
    print(f"{len(honest)} honest sessions, {len(honest) * args.per_run} attacked copies -> {args.out}")


def monitor(args):
    client = anthropic.Anthropic(max_retries=6)
    recs = [json.loads(l) for l in open(args.inp, encoding="utf-8")]

    def one(rec):
        led = ledger_from_record(rec)
        rec["controls"] = {"naive": controls.naive(led), "aware": controls.aware(led)}
        rec["monitor"] = {}
        for name, model in MONITORS.items():
            rec["monitor"][name] = score(client, model, rec["transcript"])
            rec["monitor"][name + "+controls"] = score(client, model, rec["transcript"], rec["controls"]["aware"])
        return rec

    with ThreadPoolExecutor(args.workers) as pool, open(args.out, "w", encoding="utf-8") as fh:
        for rec in pool.map(one, recs):
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(rec["run_id"], {k: v["suspicion"] for k, v in rec["monitor"].items()},
                  "aware exceptions", len(rec["controls"]["aware"]), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("episodes")
    e.add_argument("--honest", type=int, default=15)
    e.add_argument("--attack", type=int, default=15)
    e.add_argument("--workers", type=int, default=4)
    e.add_argument("--out", default="results/runs.jsonl")
    i = sub.add_parser("inject")
    i.add_argument("--in", dest="inp", default="results/runs.jsonl")
    i.add_argument("--out", default="results/sessions.jsonl")
    i.add_argument("--per-run", type=int, default=2)
    m = sub.add_parser("monitor")
    m.add_argument("--in", dest="inp", default="results/sessions.jsonl")
    m.add_argument("--out", default="results/scored.jsonl")
    m.add_argument("--workers", type=int, default=4)
    a = p.parse_args()
    {"episodes": episodes, "inject": inject, "monitor": monitor}[a.cmd](a)
