---
name: job-feed
description: 'Bulk-pull fresh job listings via the JobSpy MCP or your target companies'' own ATS feeds (watchlist), then run a ZERO-web-search local triage — role-family / YOE / location gates, the consultancy/staffing skip-list, URL-first dedup via job_track.py, and a keyword pre-score from your profile — to turn 50-100 raw listings into a ranked shortlist. Parks survivors as ⏳ Pipeline rows (with the JD text and posting date) and hands the top hits to /job-match. Also drains that queue: "/job-feed pipeline" lists parked rows by age and flags stale ones as JD Expired. Use when you want to find new roles in bulk instead of analyzing one JD at a time.'
argument-hint: '[search term | "remote" | "<site>" | "watch" | "pipeline" | "dry-run" | "go"]'
allowed-tools: Read, Bash, Grep, Glob, WebFetch, mcp__jobspy__search_jobs, Skill
---

# Job Feed — Bulk Discovery + Triage

This skill is the cheap **Stage-1 triage gate** between bulk discovery and the expensive deep analysis in `/job-match`.

```
Stage 0  Pull            JobSpy MCP or watchlist ATS feeds  → 50-100 raw listings
Stage 1  Triage  ← THIS SKILL — ZERO web searches:
            role/YOE/location gates · skip-list · URL-first dedup · keyword pre-score
                                                            → ranked shortlist (~5-15)
         Park            ⏳ Pipeline rows, JD text + posted_date kept
Stage 1b Drain   ← THIS SKILL (`/job-feed pipeline`)        → age-ranked, stale ones expired
Stage 2  Deep analysis   /job-match on the top hits         → full research + verdict
```

**Why the gate exists:** `/job-match` spends about 9 web searches per job. Running it on 100 raw listings means about 900 searches. Stage 1 is pure text work on JDs you already pulled. It costs almost nothing and protects the deep-analysis budget. Never pipe raw pull output straight into `/job-match`.

---

## Step 0 — Load the profile

Read **`.claude/skills/_shared/PROFILE_AND_FILTERS.md`** at the start of every run.

- If it does not exist, **stop**. Tell the user: `No profile found. Run /setup-profile, or copy PROFILE_AND_FILTERS.template.md to PROFILE_AND_FILTERS.md and fill it in.`
- If it still has `<<…>>` placeholders in a section this skill needs (§2, §4, §6, §7, §8, §10), list them and stop.
- Never copy values from the profile into this skill or into a sub-agent prompt. Read them at run time.

Also read **`.claude/skills/_shared/TRACKER_RULES.md`** for the Status enum (including `⏳ Pipeline`) and the Channel enum.

**The tracker** is `data/jobs_data.json`. Use only `scripts/job_track.py` to read or write it. Never Read/Edit the JSON, and never create a second tracker. Run commands from the repo root as `python3 scripts/job_track.py …` (on Windows, use `python`).

---

## Invocation

```
/job-feed                 → default pull (profile §7 terms + location) → triage → shortlist (dry-run)
/job-feed "<term>"        → custom search term
/job-feed remote          → remote focus (profile §7 remote location)
/job-feed naukri          → one site only (naukri | indeed | linkedin | glassdoor | google)
/job-feed dry-run         → pull + triage + shortlist, write NO tracker rows
/job-feed go              → same as default, but write ⏳ Pipeline rows after the preview
/job-feed watch           → skip JobSpy; pull your §13 watchlist companies' own ATS feeds, then triage
/job-feed pipeline        → no pull; list parked ⏳ Pipeline rows by age, flag >21d ones, hand live ones to /job-match
```

With no argument, behave like **dry-run**: show the shortlist and ask before writing rows.

---

## Steps

### Step 1 — Build the skip-list

1. **Do not build a dedup index yourself.** Dedup is one script call in Step 3 (`job_track.py dedup`). The company-matching rule lives in `normalize_company()` in the script. Re-deriving it from prose makes the two drift apart.
2. Build the **skip-list** in memory from:
   - The consultancy / body-shop / agency names in profile **§10 Exclude**, plus the personal skip-list there.
   - Every company already tagged as a consultancy or staffing firm in the tracker:
     ```bash
     python3 scripts/job_track.py list --json --all --fields company,tier \
       | grep -iE '"tier": "(Consultancy|Staffing)'
     ```

Consultancies and staffing firms rarely respond to direct applications, and the roles are usually not with the real end client. This filter is cheap and it saves the most wasted effort.

### Step 2 — Stage 0: Pull listings

**JobSpy mode (default).** Call `mcp__jobspy__search_jobs`. One call per search term. Keep `resultsWanted` modest (20–30) per call so it stays fast.

All defaults come from profile **§7 Job search defaults**:

