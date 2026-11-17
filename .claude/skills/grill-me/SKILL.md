---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Works as a system-design or project-deep-dive mock interview, and for stress-testing a job-search plan or an offer decision. Use when the user wants to stress-test a plan, get grilled on a design, practise a design round, or mentions "grill me".
argument-hint: [the plan, design or topic to be grilled on]
---

# Grill Me

Interview the user relentlessly about every part of this plan or design until you both share
the same understanding. Walk down each branch of the design tree, and resolve the
dependencies between decisions one by one. For each question, give your recommended answer.

- Ask **one question at a time**, and wait for the answer.
- Find the weakest point first. Agree only after real scrutiny, never by default.
- If the codebase or a file can answer a question, read it instead of asking.

**Mock-interview mode** — when the topic is a system-design prompt or "my project":

- Act as the interviewer. Don't give your recommended answer until the user has answered.
- Cover requirements, scale estimates, API, data model, the high-level design, then the deep
  dives (bottlenecks, failure cases, trade-offs).
- At the end, give a short scorecard: what was strong, what was missing, and 2–3 things to
  practise. If `/interview-debrief` is set up, offer to log the gaps as lessons.

Write in short, plain sentences.
