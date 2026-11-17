---
name: resume-tailor
description: Make a one-page, ATS-safe resume tailored to one job. Takes a JD URL or the pasted JD text, copies the master resume (resume/master.html) into resume/tailored/<slug>/, adds only truthful JD keywords, reorders skills and bullets, renders the PDF, and reports the keyword score before and after. Never modifies the master resume. Use when the user says "/resume-tailor", "tailor my resume for this job", "make a resume for this JD", or pastes a JD and asks for a resume.
argument-hint: <jd-url> OR <pasted JD text>
allowed-tools: Read, Write, Edit, Bash, WebFetch, Glob, Grep
---

# Resume Tailor

Write the report in short, plain sentences with common words. Technical terms stay exact.

## Step 0 — Preconditions

1. Read **`.claude/skills/_shared/PROFILE_AND_FILTERS.md`**. If it does not exist, stop and say:
   `No profile yet. Run /setup-profile first (it copies the template and asks you a few questions).`
2. If **`resume/master.html`** does not exist, stop and say:
   `No master resume yet. Copy resume/master.template.html to resume/master.html and fill it in (or run /setup-profile).`
3. Read **[`_shared/RESUME_RULES.md`](../_shared/RESUME_RULES.md)**. It has the file paths, the
   three buckets, the allowed edits, and how to get the JD.

> ⛔ The master `resume/master.html` is **read-only** for this skill.
> Every edit goes to the copy that `init` makes.

## Input

```
/resume-tailor <jd-url>
/resume-tailor <pasted JD text>
```

If the input has both a URL and pasted text, use the text. If it has nothing, ask for the JD.

## Steps

### 1. Get the JD

Follow *Getting the JD* in RESUME_RULES. On a 403 or an empty page, stop and ask for the
pasted text. Note the company, role title, seniority and the 5–8 things the JD stresses most.

### 2. Make the copy

```bash
python3 scripts/resume_match.py init --slug <company>-<role-keyword>
```

If it says the folder exists, ask: start over (`--force`) or keep editing the existing copy?
Save the JD to `<dir>/jd.txt`. Keep the `master_sha256` and the `pdf` path it prints.

### 3. Score before

```bash
python3 scripts/resume_match.py score --jd <dir>/jd.txt --resume <dir>/resume.html --json
```

### 4. Sort the missing terms

Put each missing term in ✅ / 🟡 / ⛔ (RESUME_RULES). Also read the JD for important terms
the script doesn't score.

**If there are 🟡 terms, ask about them in one short message and wait:**

```
Before I tailor: do you have real experience with these? (yes/no each)
- gRPC — JD: "nice to have"
- Prometheus — JD: "required"
```

If there are none, go straight on.

### 5. Edit the copy

Use the *Allowed edits* table in RESUME_RULES, in this order:

1. **Tagline:** match the JD's role words, as long as they stay true.
2. **Skills:** put the JD's main stack first in each line, use the JD's spelling, and add the ✅ terms (and the 🟡 ones the user confirmed).
3. **Bullets:** in each job, move the most JD-relevant bullet to the top. Reword a bullet only to use the JD's word for the same work.
4. **Summary:** change at most 1–2 phrases toward the JD's main need.
5. **Bold:** at most one JD keyword per bullet. Keep the numbers bold.

Use the Edit tool on `<dir>/resume.html` only.

### 6. Render and check

```bash
python3 scripts/resume_match.py render <dir>/resume.html "<dir>/<PDF name>"
python3 scripts/resume_match.py score --jd <dir>/jd.txt --resume "<dir>/<PDF name>"
pdftotext -layout "<dir>/<PDF name>" - | head -30
```

`<PDF name>` comes from RESUME_RULES (*PDF file name*).

- More than 1 page → trim (RESUME_RULES) and render again.
- The `pdftotext` output must read top to bottom in the right order.
- Check that the master's hash still equals `master_sha256`.
- Also run `pdftoppm -png -r 80 "<dir>/<PDF name>" <scratchpad>/tailor_preview` and look at the image. Fix anything that looks broken.
- If `pdftotext` / `pdftoppm` are not installed (poppler), score the `.html` instead and say the visual check was skipped.

### 7. Report (final message)

```
## Tailored resume — <Company>, <Role>

**Keyword score: NN% → MM%**

**Changes**
- Tagline: "<old>" → "<new>"
- Skills: added Redis, DynamoDB; moved Kafka first
- First job: bullet 3 moved to the top
- …

**Left out (no real experience):** Cassandra, Golang. These are real gaps, so prepare for them if they come up.
**Not scored but in the JD:** …

📄 PDF: [<PDF name>](<dir link>) · 1 page
📝 Source: [resume.html](<dir link>)
Master resume: unchanged ✅
```

Use repo-relative markdown links, with spaces in file names encoded as `%20`.
If the score was already above ~80% before you started, say so — often only the tagline and
the skill order need to change.
