#!/usr/bin/env python3
# demo.py — the single entry point every capability in capabilities.json runs through.
#
#   python demo.py --cap R1          one capability
#   python demo.py --all             all of them, in manifest order
#   python demo.py --cap R3 --approve   prompt per irreversible action
#
# Default gate mode is dry-run, so a clean checkout can be graded without a key
# and without anything leaving the system.

import argparse, sys
import gate, trace, actions, memory, llm, config
import capabilities as caps

ORDER = ["R1", "R2", "R3", "R4", "R5", "R6", "X1", "X2", "X3", "X4", "X5"]

REGISTRY = {
    "R1": ("Zero the inbox", lambda a: caps.R1_zero_the_inbox(use_model=a.model)),
    "R2": ("Grounded reply", lambda a: caps.R2_grounded_reply(a.msg or "m008")),
    "R3": ("Gate the irreversible", lambda a: caps.R3_gate()),
    "R4": ("Persistent preference", lambda a: caps.R4_preference(a.phase)),
    "R5": ("Refuse embedded instructions", lambda a: caps.R5_refuse_injections()),
    "R6": ("Dashboard", lambda a: caps.R6_dashboard(use_model=a.model)),
    "X1": ("Follow-up tracking", lambda a: caps.X1_follow_ups()),
    "X2": ("Morning digest", lambda a: caps.X2_digest(use_model=a.model)),
    "X3": ("Thread to open question", lambda a: caps.X3_thread_summary(a.thread)),
    "X4": ("Why did you do that", lambda a: caps.X4_why(a.msg or "m023")),
    "X5": ("Negotiate a meeting", lambda a: caps.X5_negotiate_meeting(a.msg or "m043")),
}


def main():
    p = argparse.ArgumentParser(description="inboxHero")
    p.add_argument("--cap", help="capability id, e.g. R1")
    p.add_argument("--all", action="store_true", help="run every capability")
    p.add_argument("--dry-run", dest="dry", action="store_true",
                   help="show irreversible actions without performing them (default)")
    p.add_argument("--approve", action="store_true",
                   help="prompt for approval per irreversible action")
    p.add_argument("--yes", action="store_true",
                   help="answer approval prompts automatically (for scripted demos)")
    p.add_argument("--model", action="store_true",
                   help="use the language model for triage where a rule did not decide")
    p.add_argument("--msg", help="message id, for capabilities that take one")
    p.add_argument("--thread", default="t-launch", help="thread id for X3")
    p.add_argument("--phase", default="auto", choices=["auto", "record", "apply"],
                   help="R4: force the record or apply half of the demo")
    p.add_argument("--reset", action="store_true",
                   help="clear prefs.json, outbox/ and trace.jsonl first")
    args = p.parse_args()

    if args.reset:
        memory.forget_all()
        actions.clear_outbox()
        trace.reset()
        print("reset: prefs.json, outbox/, trace.jsonl\n")

    gate.configure(mode="approval" if (args.approve or args.yes) else "dry-run",
                   auto=True if args.yes else None)

    print("inboxHero | gate=%s | model=%s\n" % (
        gate.mode(),
        config.MODEL_NAME if (args.model and llm.available()) else "off (deterministic path)"))

    if args.all:
        for cid in ORDER:
            name, fn = REGISTRY[cid]
            print("\n" + "=" * 70)
            print("%s  %s" % (cid, name))
            print("=" * 70)
            fn(args)
        return 0

    if not args.cap:
        p.print_help()
        print("\ncapabilities: %s" % ", ".join(ORDER))
        return 1

    cid = args.cap.upper()
    if cid not in REGISTRY:
        print("unknown capability %r; known: %s" % (args.cap, ", ".join(ORDER)))
        return 1
    name, fn = REGISTRY[cid]
    print("%s  %s\n%s" % (cid, name, "-" * 70))
    fn(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
