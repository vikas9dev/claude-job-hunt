---
name: job-match
description: Analyzes job listings against the user's profile (stack, YOE, target CTC, locations, goals) and gives an Apply / Maybe / Practice / Skip verdict scored out of 14. Runs a zero-cost JD-text gate before any web search, reuses a JD already cached by /job-feed, researches the company (salary, reviews, layoffs, interview experiences), writes the result to the job tracker, and emits a ready-to-send referral outreach packet for high-payoff roles. Accepts a single URL, several URLs, a file of URLs, pasted JD text, or "stats".
argument-hint: <job-url> OR <path-to-file-with-urls> OR "paste" OR "stats"
allowed-tools: Read, Bash, WebFetch, WebSearch, Agent, Glob, Grep
---

# Job Match

Score one job listing (or a batch) against the user's profile and give a clear verdict with
reasons. Write every result to the tracker.

**Writing style:** short, plain sentences. Technical terms stay exact.

## Step 0 — Load the profile (every run)

Read **`.claude/skills/_shared/PROFILE_AND_FILTERS.md`**.

- If it does **not** exist: stop. Tell the user to run `/setup-profile` (or copy
  `PROFILE_AND_FILTERS.template.md` and fill it in). Do nothing else.
- If it still has `<<…>>` placeholders in §1–§6: warn once, and name the sections.
  Scoring with placeholders gives wrong verdicts.

Also read **`.claude/skills/_shared/TRACKER_RULES.md`** (status, verdict, apply-via and
channel values).

> ⚠️ **Never copy profile values into this skill or into a sub-agent prompt.** Read the file at
> run time. Below, `§N` means a section of `PROFILE_AND_FILTERS.md`.

The tracker store is `data/jobs_data.json`. Use **only** `python3 scripts/job_track.py`
(`python` on Windows) from the repo root. Never Read or Edit the JSON directly.

---

## Input modes

| Input | Mode |
|---|---|
| One `http(s)://` URL | Single URL |
| Two or more URLs | Batch (Step 3B) |
| A path ending in `.md` / `.txt` | Batch — one URL per line, optional `Label — URL` |
| A URL **and** pasted JD text | Hybrid — analyze the pasted text, store the URL |
| `paste` | Ask the user to paste the JD, then wait |
| `stats` | Step 8 |

Always scan the whole input for URLs (`https?://\S+`). If any URL is present, store it in
`urls`. Use channel `Pasted JD` only when there is no URL at all.

---

## Step 1 — Get the JD

**1a. Cached JD first.** `/job-feed` may have parked this URL with its JD text:

```bash
python3 scripts/job_track.py find "<url>" --url
```

If the row has a non-empty `jd_text`, use it and skip the fetch. Say
`Using JD cached by /job-feed on <date>`. Also read its `posted_date`.

**1b. Otherwise fetch it** with `WebFetch`.

- **HTTP 403 → hard stop.** Do nothing else this turn — no searches, no tracker calls. Reply only:
  ```
  ⚠️ This URL returned 403 (login wall or blocked).
  Please paste the JD text and I'll run the full analysis. I'll still save the URL.
  ```
  Without the JD, none of the scoring criteria can be judged, so any other work is wasted.
- **Empty / JS-only page** (common on LinkedIn): try one `WebSearch` for
  `"<job title>" <company>`. If that fails too, ask for a paste and stop.

**1c. Extract:** company, role title, YOE range, tech stack, location + work mode,
seniority, domain, key responsibilities, posted date (if stated), salary range (if stated).

---

## Step 2 — Cheap gate (no web searches)

Pure text checks on the JD you already have. If any fires, the job is auto-skipped:
write the row (below) and stop. **Spend zero searches.**

| Gate | Auto-skip when | Reason |
|---|---|---|
| **Consultancy / staffing** | Company is on the §10 exclude list or personal skip-list; or the name signals staffing ("staffing", "consulting", "recruit", "talent", "technologies services"); or the JD hides the end client ("our client", "leading MNC") | `Consultancy/staffing` |
| **Role family** | Role is in §6 *Out of scope* | `Wrong role family` |
| **Location** | No presence in the §4 country and no remote policy for it | `No presence in <country>` |
| **YOE** | Outside the §2 *YOE gate* | `YOE out of band` |
| **Level** | Title is in §2 *Above band* or *Below band* | `Level out of band` |
| **Contract** | Contract / C2H / fixed-term / "on the payroll of" | `Not a full-time role` |

