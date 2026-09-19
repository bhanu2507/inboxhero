# gate.py — the single chokepoint for anything that cannot be undone.
#
# Part 4. Two modes, both supported:
#   dry-run  (default) — prints exactly what it WOULD do and performs nothing.
#   approval (--approve) — prompts per action; anything not answered 'y' is refused.
#
# The model has no route to this module. Nothing in the system calls an
# irreversible action except actions.py, and actions.py calls authorize() first.
# Every decision is logged with what was proposed, what the human said, and
# what actually happened.

import sys
import trace

IRREVERSIBLE = ["send", "delete"]
REVERSIBLE = ["draft", "label", "archive", "defer", "cc", "flag"]

_mode = "dry-run"       # "dry-run" | "approval"
_auto = None            # set to True/False to answer prompts non-interactively
_decisions = []


def configure(mode="dry-run", auto=None):
    global _mode, _auto
    _mode = mode
    _auto = auto


def mode():
    return _mode


def decisions():
    return list(_decisions)


class Refused(Exception):
    """Raised when an irreversible action was proposed and not permitted."""


def authorize(action, target, why, cap=None, detail=None):
    """Decide whether one irreversible action may proceed.

    Returns True only when it may. Reversible actions never come through here.
    """
    if action not in IRREVERSIBLE:
        return True

    proposal = {"action": action, "target": target, "why": why, "detail": detail}

    if _mode == "dry-run":
        answer, outcome = "dry-run", "not performed"
        print("  [DRY-RUN] would %s -> %s (%s)" % (action, target, why))
    else:
        if _auto is not None:
            answer = "y" if _auto else "n"
            print("  [APPROVAL] %s -> %s (%s) : auto-%s" % (action, target, why, answer))
        elif not sys.stdin.isatty():
            answer = "n"
            print("  [APPROVAL] %s -> %s : no terminal to ask, refused" % (action, target))
        else:
            print("  [APPROVAL NEEDED] %s -> %s" % (action, target))
            print("      why: %s" % why)
            if detail:
                print("      %s" % detail.replace("\n", "\n      ")[:400])
            try:
                answer = input("      proceed? [y/N] ").strip().lower()
            except EOFError:
                answer = "n"
        outcome = "performed" if answer == "y" else "not performed"

    permitted = outcome == "performed"
    record = {"proposed": proposal, "human": answer, "outcome": outcome,
              "permitted": permitted}
    _decisions.append(record)
    trace.emit("gate", cap=cap, action=action, target=target, why=why,
               human=answer, outcome=outcome, mode=_mode)
    return permitted
