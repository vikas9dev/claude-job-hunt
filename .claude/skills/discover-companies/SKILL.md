---
name: discover-companies
description: Discovers companies that are expanding in your country, recently funded, bulk hiring, or opening new offices — filtered against your profile (stack, target level, CTC bar, locations, WLB). Writes a ranked report with company profiles and can add the best ones to your watchlist. Use when you want to find new companies to target beyond your existing list.
argument-hint: [optional focus e.g. "fintech", "bengaluru", "remote", "new office", "gcc", "series C+"]
allowed-tools: Read, Edit, Write, Bash, WebFetch, WebSearch, Agent, Glob, Grep
---

# Discover Companies

Find companies worth targeting that match the user's profile. Focus on **expansion signals**: a new office, fresh funding, bulk hiring, a growing engineering team.

---

## Step 0 — Load the profile

Read **`.claude/skills/_shared/PROFILE_AND_FILTERS.md`** at the start of every run.

- If it does not exist, **stop**. Tell the user: `No profile found. Run /setup-profile, or copy PROFILE_AND_FILTERS.template.md to PROFILE_AND_FILTERS.md and fill it in.`
- If a section this skill needs (§1, §2, §3, §4, §5, §10, §11, §12) still has `<<…>>` placeholders, list them and stop.
- Never copy profile values into this skill or into a sub-agent prompt. Each sub-agent reads the profile file itself.

Also read **`.claude/skills/_shared/TRACKER_RULES.md`** → *Data sources for company research*.

Work out **the current year** from today's date (`date +%Y`). Use it, and the year before, in every search query below as `<YEAR>` / `<LAST_YEAR>`. Never hardcode a year.

---

## What this skill does

Searches the web for companies that:
1. Recently opened or grew an office in the user's country (§4), or are bulk hiring there.
2. Got fresh funding (Series B+) and are growing engineering.
3. Have open roles in the user's in-scope role families (§6) and stack (§5).
4. Pass the hard filters (§10): not a consultancy, > 100 employees, presence in the country.
5. Are realistic targets for the user's YOE and target levels (§1, §2) and can pay at least the §3 Floor.

---

## Steps

### Step 1 — Parse the focus

If `$ARGUMENTS` is given, use it to narrow the search:
- a domain (`"fintech"`, `"healthtech"`) → that domain only
- a city (`"bengaluru"`) → that city only
- `"remote"` → remote-first companies hiring in the user's country
- `"new office"` / `"gcc"` → companies that recently opened an office or GCC
- `"series C+"` → well-funded companies only
- nothing → run all search groups

### Step 2 — Run discovery searches

Launch **3–4 parallel sub-agents**, one per search group. Fill the `<…>` slots from the profile at run time:
`<COUNTRY>` = §4 Country · `<CITIES>` = §4 Preferred locations · `<LANG>` = §5 Primary language · `<STACK>` = §5 Core stack (first 1–2 items) · `<ROLE>` = §6 In scope (first family, e.g. "backend") · `<DOMAIN>` = §1 Domain.

#### Agent A — New office / expansion
- `"company opened <COUNTRY> office <LAST_YEAR> <YEAR> engineering"`
- `"tech company <COUNTRY> expansion <CITIES> <YEAR>"`
- `"global capability center <COUNTRY> <YEAR> hiring"`
- `"company opened GCC <CITIES> <YEAR>"`

#### Agent B — Recent funding + hiring
- `"series B C D funding <COUNTRY> tech company <YEAR>"`
- `"startup funding <COUNTRY> <ROLE> engineer hiring <YEAR>"`
- `"funding roundup <YEAR> <COUNTRY> startups"` (for India, Inc42 and YourStory publish these)

#### Agent C — Bulk hiring signals
- `"bulk hiring <LANG> <ROLE> engineer <COUNTRY> <YEAR>"`
- `"company hiring 50+ engineers <COUNTRY> <YEAR>"`
- `"tech company mass hiring <CITIES> <YEAR>"`

#### Agent D — Focus or domain (only if a focus was given, or §1 Domain is set)
- `"<DOMAIN> company hiring <LANG> <ROLE> <COUNTRY> <YEAR>"`
- `"<DOMAIN> startup funding <COUNTRY> <YEAR>"`