- `searchTerm`: each term in §7 *Search terms*, unless the user gave a custom term.
- `location`: §7 *Default location*; §7 *Remote location* for `remote` mode; any city the user named wins.
- `siteNames`: §7 *Sites*. **LinkedIn scraping is flaky** (IP blocks). Set `linkedinFetchDescription` to `false` unless the user asks for LinkedIn.
- `countryIndeed`: §7 *Country for Indeed*. `hoursOld`: §7 *Hours old* (or wider if the user asks). `isRemote`: true for `remote` mode.
- **`jobType`: always `"fulltime"`.** This drops contract, C2H and internship roles at the source.

**If a call errors, say so plainly.** JobSpy runs a Docker image and scrapes live job boards. Tell the user:
> JobSpy failed: `<error>`. It needs Docker running and the `jobspy` image built. Start Docker, or run `bash scripts/setup_mcp.sh`. You can also try `/job-feed watch`, which does not use JobSpy.

Then go on with whatever calls did work. Never report an empty feed as "nothing found".

**Keep the JD and the posting date.** Pulls usually return a description and a posted date. Carry both through triage and into the tracker row (Step 5). If you drop them, `/job-match` has to fetch the same URL days later, and it may hit a 403 or an expired posting.

**Watch mode (`/job-feed watch`).** Skip JobSpy. Read profile **§13 Watchlist**, then look up each company in **[`ATS_FEEDS.md`](../_shared/ATS_FEEDS.md)** (URL templates + the token registry). Pull each company's **own ATS feed**. This catches roles that appear on a company's own board before they reach LinkedIn or Indeed — often true for GCCs.

- **✅ API rows** (Greenhouse, Lever, Ashby, SmartRecruiters): `WebFetch` the JSON feed URL. Extract `{title, location, url, posted date, description}` for each posting. Greenhouse → `jobs[]` with `.title`, `.location.name`, `.absolute_url`. Lever → array with `.text`, `.categories.location`, `.hostedUrl`. This `WebFetch` is a **Stage-0 pull** (structured data, like JobSpy). It is not a Stage-1 web search, so triage stays web-free.
- **Custom feeds need `curl`, not `WebFetch`.** `WebFetch` cannot POST, and it summarizes large JSON through a small model. Workday is a `POST`; some custom feeds return large payloads. Use the exact templates in `ATS_FEEDS.md` and parse the JSON in code (a short `python3 -c` or script in the scratchpad).
- **Filter by location in code.** These feeds are global. Keep only postings in the user's §4 country and preferred/acceptable locations (plus remote roles for that country). Never trust a URL's location parameter — many careers pages apply it in the browser with JavaScript, so a server-side fetch ignores it.
- **⚠️ JS-scrape rows:** try one `WebFetch` of the careers URL. Treat results as unreliable. If it returns junk, skip the company and say so.
- **❌ Paste-only rows:** do not automate. List them at the end so the user can check them by hand.
- **Company not in `ATS_FEEDS.md`:** list it at the end as `no token on file — add it to ATS_FEEDS.md`.
- **Feed returns 404:** report it (`token for <company> looks wrong — fix it in ATS_FEEDS.md`). Never drop the company silently.
- **Channel** for these rows = `Watchlist`.

Merge all pulled listings into one list. Remove exact duplicates inside the pull (same URL, or same company + title).

### Step 3 — Stage 1: Triage (NO web searches)

Work on each listing using **only the text you already pulled**. No `WebSearch`, no `WebFetch`.

**Run the free gates first, then dedup.** The gates are string checks. Dedup is a script call. Filtering first keeps the dedup payload small.

| Gate | Rule | Drop reason |
|---|---|---|
| **Skip-list** | Company is on the Step 1 skip-list, OR its name signals staffing ("staffing", "consulting", "recruit", "talent", "technologies services"), OR the JD hides the end client ("our client", "leading MNC") | `Consultancy/staffing` |
| **Role family** | Title is in profile §6 *Out of scope* | `Wrong role family` |
| **YOE** | Outside the profile §2 *YOE gate*. A level in §2 *Stretch levels* is **in scope** — flag it, don't drop it | `YOE out of band` |
| **Location** | Not in the profile §4 country, and no remote option there | `Location mismatch` |

#### Dedup — the URL is the only identity

Send every survivor to the tracker in **one** call. Include the role title — it is not used for matching, but it is echoed back for display:

```bash
python3 scripts/job_track.py dedup << 'EOF'
[{"company": "Acme Corp", "role": "Senior Backend Engineer", "url": "https://…"},
 {"company": "Globex",    "role": "SDE II",                  "url": "https://…"}]
EOF
```

