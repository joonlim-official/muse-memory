# Subagent briefing — need-to-know policy

Subagents and browser-task agents get ONLY the context needed for the
specific task — never Joon's private data by default. Private data =
anything the egress gate would flag (credentials, SSNs, card data,
financial figures, phone numbers, denylisted literals) plus identifying
info (full name, home address, family details).

Rules:

1. **Briefs carry task context, not private data.** The objective, the
   site, the item, constraints — without the private payload.
2. **If a step needs a private field, the agent stops and asks.**
   Browser tasks use ask_for_information; subagents report back. The
   field is supplied for that step only — never pre-loaded "just in
   case."
3. **Purchases never put payment details in the brief.** The wallet /
   approval-card flow handles payment; the brief ends at the review step.
4. **Generic subagents inherit the transcript** (mechanism, cannot be
   disabled) — so the brief additionally forbids them from using personal
   info from context for any external disclosure. Browser-task agents get
   only the brief, which is the stronger boundary.

## Standard paragraph — include verbatim in every subagent and browser-task brief

> Privacy: least privilege. Use only the facts in this brief. If a step
> needs personal details (name, address, phone, email, payment, account
> identifiers, or anything about the user's family or finances), STOP and
> ask for that specific field — do not guess, do not fill it from any
> other context, and do not reuse personal info you may have seen
> elsewhere. Never type private data into a page, message, or form unless
> it was explicitly provided for that step in this task. Details given
> for one step stay in that step.
