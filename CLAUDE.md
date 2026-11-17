# claude-job-hunt — rules for Claude

Claude Code skills for a job search: find roles, score them, research companies, tailor a
resume, debrief interviews, compare offers, and track every application.

## Privacy — this repo is public

Personal data lives only in gitignored files:

| File / folder | Holds |
|---|---|
| `.claude/skills/_shared/PROFILE_AND_FILTERS.md` | The user's profile, CTC, targets |
| `resume/master.html`, `resume/tailored/` | Resumes |
| `data/jobs_data.json`, `data/interviews_data.json` | The job tracker and the interview log |
| `offers/` | Offer letters |
| `reports/` | Discovery and offer reports |

- **Never** copy content from these files into a tracked file (skills, templates, docs, tests,
  commit messages).
- Before any commit, run `git status --short` and check none of them is staged.
- Examples in tracked files use made-up names (Acme, Globex) or placeholders (`<<…>>`).

## Where things are

| Path | What |
|---|---|
| `.claude/skills/<name>/SKILL.md` | The skills: `setup-profile`, `job-feed`, `job-match`, `discover-companies`, `resume-check`, `resume-tailor`, `interview-debrief`, `grill-me`, `offer-compare` |
| `.claude/skills/_shared/PROFILE_AND_FILTERS.template.md` | Profile template — the real file is a gitignored copy |
| `.claude/skills/_shared/TRACKER_RULES.md` | Status / verdict / channel values, archive rule |
| `.claude/skills/_shared/RESUME_RULES.md` | What the resume skills may and may not change |
| `.claude/skills/_shared/ATS_FEEDS.md` | Public registry of company career-feed tokens |
| `scripts/job_track.py` | The **only** write path for `data/jobs_data.json` |
| `scripts/interview_track.py` | The **only** write path for `data/interviews_data.json` |
| `scripts/resume_match.py` | Keyword score, tailored-copy `init`, PDF `render` |
| `ui/server.py` + `ui/index.html` | Local tracker page (stdlib only) |
| `scripts/setup_mcp.sh` | Installs the JobSpy MCP server |
| `examples/` | Fictional example profile + demo data (`ui/server.py --demo`) — keep it fictional |

## Rules

- **The profile is read at run time.** Skills reference sections as `§N`. Never paste profile
  values into a skill. If the profile is missing, tell the user to run `/setup-profile`.
- **Tracker writes go through `scripts/job_track.py`** (or the UI, which imports it). Never
  Read or Edit `data/jobs_data.json` directly.
- The status list is defined twice: `TRACKER_RULES.md` and `job_track.py`
  (`ACTIVE_LADDER`, `TERMINAL_STATUSES`). Change both together.
- **The master resume is read-only for the resume skills.** They work on copies made by
  `resume_match.py init`.
- Never add a skill, a word, or a claim to a resume that the user has not confirmed is true.
- Interview logs record the interviewer's **role** only, never a name. Paraphrase questions;
  log only the topic when the user is under an NDA.
- Offer numbers stay in `offers/` and `reports/`. Never copy them anywhere else.
- Run scripts from the repo root: `python3 …` on Linux/macOS, `python …` on Windows.

## Tests

```bash
cd scripts && python3 -m unittest discover -s tests -t . -v
```

## Writing style

Short sentences, common words, no idioms. Technical terms stay exact. Many users read
English as a second language.