| `recommend` | Meaning | Action |
|---|---|---|
| `fresh` | Company not tracked at all | Survives → `add` in Step 5 |
| `new-role` | Company is tracked, but **this posting is not** | **Survives** → `add --force-new` in Step 5 |
| `drop` | **This exact URL is already tracked** | Drop, and show the `reason` |

> ### The company never causes a drop. Only the URL does.
>
> A company runs many openings at once. You can apply to several, even while an interview
> loop is running there on another team. **Two job ids are two jobs.** Hiding a new opening
> because of a different one at the same company is wrong, and it is wrong silently.
>
> There is exactly **one** drop rule: this URL is already in the tracker. Nothing else — not
> status, not age, not tier — may hide a listing.

**Two advisory flags** come back on `new-role` rows. Neither filters anything. Both must be **shown** so a re-apply is a conscious choice:

| Field | Set when | Show as |
|---|---|---|
| `live_process` | Something is in flight at this company on another opening | `⚠️ live: 🔄 Round 2 on "Payments" (id=201)` |
| `recent_contact` | Last activity here was within **15 days** | `⚠️ heard from them 9d ago (❌ Rejected)` |

The 15-day window only decides what gets flagged. Change it with `--cooloff-days N`. `dedup --explain` shows how many rows each window would flag.

