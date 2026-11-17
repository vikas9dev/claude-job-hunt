# Tracker Rules — shared by every job skill

> The tracker store is **`data/jobs_data.json`**. Write it **only** through
> `scripts/job_track.py` (or the tracker UI, which uses the same code). Never Read or Edit the
> JSON by hand, and never create a second tracker file.
>
> The status list below is enforced in `scripts/job_track.py` (`ACTIVE_LADDER`,
> `TERMINAL_STATUSES`). If you change one, change the other in the same commit.

Run the script from the repo root. Use `python3` on Linux/macOS and `python` on Windows.

---

## Status enum

Use only these exact strings — no extra notes, no dates.

### Active statuses (ordered — the ladder)

`set-status` refuses to move a job **down** this ladder unless you pass `--force`.

| Status | Meaning |
|---|---|
| `⏳ Pipeline` | Parked by `/job-feed`, not analyzed yet |
| `📝 To Do` | Analyzed by `/job-match`, worth applying, not sent yet |
| `✅ Applied` | Application sent, waiting |
| `📋 Form Pending` | Screening form received, not sent |
| `📋 Form Submitted` | Screening form sent, waiting for shortlist |
| `🔄 Referral Pending` | Referral asked for, not confirmed |
| `🔄 Assessment Sent` | Assessment link received, not attempted |
| `🔄 Assessment Submitted` | Assessment done, waiting for result |
| `📞 Interview Scheduled` | Call / interview has a date |
| `🔄 Round 1` | In round 1 |
| `🔄 Round 2` | In round 2 |
| `🔄 Final Round` | In the final round |
| `🤝 Pre-offer` | All rounds cleared — HR / offer talk, no written offer yet |
| `🚫 No Response` | 30+ days since applying and nothing heard. Can move back up if they reply |

### Terminal statuses

| Status | Meaning |
|---|---|
| `—` | Never applied |
| `⏭️ Skipped` | Decided not to pursue |
| `⏭️ Declined` | You withdrew |
| `⚠️ JD Expired` | Role closed |
| `❌ Rejected` | Company said no |
| `❌ Failed Assessment` | Assessment not passed |
| `🎉 Offer` | Offer received (never auto-archived) |
| `🎉 Accepted` | Offer accepted |

---

## Verdict values (`/job-match`)

Exactly one of: `✅ Apply` · `🟡 Maybe` · `⚠️ Practice` · `❌ Skip` · `⏳ Pending` (parked, not analyzed).

## Apply-via values (`/job-match`)

`🎯 Aggressive Push` · `🤝 Referral First` · `📝 Direct Apply` · `⏩ Low Priority` · `❌ Skip` · `⏳ Pending`.

## Priority buckets

| Priority | Tier | Purpose |
|---|---|---|
| `Dream` | Tier-1 / GCC | Main targets — use referrals |
| `Real` | Tier-2 | Real targets |
| `Practice` | Tier-3 / Startup | Interview practice, market check |

Your profile (§12 *Tiers in scope right now*) decides which buckets you actually pursue.

---

## Channel enum

`channel` records **where the JD was found**. It is not how you apply (that is `apply_via`).

| Value | Use when |
|---|---|
| `Careers` | Company's own careers page / ATS (add the ATS: `Careers (Greenhouse)`) |
| `LinkedIn` | LinkedIn job post |
| `Naukri` · `Instahyre` · `Indeed` · `Cutshort` | That job board |
| `JobSpy` | Bulk pull by `/job-feed` (JobSpy MCP) |
| `Watchlist` | `/job-feed watch` — a company's own ATS feed |
| `Referral` | Came through a person (add the name: `Referral (Asha)`) |
| `Recruiter` | A recruiter contacted you (add the name) |
| `Pasted JD` | You pasted the JD and there was no URL |

`upsert` never changes `channel`, `date` or `status` on an existing row. So `channel`
always means "where I found it", even after you apply somewhere else.

---

## Archiving

The tracker UI has an **Archive** button, and the CLI has `job_track.py archive`. Both use the
same rule (`archive_eligible` in `job_track.py`):

- Archive at once: `❌ Rejected`, `❌ Failed Assessment`, `⏭️ Skipped`, `⏭️ Declined`, `⚠️ JD Expired`, `🎉 Accepted`.
- Archive a `❌ Skip` verdict that was never applied (`—`).
- Never archive: `⏳ Pipeline`, `📝 To Do`, `🔄 Referral Pending`, any assessment, interview or round status, `🤝 Pre-offer`, `🎉 Offer`.
- Anything else older than 30 days.

`job_track.py unarchive <id>` brings a row back.

---

## Data sources for company research

| Source | What to check | Search |
|---|---|---|
| **AmbitionBox** | Ratings, salary, WLB, reviews | `<company> AmbitionBox` |
| **Glassdoor** | Ratings, interview experiences, salary | `<company> Glassdoor India` |
| **levels.fyi** | Level-wise pay | `<company> salary levels.fyi India` |
| **Crunchbase** | Funding, employee count | `<company> Crunchbase` |
| **LinkedIn** | Employee count, recent hires | `<company> LinkedIn` |
| **Inc42 / YourStory** | Funding news, India expansion | `<company> funding <year> Inc42` |
| **LeetCode Discuss / GeeksforGeeks** | Interview experiences | `<company> SDE interview experience` |

Salary data from these sites can be old. Treat it as a direction, not a fact.
