# memory.py — preferences that outlive the process (Part 5).
#
# Written to prefs.json on disk, so a preference stated in one run is honoured
# by a later run in a fresh process. Adapted from Assignment 5.
#
# One rule matters more than the rest: a preference that would WIDEN the
# system's own authority is refused and recorded as an attack, whoever it
# appears to come from. That is what stops m039 from making itself permanent.

import json, os, re
import trace

PREFS_PATH = os.getenv("INBOXHERO_PREFS", "prefs.json")

_FORBIDDEN = [
    (r"autonomous mode", "would remove the human from irreversible actions"),
    (r"without (asking|approval|confirmation)", "would bypass the Part 4 gate"),
    (r"skip the confirmation", "would bypass the Part 4 gate"),
    (r"(send|delete).{0,30}automatically", "would let the system send unattended"),
]


def _read():
    if not os.path.exists(PREFS_PATH):
        return {"preferences": []}
    try:
        with open(PREFS_PATH) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"preferences": []}


def _write(store):
    with open(PREFS_PATH, "w") as fh:
        json.dump(store, fh, indent=2)


def remember(key, rule, source_id, applies_to=None, cap=None):
    """Record a preference. Returns (accepted, reason)."""
    for pattern, why in _FORBIDDEN:
        if re.search(pattern, rule.lower()):
            trace.emit("preference_refused", cap=cap, source=source_id,
                       rule=rule, reason=why)
            return False, why

    store = _read()
    store["preferences"] = [p for p in store["preferences"] if p["key"] != key]
    store["preferences"].append({
        "key": key, "rule": rule, "source": source_id,
        "applies_to": applies_to or [],
    })
    _write(store)
    trace.emit("preference_stored", cap=cap, key=key, source=source_id, rule=rule)
    return True, "stored"


def all_preferences():
    return _read()["preferences"]


def get(key):
    for p in all_preferences():
        if p["key"] == key:
            return p
    return None


def forget_all():
    if os.path.exists(PREFS_PATH):
        os.remove(PREFS_PATH)