Each agent must:
1. Read `PROFILE_AND_FILTERS.md` itself (do not paste profile values into its prompt).
2. Run its searches with `WebSearch`.
3. Pull company names out of the results.
4. For each company: name, what it does, why it is expanding, HQ, office location in the user's country, rough size, funding stage, and the source URL.
5. Return a structured list. Mark anything it guessed as an estimate.

### Step 3 — Dedup and filter

Merge the agents' results. For each company:

1. **Dedup** — the same company found by several searches.
2. **Already tracked?** Check once per company:
   ```bash
   python3 scripts/job_track.py find "<company>"
   ```
   (On Windows, use `python`.) A tracked company is not dropped — mark it `already tracked (id=…, <status>)` in the report.
3. **Hard filters** (§10):
   - Skip consultancies, body-shops, agencies, and anything on the personal skip-list.
   - Skip if < 100 employees.
   - Skip if no presence (office or remote policy) in the §4 country.
4. **Stack check** — `WebSearch "<company> <LANG> <ROLE> engineer careers"`. Skip if the company only hires for stacks the user does not have (§5).

### Step 4 — Enrich each company

For each company that is left, gather:

| Data point | How to get it |
|---|---|
| **AmbitionBox / Glassdoor rating** | `WebSearch "<company> AmbitionBox"` / `"<company> Glassdoor"` |
| **WLB rating** | From the same pages |
| **Employee count** | Crunchbase or LinkedIn |
| **Eng team size** | Estimate from LinkedIn or the careers page — say it is an estimate |
| **Salary range at the user's target level (§2)** | AmbitionBox / Glassdoor / levels.fyi |
| **Funding stage** | Crunchbase |
| **Careers page URL** | `WebSearch "<company> careers <COUNTRY>"` |
| **ATS + board token** | From the careers page links (`boards.greenhouse.io/<token>`, `jobs.lever.co/<token>`, `jobs.ashbyhq.com/<token>`, `careers.smartrecruiters.com/<token>`, `*.myworkdayjobs.com`) — needed for `/job-feed watch` |
| **Open roles** | Check the careers page for in-scope roles |
| **Expansion signal** | What triggered the find (new office / funding / bulk hiring) |
| **GCC status** | Foreign HQ + engineering centre in the user's country + direct FTE hiring → ⭐ GCC (§12). `WebSearch "<company> <COUNTRY> GCC OR captive center OR development center"` |

Use only what you found. Never invent a rating, a salary or a headcount. Write `?` when unknown.

### Step 5 — Score and rank

Score each company. All bars come from the profile:

| Factor | Weight | Scoring (0 / 1 / 2) |
|---|---|---|
| **Stack match** | 3x | Use the §5 *Tech-stack match rule* → 2 / 1 / 0 |
| **WLB rating** | 2x | §11 bands: > 3.5 = 2 · 3.0–3.5 = 1 · < 3.0 = 0 |
| **CTC potential** | 2x | At or above §3 Target = 2 · between Floor and Target = 1 · below Floor = 0. **If §3 Hard CTC gate = yes, a 0 here drops the company from the list**, whatever its total |
| **Expansion signal** | 2x | Bulk hiring now = 2 · new office = 2 · recent funding = 1 |
| **Location match** | 1x | §4 Preferred = 2 · §4 Acceptable = 1 · neither = 0 |
| **GCC bonus** | 1x | Foreign company's own centre in the user's country, hiring FTE = 2 · foreign company, remote / contractor only = 1 · domestic company = 0 |

**Max score: 22.** Also respect §12 *Tiers in scope right now* — if a company's tier is out of scope, list it under *Notable mentions*, not in the top table.

Rank highest first. **Tiebreaker:** on equal scores, rank the role that matches §4 *Work mode preference* first. This only breaks ties; it never changes points.

**GCC is a boost, not a filter** (§12). Strong domestic product companies still rank well on the other factors.

### Step 6 — Show the results

Show the user a summary. The rows below are **illustrative only** — fill them with what you actually found:

