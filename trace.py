# trace.py — append-only run log. Every capability writes here, tagged cap=<id>,
# so each claim in capabilities.json can be checked against evidence.

import json, os, datetime

TRACE_PATH = os.getenv("INBOXHERO_TRACE", "trace.jsonl")
_run_id = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")


def emit(event, cap=None, **fields):
    """Append one event. Never raises — tracing must not break a run."""
    rec = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "run": _run_id,
        "event": event,
        "cap": cap,
    }
    rec.update(fields)
    try:
        with open(TRACE_PATH, "a") as fh:
            fh.write(json.dumps(rec) + "\n")
    except OSError:
        pass
    return rec


def reset():
    """Start a fresh trace file (used by --all)."""
    try:
        os.remove(TRACE_PATH)
    except OSError:
        pass
