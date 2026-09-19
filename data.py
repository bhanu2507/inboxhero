# data.py — the mail store. The ONLY module that reads inbox.json.
# Everything downstream asks this module for messages, which is what makes the
# citation check in grounding.py meaningful: a cited id is checked against here.

import json, datetime
import config

_messages = None


def _load():
    global _messages
    if _messages is None:
        with open(config.INBOX_PATH) as fh:
            _messages = json.load(fh)
        _messages.sort(key=lambda m: m["timestamp"])
    return _messages


def all_messages():
    return list(_load())


def by_id(mid):
    for m in _load():
        if m["id"] == mid:
            return m
    return None


def exists(mid):
    return by_id(mid) is not None


def thread(thread_id):
    """Every message in a thread, oldest first."""
    return [m for m in _load() if m["thread_id"] == thread_id]


def thread_of(mid):
    m = by_id(mid)
    return thread(m["thread_id"]) if m else []


def sent_by_owner():
    return [m for m in _load() if m["from"] == config.OWNER]


def parse_ts(m):
    return datetime.datetime.fromisoformat(m["timestamp"])


def now():
    """'Now' is anchored to the newest message so runs are reproducible."""
    return max(parse_ts(m) for m in _load())
