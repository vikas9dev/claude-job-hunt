# Resume Rules — shared by `/resume-check` and `/resume-tailor`

## Files

| What | Path |
|---|---|
| **Your profile** | `.claude/skills/_shared/PROFILE_AND_FILTERS.md` (gitignored) |
| **Master resume (HTML source)** | `resume/master.html` (gitignored) |
| Master template (placeholders) | `resume/master.template.html` |
| Tailored copies | `resume/tailored/<slug>/` → `resume.html`, `jd.txt`, `<PDF name>` (gitignored) |
| Score + render script | `scripts/resume_match.py` (`score` · `init` · `render`) |

**Before anything else:**

- No `PROFILE_AND_FILTERS.md` → stop. Tell the user to run `/setup-profile`.
- No `resume/master.html` → stop. Tell the user to copy `resume/master.template.html` to
  `resume/master.html` and fill it in (or run `/setup-profile`).

> ⛔ **Never edit the master.** Neither skill writes to `resume/master.html`. A tailored resume
> always starts with `resume_match.py init --slug <slug>`, which copies the master. Record the
> `master_sha256` that `init` prints, and check it again at the end
> (`sha256sum resume/master.html`, or
> `python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" resume/master.html`).
> If it changed, say so plainly. Changing the master is a separate task that only the user starts.

**Slug:** `<company>-<role-keyword>`, lowercase, e.g. `acme-backend`, `globex-sse`.

**PDF file name:** profile §14 *PDF file name* if set; otherwise the `pdf` path that `init`
prints (`<Name in the resume's h1> - Resume.pdf`). The recruiter sees this name, so it never
contains the company. The folder keeps the copies apart.

## Run the script

From the repo root. Use `python3` on Linux/macOS and `python` on Windows.

```bash
python3 scripts/resume_match.py score --jd <jd.txt> --resume <resume.pdf|.html> [--json]
python3 scripts/resume_match.py init  --slug <slug>            # refuses to overwrite; --force starts over
python3 scripts/resume_match.py render <resume.html> [<out.pdf>] # prints {"pdf":…, "pages":N}; exits non-zero if N > 1
```

`render` needs Chrome, Edge or Chromium. `score` on a PDF needs `pdftotext` (poppler) — or
pass the `.html` instead.

## What the score means — say this, don't over-sell it

- It is a **keyword score**, the same idea as Jobscan. It does **not** say whether the user fits the job (`/job-match` does that).
- Required terms (on a "Requirements / must" line, or named 3+ times in the JD) weigh **2**. Other terms weigh **1**.
- **~70–80% is enough.** Above that, each extra point gives very little. Never stuff keywords to chase 90%+: a person reads the resume next, and the interviewer can ask about every word on it.
- A term matches only by its own word or a spelling variant (`K8s` = `Kubernetes`). Words like `ElastiCache` for `Redis` are shown as **related evidence**, not a match, because an ATS search for "Redis" will not find "ElastiCache".
- The vocabulary is fixed, so scores compare across jobs. The script does not know every JD term. **Read the JD yourself** and list important terms it missed (domain words, named tools) in a separate "Not scored" line.

## Sorting each missing term

Check every missing term against the user's real experience, in this order:

1. The master resume (`resume/master.html`).
2. Profile §5 *Skills* — the skill tables **and** the list *Skills I have but my resume does not show*.

Put it in exactly one bucket:

| Bucket | Meaning | Action |
|---|---|---|
| ✅ **Have it, add the word** | The resume or profile §5 shows the user did this (e.g. ElastiCache → "Redis"; §5 lists DynamoDB) | Add it where it is true: a skills line, or a bullet that already describes that work |
| 🟡 **Ask first** | Possible, but no evidence (e.g. "gRPC", "Prometheus") | Ask the user. Add only on a clear yes |
| ⛔ **Don't have it, leave it out** | No evidence, and the user didn't confirm | Never add. Say it is a real gap to prepare for, not a wording problem |

When the user confirms a 🟡 term, suggest they also add it to profile §5 *Skills I have but my
resume does not show*, so the next run puts it in ✅ by itself.

## Allowed edits (on a tailored copy only)

| ✅ Allowed | ⛔ Never |
|---|---|
| Tagline under the name: use the JD's title words ("Backend Engineer", "Platform Engineer") | Job titles, company names, dates, locations |
| Summary: change at most 1–2 phrases to match the JD's main need | Any number (percentages, counts, years of experience) |
| Skills: put the JD's stack first, use the JD's spelling, add ✅-bucket terms | Skills from the ⛔ bucket, or 🟡 ones without a yes |
| Reorder bullets inside one job, so the most relevant comes first | Moving a bullet to a different job |
| Light rewording of a bullet to use the JD's word for the **same** work | Claims copied from the JD that the user did not do |
| Bold one JD keyword per bullet, at most | Removing any line listed in profile §14 *Lines that must never be removed* |

Other rules:

- **One page.** `render` must report `"pages": 1`. If it reports 2, trim the weakest bullet or skills words. Don't shrink the CSS font below 9pt.
- **Keep the HTML structure.** Edit text inside the existing tags. Leave the `<style>` block alone. The layout is single-column and ATS-safe, and must stay that way.
- **Chat report:** short, plain sentences and common words. In resume bullets keep normal resume style (an action verb first, no "I").

## Getting the JD

| Input | Do this |
|---|---|
| A file path | Read it |
| Pasted JD text | Use it as is |
| A URL | First `python3 scripts/job_track.py find "<url>" --url`. If that row has a non-empty `jd_text`, use it. If not (or `NOT FOUND`), use `WebFetch`. On a **403**, or an empty or JS-only page, stop and ask the user to paste the JD. Never guess the JD from the title |

Save the JD text to a file before scoring: `jd.txt` in the tailored folder, or in the
scratchpad for `/resume-check`. The script reads files, not arguments.
