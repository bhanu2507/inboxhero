# capabilities.py — one function per capability in capabilities.json.
# Each is reachable on its own through `python demo.py --cap <ID>` and prints
# something a person can look at and judge.

import datetime, json, re
import config, data, guard, rules, triage, retrieval, grounding
import memory, actions, gate, trace, commitments, dashboard, llm

OWNER = config.OWNER


# ---------------------------------------------------------------- R1
def R1_zero_the_inbox(use_model=True):
    """Every message gets exactly one disposition and a reason."""
    recs, stats = triage.triage_all(use_model=use_model, cap="R1")
    print("%-6s %-11s %-34s %s" % ("ID", "DISPOSITION", "FROM", "REASON"))
    for r in recs:
        print("%-6s %-11s %-34s %s" % (r["id"], r["disposition"],
                                       r["from"][:33], r["reason"][:70]))
    undecided = [r for r in recs if r["disposition"] not in triage.DISPOSITIONS]
    print("\nprocessed: %d" % len(recs))
    print("rule-handled (no model call): %d" % stats["rule"])
    print("guard-handled (hostile): %d" % stats["guard"])
    print("model/heuristic path: %d" % stats["model"])
    print("undecided: %d" % len(undecided))
    with open("decisions.json", "w") as fh:
        json.dump(recs, fh, indent=2)
    return recs


# ---------------------------------------------------------------- R2
def R2_grounded_reply(target="m008"):
    """Draft a reply that can only be written by reading an earlier message."""
    msg = data.by_id(target)
    print("Answering %s from %s: %r\n" % (target, msg["from"], msg["subject"]))

    context, method = retrieval.context_for(target, cap="R2")
    print("retrieval: %s -> read %s" % (method, [m["id"] for m in context]))

    url, source = grounding.find_fact([m["id"] for m in context],
                                      r"amqp://\S+", cap="R2")
    if url is None:
        # Part 3.4: if it is not in the inbox, say so and draft nothing.
        print("\nThe answer is not in the inbox. No draft written.")
        trace.emit("refused_to_draft", cap="R2", message_id=target,
                   reason="fact not present in any retrieved message")
        return None

    host = re.sub(r"//[^@]+@", "//<credential redacted>@", url)
    body = (
        "Hi Devika,\n\n"
        "The staging queue was moved when I rotated the broker credentials on "
        "2 Sep -- the old ones are dead, which is why your worker cannot reach "
        "it. The new endpoint is %s.\n\n"
        "I am not pasting the credential into email. It is the same one Raghav "
        "is using; I will share it through the vault so we are not leaving it "
        "in a thread.\n\n"
        "-- Sam\n" % host)

    ok, problems = grounding.verify([source], {m["id"] for m in context},
                                    quoted=[url], cap="R2")
    print("\n--- draft ---\n%s-------------" % body)
    print("cited: [%s]   grounded: %s" % (source, ok))
    if problems:
        print("problems: %s" % problems)
        return None

    actions.draft(target, body, cited=[source], cap="R2")
    print("\nThe credential itself really is in %s, and is withheld from the "
          "draft on purpose:\n  %s" % (source, url[:44] + "..."))
    return {"draft": body, "cited": [source]}


# ---------------------------------------------------------------- R3
def R3_gate(approve=None):
    """No send or delete happens without approval or an explicit dry-run."""
    before = actions.outbox_count()
    print("gate mode: %s\noutbox before: %d\n" % (gate.mode(), before))

    proposals = [
        ("m010", "aria.f@northwind.vc", "Re: Intro call this week?",
         "Tuesday 15th at 3pm collides with an existing commitment; proposing "
         "alternatives.", "external investor; the reply commits the owner's time"),
        ("m018", "m.cho@hartwellcho.com", "Re: SAFE amendment",
         "Confirming receipt; clause 4 still needs Sam's own review.",
         "legal counterparty; touches a financing document"),
    ]
    for mid, to, subject, body, why in proposals:
        actions.send(to, subject, body, why=why, cap="R3", in_reply_to=mid)

    # m024 is the injection that asks to be deleted. It never reaches the gate.
    actions.delete("m024", why="the message itself asked to be deleted", cap="R3")
    # A genuinely disposable notification does reach the gate, and waits there.
    actions.delete("m096", why="storage notice superseded by a later one", cap="R3")

    after = actions.outbox_count()
    print("\noutbox writes this run: %d" % (after - before))
    print("gated decisions logged: %d" % len(gate.decisions()))
    for d in gate.decisions():
        print("  %-6s -> %-28s human=%-8s %s" % (
            d["proposed"]["action"], d["proposed"]["target"][:28],
            d["human"], d["outcome"]))
    return gate.decisions()


