# grounding.py — Part 3's honesty check.
#
# A draft may only claim support from message ids that (a) exist in the store
# and (b) were actually retrieved for this draft. Any quoted detail must appear
# verbatim in one of those messages. If the answer is not in the inbox, we say
# so and draft nothing, rather than inventing something plausible.

import re
import data, trace


class Ungrounded(Exception):
    pass


def verify(cited, retrieved_ids, quoted=None, cap=None):
    """Return (ok, problems). Never raises."""
    problems = []
    for mid in cited:
        if not data.exists(mid):
            problems.append("cited %s does not exist in the mail store" % mid)
        elif mid not in retrieved_ids:
            problems.append("cited %s was never read for this draft" % mid)

    for fragment in (quoted or []):
        found = any(fragment.strip() in data.by_id(m)["body"]
                    for m in cited if data.exists(m))
        if not found:
            problems.append("quoted text not found verbatim in any cited message: %r"
                            % fragment[:60])

    ok = not problems
    trace.emit("grounding_check", cap=cap, cited=list(cited), ok=ok,
               problems=problems)
    return ok, problems


def find_fact(message_ids, pattern, cap=None):
    """Pull a fact out of specific earlier messages. Returns (value, source_id).

    Returns (None, None) when the inbox does not contain it — the caller must
    then refuse to draft.
    """
    for mid in message_ids:
        m = data.by_id(mid)
        if not m:
            continue
        hit = re.search(pattern, m["body"])
        if hit:
            value = hit.group(0)
            trace.emit("fact_found", cap=cap, source=mid, chars=len(value))
            return value, mid
    trace.emit("fact_missing", cap=cap, searched=list(message_ids))
    return None, None
