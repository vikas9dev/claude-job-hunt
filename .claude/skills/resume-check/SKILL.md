---
name: resume-check
description: Score a resume against a job description (keyword match %, same idea as Jobscan), sort every missing keyword into "have it, add the word" / "ask first" / "don't have it", and offer to make an updated resume. Takes a JD (file path, URL or pasted text) and an optional resume path (.pdf or .html; defaults to resume/master.html). Never edits the master resume — an update always goes into a tailored copy. Use when the user says "/resume-check", "score my resume against this JD", "resume match score", or "how well does my resume match this job".
argument-hint: <jd-file | jd-url | "paste"> [resume.pdf|resume.html]
allowed-tools: Read, Write, Edit, Bash, WebFetch, Glob, Grep
---

# Resume Check

Write the report in short, plain sentences with common words. Technical terms stay exact.

## Step 0 — Preconditions

1. Read **`.claude/skills/_shared/PROFILE_AND_FILTERS.md`**. If it does not exist, stop and say:
   `No profile yet. Run /setup-profile first (it copies the template and asks you a few questions).`
2. Read **[`_shared/RESUME_RULES.md`](../_shared/RESUME_RULES.md)**. It has the file paths, what
   the score means, the three buckets, the allowed edits, and how to get the JD.

## Input

```
/resume-check <jd> [<resume-path>]
```

- `<jd>`: a file path, a URL, or `paste` (then ask for the JD text and wait for it).
  If the message has JD text as well as a path, use the pasted text.
- `<resume-path>`: `.pdf` or `.html`. **If it is missing, use `resume/master.html`** and say so
  in one line. If `resume/master.html` does not exist either, stop and tell the user to copy
  `resume/master.template.html` to `resume/master.html` and fill it in (or run `/setup-profile`).

## Steps

### 1. Get the JD and save it

Follow *Getting the JD* in RESUME_RULES. Save the text to `<scratchpad>/resume-check/jd.txt`.
From the JD, note the company, role title and seniority.

### 2. Score

```bash
python3 scripts/resume_match.py score --jd <jd.txt> --resume "<resume-path>" --json
```

### 3. Judge it yourself

The script counts words. You add the judgment:

1. **Sort every missing term** into ✅ / 🟡 / ⛔ (RESUME_RULES → *Sorting each missing term*). Use `related_evidence` as a hint for ✅.
2. **Not scored:** read the JD and list important words the script doesn't know (domain words, named tools, "ledger", "SRE"). Keep it to 8 at most.
3. **Title and seniority:** compare the JD title and years with the resume's tagline and summary, and with profile §2 *Target band*. Flag a gap (e.g. the JD asks for 8+ years, or says "Staff").
4. **ATS form:** if the input is a PDF, run `pdftotext -layout <file> - | head -40`. If two columns are mixed on the same lines, say the layout is not ATS-safe and point to `resume/master.template.html` as a safe layout.

### 4. Report (final message)

```
## Resume check — <Company>, <Role>

**Keyword score: NN%** (X of Y JD terms). Good enough above ~70–80%.

| Term | JD | In resume | Bucket |
|---|---|---|---|
| Redis | required | ❌ (has ElastiCache) | ✅ add the word |
| gRPC | nice to have | ❌ | 🟡 ask first |
| Cassandra | nice to have | ❌ | ⛔ leave out |
…only the missing terms and the "as:" matches, not every ✅ term…

**Not scored but in the JD:** …
**Title / seniority:** …
**Estimated score after ✅ edits:** ~NN%. Rough: add the weight of the ✅ terms; say it is an estimate.

Do you want an updated resume? I'll add the ✅ words and only the 🟡 words you confirm.
For the 🟡 ones, tell me: gRPC yes/no, …
```

Stop here and wait. **Don't make changes before the user says yes.**

### 5. If the user says yes, update

- **Input was the master (HTML), or any PDF:** never edit it. Run
  `python3 scripts/resume_match.py init --slug <company>-<role>` and edit the copy. A PDF can't be
  edited; the copy always comes from `resume/master.html`. If the input PDF was *not* built from
  the master, say that the new copy is based on the master.
- **Input was already a tailored copy** (`resume/tailored/<slug>/resume.html`): edit that file in place.

Make only the edits allowed by RESUME_RULES. Then:

```bash
python3 scripts/resume_match.py render <copy.html> "<dir>/<PDF name>"
python3 scripts/resume_match.py score --jd <jd.txt> --resume <copy.html>
```

`<PDF name>` comes from RESUME_RULES (*PDF file name*). Copy `jd.txt` into the tailored folder
too. Check the master's hash again (RESUME_RULES).

Final message: the before → after score, a short list of every change (old → new for
reworded lines), the ⛔ terms you left out and why, the page count, and links to the
new PDF and HTML (repo-relative markdown links, spaces encoded as `%20`).