```
## 🔍 Company Discovery Results

**Search focus:** [All / <focus>]
**Date:** <DD Mon YYYY>
**Companies found:** 12 (after filtering)

### Top matches

| # | Company | What they do | Expansion signal | Size | Funding | WLB | CTC range | Location | Score | Careers |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ⭐ Example GCC Co | Data platform | New <city> office, bulk hiring | 5000+ | Public | 3.8 | <range> | <city> Hybrid | 20/22 | [Careers](url) |
| 2 | Example Product Co | Payments | Series D, hiring 50+ | 1200 | Series D | 3.6 | <range> | <city> | 17/22 | [Careers](url) |

> ⭐ = GCC (foreign company's own engineering centre). Scores are out of 22.

### Notable mentions (lower score, worth watching)
- **Company X** — just raised Series C, hiring starts next quarter

### Excluded (and why)
- Company Z — < 100 employees
- Company W — consultancy model
```

### Step 7 — Write the report

**File:** `reports/DISCOVERED_COMPANIES_<DD_Mon_YYYY>.md` (e.g. `DISCOVERED_COMPANIES_09_Apr_2027.md`). `reports/` is gitignored, so the report stays on the user's machine. If a file with that name exists, add `_v2`, `_v3`, ….

One file per run, with the summary and the detailed profiles:

```markdown
# Company Discovery Report — <DD Mon YYYY>

> **Focus:** [All / <focus>]  
> **Total found:** 12 | **Top matches:** 5 | **Excluded:** 4

---

## Summary

<the Step 6 tables: top matches, notable mentions, excluded>

---

## Detailed Profiles

> Profiles for companies scoring **11+ out of 22**.

### 1. ⭐ <Company> — 20/22 (GCC)

| Field | Details |
|---|---|
| **What they do** | … |
| **Why they're hiring** | … |
| **Headquarters** | … |
| **Office in <COUNTRY>** | … (Hybrid / Remote / Onsite) |
| **Company size** | … |
| **Engineering team** | … (estimate) |
| **Funding / revenue** | … |
| **AmbitionBox rating** | … |
| **WLB rating** | … — 🟢 / 🟡 / 🔴 (per §11) |
| **Glassdoor rating** | … |
| **CTC range (your target level)** | … (source) |
| **Tech stack** | … |
| **Stack match** | e.g. "matches your §5 core stack and messaging" — only claims backed by the profile |
| **ATS / token** | e.g. Greenhouse `examplecorp` — or "custom / paste-only" |
| **Red flags** | … or "none found" |
| **Already tracked** | id=… / no |
| **Careers page** | [link](url) |

#### Why this is a match
- 2–3 bullets that tie the company to specific profile sections (§5 stack, §1 domain, §4 location, §3 CTC).

#### Open roles (as of <DD Mon YYYY>)
- <Role> (<city>) — [Link](url)

#### Interview prep focus
- 3–4 topics from interview-experience searches for this company.

#### How to apply
- **Channel:** referral if possible (search LinkedIn for peers on the team), else direct.
- **Next step:** `/job-match <url>` on an open role.
```

**Rules:**
- The summary table lists **all** companies found, highest score first.
- Detailed profiles only for companies scoring **11+**.
- Use only data gathered in Step 4. Never make up information.

### Step 8 — Offer to update the watchlist (ask first)

For companies scoring **15+** that have a ✅ API feed (Greenhouse / Lever / Ashby / SmartRecruiters):

> These look like strong targets: <A>, <B>, <C>. Add them to your watchlist (profile §13) so `/job-feed watch` checks their boards? (y / pick some / no)

On a yes:
- Add the company names to §13 in `PROFILE_AND_FILTERS.md` with `Edit`.
- If a company's token is not in `.claude/skills/_shared/ATS_FEEDS.md`, **probe the feed URL once** (`WebFetch` the JSON). Add the row only if the probe returns a real board. Never record an unprobed token.

Never edit the profile or `ATS_FEEDS.md` without this yes.

---

## Notes

- Results are a snapshot. Hiring changes fast. Re-run every 2–4 weeks.
- Not every company will have open roles today. Some are "watch and apply when they post" — that is what the watchlist is for.
- This skill finds companies; `/job-match` judges one job; `/job-feed watch` keeps an eye on the companies you chose.
- Web search coverage is limited. This is best-effort discovery, not a full list.
- If a company looks good but has no feed, suggest searching for it on LinkedIn / Naukri / Instahyre for current openings.