> **Known limit.** Because identity is the URL, the same opening found on two sites (LinkedIn
> and the company's own board) has two URLs and passes dedup twice. Prefer the company's own
> ATS URL when both show up in one pull. An occasional duplicate row is the accepted cost of
> never hiding a real opening.

#### Pre-score (0–10, floor 0)

For survivors, compute a **keyword pre-score** from the JD text only, using the tables in profile **§8 Keyword pre-score**. It is a cheap ranking signal, not a verdict.

- Add the positive points for each signal that appears. Subtract the negative points. Clamp at 0.
- A negative signal **never drops** a listing. That is `/job-match`'s call. It only lowers the rank. Show every negative that fired in the Flags column, so a −3 is visible.
- Also flag, without scoring:
  - a full-stack / frontend requirement when §6 does not include it, and
  - `↗ stretch band` when the title or YOE floor matches profile §2 *Stretch levels*. This is a display marker only. It costs no points and never drops a row.

### Step 4 — Show the ranked shortlist

Show survivors sorted by pre-score (highest first). Then show a short summary of what was dropped, so nothing disappears silently. Example (illustrative companies):

```
## 🧲 Job Feed — <date>

**Pulled:** 64 (indeed 30, naukri 34)  ·  **Survived triage:** 9  ·  **Dropped:** 55

### Shortlist (ranked — pre-score is a cheap signal, not a verdict)
| # | Company | Role | YOE | Location | Posted | Stack hits | Pre | Flags | URL |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Acme Corp | Senior Backend Engineer | 5-8 | Bengaluru Hybrid | 2d | <hits from §8> | 9 | ↗ stretch band | [Link](...) |
| 2 | Globex GCC | Backend Engineer II | 4-7 | Hyderabad | 5d | <hits> | 4 | ⚠️ −3 US shift · ⚠️ heard from them 9d ago (❌ Rejected) | [Link](...) |
| 3 | Initech | SDE III — Search | 5-8 | Bengaluru | 1d | <hits> | 8 | ⚠️ live: 🔄 Round 2 on "Payments" (id=201) | [Link](...) |

### Dropped (grouped by reason)
- **Consultancy/staffing (18):** …
- **Already tracked — same URL (4):** …
- **Wrong role family (15):** …
- **YOE out of band (7):** …
- **Location mismatch (3):** …
```

Three display rules:
- **The only dedup drop is "same URL".** Say exactly that. A company showing up in the shortlist while it already has a row is normal.
- **Always show `live_process` and `recent_contact`** in the Flags column. An unshown flag is the same as no flag.
- **Never merge the two.** "Live process here" (a second opening is a real strategy choice) and "recent contact" (they said no recently) need different decisions.

### Step 5 — Write survivors as `⏳ Pipeline` rows (confirm first)

Unless this is a dry-run, show a **confirm preview** (the rows you will write). On a yes, write each shortlisted listing with one `add --stdin-json` call:

```bash
python3 scripts/job_track.py add --stdin-json << 'EOF'
{
  "company": "Acme Corp",
  "role": "Senior Backend Engineer",
  "yoe": "5-8",
  "tech_stack": "<keyword hits from §8>",
  "location": "Bengaluru Hybrid",
  "tier": "?",
  "ctc": "?",
  "score": "⏳ Pending",
  "verdict": "⏳ Pending",
  "apply_via": "⏳ Pending",
  "priority": "?",
  "channel": "JobSpy",
  "posted_date": "YYYY-MM-DD",
  "jd_text": "…full scraped JD text, verbatim…",
  "recommendation": "Pulled via /job-feed (pre-score 9/10) — run /job-match for deep analysis",
  "status": "⏳ Pipeline",
  "urls": [{"label": "Link", "url": "https://…"}]
}
EOF
```

- **`channel`**: from the Channel enum in `TRACKER_RULES.md` — `JobSpy` or `Watchlist`. `upsert` never changes it, so it records where the job was *found*.
- **`posted_date`**: the company's posting date (`YYYY-MM-DD`), not today's. Leave it out if the feed doesn't give one. Never guess.
- **`jd_text`**: the scraped JD, verbatim. This lets `/job-match` skip its fetch. A Pipeline row without it forces a re-fetch later, when the URL may be dead.
- **Which command:** `add` for `recommend: fresh`; **`add --force-new`** for `recommend: new-role`. Plain `add` fails on a tracked company — that is the last safety check behind Step 3. If it fails on a `fresh` row, report it and stop. Do not retry with `--force-new` just to make the error go away.
- `⏳ Pipeline` is never auto-archived, so parked rows stay until you act on them.

`go` mode writes after the preview without a second prompt.

### Step 6 — Hand off to deep analysis

Recommend the top 3–5 by pre-score for Stage 2:

> Run `/job-match <url>` on the top hits (Acme Corp, …) for full company research and scoring. `/job-match` updates each `⏳ Pipeline` row in place with the real verdict.

Do **not** run `/job-match` on every survivor yourself. That brings back the search-budget blowout this funnel exists to prevent. Let the user choose which ones get the full treatment.

Then **always close with the pipeline count**:
`⏳ Pipeline now holds N rows (oldest: <company>, <n>d). Run /job-feed pipeline to work the queue.`
Parking rows without a reminder is how the queue stalls.

---

## `/job-feed pipeline` — work the parked queue

Parking rows is only half a funnel. This mode drains it. It makes **no** web calls and no pulls.

1. Get the parked rows:
   ```bash
   python3 scripts/job_track.py list --json --status-group active \
     --fields id,company,role,date,posted_date,location,tech_stack,recommendation,status,urls,jd_text
   ```
   Keep only rows with `status == "⏳ Pipeline"`.

2. Work out the **age** of each row: days since `posted_date` when present, else since `date`. Say which one you used — "posted 26d ago" and "parked 26d ago" are different claims.

3. Show them, oldest first:

```
## ⏳ Pipeline — 10 parked

| # | Company | Role | Age | Pre | Stack | Status |
|---|---|---|---|---|---|---|
| 1 | Acme Corp | Backend Engineer | posted 41d ⚠️ | 8 | … | likely expired |
| 2 | Globex | SDE II | parked 12d | 9 | … | live |
```

4. **Staleness rule.** Anything **older than 21 days** is flagged `⚠️ likely expired`. Do **not** change the status by yourself — some openings stay open longer. List the flagged rows and ask once:

   > 5 rows are older than 21 days and are probably closed. Mark them `⚠️ JD Expired`? (y / pick some / no)

   On a yes:
   ```bash
   python3 scripts/job_track.py set-status <id> "⚠️ JD Expired"
   ```
   `⚠️ JD Expired` is terminal and can be archived, so this really clears the queue.

5. **Hand the live rows to Stage 2**, highest pre-score first. Prefer rows that already have `jd_text` — `/job-match` needs no fetch for those.

---

## Notes

- **Triage is web-free by design.** If you reach for `WebSearch` in Steps 1–5, stop. That is Stage 2's job.
- **JobSpy reliability:** it runs a Docker image and scrapes live job boards. Indeed and Naukri are usually reliable; LinkedIn is often blocked. If a pull fails or comes back thin, say so.
- **Watch mode is the reliable backbone.** Company ATS feeds are not IP-blocked. Use it for a dependable regular check of real targets; use JobSpy for broad sweeps.
- **Pre-score ≠ verdict.** A high pre-score only means the JD keywords match. Company tier, WLB, layoffs, pay and staffing reality are decided in `/job-match`.
- **Dedup is the script's job.** One `dedup` call; act on `recommend`.
- **More listings is rarely the fix.** If applications get responses but not interviews or offers, the problem is after this skill. Prefer a small, good shortlist and a drained pipeline over a bigger pull.
- **Keep the watchlist short.** §13 is a list of real targets, not a copy of every company. Prefer companies with ✅ API feeds in `ATS_FEEDS.md`; for Workday-only or JS-only targets, accept the paste fallback.
- This skill works with `/discover-companies` (finds new companies) and `/job-match` (deep analysis of one job): `/discover-companies` → add to §13 → `/job-feed watch` → `/job-match`.
