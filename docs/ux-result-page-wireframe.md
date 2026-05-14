# Evidrai UX Result Page Wireframe

Date: 2026-05-14
Status: Draft

## Goal

Move Evidrai from a report-like Streamlit output to a professional result page that gives users a clear answer quickly while preserving nuance and trust.

The page should answer, in order:

1. What is the verdict?
2. What exactly is supported?
3. What is disputed or unknown?
4. What evidence supports that judgement?
5. What should the user do if the verdict feels wrong?

---

## Page layout

```text
┌─────────────────────────────────────────────────────────────┐
│ Evidrai                                                     │
│ [New check] [History] [About]                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ VERDICT CARD                                                │
│ Likely supported · Medium confidence                        │
│                                                             │
│ Evidence supports the factual core, but the legal           │
│ obligation remains contested.                               │
│                                                             │
│ Evidence strength     █████░░░░░ 5.0/10                     │
│ Source quality        ███████░░░ 3.5/5                      │
│ Contradictions        0                                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ CLAIM BREAKDOWN                                             │
│                                                             │
│ ✓ £5M gift existed                    Supported             │
│ ✓ Gift initially undisclosed           Likely supported      │
│ ? Rules required disclosure            Contested             │
│ ? Wrongdoing established               Unproven              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ KEY CAVEAT                                                  │
│ The dispute is not mainly whether the gift existed.          │
│ It is whether the gift had to be declared under the          │
│ relevant rules.                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ EVIDENCE MAP                                                │
│                                                             │
│ Supports factual core                                       │
│ - Guardian: reports £5M gift and disclosure issue            │
│ - Independent: reports standards watchdog referral           │
│                                                             │
│ Disputes interpretation                                     │
│ - Farage statement: says no obligation to declare            │
│                                                             │
│ Context only                                                │
│ - Political criticism and reaction                          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ WHAT WOULD CHANGE THIS?                                     │
│ - Standards Commissioner ruling                             │
│ - Electoral Commission finding                              │
│ - Parliamentary register/documentary disclosure record       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ SOURCES                                                     │
│ [Expandable detailed source cards]                          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ FEEDBACK                                                    │
│ Was this verdict too weak, too strong, unclear, or useful?  │
└─────────────────────────────────────────────────────────────┘
```

---

## Component details

### VerdictCard

Purpose: provide the answer in under 10 seconds.

Fields:

- verdict
- confidence
- one-sentence answer
- key caveat
- evidence strength score
- average source quality
- contradiction count

Rules:

- Never show raw model prose before the verdict.
- Avoid vague labels without explanation.
- If confidence is Medium or Low, state what limits confidence.

### ClaimBreakdown

Purpose: prevent simple claims with hidden nuance from producing unclear verdicts.

Each row:

- subclaim text
- dimension
- status
- confidence
- short rationale

Status options:

- Supported
- Likely supported
- Contested
- Unverified
- Not supported
- Unproven

Dimension options:

- factual core
- interpretation
- obligation
- wrongdoing
- context

### KeyCaveat

Purpose: explain the main boundary of the verdict.

Examples:

- "The factual event is supported; the legal implication is contested."
- "There is reporting of an allegation, but no direct evidence in the reviewed packet."
- "The source confirms the quote, but not the interpretation attached to it."

### EvidenceMap

Purpose: make source role obvious.

Groups:

- Supports factual core
- Contradicts factual core
- Supports interpretation
- Disputes interpretation
- Context/noise
- Weak/irrelevant

Each source card:

- title
- domain
- source type
- stance
- evidence category
- score
- one-line classification reason

### WhatWouldChangeThis

Purpose: show that uncertainty is structured, not evasive.

Examples:

- official ruling
- primary document
- direct transcript/video
- correction/retraction
- independently verified source

### FeedbackPanel

Purpose: convert user disagreement into reviewable data.

Fields:

- rating
- reason tags
- expected verdict
- expected confidence
- free-text comment

Future: if user says verdict is wrong, ask one follow-up:

> What verdict did you expect?

---

## UX principles

1. One clear answer first.
2. Nuance immediately below, not hidden.
3. Separate facts from interpretation.
4. Show evidence roles, not just source list.
5. Collapse deep internals by default.
6. Make disagreement easy to submit.
7. Use visual hierarchy, not walls of text.
8. Mobile-first: cards over tables.

---

## Mobile layout

Mobile order:

1. Verdict card
2. Key caveat
3. Claim breakdown cards
4. Evidence strength bars
5. Evidence map accordions
6. Sources
7. Feedback
8. Debug/internal only if enabled

Avoid multi-column layouts on mobile.

---

## Immediate Streamlit approximation

Before a full frontend rebuild, Streamlit can approximate this by:

- moving Deep result above Fast
- adding Claim Breakdown section
- renaming Evidence Snapshot to Evidence Map
- grouping sources by role
- making Feedback more prominent
- collapsing raw details

This is not the final UX, but it narrows the gap while the proper frontend is planned.
