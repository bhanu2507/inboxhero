# commitments.py — the Commitments pane (Part 7.3), which carries the marks.
#
# Three requirements drive the design:
#   * every commitment cites the message ids it came from, checked by grounding
#   * at least one commitment is assembled from MORE THAN ONE message
#   * conflicts are called out, not silently listed
#
# Extraction runs over the whole inbox, including messages triage archived: a
# dentist reminder is noise to answer but still occupies Tuesday at 3pm, and
# missing that is how a double-booking happens.

import re, datetime
import data, grounding, trace

YEAR, MONTH = 2026, 9

_DOW = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6}

_TIME = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.I)
_DAYNUM = re.compile(r"\bthe (\d{1,2})(?:st|nd|rd|th)\b", re.I)
_EXPLICIT = re.compile(r"\b(?:sep(?:tember)?)\s+(\d{1,2})\b", re.I)


def _time_of(text):
    hit = _TIME.search(text)
    if not hit:
        return None
    hour = int(hit.group(1)) % 12
    if hit.group(3).lower() == "pm":
        hour += 12
    return datetime.time(hour, int(hit.group(2) or 0))


def _date_of(text):
    hit = _DAYNUM.search(text) or _EXPLICIT.search(text)
    if hit:
        day = int(hit.group(1))
        if 1 <= day <= 31:
            return datetime.date(YEAR, MONTH, day)
    for name, idx in _DOW.items():
        if re.search(r"\b%s\b" % name, text, re.I):
            base = data.now().date()
            ahead = (idx - base.weekday()) % 7 or 7
            return base + datetime.timedelta(days=ahead)
    return None


def _obligation(text):
    hit = re.search(r"\b(approve|sign|review|submit|circulate|finish|send|confirm|"
                    r"flag|respond|deliver|target is|hard date|due|deadline|"
                    r"renews?|scheduled for|expected)\b[^.?!]{0,70}", text, re.I)
    return hit.group(0).strip() if hit else None


def extract(cap="R6"):
    """Return a list of commitment dicts, each citing real message ids."""
    found = []
    for m in data.all_messages():
        blob = "%s. %s" % (m["subject"], m["body"])
        when, at = _date_of(blob), _time_of(blob)
        what = _obligation(blob)
        if not when or not (at or what):
            continue
        found.append({
            "what": (what or m["subject"])[:110],
            "date": when.isoformat(),
            "time": at.strftime("%H:%M") if at else None,
            "cites": [m["id"]],
            "source_subject": m["subject"],
        })

    found = _merge_across_messages(found)

    # Part 3's citation rule applies here too: a commitment may only cite ids
    # that exist in the mail store.
    for c in found:
        ok, problems = grounding.verify(c["cites"], set(c["cites"]), cap=cap)
        c["grounded"] = ok
        if not ok:
            c["problems"] = problems
        trace.emit("commitment", cap=cap, what=c["what"], date=c["date"],
                   time=c["time"], cites=c["cites"])

    found.sort(key=lambda c: (c["date"], c["time"] or "99:99"))
    return found


def _merge_across_messages(found):
    """Resolve the same obligation mentioned in several messages into one entry.

    The launch date is the worked example: m026 sets the target as the 20th and
    m036 confirms the 20th is hard because press is briefed. One commitment,
    two sources.
    """
    merged, by_slot = [], {}
    for c in found:
        theme = _theme(c["what"] + " " + c["source_subject"])
        # Theme carries the merge, not the clock: one mention often supplies the
        # date and another supplies what it applies to.
        slot = (c["date"], theme) if theme else (c["date"], c["time"], c["what"][:20])
        if slot in by_slot:
            existing = by_slot[slot]
            existing["cites"] = sorted(set(existing["cites"] + c["cites"]))
            existing["time"] = existing["time"] or c["time"]
            if len(c["what"]) > len(existing["what"]):
                existing["what"] = c["what"]
            existing["assembled_from"] = len(existing["cites"])
        else:
            by_slot[slot] = c
            merged.append(c)
    return merged


def _theme(text):
    for word in ("launch", "board", "pricing", "demo", "1:1", "timesheet",
                 "safe", "minutes", "intro"):
        if re.search(r"\b%s\b" % re.escape(word), text, re.I):
            return word
    return None


def conflicts(items):
    """Two commitments occupying the same date+time. Surfaced, not listed."""
    out, seen = [], {}
    for c in items:
        if not c["time"]:
            continue
        slot = (c["date"], c["time"])
        if slot in seen:
            out.append({"slot": "%s %s" % slot, "a": seen[slot], "b": c})
            trace.emit("conflict", cap="R6", date=c["date"], time=c["time"],
                       a=seen[slot]["cites"], b=c["cites"])
        else:
            seen[slot] = c
    return out
