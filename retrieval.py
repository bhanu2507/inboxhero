# retrieval.py — finding the earlier message that actually answers a question.
#
# Method: thread-walk first, keyword search as the cross-thread fallback.
# An inbox already carries its own structure in thread_id, so walking the
# thread is cheaper and more precise than embeddings for this corpus: the
# message that answers m008 is four messages up its own thread. Keyword search
# covers the case where the answer lives in a different thread.

import re
import data, trace

_STOP = set("the a an and or of to in on for is are was were be been i you we it "
            "this that these those with can could would should please re fwd my "
            "your our me us do does did not no yes if at by from as".split())


def _terms(text):
    return {w for w in re.findall(r"[a-z0-9_]+", text.lower())
            if w not in _STOP and len(w) > 2}


def walk_thread(message_id, cap=None):
    """Every earlier message in the same thread, oldest first."""
    msg = data.by_id(message_id)
    if msg is None:
        return []
    earlier = [m for m in data.thread(msg["thread_id"])
               if m["timestamp"] < msg["timestamp"]]
    for m in earlier:
        trace.emit("read", cap=cap, message_id=m["id"], via="thread-walk",
                   for_message=message_id)
    return earlier


def keyword(query, exclude=(), limit=5, cap=None):
    """Cross-thread fallback: rank messages by shared terms with the query."""
    q = _terms(query)
    scored = []
    for m in data.all_messages():
        if m["id"] in exclude:
            continue
        overlap = len(q & _terms(m["subject"] + " " + m["body"]))
        if overlap:
            scored.append((overlap, m))
    scored.sort(key=lambda p: (-p[0], p[1]["timestamp"]))
    hits = [m for _, m in scored[:limit]]
    for m in hits:
        trace.emit("read", cap=cap, message_id=m["id"], via="keyword")
    return hits


def context_for(message_id, cap=None):
    """Thread first; if the thread is a singleton, fall back to keyword."""
    msg = data.by_id(message_id)
    earlier = walk_thread(message_id, cap=cap)
    if earlier:
        return earlier, "thread-walk"
    hits = keyword(msg["subject"] + " " + msg["body"], exclude={message_id},
                   cap=cap)
    return hits, "keyword"
