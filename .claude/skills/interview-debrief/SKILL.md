---
name: interview-debrief
description: Log an interview right after it happens — the questions asked, what you answered, a better answer, how each round went, and the lessons. Reuses an existing lesson when the same mistake happens again, so repeated habits become visible and ranked. Also "lessons" (top repeated open lessons with practice steps) and "prep <company>" (before an interview — open lessons plus past questions at that company and on the same topics). Use when the user says "/interview-debrief", "I just had an interview", "log my interview", "what do I keep getting wrong in interviews", or "prep me for my interview at X".
argument-hint: '[<company>] | "lessons" | "prep <company>"'
allowed-tools: Read, Bash, Grep, Glob
---

# Interview Debrief

Turn an interview into a record you can learn from. The value is in the **repeats**: one bad
answer is noise; the same mistake in three interviews is a habit to fix.

**Writing style:** short, plain sentences. Technical terms stay exact. Be honest about weak
answers — a kind but vague debrief teaches nothing.

## Step 0 — Load context (every run)

1. Read **`.claude/skills/_shared/PROFILE_AND_FILTERS.md`**. If it does not exist, stop and
   tell the user to run `/setup-profile`. The profile gives the user's level (§1, §2) and stack
   (§5) — better answers must fit that level.
2. Read **`.claude/skills/_shared/TRACKER_RULES.md`** (job status values).

The store is `data/interviews_data.json`. Use **only** `python3 scripts/interview_track.py`
(`python` on Windows) from the repo root. Never Read or Edit the JSON directly.

## Privacy rules (always)

- **No interviewer names.** Record the role only: "Senior engineer", "Engineering manager",
  "HR". If the user gives a name, drop it.
- **Paraphrase questions.** Keep enough to practise from ("design a URL shortener"). If the
  user is under an NDA or the company asked not to share questions, write only the topic and
  a one-line paraphrase.
- No salary figures from the interview here — those belong in the job tracker or `/offer-compare`.

---

## Mode A — Debrief (default)

### A1. Collect

Ask once, in one message, and wait:

```
Tell me everything you remember, in any order:
- company, role, and which round(s) (coding / system design / LLD / HR / hiring manager / behavioral)
- date of each round
- every question you remember, and roughly what you answered
- anything that went well or badly, and how it felt
- the result, if you know it
```

If the user already gave this in the command, skip the ask.

### A2. Find what exists

Run these together:

```bash
python3 scripts/interview_track.py list
python3 scripts/interview_track.py lessons --json
python3 scripts/job_track.py find "<company>"
```

- An interview for this company + role already logged → this is a **new round** (`add-round`).
- Otherwise → a **new interview** (`add-interview`). Slug: `<company>-<role-keyword>-<YYYY-MM>`,
  lowercase kebab-case (e.g. `acme-backend-2026-03`).
- If the job tracker has the role, note its `id` to link it (`job_id`).

### A3. Structure and grade

For each round: `name`, `date`, `format`, `interviewer` (role only), `result`
(`passed` / `failed` / `pending` / `unknown`).

For each question:

| Field | What to write |
|---|---|
| `q` | Short paraphrase |
| `topic` | One stable label, reused across interviews (e.g. `Arrays`, `System design`, `Java concurrency`, `Behavioral — conflict`). Check existing topics with `interview_track.py topics` and reuse the same spelling |
| `my_answer` | What the user said, in one or two lines — their words, not improved |
| `better_answer` | 2–4 lines: the answer a strong candidate **at the user's level** would give. Correct and honest. For design questions, the key steps and the main trade-off. For behavioral ones, the STAR shape with what was missing |
| `verdict` | 🟢 solid · 🟡 partly right or slow · 🔴 wrong, stuck, or missed the point |

