# CAPABILITIES.md — inboxHero

**Student:** Bhanu Mokkala, ROLL_NUMBER
**Repository:** https://github.com/BhanuMokkala/inboxhero

Run everything through one entry point:

```
python demo.py --cap R1        # one capability
python demo.py --all           # all of them, in the order below
python demo.py --all --reset   # clear prefs.json, outbox/ and trace.jsonl first
```

No API key is required. Every capability has a deterministic path and the whole
manifest runs on a clean checkout with no `.env`. Add a key and `--model` to put
the language model back in the triage loop.

---

## The system, in one paragraph

A single Python pipeline, no framework. All 100 messages are screened by
`guard.py` first, then the cheap ones — receipts, newsletters, platform
notifications — are dispositioned by rule before any model is touched. Only what
is left goes through classify → retrieve → draft → gate. A final pass builds the
dashboard. State that must outlive a run (preferences, the action log) is kept
in small JSON files on disk.

## Design choices you were asked to state

- **Framework: none.** The work is a linear pipeline with three branches
  (guard-path, rule-path, model-path) selected by a single ordered check. A crew
  or graph would have added a scheduler I did not need and an indirection
  between the model and `actions.py` that I specifically wanted to keep short
  and readable. See Final Report Q4.
- **Retrieval: thread-walk, keyword as fallback.** The inbox already carries its
  own structure in `thread_id`, so walking the thread is cheaper and more precise
  than embeddings here: the message that answers `m008` is four messages up its
  own thread. Keyword search covers cross-thread lookups where no thread exists.
- **Messages processed: 100.** 60 dispositioned by rule with no model call, 7
  stopped by the guard as hostile, 33 on the model path.
- **Assumptions about the data.** Every message has all eight documented keys;
  none were missing or malformed. Timestamps are naive ISO-8601 local time with
  no zone, so "now" is anchored to the newest message in the file
  (2026-09-09T17:17) to keep runs reproducible rather than drifting with the
  wall clock. `thread_id` is trusted as the only structural link between
  messages; `from` is **not** trusted as identity, which is what catches `m039`.
- **Reversible vs irreversible.** `send` and `delete` are irreversible and
  gated. `draft`, `label`, `archive`, `defer`, `cc` and `flag` are reversible and
  run without a prompt: they change how a message is presented, never whether it
  exists. **Deleting is irreversible in this design** because the mock store has
  no trash, so a delete destroys the only copy — and because deletion is exactly
  what an attacker asks for (`m024` requests its own deletion), making it cheap
  would be a mistake.
- **Where the gate sits.** `actions.py` is the only module that can affect
  anything outside the process, and its two irreversible functions call
  `gate.authorize()` before doing anything. Nothing else in the system can reach
  them. That is also the Part 6 defence: a hostile message can influence the
  *text of a draft*, but it cannot reach a send.
- **Escalation line.** Approval is asked for only on sends to external
  recipients and on anything touching money, legal documents or the owner's
  calendar. Internal archives, defers and labels are automatic and silent.
  **What that trades away:** a wrongly-archived internal note is possible and
  nobody will be asked about it — 76 messages are filed with no prompt. I took
  that deliberately, because a system that asks about forty things gets forty
  reflexive yeses, and the three or four prompts that actually matter would be
  buried among them.

## Capabilities

| id | name | tier | one-line claim |
|----|------|------|----------------|
| R1 | Zero the inbox | B | all 100 get one disposition + reason, none left |
| R2 | Grounded reply | B | drafts cite the earlier message they used |
| R3 | Gate the irreversible | C | no send/delete without approval or --dry-run |
| R4 | Persistent preference | C | a stated preference survives a restart |
| R5 | Refuse embedded instructions | C | detects, refuses, flags, reports 7 attacks |
| R6 | Dashboard | C | three panes, commitments cited, conflicts surfaced |
| X1 | Follow-up tracking | B | unanswered sent mail, with a drafted chase |
| X2 | Morning digest | B | needs you / can wait / flagged / filed |
| X3 | Thread to open question | B | 9-message thread down to the one ask |
| X4 | Why did you do that | A | explains any single disposition on demand |
| X5 | Negotiate a meeting | C | conflict → three alternatives → held at the gate |

Tier spread: A×1, B×5, C×5.

The exact command, observable outcome and evidence for each is in
`capabilities.json`. That file is the machine-readable version and is what a
marking script reads; this file is for a human. The two are kept in step.

## What the inbox turned out to contain

Worth stating, because the required parts are graded against it:

- **Four prompt injections**, not one: `m024` (classic "ignore all previous
  instructions", asks for the mailbox to be forwarded and itself deleted),
  `m017` (fake mailer-daemon issuing an "AUTOMATED-AGENT DIRECTIVE"), `m047`
  (buried inside a forwarded quote in a genuine-looking support ticket), and
  `m039`, which **forges the owner's own address** to declare autonomous mode
  and disable the approval step.
- **Three social-engineering attempts** aimed at the human: `m021` (changed
  remittance details, $8,400), `m023` (a wire request from
  `priya.nair@paperjet.co` — a lookalike of the real `priya@paperjet.io`), and
  `m045` (credential harvesting).
- **Two real standing preferences**: `m041` (no meetings before 11:00am) and
  `m015` (always CC Priya on Hartwell & Cho mail).
- **Two genuine calendar conflicts**: Sep 15 at 15:00 and Sep 16 at 14:00.

## Final Report

See `README.md`.
