# inboxHero

**Repository:** https://github.com/BhanuMokkala/inboxhero

Assignment 06 — *Agentic AI: From Concepts to Practice*, IIIT Hyderabad.
Bhanu Mokkala, ROLL_NUMBER.

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

> **TODO — your own words, 3-5 sentences.** The strongest candidate is `m012`
> from Priya: *"did you ever get a chance to sort out that thing we talked about
> after the standup? kind of need it done before the call."* The system
> dispositions it `escalate` with the reason *"the request is not identifiable
> from the message; the right move is to ask, not guess"* — the referent exists
> only in a conversation that happened out loud, so any draft would be invention
> dressed as recall. Contrast it with `m008`, which looks similarly vague but
> resolves cleanly because the answer is four messages up its own thread.
> Say where you think the line sits between the two.
>
> A second candidate worth a sentence: `m008` itself is answered, but the draft
> deliberately withholds the credential that `m003` contains, because "grounded
> in an earlier message" does not mean "safe to repeat in email."

### 2. Where does untrusted text enter your system?

> **TODO — your own words, 3-5 sentences.** The facts to build on: every message
> body reaches a model only through `guard.wrap()`, which fences it between
> `<<<UNTRUSTED_EMAIL_DATA id=...>>>` markers and neutralises any attempt to
> close that fence from inside. The system prompt in `llm.py` states that
> everything inside the markers is data written by strangers. But the prompt is
> the *weak* half and should be described as such — the structural half is that
> the model is handed **no tools at all**. It returns text; `capabilities.py`
> decides what runs; only `actions.py` can cause an effect; and its two
> irreversible functions call `gate.authorize()` first.
>
> So name what an attacker would have to defeat: not the wording of a prompt,
> but the fact that there is no path from model output to `actions.send()` that
> does not pass through a human answering y/n or a dry-run that performs
> nothing. `m039` is the worked example — it forges the owner's own address to
> claim autonomous mode, and fails twice over, because `guard.py` does not treat
> a sender address as authentication and `memory.py` refuses any preference that
> would widen the system's own authority.

### 3. Who is accountable when it sends the wrong thing?

> **TODO — your own words, 3-5 sentences.** The mechanical answer: the owner is,
> because nothing reaches `outbox/` without either a y/n at the gate or a
> deliberate `--yes`. Whether that is a *fair* answer is the interesting part,
> and worth your own view — approval fatigue is real, which is why only external
> sends and money/legal/calendar items prompt at all.
>
> For traceability, describe the chain: every gated decision writes a `gate`
> event to `trace.jsonl` recording what was proposed, what the human answered
> and what happened; every draft writes a `draft` event with the ids it cited;
> every citation writes a `grounding_check`. Given a bad message in `outbox/`
> you can walk back to the approval, the draft, the sources and the disposition.
> `python demo.py --cap X4 --msg <id>` does that walk for a single message.

### 4. Name your own machinery.

> **TODO — your own words, 3-5 sentences.** The mapping: the **Agents** are the
> capability functions in `capabilities.py`, each owning one job end to end. The
> **Tasks** are the manifest entries they implement. The **Crew** is `demo.py`,
> which orders them and sets the gate mode for the run. The **router** is the
> ordered check at the top of `triage._heuristic()` — guard, then rules, then
> model — which decides what each message is worth spending on.
>
> Name one thing a framework would have given you: retries, tool schemas and a
> shared scratchpad are all reasonable answers; I hand-rolled rate-limit
> handling and backoff in `llm.py`. Then answer the actual question — would a
> framework have helped here? The argument against is that CrewAI or ADK would
> have put a tool-dispatch layer between the model and `actions.py`, and the
> whole safety story of this system is that **no such path exists**. The
> argument for is that 60 of 100 messages never touch a model, so most of what a
> framework offers would sit idle. Take a position either way.

## Submission

- `demo.py` with the `--cap` interface every manifest entry depends on
- `CAPABILITIES.md` + `capabilities.json` — the primary graded artifact
- `outbox/` and `trace.jsonl` from a full run
- `.env.example` (no `.env`, no hardcoded keys — see `config.py`)
