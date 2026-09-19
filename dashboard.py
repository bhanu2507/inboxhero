# dashboard.py — Part 7. Exactly three panes, written from a completed run.
# Reproducible: everything here comes from the run's own records, never typed in.

import json, html, datetime
import commitments, trace

JSON_PATH, HTML_PATH = "dashboard.json", "dashboard.html"


def build(decisions, pending, flagged, cap="R6"):
    items = commitments.extract(cap=cap)
    clashes = commitments.conflicts(items)
    doc = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "messages": len(decisions),
        "panes": {
            "pending_actions": pending,
            "flagged": flagged,
            "commitments": items,
        },
        "conflicts": clashes,
    }
    with open(JSON_PATH, "w") as fh:
        json.dump(doc, fh, indent=2)
    _render(doc)
    trace.emit("dashboard", cap=cap, pending=len(pending), flagged=len(flagged),
               commitments=len(items), conflicts=len(clashes))
    return doc


def _rows(rows, cols):
    if not rows:
        return "<p class=empty>Nothing in this pane.</p>"
    head = "".join("<th>%s</th>" % html.escape(c[0]) for c in cols)
    body = ""
    for r in rows:
        body += "<tr>" + "".join(
            "<td>%s</td>" % html.escape(str(c[1](r) or "--")) for c in cols
        ) + "</tr>"
    return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (head, body)


def _render(doc):
    panes = doc["panes"]
    conflict_html = ""
    for c in doc["conflicts"]:
        conflict_html += (
            "<div class=conflict><strong>CONFLICT at %s</strong><br>%s "
            "<em>(%s)</em><br>collides with %s <em>(%s)</em></div>" % (
                html.escape(c["slot"]),
                html.escape(c["a"]["what"]), ", ".join(c["a"]["cites"]),
                html.escape(c["b"]["what"]), ", ".join(c["b"]["cites"])))

    page = """<!doctype html><meta charset=utf-8>
<title>inboxHero dashboard</title>
<style>
 body{font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      margin:0;padding:24px;background:#faf9f7;color:#1c1b19}
 h1{font-size:20px;margin:0 0 4px} .meta{color:#6b6a67;margin-bottom:24px}
 h2{font-size:15px;text-transform:uppercase;letter-spacing:.06em;
    border-bottom:2px solid #1c1b19;padding-bottom:6px;margin:32px 0 12px}
 table{border-collapse:collapse;width:100%%;background:#fff;
       box-shadow:0 1px 2px rgba(0,0,0,.08)}
 th{text-align:left;background:#f0efec;padding:8px 10px;font-size:12px;
    text-transform:uppercase;letter-spacing:.04em}
 td{padding:8px 10px;border-top:1px solid #eceae6;vertical-align:top}
 code,.cites{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#8a5a00}
 .conflict{background:#fff2f0;border-left:4px solid #c0392b;padding:10px 14px;
           margin:10px 0}
 .empty{color:#6b6a67;font-style:italic}
</style>
<h1>inboxHero &mdash; run dashboard</h1>
<div class=meta>%(generated)s &middot; %(messages)s messages processed</div>

<h2>1 &middot; Pending actions <span class=meta>(proposed, not performed alone)</span></h2>
%(pending)s

<h2>2 &middot; Flagged <span class=meta>(refused, left in place)</span></h2>
%(flagged)s

<h2>3 &middot; Commitments</h2>
%(conflicts)s
%(commitments)s
""" % {
        "generated": doc["generated"],
        "messages": doc["messages"],
        "pending": _rows(panes["pending_actions"], [
            ("Message", lambda r: r["message"]),
            ("Proposed action", lambda r: r["action"]),
            ("Why it needs a human", lambda r: r["why"]),
        ]),
        "flagged": _rows(panes["flagged"], [
            ("Message", lambda r: r["message"]),
            ("What was attempted", lambda r: r["attempted"]),
            ("What the system did", lambda r: r["did"]),
        ]),
        "commitments": _rows(panes["commitments"], [
            ("Date", lambda r: r["date"]),
            ("Time", lambda r: r["time"]),
            ("Commitment", lambda r: r["what"]),
            ("Cited from", lambda r: ", ".join(r["cites"])),
        ]),
        "conflicts": conflict_html,
    }
    with open(HTML_PATH, "w") as fh:
        fh.write(page)
