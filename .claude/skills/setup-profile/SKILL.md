---
name: setup-profile
description: First-run setup. Creates the user's private PROFILE_AND_FILTERS.md from the template by reading their existing resume (PDF, DOCX, HTML or text) and asking only for what the resume can't tell (target CTC, locations, target level, search terms). Can also build resume/master.html — the ATS-safe, one-page HTML resume the resume skills edit — from the same resume. Re-run any time to update one section. Use when the user says "/setup-profile", "set up my profile", "create my profile", or when another skill reports the profile is missing.
argument-hint: [path-to-your-current-resume] [section to update, e.g. "§3"]
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# Setup Profile

Make the two private files every other skill needs:

| File | From | Gitignored |
|---|---|---|
| `.claude/skills/_shared/PROFILE_AND_FILTERS.md` | `PROFILE_AND_FILTERS.template.md` | yes |
| `resume/master.html` (optional) | `resume/master.template.html` | yes |

**Writing style:** short, plain sentences. Ask few questions, in small groups.

> **Privacy:** these files hold personal data (CTC, notice period, contact details). They are
> gitignored. Never copy their contents into any tracked file, commit message or skill.
> Before finishing, run `git status --short` and confirm neither file is listed as tracked
> or staged.

---

## Step 1 — Check what exists

```bash
ls .claude/skills/_shared/PROFILE_AND_FILTERS.md resume/master.html 2>/dev/null
```

- **Profile exists and the user named a section** (e.g. `§3`): update only that section (Step 4)
  and stop.
- **Profile exists, no section named:** show which sections still have `<<…>>` placeholders and
  ask which to fill. Never overwrite the whole file without asking.
- **No profile:** full setup (Step 2 onward).

## Step 2 — Read the current resume (if given)

Ask for the path if the user didn't give one: `Do you have a current resume file I can read?
(PDF / DOCX / HTML / TXT path — or "no")`.

| Type | Read with |
|---|---|
| `.pdf` | `pdftotext -layout <file> -` (poppler). If missing, use the Read tool on the PDF |
| `.docx` | `python3 -c "import zipfile,re,sys;x=zipfile.ZipFile(sys.argv[1]).read('word/document.xml').decode();print(re.sub(r'<[^>]+>',' ',x))" <file>` |
| `.html` / `.txt` / `.md` | Read tool |

From it, draft: name, current role + company, YOE (from the earliest job date to today), domain,
certifications, a one-line pitch, all of §5 Skills, and a first guess at §6 role families and
§2 target levels. **Only things the resume shows.** Don't invent.

## Step 3 — Ask for the rest

Ask in **three short groups**, waiting for each answer. Offer the drafted values as defaults
the user can accept with "ok".

1. **Target:** target levels; levels that are a stretch; levels to skip (above / below);
   YOE gate; role families in and out of scope.
2. **Money and place:** current CTC; Floor; Target; hard CTC gate (yes when they hold an offer
   already); unit (`LPA` etc.); preferred and acceptable locations; country; work-mode
   preference; notice period.
3. **Search and outreach:** 2–3 JobSpy search terms and sites (suggest them from the stack);
   watchlist companies (suggest a few from `ATS_FEEDS.md` that fit the stack); 2–4 outreach
   hooks — real, short achievements tied to a JD signal (suggest them from resume bullets,
   and ask the user to confirm each one is true and safe to say).

Fill §8 *Keyword pre-score* from §5: primary language +3, main framework +2, then +1 each for
the next most important skills and the domain. Keep the default negative rows and set the
"different primary language" row from §5.

Leave §10 filters, §11 WLB and the §12 tier table at their defaults unless the user wants
changes. Ask once whether the example companies in §12 fit their market. Leave §12
*Tier calibration* empty — it is filled from real data later.

## Step 4 — Write the profile

```bash
cp .claude/skills/_shared/PROFILE_AND_FILTERS.template.md .claude/skills/_shared/PROFILE_AND_FILTERS.md
```

Then Edit the copy section by section. Keep every `## N.` heading exactly as it is — the other
skills find sections by these headings. Remove the "How to use this file" block at the top.
Replace the title placeholder with the user's name.

At the end, grep the file for `<<` and list any placeholder left, with its section.

## Step 5 — Master resume (optional)

Ask: `Shall I build resume/master.html from your resume? The /resume-check and /resume-tailor
skills edit copies of it.`

On yes:

1. `cp resume/master.template.html resume/master.html`
2. Replace the placeholder text with the user's real content. Keep the HTML structure and the
   `<style>` block as they are. Edit text inside the existing tags; add or remove whole `.job`
   blocks or `<li>` items as needed.
3. Copy facts exactly — titles, company names, dates, numbers. Don't improve or inflate any
   claim. Bullets start with an action verb; bold the key number in each bullet.
4. Render and check it fits one page:
   ```bash
   python3 scripts/resume_match.py render resume/master.html "resume/<PDF file name from §14>"
   ```
   If it reports more than 1 page, ask the user which bullets to cut. Don't shrink the font
   below 9pt.
5. Look at the PDF text (`pdftotext -layout <pdf> - | head -40`) to confirm it reads top to
   bottom in order.

## Step 6 — Finish

```bash
git status --short
```

Neither private file may appear as staged or tracked. Then tell the user:

- which sections are filled and which still have placeholders;
- next steps: `/job-feed dry-run` to find roles, `/job-match <url>` to score one,
  `/resume-check <jd> resume/master.html` to score the resume, and
  `python3 ui/server.py` for the tracker page.
