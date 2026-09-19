# inboxHero

**Repository:** https://github.com/bhanu2507/inboxhero

Assignment 06 — *Agentic AI: From Concepts to Practice*, IIIT Hyderabad.
Bhanu Mokkala, cert-aai-2026-06-0009.

An agentic system that takes a 100-message inbox from unread to empty by
deciding what to do with every message, doing the parts it should do, and
refusing the parts it should not.

## Run it

```bash
pip install -r requirements.txt
python demo.py --all --reset      # every capability, in manifest order
python demo.py --cap R2           # just one
python demo.py --cap R3 --approve # prompt before each irreversible action
```

No API key needed — every capability has a deterministic path, so the whole
manifest runs on a clean checkout. For the model path:

```bash
cp .env.example .env    # add GEMINI_API_KEY
python demo.py --cap R1 --model
```

`CAPABILITIES.md` and `capabilities.json` list all eleven capabilities and are
the primary graded artifact.

## Architecture

```
demo.py            single entry point, --cap / --all, sets the gate mode
 └ capabilities.py one function per manifest entry (R1-R6, X1-X5)
    ├ guard.py     TRUST BOUNDARY: fences untrusted text, screens for attacks
    ├ rules.py     the no-model path: 60 of 100 messages
    ├ triage.py    exactly one disposition per message, with a reason
    ├ retrieval.py thread-walk, keyword fallback
    ├ grounding.py verifies every citation against the mail store
    ├ memory.py    prefs.json — preferences that outlive the process
    ├ gate.py      THE CHOKEPOINT: dry-run or per-action approval
    ├ actions.py   the only module with outside effects; send → outbox/
    ├ commitments.py  dates, multi-message merge, conflict detection
    ├ dashboard.py three panes → dashboard.html + dashboard.json
    ├ llm.py       the only provider-aware module; degrades to None
    ├ data.py      the only reader of inbox.json
    └ trace.py     append-only trace.jsonl, every event tagged cap=<id>
```

**Disposition vocabulary:** `reply` (needs an answer), `archive` (nothing owed),
`defer` (real but later), `delegate` (someone else owns it), `escalate` (needs
the owner's judgement before anything leaves), `quarantine` (hostile — flagged,
left in place, never acted on).

**Reversible:** draft, label, archive, defer, cc, flag.
**Irreversible:** send, delete — both gated. Deleting counts as irreversible
because this store has no trash.

**Retrieval:** thread-walk first, keyword search as the cross-thread fallback.

**Framework:** none. Reasoning in `CAPABILITIES.md` and Q4 below.

## Final Report

### 1. What did you refuse to automate?

Refused to automate `m012`, which has vague text from Priya: *"did you ever get
a chance to sort out that thing we talked about after the standup? kind of need
it done before the call."* The system marks it `escalate` with the reason *"the
request is not identifiable from the message; the right move is to ask, not
guess"*. `m008` is just as vague on the surface — "resend the URL you gave
Raghav" — but resolves, because the thing it refers to is four messages up its
own thread. The line is not vagueness, it is whether the inbox contains the
referent.

### 2. Where does untrusted text enter your system?

Every message body reaches a model only through `guard.wrap()`, which fences it
between `<<<UNTRUSTED_EMAIL_DATA id=...>>>` markers and neutralises any attempt
to close that fence from inside. The system prompt in `llm.py` states that
everything inside the markers is data written by strangers. But the prompt is
the weak half — the structural half is that the model is handed **no tools at
all**. It returns text; `capabilities.py` decides what runs; only `actions.py`
can cause an effect; and its two irreversible functions call `gate.authorize()`
first.

There is no path from model output to `actions.send()` that does not pass
through a human answering y/n or a dry-run that performs nothing. `m039` is the
worked example — it forges the owner's own address to claim autonomous mode, and
fails twice: `guard.py` does not treat `from` as authentication, and `memory.py`
refuses any preference that widens the system's own authority.

### 3. Who is accountable when it sends the wrong thing?

The owner is accountable when the system sends a wrong thing, because nothing
reaches `outbox/` without either a y/n at the gate or a deliberate `--yes`.
Every gated decision writes a `gate` event to `trace.jsonl` with the proposal,
the human's answer and the outcome; every draft writes the ids it cited; every
citation writes a `grounding_check`. From a bad file in `outbox/` you can walk
back to the approval, the draft, its sources and the disposition.
`python demo.py --cap X4 --msg <id>` does that walk.

### 4. Name your own machinery.

The mapping: the **Agents** are the capability functions in `capabilities.py`,
each owning one job end to end. The **Tasks** are the manifest entries they
implement. The **Crew** is `demo.py`, which orders them and sets the gate mode
for the run. The **router** is the ordered check at the top of
`triage._heuristic()` — guard, then rules, then model — which decides what each
message is worth spending on.

A framework would have given me retry and rate-limit handling; I wrote that by
hand in `llm.py`. 

## Submission

- `demo.py` with the `--cap` interface every manifest entry depends on
- `CAPABILITIES.md` + `capabilities.json` — the primary graded artifact
- `outbox/` and `trace.jsonl` from a full run
- `.env.example` (no `.env`, no hardcoded keys — see `config.py`)