> A §2 *Stretch* level is **not** a gate. Flag it `↗ stretch band` and score it normally.

```bash
python3 scripts/job_track.py upsert --stdin-json << 'EOF'
{"company": "…", "role": "…", "tier": "…", "score": "— (HF capped)",
 "verdict": "❌ Skip", "apply_via": "❌ Skip", "status": "⏭️ Skipped",
 "channel": "…", "recommendation": "Auto-skipped at the cheap gate: <reason>",
 "urls": [{"label": "Link", "url": "…"}]}
EOF
```

---

## Step 3 — Company research (single job)

Only after Step 2 passed and you have JD text. **Fire all of these in ONE message**, in
parallel — direct tool calls, not sub-agents (sub-agents add start-up time each):

| # | Search |
|---|---|
| 1 | `<COMPANY> <level from the JD> salary AmbitionBox` |
| 2 | `<COMPANY> software engineer salary Glassdoor <country>` |
| 3 | `<COMPANY> salary levels.fyi <country>` |
| 4 | `<COMPANY> reviews AmbitionBox work life balance` |
| 5 | `<COMPANY> Glassdoor rating <country>` |
| 6 | `<COMPANY> layoffs <last year> <this year>` (compute the years from today's date) |
| 7 | `<COMPANY> SDE interview experience GeeksforGeeks` |
| 8 | `<COMPANY> <role family> engineer interview LeetCode discuss` |
| 9 | `<COMPANY> software engineer interview questions <country>` |
| 10 | Bash: `python3 scripts/job_track.py find "<COMPANY>"` — duplicate check (exit 1 = `NOT FOUND`) |

If the user's country is not India, swap AmbitionBox for a local equivalent or drop it.

**Also scan the JD text for red flags:**

| JD red flag | Why it matters |
|---|---|
| "Wear multiple hats" | Understaffed, unclear role |
| "Fast-paced hustle culture" | Likely overwork |
| "Work on weekends when needed" | Usually the norm, not rare |
| "Unlimited PTO" | Often means no leave tracking, so less leave taken |
| "Competitive salary" with no range | Often below market |
| No tech stack named | Role may be poorly defined |
| "Equity in lieu of salary" | Below-market cash |

### Step 3A — Search-dependent filters

| Filter | Fails when | Then |
|---|---|---|
| Company size | Below the §10 threshold | `❌ Skip` — "Too small" |
| Engineering team | Below the §10 threshold (estimate if needed) | `❌ Skip` — "Eng team too small" |
| Hidden consultancy | Searches show a body-shop the JD hid | `❌ Skip` — "Consultancy/staffing" |

Write the skip like Step 2 (`score: "— (HF capped)"`) and stop.

### Step 3B — Batch mode

One sub-agent per job, **at most 5 at a time**, ~8 jobs per run unless the user asks for more.

```
Agent per job:
  subagent_type: "general-purpose"
  description: "Analyze job: <COMPANY>"
  prompt: "Analyze one job listing against a user profile.
    0. FIRST read .claude/skills/_shared/PROFILE_AND_FILTERS.md and
       .claude/skills/_shared/TRACKER_RULES.md and .claude/skills/job-match/SKILL.md.
       Do not assume any profile value; read it.
    1. Get the JD for <URL> per SKILL.md Step 1 (cached jd_text first, then WebFetch;
       on 403 return 'NEEDS PASTE' and stop).
    2. Run the Step 2 cheap gate. If it fires, return verdict ❌ Skip + reason. Zero searches.
    3. Run the Step 3 searches in ONE message, then Step 3A.
    4. Score per Step 4, decide apply_via per Step 5 (with the outreach packet if needed).
    5. Do NOT write to the tracker. Return: extracted fields, score table, red flags,
       verdict, and a JSON object with the Step 7 fields ready for upsert. analysis_md =
       condensed markdown (score table + red flags + 2-3 strategy bullets + outreach packet
       if any, ≤ 250 words) starting with '> Analyzed: <DD Mon YYYY>'.
    Keep the reply under 700 words."
```

Then show the summary table, the single analyses, and write each job yourself with one
`upsert` per job (Step 7). Batch jobs get the same 9 searches as single mode; the savings
come from the cheap gate.

---

## Step 4 — Score (7 criteria × 0/1/2 = out of 14)

| Criterion | 2 — strong | 1 — partial | 0 — mismatch |
|---|---|---|---|
| **Tech stack** | §5 *Tech-stack match rule* → 2 | → 1 | → 0 |
| **YOE band** | User's §1 YOE is inside the JD range | Slightly outside, or a §2 stretch | Far outside |
| **Role type** | §6 in-scope family at a §2 target level | In-scope family one level off, or a hybrid role leaning to the in-scope family | Out-of-scope family |
| **Company tier** | Score from §12 *Tier calibration* | ← | ← |
| **Location** | §4 Preferred | §4 Acceptable | Anything else |
| **CTC potential** | Likely ≥ §3 Target | Between §3 Floor and Target | Likely < §3 Floor |
| **WLB risk** | 🟢 Low (§11) | 🟡 Medium | 🔴 High |

**Verdict** — write the exact string into the tracker:

| Score | `verdict` |
|---|---|
| 12–14 | `✅ Apply` |
| 9–11 | `🟡 Maybe` |
| 5–8 | `⚠️ Practice` |
| 0–4 | `❌ Skip` |

**Rules that override the total:**

- **Hard CTC gate.** If §3 *Hard CTC gate* = `yes` and CTC potential = 0 → `❌ Skip`.
- **Tiers in scope.** If the company's tier is not in §12 *Tiers in scope right now*, cap at
  `⚠️ Practice` and say why.
- **Freshness cap.** If `posted_date` is known and is **more than 21 days old**, cap at
  `🟡 Maybe` (`posted 34d ago — likely filled`). Don't cap when the date is unknown. This rule
  never raises a verdict.
- **Calibration age.** If §12 *Calibrated on* is more than ~3 months old, say the tier scores
  may be stale. If it says "never", say defaults are in use.
- **Work-mode tiebreaker.** Equal totals → rank the §4 preferred work mode first. It never
  moves a role between verdicts.

Don't over-weight JD requirements — JDs are wish lists. If 70%+ of the stack matches, it is a
good fit. Salary data from review sites can be old; treat it as a direction.

---

## Step 5 — How to apply (`apply_via`)

```
if hard_filter_failed or score < 5:                          → ❌ Skip
elif score <= 8:                                             → ⏩ Low Priority
elif tier in (Tier-1, GCC) and score >= 11 and location_ok:  → 🎯 Aggressive Push
elif tier in (Tier-1, GCC) or (tier == Tier-2 and score >= 11): → 🤝 Referral First
else:                                                        → 📝 Direct Apply
```

`location_ok` = §4 Preferred. A role in an Acceptable-only city drops one level
(Aggressive Push → Referral First).

Referrals raise callback rates a lot at top companies, but each one costs 30–45 minutes.
Save them for high-payoff roles. Message **peer engineers** on the team (they get a referral
bonus) — **not** hiring managers, VPs or recruiters.

### Outreach packet — required for 🤝 Referral First and 🎯 Aggressive Push

> A referral verdict with no packet is not allowed. If you can't produce all four items,
> downgrade to `📝 Direct Apply` and say why. A label with no ready action rarely gets acted on.

1. **People-search link** (clickable):
   `https://www.linkedin.com/search/results/people/?keywords=<Company>%20<role family>%20engineer&origin=FACETED_SEARCH`
2. **Connection note, ≤ 300 characters**, ready to paste: the §9 *opener*, then the **one** §9
   hook that best fits this JD, then the role name and a polite ask
   (`Would you be open to referring me? Happy to send my resume first.`).
   Only use hooks from §9 — never invent experience.
3. **Fallback date:** a real date 5–7 days out: `if no reply by <DD Mon>, apply direct at <URL>`.
4. **Status command**, to run only after the notes are actually sent:
   ```bash
   python3 scripts/job_track.py set-status <id> "🔄 Referral Pending"
   ```
   Until then the row stays `📝 To Do`.

---

## Step 6 — Show the result

```
## Job Match — <Company>, <Role>

**Location:** … · **YOE asked:** … · **Salary data:** … (source)

### Score: 12/14 — ✅ Apply

| Criterion | Score | Notes |
|---|---|---|
| Tech stack | 2/2 | … |
| YOE band | 2/2 | … |
| Role type | 2/2 | … |
| Company tier | 2/2 | … |
| Location | 2/2 | … |
| CTC potential | 1/2 | … |
| WLB risk | 1/2 | 🟡 AmbitionBox WLB 3.3, mixed reviews |

### Red flags
…

### How to apply — 🤝 Referral First
① People search: <link>
② Connection note: > …
③ Fallback: if no reply by <DD Mon>, apply at <URL>
④ After sending: `python3 scripts/job_track.py set-status <id> "🔄 Referral Pending"`

### Prep topics (from interview experiences)
- …
```

If the company was already tracked (Step 3 #10), first say:
`ℹ️ Analyzed before on <date> — <score>, <verdict>. Re-analyzing…`

For a batch, show a summary table first:
`| # | Company | Role | Score | Verdict | Red flags | Apply via |`

---

## Step 7 — Save to the tracker

One `upsert` per job:

```bash
python3 scripts/job_track.py upsert --stdin-json << 'EOF'
{
  "company": "…", "role": "…", "tier": "Tier-1",
  "yoe": "4-7 (you ~5 — in band)", "tech_stack": "…", "location": "…",
  "ctc": "…", "score": "12/14", "verdict": "✅ Apply",
  "apply_via": "🤝 Referral First", "priority": "Dream", "channel": "LinkedIn",
  "status": "📝 To Do",
  "recommendation": "one-line next action",
  "analysis_md": "> Analyzed: DD Mon YYYY\n\n### Score: 12/14 — ✅ Apply\n…full Step 6 markdown, incl. the outreach packet…",
  "posted_date": "YYYY-MM-DD",
  "urls": [{"label": "Link", "url": "…"}]
}
EOF
```

- **Status by verdict:** `✅ / 🟡 / ⚠️` → `📝 To Do`; `❌ Skip` → `⏭️ Skipped`.
- **On an update** the script keeps `date`, `channel` and `status` as they were. One exception
  needs a follow-up: if the old status was `—` or `⏳ Pipeline`, align it:
  `python3 scripts/job_track.py set-status <id> "📝 To Do"` (or `"⏭️ Skipped"`).
  Never touch rows already at `✅ Applied` or beyond.
- **Same company, different role:** `upsert` updates by company. If the company has several
  rows, it stops and asks for `--id`. For a brand-new req at a tracked company, use
  `add --stdin-json --force-new` instead.
- `analysis_md` is what the tracker UI shows under the job. Always include it, except for
  cheap-gate skips.
- `jd_text`: set it only when you got a JD that wasn't cached (e.g. a paste). Never overwrite
  a cached JD with a shorter one.
- `posted_date`: only when known. Never guess.
- `priority`: per TRACKER_RULES *Priority buckets*.
- Use `--stdin-json` with a quoted `'EOF'` heredoc for anything with prose or emoji.

---

## Step 8 — Stats

```bash
python3 scripts/job_track.py stats            # all time
python3 scripts/job_track.py stats --month 2026-01
```

Relay the output as is. Don't recompute numbers. If the store is empty, say:
`No jobs analyzed yet. Run /job-match <url> to start.`

After 30+ applications, offer to copy the per-tier response rates into §12 *Tier calibration*
(ask first; it's the user's file).

---

## Notes

- **Cheap gates before expensive ones.** Step 2 is free; Step 3 costs 9 searches. Never swap them.
- **403 = hard stop.** See Step 1b.
- When torn between Apply and Skip, lean to Apply — the worst case is interview practice.
  (Unless the §3 hard CTC gate is on.)
- A strong score is not progress by itself. If the stats show many responses but few
  interviews, the problem is after the application (screening, assessments), not the
  targeting. Say so when it shows up.
- The tracker UI: `python3 ui/server.py`, then open http://127.0.0.1:8765.