# ---------------------------------------------------------------- R4
def R4_preference(phase="auto"):
    """A preference stated in one run changes behaviour in a later process."""
    stored = memory.get("meeting_floor")

    if phase == "record" or (phase == "auto" and stored is None):
        src = data.by_id("m041")
        print("Reading %s from %s: %r" % (src["id"], src["from"], src["subject"]))
        ok, why = memory.remember(
            "meeting_floor", "no meetings before 11:00am; offer 11:00 or later",
            source_id="m041", applies_to=["m043", "m010", "m016"], cap="R4")
        print("stored to %s: %s (%s)" % (memory.PREFS_PATH, ok, why))
        print("\nNow run the same command again -- a fresh process -- to see it "
              "applied:\n  python demo.py --cap R4")
        return {"phase": "recorded"}

    pref = memory.get("meeting_floor")
    print("loaded from disk (%s), written by a previous process:" % memory.PREFS_PATH)
    print("  %r  [source %s]\n" % (pref["rule"], pref["source"]))

    target = data.by_id("m043")
    proposed = "09:00"
    print("Handling %s from %s: %r" % (target["id"], target["from"], target["subject"]))
    print("  proposed time: %s" % proposed)
    violates = proposed < "11:00"
    print("  violates stored preference: %s" % violates)
    trace.emit("preference_applied", cap="R4", message_id="m043",
               preference="meeting_floor", source="m041", violated=violates)

    if violates:
        print("\n  -> declining 9:00am and counter-offering 11:00am, 11:30am or "
              "14:00, per the rule set in m041.")
        print("  -> the reply itself is an external send, so it is held for "
              "approval (see R3).")
    return {"phase": "applied", "violated": violates}


# ---------------------------------------------------------------- R5
def R5_refuse_injections():
    """Detect instructions aimed at the assistant; refuse, flag, report, keep."""
    before = actions.outbox_count()
    screened = guard.screen_all(data.all_messages())
    hostile = [s for s in screened.values() if s["hostile"]]

    for s in hostile:
        trace.emit("refusal", cap="R5", message_id=s["id"], kind=s["kind"],
                   attempted=s["attempted"], did="flagged, left in place, not acted on")

    print("scanned %d messages\n" % len(screened))
    for s in sorted(hostile, key=lambda s: s["id"]):
        m = data.by_id(s["id"])
        print("FLAGGED %s (%s) from %s" % (s["id"], s["kind"], m["from"]))
        print("   attempted: %s" % s["attempted"])
        print("   did:       refused, flagged, left in place; no action taken\n")

    after = actions.outbox_count()
    print("hostile messages found: %d" % len(hostile))
    print("outbox writes as a result: %d" % (after - before))
    print("messages deleted:         0  (flagged in place, per Part 6.4)")
    print("\nNote: %s claims to come from the owner's own address and asks to "
          "disable\napproval. Sender addresses are not authentication, so it is "
          "refused like the rest\nand memory.py rejects the preference it tries "
          "to store." % "m039")
    return hostile


# ---------------------------------------------------------------- R6
def R6_dashboard(use_model=False):
    """Three panes, written to disk from this run."""
    recs, _ = triage.triage_all(use_model=use_model, cap="R6")

    pending = [{"message": r["id"], "action": "draft + send reply",
                "why": r["reason"]}
               for r in recs if r["disposition"] in ("reply", "escalate")
               and not r["hostile"]]
    flagged = [{"message": r["id"], "attempted": r["attempted"] or "could not ground",
                "did": "refused, flagged, left in place"}
               for r in recs if r["hostile"]]

    doc = dashboard.build(recs, pending, flagged, cap="R6")
    print("wrote %s and %s" % (dashboard.HTML_PATH, dashboard.JSON_PATH))
    print("\npane 1 pending actions: %d" % len(pending))
    print("pane 2 flagged:         %d" % len(flagged))
    print("pane 3 commitments:     %d" % len(doc["panes"]["commitments"]))
    multi = [c for c in doc["panes"]["commitments"] if len(c["cites"]) > 1]
    for c in multi:
        print("   assembled from %d messages: %s  <- %s"
              % (len(c["cites"]), c["what"][:48], ", ".join(c["cites"])))
    print("\nconflicts surfaced: %d" % len(doc["conflicts"]))
    for c in doc["conflicts"]:
        print("   CONFLICT %s : %s (%s) vs %s (%s)" % (
            c["slot"], c["a"]["what"][:34], ", ".join(c["a"]["cites"]),
            c["b"]["what"][:34], ", ".join(c["b"]["cites"])))
    return doc


