# rules.py — the no-model path (Part 2.3).
#
# Receipts, newsletters and platform notifications are recognised by sender and
# subject shape. Spending a model call to notice that Stripe sent a payout
# notice costs money and latency and buys nothing. As the lectures put it, not
# every time do we need to build agents: part of this inbox is a workflow
# problem, and only part of it is an agent problem.
#
# Every rule states its own reason so the disposition is explainable without a
# model in the loop.

import re

_NOISE_SENDERS = re.compile(
    r"(^|[.@+])(no-?reply|no_reply|noreply|notifications?|notify|receipts?|billing|"
    r"invoice\w*|mailer-daemon|support|success|appointments|calendar-notification|"
    r"alerts?|newsletter|orders?|ship-confirm|feedback|status|hello|info|news|"
    r"digest|updates?|marketing|security|insights|checkin|help|events)@|"
    r"@(github|slack|dropbox|vercel|stripe|notion|zoom|todoist|coursera|apple|"
    r"1password|digitalocean|calendly|openai|medium|substack|linkedin|figma|"
    r"atlassian|google|goog\w*|amazon|netflix|producthunt|sentry|datadoghq|"
    r"twitter|instacart|swiggy|intercom|chase|paystream|grammarly|united|"
    r"hackernewsletter|pragmaticengineer|paperjet-monitoring)\.", re.I)

_NOISE_SUBJECT = re.compile(
    r"\b(invoice|receipt|payout|renews?|usage|digest|newsletter|unsubscribe|"
    r"notification|reminder: your|is ready|almost full|unread messages|"
    r"weekly|monthly|daily|statement|password was changed|deploy(ed|ment)?)\b", re.I)


def classify(message):
    """Return (disposition, reason) if a rule decides this message, else None.

    A rule never fires on a message the guard flagged; demo.py screens first.
    """
    sender = message["from"].lower()
    subject = message["subject"]

    if _NOISE_SENDERS.search(sender) and _NOISE_SUBJECT.search(subject):
        return "archive", "automated notification from %s; matched noise rule, no model call" % sender.split("@")[-1]
    if _NOISE_SENDERS.search(sender):
        return "archive", "no-reply sender %s; nothing to answer, no model call" % sender.split("@")[-1]
    if re.search(r"\bunsubscribe\b|\bnewsletter\b|\bdigest\b", message["body"], re.I) \
            and _NOISE_SUBJECT.search(subject):
        return "archive", "bulk mail body; matched noise rule, no model call"
    return None


def is_noise(message):
    return classify(message) is not None