Then `went_well` and `went_wrong` per round — concrete behaviours ("asked clarifying questions
first", "no complexity stated"), not feelings.

### A4. Match lessons — the important step

For each `went_wrong` item and each 🔴 answer, ask: **is this the same mistake as an existing
lesson?** Compare by meaning, not wording (e.g. "didn't estimate traffic" = existing
`estimate-before-design`).

- Same mistake → **reuse the existing lesson id** and add this interview to `seen_in`.
  Say it plainly: `This is the 3rd time: "Do a capacity estimate before drawing boxes".`
- A lesson marked `fixed` that shows up again → reopen it (`status: open`) and say so.
- New mistake → a new lesson: `id` (kebab-case), `title` (an instruction, ≤ 10 words),
  `category` (`communication` / `technical` / `preparation` / `logistics` / `negotiation`),
  `detail` (what happened), `practice` (one concrete drill the user can do this week).

Keep it to the 1–4 lessons that matter. Not every small slip is a lesson.

### A5. Preview, then write

Show the whole debrief first:

```
## Debrief — <Company>, <Role> — <Round>

| Question | Topic | You said | Better answer | |
|---|---|---|---|---|
| … | … | … | … | 🔴 |

**Went well:** …
**Went wrong:** …

**Lessons**
- 🔁 ×3 estimate-before-design — "Do a capacity estimate before drawing boxes" (repeat)
- 🆕 state-complexity-early — "State time and space complexity before coding"

Save this? (yes / change …)
```

Write only after a yes. Order matters — the interview must exist before a lesson can point to it:

```bash
# new interview (rounds can be included here)
python3 scripts/interview_track.py add-interview --link-job <id> --stdin-json << 'EOF'
{"slug": "acme-backend-2026-03", "company": "Acme", "role": "Backend Engineer",
 "outcome": "in-progress", "summary": "…",
 "rounds": [{"name": "Round 1 — Coding", "date": "2026-03-02", "format": "DSA",
             "interviewer": "Senior engineer", "result": "pending",
             "questions": [{"q": "…", "topic": "…", "my_answer": "…", "better_answer": "…", "verdict": "🟡"}],
             "went_well": ["…"], "went_wrong": ["…"]}]}
EOF

# or, for a later round of an interview already logged
python3 scripts/interview_track.py add-round acme-backend-2026-03 --stdin-json << 'EOF'
{"name": "Round 2 — System design", "date": "2026-03-09", "format": "system design", …}
EOF

# one call per lesson — new or repeat; seen_in is only ever added to
python3 scripts/interview_track.py lesson-upsert --stdin-json << 'EOF'
{"id": "estimate-before-design", "seen_in": "acme-backend-2026-03"}
EOF
```

Leave out `--link-job` when the job is not in the tracker. If the result is known, also run
`python3 scripts/interview_track.py set-outcome <slug> <in-progress|rejected|offer|withdrew|no-response>`.

### A6. Update the job tracker (offer, don't assume)

If the job is in the tracker, suggest the matching status and run it only on a yes:

| What happened | Status |
|---|---|
| Round 1 / 2 / final done, waiting | `🔄 Round 1` / `🔄 Round 2` / `🔄 Final Round` |
| Next round booked | `📞 Interview Scheduled` |
| All rounds cleared, offer talk | `🤝 Pre-offer` |
| Rejected | `❌ Rejected` |
| Failed a test | `❌ Failed Assessment` |
| You withdrew | `⏭️ Declined` |

```bash
python3 scripts/job_track.py set-status <id> "🔄 Round 2"
```

### A7. Close

End with the **top 3 open lessons by repeats** (`interview_track.py lessons --open`) and one
line each on what to practise before the next interview.

---

## Mode B — `lessons`

```bash
python3 scripts/interview_track.py lessons --open
python3 scripts/interview_track.py topics
python3 scripts/interview_track.py stats
```

Show:

1. Open lessons, most repeated first, each with its practice step.
2. Topics with the highest 🔴 share (at least 2 questions asked) — these are study priorities.
3. One honest line on the pattern, e.g. *"Coding rounds pass; 4 of 5 design rounds fail on
   estimation. Practise estimates before more LeetCode."*

Offer to mark a lesson fixed only when the user says it went well in a recent interview:
`python3 scripts/interview_track.py set-lesson-status <id> fixed`.

---

## Mode C — `prep <company>`

Before an interview:

```bash
python3 scripts/interview_track.py lessons --open --json
python3 scripts/interview_track.py list --json
python3 scripts/job_track.py find "<company>"
```

Then `show <slug>` for any past interview at this company.

Give a one-screen brief:

1. **Your open lessons** — top 3 by repeats, each with the practice step.
2. **Past questions here** (if any) — with the better answers.
3. **Topics you miss most** (from `topics`) that this round is likely to cover. If the job row
   has `analysis_md` with "Prep topics", use those too.
4. **Two questions to ask each interviewer**, fitted to this company's work.

No web searches in this mode — `/job-match` already did the company research.

---

## Notes

- The UI shows all of this under **Interviews**: `python3 ui/server.py`.
- Grade the idea, not the wording. A right answer with a wrong label is 🟡 at worst.
- If the user debriefs days later and remembers little, log what they have. A thin record
  still builds the repeat count.
