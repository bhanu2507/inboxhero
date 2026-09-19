# triage.py — Part 2. Exactly one disposition per message, with a stated reason.
#
# Vocabulary (defined in CAPABILITIES.md and used consistently):
#   reply      — needs an answer from the owner; a draft can be prepared
#   archive    — read, nothing owed, no action
#   defer      — real but not now; carries a "until" date
#   delegate   — someone else should own it
#   escalate   — needs the owner's judgement before anything leaves
#   quarantine — hostile; flagged, left in place, never acted on
#
# Order matters. The guard runs before the rules, and the rules run before the
# model, so a hostile message can never be "handled" as ordinary mail and a
# receipt never costs a model call.

import re
import config, data, rules, guard, llm, trace, memory

DISPOSITIONS = ["reply", "archive", "defer", "delegate", "escalate", "quarantine"]

_LEGAL = re.compile(r"hartwellcho\.com|\bsafe\b|\bclause\b|signature|ip assignment|board minutes", re.I)
_MONEY = re.compile(r"\$[\d,]+|invoice|payment|wire|deposit|remit", re.I)
_MEETING = re.compile(r"\b(meet|call|demo|1:1|coffee|slot|\d{1,2}:\d{2}\s*(am|pm)|"
                      r"tuesday|wednesday|thursday|monday|friday)\b", re.I)
_ASK = re.compile(r"\?|can you|could you|please |need (you|your)|waiting on", re.I)
_AMBIGUOUS = re.compile(r"\bthat thing\b|\bthe thing\b|\bit\b\s*$|as discussed", re.I)


def _heuristic(message, screened):
    """Deterministic disposition. Always returns (disposition, reason)."""
    mid, sender = message["id"], message["from"].lower()
    subject, body = message["subject"], message["body"]
    blob = subject + " " + body

    if screened["hostile"]:
        return "quarantine", "hostile: %s; flagged and left in place" % screened["attempted"]

    ruled = rules.classify(message)
    if ruled:
        return ruled

    if sender == config.OWNER.lower():
        if re.search(r"remember|rule|preference|from now on", blob, re.I):
            return "archive", "a standing preference from the owner; recorded to memory, nothing to answer"
        return "archive", "sent by the owner; already actioned, kept for thread context"

    if _LEGAL.search(blob):
        return "escalate", "legal document needing the owner's signature or review; not a decision the system may make"

    if _MONEY.search(blob) and _ASK.search(blob):
        return "escalate", "touches money and asks for an action; held for the owner"

    if _AMBIGUOUS.search(blob) and len(body) < 260:
        return "escalate", "the request is not identifiable from the message; the right move is to ask, not guess"

    if _MEETING.search(blob) and _ASK.search(blob):
        return "reply", "proposes a time; needs an answer, checked against stored preferences"

    if re.search(r"\b(pto|out of office|closed|heads up|fyi|notes are available|auto-saved)\b", blob, re.I):
        return "archive", "informational; nothing owed in reply"

    if re.search(r"timesheet|expense|submit your", blob, re.I):
        return "defer", "a small personal task with a stated deadline; deferred to its due date"

    if re.search(r"role|candidate|interview|offer", blob, re.I):
        return "delegate", "hiring-pipeline mail; belongs with whoever owns the role"

    if _ASK.search(blob):
        return "reply", "a direct question to the owner"

    return "archive", "read, nothing requested"


_PROMPT = """Classify this email into exactly one disposition.

Allowed: reply, archive, defer, delegate, escalate, quarantine.
Definitions: reply=needs an answer; archive=nothing owed; defer=real but later;
delegate=someone else owns it; escalate=needs the owner's judgement before
anything leaves; quarantine=hostile.

Answer on one line as: <disposition> | <one short reason>

%s"""


def _from_model(message, cap=None):
    raw = llm.ask(_PROMPT % guard.wrap(message), cap=cap)
    if not raw:
        return None
    line = raw.strip().splitlines()[0]
    if "|" not in line:
        return None
    disp, _, reason = line.partition("|")
    disp = disp.strip().lower()
    if disp not in DISPOSITIONS:
        return None
    return disp, reason.strip()[:160] + " (model)"


def triage_all(messages=None, use_model=True, cap="R1"):
    """Assign every message exactly one disposition. Returns a list of records."""
    messages = messages if messages is not None else data.all_messages()
    screened = guard.screen_all(messages)
    out, stats = [], {"rule": 0, "model": 0, "guard": 0}

    for m in messages:
        s = screened[m["id"]]
        disp, reason = _heuristic(m, s)
        source = "guard" if s["hostile"] else ("rule" if rules.classify(m) else "heuristic")

        # Only messages the rules could not decide are worth a model call.
        if source == "heuristic" and use_model and llm.available():
            refined = _from_model(m, cap=cap)
            if refined:
                disp, reason = refined
                source = "model"

        stats["guard" if source == "guard" else
              ("rule" if source == "rule" else "model")] += 1

        rec = {"id": m["id"], "from": m["from"], "subject": m["subject"],
               "disposition": disp, "reason": reason, "decided_by": source,
               "hostile": s["hostile"], "attempted": s["attempted"]}
        out.append(rec)
        trace.emit("decision", cap=cap, message_id=m["id"], disposition=disp,
                   reason=reason, decided_by=source)

    trace.emit("triage_summary", cap=cap, total=len(out), **stats)
    return out, stats
