---
name: offer-compare
description: Compare job offers side by side (and against the current job). Breaks each offer into fixed pay, variable/bonus, joining and retention bonus, stock (RSU/ESOP) and benefits; shows guaranteed pay, year-1 cash, a 4-year average and an estimated monthly take-home; flags risks (bonus payout history, clawbacks, vesting cliffs, ESOP liquidity, notice terms); scores non-money factors with weights the user picks; and suggests what to negotiate. Reads offer letters (PDF/DOCX/text) or pasted numbers. Use when the user says "/offer-compare", "compare these offers", "is this offer good", "which offer should I take", or "how much hike is this".
argument-hint: <offer-letter files or "paste"> [more offers…]
allowed-tools: Read, Write, Bash, Glob, Grep, WebSearch
---

# Offer Compare

Put every offer (and the current job) on the same footing, so the user compares like with
like. A CTC number alone hides most of the difference.

**Writing style:** short, plain sentences. Show the maths. Never round a number in a way that
changes a decision.

> **Privacy:** offers are personal. Keep offer letters in `offers/` and reports in
> `reports/offers/` — both gitignored. Never copy offer figures into any tracked file.

## Step 0 — Load the baseline

Read `.claude/skills/_shared/PROFILE_AND_FILTERS.md` (if missing, stop → `/setup-profile`).
Use §3 *Current CTC* as the baseline, and §1 notice period. Ask once for the current
**fixed / variable split** if the profile has only a total — the split matters for every
comparison below.

## Step 1 — Read each offer

| Input | Read with |
|---|---|
| `.pdf` | `pdftotext -layout <file> -`, or the Read tool |
| `.docx` | `python3 -c "import zipfile,re,sys;x=zipfile.ZipFile(sys.argv[1]).read('word/document.xml').decode();print(re.sub(r'<[^>]+>',' ',x))" <file>` |
| `paste` | Ask for the numbers, then wait |

Fill this for **every** offer and for the current job. Write `?` for anything the letter does
not state — **never assume a value**.

| Component | What to capture |
|---|---|
| **Fixed** | Annual fixed pay. Note whether employer PF and gratuity are *inside* the CTC |
| **Variable / bonus** | Target amount or %, who decides it (individual / company), how often it paid out in full in past years (ask; or say unknown) |
| **Joining bonus** | Amount, when paid, **clawback** terms (repay if you leave within N months) |
| **Retention bonus** | Amount, schedule, conditions |
| **Stock** | RSU or ESOP; grant value or count; vesting schedule; cliff; refreshers. For ESOPs: strike price, last valuation, and whether there is any way to sell (buyback, listed, none) |
| **Benefits** | Health cover (self / family / parents), insurance, NPS, meal cards, WFH or other allowances, relocation |
| **Level & title** | Level, title, team, manager's level |
| **Work** | Location, work mode, on-call, joining date, notice period, probation |

## Step 2 — Normalize (per offer)

| Number | How |
|---|---|
| **Guaranteed annual** | Fixed only. Exclude employer PF / gratuity if they sit inside CTC — say how much they were |
| **Expected annual** | Fixed + variable × expected payout (100% only if history supports it; otherwise state the % used) |
| **Year-1 cash** | Expected annual + joining bonus + year-1 vested stock (RSU at grant value; ESOP at 0 unless it can be sold) |
| **4-year average** | (4 × expected annual + joining + retention + all 4 years of vested stock) ÷ 4. Assume no refreshers and no hikes; say so |
| **Hike vs current** | On guaranteed **and** on expected — both. A hike that is mostly variable is not the same as a fixed hike |
| **Monthly take-home (estimate)** | Fixed ÷ 12 minus employee PF and income tax. Use the default tax regime of the user's country for the current year. Look the slabs up with `WebSearch` if you are not sure they are current. Label it an **estimate** and suggest checking with a payroll calculator |

Show the formulas and the numbers in a table. Stock and ESOP values are the most uncertain
part — show a "stock at 0" line too, so the user sees how much the decision depends on it.

## Step 3 — Risks

Flag each one that applies, with the money at stake:

- Variable is a large share of CTC, or no payout history is known.
- Joining-bonus clawback — the amount repayable if they leave early.
- Vesting cliff (nothing vests before month 12, for example).
- ESOPs with no sale route — paper value only.
- Gratuity or employer PF counted inside CTC (inflates the headline).
- Long notice or probation terms; non-compete; bond.
- Company risk: recent layoffs or funding trouble (`WebSearch "<company> layoffs <this year>"`).
- Level is lower than the current one (a pay rise can still be a career step down).

## Step 4 — Non-money factors

Ask the user to weight these 1–5 (offer the default in brackets), then score each offer 1–5
with a one-line reason:

| Factor | Default weight |
|---|---|
| Role level & growth | 5 |
| Tech stack & learning | 4 |
| Team / manager | 4 |
| Work-life balance (§11 signals) | 4 |
| Location & work mode (§4) | 3 |
| Brand on resume | 3 |
| Job security | 3 |

Weighted score = Σ(weight × score). Show it next to the money, never merged into it.

## Step 5 — Negotiation points

For the offer the user leans to, list 2–4 concrete asks, each with a reason they can say:

- Fixed over variable or joining bonus (it compounds into every future hike).
- Match a competing offer — quote the **guaranteed** number of the other offer, not its headline.
- Joining bonus to cover a notice-period buyout or lost bonus at the current job.
- Earlier joining date, or a later one to finish notice cleanly.
- Level or title, if the scope matches the next level.

Remind the user: negotiate once, in writing, and never claim an offer they don't hold.

## Step 6 — Output

```
## Offer comparison — <date>

| | Current | <Offer A> | <Offer B> |
|---|---|---|---|
| Fixed | … | … | … |
| Variable (target) | … | … | … |
| Guaranteed annual | … | … | … |
| Expected annual | … | … | … |
| Year-1 cash | … | … | … |
| 4-year average | … | … | … |
| 4-year average (stock at 0) | … | … | … |
| Hike on guaranteed / expected | — | +x% / +y% | … |
| Est. monthly take-home | … | … | … |
| Non-money score (/max) | … | … | … |

### Risks
### Negotiation points
### My read
```

**My read:** one short paragraph — which offer is stronger and the **one** thing that would
change the answer. Find the weakest point in the user's preferred option first. The decision
stays with the user.

Then ask: `Save this to reports/offers/<YYYY-MM-DD>_<companies>.md?` and write it only on yes.
If any company is in the job tracker, offer the status update
(`python3 scripts/job_track.py set-status <id> "🎉 Offer"`).
