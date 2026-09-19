# actions.py — the only module that can cause an effect outside the process.
# Every irreversible action asks gate.authorize() first and returns early if
# refused. There is no second path to outbox/.
#
# Reversible vs irreversible, and why:
#   send   — irreversible. The message is gone the moment it leaves.
#   delete — irreversible BY DESIGN CHOICE: this mail store has no trash, so a
#            delete destroys the only copy. It is also what an attacker asks for
#            (m024 wants itself deleted), so making it cheap would be a mistake.
#   draft/label/archive/defer/cc — reversible. They change how a message is
#            presented, never whether it exists, and a later run can undo them.

import json, os, re
import gate, trace

OUTBOX = os.getenv("INBOXHERO_OUTBOX", "outbox")
_deleted = set()


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50] or "message"


def send(to, subject, body, why, cap=None, cc=None, in_reply_to=None):
    """Write one message to outbox/, and nowhere else. Gated."""
    detail = "to: %s\nsubject: %s\n\n%s" % (to, subject, body[:300])
    if not gate.authorize("send", to, why, cap=cap, detail=detail):
        return None
    os.makedirs(OUTBOX, exist_ok=True)
    name = "%s_%s.json" % (in_reply_to or "new", _slug(subject))
    path = os.path.join(OUTBOX, name)
    payload = {"to": to, "cc": cc or [], "subject": subject, "body": body,
               "in_reply_to": in_reply_to}
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2)
    trace.emit("send", cap=cap, to=to, subject=subject, path=path,
               in_reply_to=in_reply_to)
    return path


def delete(message_id, why, cap=None):
    """Gated, and never called on a hostile message — those are flagged in place."""
    if not gate.authorize("delete", message_id, why, cap=cap):
        return False
    _deleted.add(message_id)
    trace.emit("delete", cap=cap, message_id=message_id)
    return True


# ---- reversible actions: no gate, logged anyway so the dashboard can show them

def draft(message_id, body, cited, cap=None):
    trace.emit("draft", cap=cap, message_id=message_id, cited=cited,
               chars=len(body))
    return {"message_id": message_id, "body": body, "cited": cited}


def label(message_id, name, cap=None):
    trace.emit("label", cap=cap, message_id=message_id, label=name)
    return True


def archive(message_id, why, cap=None):
    trace.emit("archive", cap=cap, message_id=message_id, why=why)
    return True


def defer(message_id, until, cap=None):
    trace.emit("defer", cap=cap, message_id=message_id, until=until)
    return True


def outbox_count():
    if not os.path.isdir(OUTBOX):
        return 0
    return len([f for f in os.listdir(OUTBOX) if f.endswith(".json")])


def clear_outbox():
    if os.path.isdir(OUTBOX):
        for f in os.listdir(OUTBOX):
            if f.endswith(".json"):
                os.remove(os.path.join(OUTBOX, f))
