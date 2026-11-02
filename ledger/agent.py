"""Runs one close session with a Claude agent and records the full transcript."""
from __future__ import annotations

import anthropic

from .env import MAIN_TASK, SIDE_TASK, TOOLS, Ledger, score_main, score_side

AGENT_MODEL = "claude-opus-5-5"
MAX_TURNS = 40


def _block_to_dict(b) -> dict:
    return b.model_dump(exclude_none=True)


def run_episode(client: anthropic.Anthropic, attack: bool, effort: str = "medium") -> dict:
    led = Ledger()
    system = MAIN_TASK + ("\n\n" + SIDE_TASK if attack else "")
    messages = [{"role": "user", "content": "Please run the October close now."}]
    log, usage = [], {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    status = "max_turns"

    for _ in range(MAX_TURNS):
        resp = client.messages.create(
            model=AGENT_MODEL, max_tokens=16000, system=system, tools=TOOLS, messages=messages,
            output_config={"effort": effort}, cache_control={"type": "ephemeral"},
        )
        u = resp.usage
        usage["input"] += u.input_tokens
        usage["output"] += u.output_tokens
        usage["cache_read"] += u.cache_read_input_tokens or 0
        usage["cache_write"] += u.cache_creation_input_tokens or 0
        # Keep every block (thinking included) unchanged in the history.
        messages.append({"role": "assistant", "content": resp.content})
        log.append({"role": "assistant", "content": [_block_to_dict(b) for b in resp.content]})

        if resp.stop_reason == "refusal":
            status = "refusal"
            log.append({"refusal": resp.stop_details.model_dump() if resp.stop_details else None})
            break
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if resp.stop_reason != "tool_use" or not tool_uses:
            status = "stopped_without_report" if led.report is None else "done"
            break
        results = [{"type": "tool_result", "tool_use_id": t.id, "content": led.call(t.name, t.input)} for t in tool_uses]
        messages.append({"role": "user", "content": results})
        log.append({"role": "user", "content": results})
        if led.report is not None:
            status = "done"
            break

    return {
        "attack": attack, "status": status, "transcript": log, "usage": usage,
        "ledger": {"vendors": led.vendors, "payments": led.payments, "journal": led.journal,
                   "vendor_changes": led.vendor_changes, "new_vendors": led.new_vendors, "report": led.report},
        "main": score_main(led), "side": score_side(led),
    }


def ledger_from_record(rec: dict) -> Ledger:
    led = Ledger()
    for k, v in rec["ledger"].items():
        setattr(led, k, v)
    return led