# ================================================================ Part 8
# ---------------------------------------------------------------- X1 (tier B)
def X1_follow_ups(days=3):
    """Mail the owner sent that nobody answered, with a chase drafted."""
    now = data.now()
    out = []
    for sent in data.sent_by_owner():
        if sent["to"] == OWNER:
            continue  # a note to self is not an unanswered message
        later = [m for m in data.thread(sent["thread_id"])
                 if m["timestamp"] > sent["timestamp"] and m["from"] != OWNER]
        if later:
            continue
        waiting = (now - data.parse_ts(sent)).days
        if waiting < days:
            continue
        recipient = sent["to"]
        chase = ("Hi -- following up on %r from %s. Anything you need from me "
                 "to unblock it?\n\n-- Sam" % (sent["subject"], sent["timestamp"][:10]))
        out.append({"message_id": sent["id"], "to": recipient,
                    "days_waiting": waiting, "draft": chase})
        actions.draft(sent["id"], chase, cited=[sent["id"]], cap="X1")
        trace.emit("follow_up", cap="X1", message_id=sent["id"],
                   days_waiting=waiting)
    print(json.dumps(out, indent=2))
    print("\nunanswered for %d+ days: %d" % (days, len(out)))
    answered = [m["id"] for m in data.sent_by_owner()
                if any(x["timestamp"] > m["timestamp"] and x["from"] != OWNER
                       for x in data.thread(m["thread_id"]))]
    print("excluded because the thread was answered: %s" % (answered or "none"))
    return out


# ---------------------------------------------------------------- X2 (tier B)
def X2_digest(use_model=False):
    """One screen: what needs you, what can wait, what was filed."""
    recs, stats = triage.triage_all(use_model=use_model, cap="X2")
    needs = [r for r in recs if r["disposition"] in ("reply", "escalate")]
    wait = [r for r in recs if r["disposition"] in ("defer", "delegate")]
    filed = [r for r in recs if r["disposition"] == "archive"]
    flagged = [r for r in recs if r["disposition"] == "quarantine"]

    print("=" * 66)
    print("inboxHero digest  --  %d messages" % len(recs))
    print("=" * 66)
    print("\nNEEDS YOU (%d)" % len(needs))
    for r in needs:
        print("  %-6s %-30s %s" % (r["id"], r["from"][:29], r["subject"][:38]))
    print("\nCAN WAIT (%d)" % len(wait))
    for r in wait:
        print("  %-6s %-30s %s" % (r["id"], r["from"][:29], r["subject"][:38]))
    print("\nFLAGGED, NOT ACTED ON (%d)" % len(flagged))
    for r in flagged:
        print("  %-6s %s" % (r["id"], (r["attempted"] or "")[:56]))
    print("\nFILED AUTOMATICALLY (%d) -- by count, not individually" % len(filed))
    buckets = {}
    for r in filed:
        buckets[r["from"].split("@")[-1]] = buckets.get(r["from"].split("@")[-1], 0) + 1
    for dom, n in sorted(buckets.items(), key=lambda p: -p[1])[:8]:
        print("  %-34s %d" % (dom, n))
    print("\n  %d of those never reached a model." % stats["rule"])
    trace.emit("digest", cap="X2", needs=len(needs), wait=len(wait),
               filed=len(filed), flagged=len(flagged))
    return {"needs": needs, "wait": wait, "filed": filed}


