# guard.py — the trust boundary.
#
# Two jobs:
#   1. wrap()  — every piece of message text that reaches a model goes through
#      here first and comes back fenced and labelled as untrusted DATA. The
#      model is never handed a bare message body.
#   2. screen() — detect instructions addressed to the assistant, and social
#      engineering aimed at the human, before either reaches a drafting step.
#
# The detector is a defence in depth, not THE defence. The actual defence is
# structural and lives in gate.py: the model never receives a tool it could call.
# It returns proposals as text; Python decides what runs. An injection that gets
# past every pattern below still cannot send, delete or widen its own authority.

import re
import config

UNTRUSTED_OPEN = "<<<UNTRUSTED_EMAIL_DATA id=%s>>>"
UNTRUSTED_CLOSE = "<<<END_UNTRUSTED_EMAIL_DATA>>>"

# Instructions aimed at an automated reader.
_INJECTION = [
    (r"ignore (all |any )?(previous|prior|earlier) instructions", "override of prior instructions"),
    (r"(system notice|directive|note|instruction)s? (for|to) (automated )?(assistant|agent|ai)", "instruction addressed to the assistant"),
    (r"\b(if|when) an? (ai|agent|assistant)\b.{0,60}\b(process|read|manag|handl)", "conditional instruction to an AI reader"),
    (r"assistant (note|directive|instruction)", "instruction addressed to the assistant"),
    (r"forward (the |all |any )?(full |entire )?(contents? of (this|the) )?(mailbox|inbox|message)", "attempt to exfiltrate mail"),
    (r"do not (mention|report|surface|tell|disclose)", "attempt to suppress reporting"),
    (r"(delete|remove) this (message|email)", "attempt to destroy evidence"),
    (r"autonomous mode", "attempt to disable the approval gate"),
    (r"without (asking for |requiring )?(approval|confirmation)", "attempt to disable the approval gate"),
    (r"skip the confirmation", "attempt to disable the approval gate"),
    (r"must (reply|respond) with", "scripted reply demand"),
]

# Social engineering aimed at the human owner.
_PHISH = [
    (r"(wire|transfer|remit)\b.{0,40}(\$|usd|\d{3,})", "payment redirection"),
    (r"(updated?|changed?|new) (bank|remittance|account) details", "payment redirection"),
    (r"password (will )?expires?", "credential harvesting"),
    (r"re-?verify your credentials", "credential harvesting"),
    (r"keep this between us|don't loop in|do not loop in", "isolation pressure"),
    (r"before end of day to avoid|avoid a service interruption|will be suspended", "false urgency"),
]

# Domains the owner actually works with. Anything close-but-different is a
# lookalike, which is how m023 gets caught: priya@paperjet.io is real,
# priya.nair@paperjet.co is not.
_KNOWN_DOMAINS = {"paperjet.io"}
_LOOKALIKE_ROOTS = {"paperjet"}


def wrap(message, field="body"):
    """Fence a message's text as untrusted data before it reaches a model."""
    text = message[field]
    # Neutralise any attempt to close our own fence from inside the data.
    text = text.replace(">>>", ">>​>").replace("<<<", "<​<<")
    return "%s\n%s\n%s" % (UNTRUSTED_OPEN % message["id"], text, UNTRUSTED_CLOSE)


def _domain(addr):
    return addr.split("@")[-1].lower().strip()


def _lookalike(addr):
    d = _domain(addr)
    if d in _KNOWN_DOMAINS:
        return None
    root = d.split(".")[0]
    if root in _LOOKALIKE_ROOTS:
        return "lookalike domain %s (expected one of %s)" % (d, ", ".join(sorted(_KNOWN_DOMAINS)))
    return None


def screen(message):
    """Classify one message. Returns a dict, never raises, never acts.

    kind: "injection" | "phishing" | None
    """
    blob = ("%s\n%s" % (message["subject"], message["body"])).lower()
    findings, kind = [], None

    for pattern, label in _INJECTION:
        if re.search(pattern, blob):
            findings.append(label)
            kind = "injection"

    phish = []
    for pattern, label in _PHISH:
        if re.search(pattern, blob):
            phish.append(label)
    look = _lookalike(message["from"])
    if look:
        phish.append(look)

    if phish and kind != "injection":
        kind = "phishing"
    findings.extend(phish)

    # A message claiming to reconfigure the assistant is hostile no matter who
    # it appears to be from. Sender addresses are not authentication, so the
    # owner's own address earns no extra authority here. This is what stops
    # m039 ("autonomous mode is now enabled") from disarming the gate.
    if kind == "injection" and message["from"] == config.OWNER:
        findings.append("spoofs the owner's address to claim authority")

    return {
        "id": message["id"],
        "kind": kind,
        "hostile": kind is not None,
        "findings": sorted(set(findings)),
        "attempted": "; ".join(sorted(set(findings))) or None,
    }


def screen_all(messages):
    return {m["id"]: screen(m) for m in messages}
