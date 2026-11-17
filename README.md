# 🎯 claude-job-hunt

**Claude Code skills for a software-engineering job search** — from finding roles to choosing
an offer.

Find fresh listings, score each one against *your* profile, research the company, tailor your
resume to the JD, learn from every interview, and compare offers. A small local page tracks it
all.

```
 /job-feed ──▶ /job-match ──▶ /resume-tailor ──▶ apply ──▶ /interview-debrief ──▶ /offer-compare
  find roles    score + research   one-page resume          learn from each round    pick the best offer
                         └──────────── tracker page: python3 ui/server.py ────────────┘
```

Everything personal (your profile, resume, tracker, interview log, offers) stays in
**gitignored** files on your machine 🔒. `git pull` updates never conflict with your data.

---

## 🧰 Skills

| Skill | What it does |
|---|---|
| 👤 `/setup-profile` | **Run this first.** Reads your current resume, asks a few questions, writes your private profile. Can also build your one-page master resume from the template |
| 🧲 `/job-feed` | Pulls 50–100 fresh listings (JobSpy) or checks your target companies' own career feeds. Filters them **without** web searches and parks a ranked shortlist in the tracker. `/job-feed pipeline` clears old parked rows |
| ⚖️ `/job-match <url>` | Scores a job out of 14 against your profile. Researches the company (salary, reviews, layoffs, interview experiences) and gives **Apply / Maybe / Practice / Skip**. Writes a ready-to-send referral message when a role is worth one |
| 🔭 `/discover-companies` | Finds companies that are expanding, newly funded or opening offices, and that pass your filters. Writes a report to `reports/` |
| 📊 `/resume-check <jd> <resume>` | Keyword match % (like Jobscan). Sorts each missing word into "have it, add it" / "ask first" / "don't have it" |
| ✂️ `/resume-tailor <jd>` | Makes a tailored copy of your master resume for one JD and renders a one-page PDF. Shows the score before and after. Never edits the master |
| 📝 `/interview-debrief` | Right after an interview: logs the questions, your answers, better answers and lessons. Repeated mistakes are counted and ranked. `lessons` lists the top ones; `prep <company>` briefs you before the next round |
| 🔥 `/grill-me` | Questions you hard on a design or plan, one question at a time. Works as a system-design or project-deep-dive mock interview |
| 💰 `/offer-compare` | Puts offers side by side: guaranteed vs expected pay, year-1 cash, 4-year average, take-home estimate. Also covers risks (clawbacks, vesting, ESOPs), non-money factors and what to negotiate |

## 📋 Tracker page

```bash
python3 ui/server.py            # your data   → http://127.0.0.1:8765
python3 ui/server.py --demo     # sample data  (a temp copy — nothing is saved)
```

- 💼 **Jobs:** funnel (applied → responses → interviews → offers), filters, search. Change a
  status, add notes, archive, add a job by hand, and read the full `/job-match` analysis.
- 🎤 **Interviews:** lessons ranked by how often they repeat, the topics you miss most, and
  every round with your answer next to the better one.

It runs only on your machine (`127.0.0.1`), uses no external resources, and needs no installs.

---

## ⚙️ Requirements

| Need | For |
|---|---|
| [Claude Code](https://docs.claude.com/en/docs/claude-code) | All skills |
| Python 3.10+ (standard library only) | Tracker, interview log, resume scoring, UI |
| Google Chrome / Chromium / Edge | Rendering the resume PDF |
| `pdftotext` (poppler) | Reading PDF resumes and offer letters. Ubuntu: `sudo apt install poppler-utils` · macOS: `brew install poppler` |
| Node.js 18+ and Docker | **Optional** — only for JobSpy bulk search in `/job-feed` |

## 🚀 Setup (about 10 minutes)

```bash
git clone <this-repo-url> claude-job-hunt
cd claude-job-hunt
python3 ui/server.py --demo     # optional: see what you'll get
claude                          # start Claude Code here
```

In Claude Code:

```
/setup-profile path/to/your-current-resume.pdf
```

This creates two private files:

- `.claude/skills/_shared/PROFILE_AND_FILTERS.md` — your profile;
- `resume/master.html` — your one-page master resume, if you say yes.

See [`examples/PROFILE_EXAMPLE.md`](examples/PROFILE_EXAMPLE.md) for a filled-in profile of a
made-up person. To set up by hand instead:

```bash
cp .claude/skills/_shared/PROFILE_AND_FILTERS.template.md .claude/skills/_shared/PROFILE_AND_FILTERS.md
cp resume/master.template.html resume/master.html
# then replace every <<…>> placeholder
```

🐳 **Optional — JobSpy bulk search:**

```bash
bash scripts/setup_mcp.sh       # needs Node.js and a running Docker
```

Restart Claude Code and approve the `jobspy` server. Without it, everything else still works,
including `/job-feed watch` (company career feeds).

---

## 🗓️ A normal week

```
/job-feed dry-run               # what's new? nothing is written
/job-feed go                    # park the shortlist as ⏳ Pipeline
/job-feed watch                 # check your target companies' own career feeds
/job-match <url>                # deep-score the best ones → 📝 To Do
/resume-tailor <url>            # one-page resume for each one you apply to
python3 ui/server.py            # mark ✅ Applied; update as replies come in
/interview-debrief              # right after each interview
/interview-debrief prep <co>    # the day before the next one
/job-feed pipeline              # clear stale parked rows
/job-match stats                # your funnel
```

## 🧭 Your profile drives everything

Target levels, CTC floor and target, locations, stack, role families, search terms, keyword
scores, outreach hooks, company tiers, watchlist: change a value in your profile, and every
skill uses it on the next run. To update one part, run `/setup-profile §3` (any section).

After about 30 applications, run `/job-match stats` and copy your real response rates per tier
into §12 *Tier calibration*. From then on, scoring follows your own data instead of the defaults.

## 🔒 Where your data lives (all gitignored)

```
.claude/skills/_shared/PROFILE_AND_FILTERS.md   your profile
resume/master.html                              your master resume
resume/tailored/<company-role>/                 tailored copies, PDFs and the JD
data/jobs_data.json                             the job tracker
data/interviews_data.json                       the interview log
offers/                                         offer letters
reports/                                        discovery and offer reports
```

Back these up yourself, for example to a private repo or a cloud folder.

## 📁 Repo layout

```
.claude/skills/          the skills (one folder each) + _shared/ rules and templates
scripts/                 job_track.py · interview_track.py · resume_match.py · setup_mcp.sh · tests/
ui/                      server.py + index.html (the tracker page)
resume/                  master.template.html
examples/                fictional profile + demo data
```

## 🪟 Windows

- Use `python` instead of `python3`.
- `scripts/setup_mcp.sh` needs Git Bash or WSL.

## 🧪 Tests

```bash
cd scripts && python3 -m unittest discover -s tests -t . -v
```

## 🤝 Contributing

Pull requests are welcome, especially new verified board tokens in
[`ATS_FEEDS.md`](.claude/skills/_shared/ATS_FEEDS.md). Keep every example fictional: no real
personal data in any tracked file.

## ⚠️ Disclaimer

The skills give advice; the decisions are yours. Salary and review data come from public sites
and can be out of date. Check anything important yourself, and never put a skill on your
resume that you don't have.

## 📄 License

[MIT](LICENSE)