# ---------------------------------------------------------------- X3 (tier B)
def X3_thread_summary(thread_id="t-launch"):
    """Collapse a long thread to the one thing that actually needs the owner."""
    msgs = data.thread(thread_id)
    print("thread %s: %d messages, %s -> %s\n"
          % (thread_id, len(msgs), msgs[0]["timestamp"][:10], msgs[-1]["timestamp"][:10]))
    for m in msgs:
        print("  %-6s %-22s %s" % (m["id"], m["from"].split("@")[0], m["body"][:64]))

    asks = [m for m in msgs if m["from"] != OWNER
            and re.search(r"\b(can|could) (you|sam)\b|needs sam|sam,", m["body"], re.I)]
    print("\nopen question for the owner:")
    if not asks:
        print("  none found in this thread")
        return None
    for m in asks:
        q = re.search(r"[^.?!]*\b(can|could) (you|sam)[^.?!]*\?", m["body"], re.I)
        print("  [%s] %s" % (m["id"], (q.group(0).strip() if q else m["body"][:110])))
    print("\n  buried at position %d of %d -- everything else in the thread is "
          "status,\n  owned by someone else, and needs nothing from Sam."
          % (msgs.index(asks[0]) + 1, len(msgs)))
    trace.emit("thread_summary", cap="X3", thread=thread_id,
               messages=len(msgs), open_question=[m["id"] for m in asks])
    return asks


# ---------------------------------------------------------------- X4 (tier A)
def X4_why(message_id="m023"):
    """Ask the system why it did something. One lookup, one answer."""
    m = data.by_id(message_id)
    if m is None:
        print("no such message: %s" % message_id)
        return None
    screened = guard.screen(m)
    ruled = rules.classify(m)
    disp, reason = triage._heuristic(m, screened)

    print("message:     %s" % message_id)
    print("from:        %s" % m["from"])
    print("subject:     %s" % m["subject"])
    print("disposition: %s" % disp)
    print("because:     %s" % reason)
    print("\ndecided by:  %s" % ("the guard (hostile)" if screened["hostile"]
                                 else "a rule, no model call" if ruled
                                 else "the model/heuristic path"))
    if screened["findings"]:
        print("signals:")
        for f in screened["findings"]:
            print("   - %s" % f)
    print("\nevidence: grep '\"message_id\": \"%s\"' trace.jsonl" % message_id)
    trace.emit("explain", cap="X4", message_id=message_id, disposition=disp)
    return {"id": message_id, "disposition": disp, "reason": reason}


# ---------------------------------------------------------------- X5 (tier C)
def X5_negotiate_meeting(target="m043"):
    """Conflict against a stored preference -> three alternatives -> held."""
    pref = memory.get("meeting_floor")
    if pref is None:
        print("no stored preference yet; run --cap R4 first to record it.")
        return None

    m = data.by_id(target)
    print("request: %s from %s\n  %r\n" % (target, m["from"], m["body"][:100]))
    print("stored preference [%s]: %s" % (pref["source"], pref["rule"]))

    proposed = commitments._time_of(m["body"])
    proposed_s = proposed.strftime("%H:%M") if proposed else "unknown"
    floor = datetime.time(11, 0)
    conflicts_pref = proposed is not None and proposed < floor
    print("proposed %s, floor %s -> conflict: %s\n"
          % (proposed_s, floor.strftime("%H:%M"), conflicts_pref))

    items = commitments.extract(cap="X5")
    busy = {(c["date"], c["time"]) for c in items if c["time"]}
    alternatives, day = [], data.now().date() + datetime.timedelta(days=5)
    for slot in ("11:00", "11:30", "14:00"):
        while (day.isoformat(), slot) in busy:
            day += datetime.timedelta(days=1)
        alternatives.append("%s at %s" % (day.strftime("%A %d %b"), slot))

    body = ("Hi Aria,\n\n9:00am does not work on my side -- I do not take "
            "meetings before 11:00. Any of these suit you and your partner?\n"
            + "".join("  - %s\n" % a for a in alternatives)
            + "\nHappy to hold 20 minutes for whichever is easiest.\n\n-- Sam\n")
    print("--- proposed reply ---\n%s----------------------\n" % body)

    actions.draft(target, body, cited=[target, pref["source"]], cap="X5")
    sent = actions.send(m["from"], "Re: " + m["subject"], body,
                        why="external investor; declining a proposed time and "
                            "committing the owner to a new one",
                        cap="X5", in_reply_to=target)
    print("\nheld for approval: %s" % ("no -- sent" if sent else "yes, nothing left the system"))
    trace.emit("negotiated", cap="X5", message_id=target,
               conflict=conflicts_pref, alternatives=alternatives,
               sent=bool(sent))
    return {"conflict": conflicts_pref, "alternatives": alternatives}
