#!/usr/bin/env python3
"""
job_track.py — CLI for data/jobs_data.json, the job-application tracker.

Used by the /job-match and /job-feed skills and by the tracker UI (ui/server.py).
The script owns the mechanical rules so skills don't have to:
  - company normalization (company_key) + dedup-or-fail on add
  - date/channel/status preservation on upsert
  - status enum validation + never-downgrade ladder + status_history append
  - score parsing, archive eligibility

Commands:
  find <query> [--url] [--id N] [--role "…"] [--include-archived]
  list [--json] [--archived|--all] [--status-group active|terminal] [--fields a,b,c]
  dedup  < [{"company": "…", "url": "…"}, …]     (batch, URL-first — /job-feed)
  add    (field flags or --stdin-json) [--force-new]
  upsert (field flags or --stdin-json) [--id N]
  set-status <id-or-company> "<status>" [--date YYYY-MM-DD] [--force]
  archive [<id>] [--eligible] [--dry-run]
  unarchive <id>
  stats [--month YYYY-MM]

All writes are atomic (temp file + rename) and held under a lockfile shared with
the UI. `--stdin-json` reads a JSON object of fields from stdin — use it for long
prose instead of fighting shell quoting.

Set JOB_HUNT_DATA_DIR to point at another data folder (the tests do this).
"""

import argparse
import contextlib
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import console_utf8  # noqa: F401  (side effect: UTF-8 console on Windows)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("JOB_HUNT_DATA_DIR") or (REPO_ROOT / "data"))
JOBS_DATA = DATA_DIR / "jobs_data.json"
JOBS_LOCK = DATA_DIR / ".jobs.lock"
_LOCK_STALE_S = 15   # a holder older than this has crashed → steal it
_LOCK_TIMEOUT_S = 5  # give up acquiring after this


class JobTrackError(Exception):
    """A rule was broken (bad status, downgrade, unknown id). The CLI turns it
    into exit 1; the UI turns it into an HTTP 400."""


@contextlib.contextmanager
def jobs_lock():
    """Cross-process lockfile held across every read-modify-write (CLI + UI)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + _LOCK_TIMEOUT_S
    while True:
        try:
            fd = os.open(str(JOBS_LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {time.time()}\n".encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(str(JOBS_LOCK)) > _LOCK_STALE_S:
                    os.unlink(str(JOBS_LOCK))
                    continue
            except OSError:
                continue
            if time.time() >= deadline:
                raise TimeoutError("jobs store is locked by another writer — retry in a moment")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            os.unlink(str(JOBS_LOCK))
        except OSError:
            pass


def _load_json(path: Path, fallback: dict) -> dict:
    """Missing file → fallback. A file that exists but can't be parsed is FATAL:
    returning the fallback would let the next save wipe the real data."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback
    except (json.JSONDecodeError, OSError) as e:
        raise SystemExit(f"FATAL: could not read {path} — {e}. Fix or restore it before retrying.")


def _save_json_atomic(path: Path, data: dict):
    """Temp file + os.replace. newline="" keeps LF on Windows too."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, str(path))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise

# ── Status enum ──────────────────────────────────────────────────────────────
# Documented in .claude/skills/_shared/TRACKER_RULES.md §Status enum — change both together.
# ACTIVE_LADDER is ordered: set-status refuses to move a job to a LOWER rung
# without --force (🚫 No Response is the exception in both directions — a late
# reply legitimately moves a job from No Response back into the pipeline).
ACTIVE_LADDER = [
    "⏳ Pipeline",
    "📝 To Do",
    "✅ Applied",
    "📋 Form Pending",
    "📋 Form Submitted",
    "🔄 Referral Pending",
    "🔄 Assessment Sent",
    "🔄 Assessment Submitted",
    "📞 Interview Scheduled",
    "🔄 Round 1",
    "🔄 Round 2",
    "🔄 Final Round",
    "🤝 Pre-offer",
]
NO_RESPONSE = "🚫 No Response"
ACTIVE_STATUSES = ACTIVE_LADDER + [NO_RESPONSE]

TERMINAL_STATUSES = [
    "—",
    "⏭️ Skipped",
    "⏭️ Declined",
    "⚠️ JD Expired",
    "❌ Rejected",
    "❌ Failed Assessment",
    "🎉 Offer",       # terminal, but NEVER auto-archived
    "🎉 Accepted",
]
ALL_STATUSES = ACTIVE_STATUSES + TERMINAL_STATUSES

# Archive rule — shared by `archive` and the UI's Archive button.
IMMEDIATE_ARCHIVE = {"❌ Rejected", "❌ Failed Assessment", "⏭️ Skipped", "⏭️ Declined",
                     "⚠️ JD Expired", "🎉 Accepted"}
NEVER_ARCHIVE = {"⏳ Pipeline", "📝 To Do", "🔄 Round 1", "🔄 Round 2", "🔄 Final Round",
                 "🔄 Assessment Sent", "🔄 Assessment Submitted", "🔄 Referral Pending",
                 "📞 Interview Scheduled", "🤝 Pre-offer", "🎉 Offer"}
ARCHIVE_AFTER_DAYS = 30

# Funnel classification. "Applied" = an application actually went out;
# "response" = the company reacted.
NOT_APPLIED = {"—", "⏳ Pipeline", "📝 To Do", "⏭️ Skipped", "⚠️ JD Expired"}
NO_RESPONSE_YET = {"✅ Applied", NO_RESPONSE}
INTERVIEW_SET = {"📞 Interview Scheduled", "🔄 Round 1", "🔄 Round 2",
                 "🔄 Final Round", "🔄 Assessment Sent", "🔄 Assessment Submitted",
                 "🤝 Pre-offer"}
OFFER_SET = {"🎉 Offer", "🎉 Accepted"}

ANALYSIS_FIELDS = ("role", "tier", "yoe", "tech_stack", "location", "ctc",
                   "score", "verdict", "apply_via", "priority",
                   "recommendation", "analysis_md", "urls", "url_note",
                   # posted_date = when the COMPANY posted the req (not when we
                   # analyzed it — that's `date`). Drives the staleness cap in
                   # /job-match. jd_text = the JD cached by /job-feed at Stage 0
                   # so /job-match can skip WebFetch (and its 403 path) entirely.
                   "posted_date", "jd_text")
ALL_INPUT_FIELDS = ("company", "date", "channel", "status") + ANALYSIS_FIELDS

# Dedup identity = THE URL, nothing else (see .claude/skills/job-feed/SKILL.md
# Step 3 — "Dedup"). A company runs many reqs concurrently and you can legitimately apply
# to several — including while an interview loop is already running there — so
# the company never suppresses a listing. Two job ids are two jobs.
#
# RECENT_CONTACT_DAYS is therefore NOT a filter. It only decides when to FLAG a
# surviving listing as "you heard from these people recently" so a re-apply is a
# considered choice. Tune per-run with
# `dedup --cooloff-days N`; `dedup --explain` shows how many rows it flags.
RECENT_CONTACT_DAYS = 15

# Back-compat alias: the old name meant "days a dead end blocks its company",
# which is no longer a behaviour that exists.
STALE_COMPANY_DAYS = RECENT_CONTACT_DAYS

_STRIP_WORDS = {"india", "gcc", "inc", "inc.", "ltd", "ltd.", "technologies",
                "solutions", "pvt", "pvt.", "private", "limited"}


def today() -> str:
    """Local calendar date, YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def normalize_company(name: str) -> str:
    """Dedup key: lowercase, parentheticals dropped, filler suffix words stripped.

    This is the match rule for find/add/upsert across every skill and the UI.
    Skills must call the script, never re-derive this rule themselves.
    """
    s = (name or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^\w&+.-]+", " ", s)
    words = [w for w in s.split() if w not in _STRIP_WORDS]
    return " ".join(words)


def parse_score(raw) -> dict:
    """'12/14' | '— (HF capped)' | '?' → {value, max, capped, raw}."""
    if isinstance(raw, dict):        # already parsed (stdin-json round-trip)
        return raw
    raw = (str(raw) if raw is not None else "?").strip() or "?"
    m = re.search(r"(\d+)\s*/\s*(\d+)", raw)
    return {
        "value": int(m.group(1)) if m else None,
        "max": int(m.group(2)) if m else 14,
        "capped": "capped" in raw.lower(),
        "raw": raw,
    }


def norm_urls(urls) -> list:
    """Accept ["https://…", {"label","url"}] → [{"label","url"}]."""
    out = []
    for u in urls or []:
        if isinstance(u, str):
            out.append({"label": "Link", "url": u})
        else:
            out.append({"label": u.get("label") or "Link", "url": u["url"]})
    return out


def validate_status(status: str) -> str:
    status = status.strip()
    if status not in ALL_STATUSES:
        sys.exit(f"ERROR: unknown status {status!r} — must be one of the enum in "
                 f".claude/skills/_shared/TRACKER_RULES.md:\n  "
                 + "\n  ".join(ALL_STATUSES))
    return status


def validate_date(date_str: str) -> str:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        sys.exit(f"ERROR: date must be YYYY-MM-DD — got {date_str!r}")
    return date_str


def load() -> dict:
    return _load_json(JOBS_DATA, {"version": 1, "jobs": []})


def save(data: dict):
    _save_json_atomic(JOBS_DATA, data)


def dump(job: dict):
    print(json.dumps(job, ensure_ascii=False, indent=2))


def find_matches(jobs, query=None, url=None, job_id=None, role=None,
                 include_archived=False):
    pool = jobs if include_archived else [j for j in jobs if not j.get("archived")]
    if job_id is not None:
        return [j for j in pool if j["id"] == job_id]
    if url is not None:
        return [j for j in pool if any(u["url"] == url for u in j.get("urls", []))]
    key = normalize_company(query)
    exact = [j for j in pool if j.get("company_key") == key]
    matches = exact or [j for j in pool if key and key in j.get("company_key", "")]
    if role is not None:
        matches = [j for j in matches if j.get("role", "").strip().lower() == role.strip().lower()]
    return matches


def read_input_fields(args) -> dict:
    """Merge --stdin-json (if any) with explicit flags (flags win)."""
    fields = {}
    if getattr(args, "stdin_json", False):
        try:
            # lstrip BOM: PowerShell pipes prepend U+FEFF on Windows
            fields = json.loads(sys.stdin.read().lstrip("\ufeff"))
        except json.JSONDecodeError as e:
            sys.exit(f"ERROR: --stdin-json is not valid JSON — {e}")
        if not isinstance(fields, dict):
            sys.exit("ERROR: --stdin-json must be a JSON object")
        unknown = set(fields) - set(ALL_INPUT_FIELDS)
        if unknown:
            sys.exit(f"ERROR: unknown field(s) in --stdin-json: {', '.join(sorted(unknown))}\n"
                     f"  allowed: {', '.join(ALL_INPUT_FIELDS)}")
    for f in ALL_INPUT_FIELDS:
        flag = getattr(args, f, None)
        if flag is not None:
            fields[f] = flag
    if "urls" in fields:
        fields["urls"] = norm_urls(fields["urls"])
    if "score" in fields:
        fields["score"] = parse_score(fields["score"])
    if "date" in fields:
        validate_date(fields["date"])
    if fields.get("posted_date"):
        validate_date(fields["posted_date"])
    if "status" in fields:
        fields["status"] = validate_status(fields["status"])
    return fields


def new_job(data: dict, fields: dict) -> dict:
    company = fields.get("company", "").strip()
    if not company:
        sys.exit("ERROR: company is required")
    if not fields.get("role", "").strip():
        sys.exit("ERROR: role is required")
    date = fields.get("date") or today()
    status = fields.get("status", "—")
    job = {
        "id": max((j["id"] for j in data["jobs"]), default=0) + 1,
        "company": company,
        "company_key": normalize_company(company),
        "role": fields["role"].strip(),
        "date": date,
        "tier": fields.get("tier", "?"),
        "yoe": fields.get("yoe", "?"),
        "tech_stack": fields.get("tech_stack", "?"),
        "location": fields.get("location", "?"),
        "ctc": fields.get("ctc", "?"),
        "score": fields.get("score", parse_score("?")),
        "verdict": fields.get("verdict", "?"),
        "apply_via": fields.get("apply_via", "?"),
        "priority": fields.get("priority", "?"),
        "channel": fields.get("channel", "?"),
        "recommendation": fields.get("recommendation", "?"),
        # Full /job-match markdown (criteria table, red flags, strategy, prep
        # topics) — shown in the UI detail row. "" = no deep analysis yet.
        "analysis_md": fields.get("analysis_md", ""),
        # None = unknown (most rows). Only /job-feed and JDs that state it fill these.
        "posted_date": fields.get("posted_date"),
        "jd_text": fields.get("jd_text", ""),
        "status": status,
        "status_history": [{"status": status, "date": date}],
        "urls": fields.get("urls", []),
        "url_note": fields.get("url_note", ""),
        "archived": False,
        "archived_on": None,
    }
    return job


# ─── commands ────────────────────────────────────────────────────────────────

def cmd_find(args):
    jobs = load()["jobs"]
    matches = find_matches(jobs,
                           query=None if args.url else args.query,
                           url=args.query if args.url else None,
                           job_id=args.id, role=args.role,
                           include_archived=args.include_archived)
    if not matches:
        print("NOT FOUND")
        sys.exit(1)
    for j in matches:
        dump(j)


def cmd_list(args):
    jobs = load()["jobs"]
    if args.all:
        pool = jobs
    elif args.archived:
        pool = [j for j in jobs if j.get("archived")]
    else:
        pool = [j for j in jobs if not j.get("archived")]
    if args.status_group == "active":
        pool = [j for j in pool if j["status"] in ACTIVE_STATUSES]
    elif args.status_group == "terminal":
        pool = [j for j in pool if j["status"] in TERMINAL_STATUSES]

    if args.json:
        fields = args.fields.split(",") if args.fields else None
        rows = [{f: j.get(f) for f in fields} if fields else j for j in pool]
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for j in sorted(pool, key=lambda j: j["date"], reverse=True):
        score = j["score"]["raw"] if isinstance(j.get("score"), dict) else "?"
        verdict = (j.get("verdict") or "?").split("(")[0].strip()
        arch = "  [archived]" if j.get("archived") else ""
        print(f"  {j['id']:>3}  {j['date']}  {j['status']:<24} {score:>14}  "
              f"{verdict:<12} {j['company']}{arch}")
    print(f"  — {len(pool)} row(s)")


def last_activity(job: dict) -> str:
    """Most recent date on the row: its analysis date or its latest status change."""
    dates = [job.get("date") or ""]
    dates += [h.get("date") or "" for h in job.get("status_history", [])]
    return max(d for d in dates) or (job.get("date") or "")


def _age_days(date_str: str, today: str) -> int | None:
    try:
        return (datetime.strptime(today, "%Y-%m-%d")
                - datetime.strptime(date_str, "%Y-%m-%d")).days
    except (ValueError, TypeError):
        return None


def _best_match(matches: list) -> dict:
    """Pick the row that most justifies a drop: furthest along, then most recent."""
    def rank(j):
        st = j.get("status")
        rung = ACTIVE_LADDER.index(st) if st in ACTIVE_LADDER else -1
        return (rung, last_activity(j))
    return max(matches, key=rank)


def normalize_role(role: str) -> str:
    """Loose key for 'is this the same requisition?'.

    Deliberately STRICT (exact match after punctuation/case folding, no fuzzy
    matching): a false "same role" causes a silent drop, whereas a false
    "different role" only costs one extra visible row. Err toward visible.
    """
    s = (role or "").lower()
    s = re.sub(r"[^\w]+", " ", s)
    return " ".join(s.split())


def classify_dedup(jobs: list, company: str, url: str | None, today: str,
                   cooloff_days: int = STALE_COMPANY_DAYS,
                   role: str | None = None) -> dict:
    """Dedup one candidate listing. **The URL is the only identity.**

    A company runs many reqs at once and you can legitimately apply to several,
    including while an interview loop is already running there. So the company
    NEVER causes a drop — only the exact same posting does. Two different job
    ids are two different jobs, full stop.

    recommend:
      drop      — this exact URL is already tracked. The only drop there is.
      new-role  — company is on file but this posting isn't → `add --force-new`.
      fresh     — company not tracked at all → plain `add`.

    Everything else the company history tells us is returned as ADVISORY
    context, never as a veto:
      live_process   — something in flight here, on some other req
      recent_contact — last activity was within `cooloff_days` (default 15),
                       i.e. a rejection/ghosting still warm enough to think
                       about before re-applying
    `/job-feed` displays both; the decision stays with the user.
    """
    out = {"company": company, "role": role, "url": url,
           "company_key": normalize_company(company) if company else "",
           "tracked": False, "by": None, "id": None, "status": None,
           "date": None, "age_days": None, "archived": False,
           "match_count": 0, "matched_role": None,
           "live_process": None, "recent_contact": None,
           "recommend": "fresh", "reason": "not tracked"}

    # ── the one and only drop rule ────────────────────────────────────────────
    if url:
        hits = find_matches(jobs, url=url, include_archived=True)
        if hits:
            j = hits[0]
            out.update(tracked=True, by="url", id=j["id"], status=j.get("status"),
                       date=last_activity(j), archived=bool(j.get("archived")),
                       match_count=len(hits), matched_role=j.get("role"),
                       recommend="drop",
                       age_days=_age_days(last_activity(j), today),
                       reason=f"same posting already tracked (id={j['id']}, "
                              f"{j.get('status')})")
            return out

    if not company:
        return out
    hits = find_matches(jobs, query=company, include_archived=True)
    if not hits:
        return out

    # ── company is known, but this posting is not → it survives ───────────────
    j = _best_match(hits)
    activity = last_activity(j)
    age = _age_days(activity, today)
    out.update(tracked=True, by="company", id=j["id"], status=j.get("status"),
               date=activity, age_days=age, archived=bool(j.get("archived")),
               match_count=len(hits), matched_role=j.get("role"),
               recommend="new-role")

    live = [x for x in hits if x.get("status") in ACTIVE_LADDER]
    if live:
        lj = _best_match(live)
        out["live_process"] = {"id": lj["id"], "role": lj.get("role"),
                               "status": lj.get("status")}
    if age is not None and age <= cooloff_days:
        out["recent_contact"] = {"id": j["id"], "status": j.get("status"),
                                 "age_days": age, "within_days": cooloff_days}

    notes = []
    if out["live_process"]:
        lp = out["live_process"]
        notes.append(f"⚠️ live process here: {lp['status']} on {lp['role']!r} "
                     f"(id={lp['id']})")
    if out["recent_contact"]:
        rc = out["recent_contact"]
        notes.append(f"⚠️ recent contact: {rc['status']} {rc['age_days']}d ago "
                     f"(within {rc['within_days']}d)")
    tail = " — " + "; ".join(notes) if notes else ""
    out["reason"] = (f"new posting at a tracked company ({len(hits)} req(s) on "
                     f"file) — add --force-new{tail}")
    return out


def cmd_explain_cooloff(args):
    """Show what the recent-contact WINDOW flags on the real tracker.

    Nothing here filters anything — dedup drops on URL alone. This only shows
    how noisy the ⚠️ advisory flag will be at each window width.
    """
    today = validate_date(args.today) if args.today else today()
    jobs = load()["jobs"]
    names = sorted({j["company"] for j in jobs})

    print(f"# Recent-contact window — {len(names)} tracked companies, as of {today}\n")
    print("A new posting at ANY of these companies still SURVIVES dedup; the window")
    print("only decides whether it carries a ⚠️ recent-contact flag.\n")
    print("  window   flagged   (of the tracked companies)")
    candidates = sorted({7, 15, 30, 60, 90, 120, 180,
                         RECENT_CONTACT_DAYS, args.cooloff_days})
    for days in candidates:
        res = [classify_dedup(jobs, n, None, today, cooloff_days=days) for n in names]
        flagged = sum(1 for r in res if r["recent_contact"])
        mark = "  ← current" if days == RECENT_CONTACT_DAYS else ""
        print(f"  {days:>4}d   {flagged:>7}{mark}")

    res = [classify_dedup(jobs, n, None, today, cooloff_days=args.cooloff_days)
           for n in names]
    flagged = [r for r in res if r["recent_contact"]]
    live = [r for r in res if r["live_process"]]
    print(f"\n## ⚠️ recent contact at {args.cooloff_days}d ({len(flagged)}):\n")
    for r in sorted(flagged, key=lambda r: r["age_days"] or 0):
        print(f"  {r['age_days']:>4}d  {str(r['status']):<22}  {r['company']}")
    print(f"\n## ⚠️ live process, any age ({len(live)}) — a second req here is allowed,")
    print("   but you should know a loop is already running:\n")
    for r in sorted(live, key=lambda r: r["company"]):
        lp = r["live_process"]
        print(f"  {lp['status']:<22}  {r['company']} — {lp['role']}")
    print("\nNothing above is dropped. The ONLY drop is an exact URL already tracked.")


def cmd_dedup(args):
    """Batch dedup for /job-feed. Canonical normalization lives HERE, not in a
    skill's prose — see normalize_company's byte-identical contract."""
    if args.explain:
        return cmd_explain_cooloff(args)
    try:
        payload = json.loads(sys.stdin.read().lstrip("\ufeff"))
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: --stdin-json is not valid JSON — {e}")
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        sys.exit("ERROR: dedup expects a JSON array of {company, url} objects")

    today = validate_date(args.today) if args.today else today()
    jobs = load()["jobs"]
    results = []
    for i, item in enumerate(payload):
        if not isinstance(item, dict):
            sys.exit(f"ERROR: item {i} is not an object")
        results.append(classify_dedup(jobs, (item.get("company") or "").strip(),
                                      (item.get("url") or "").strip() or None,
                                      today, cooloff_days=args.cooloff_days,
                                      role=(item.get("role") or "").strip() or None))
    if args.summary:
        counts = {}
        for r in results:
            counts[r["recommend"]] = counts.get(r["recommend"], 0) + 1
        for k in ("fresh", "new-role", "drop"):
            print(f"  {counts.get(k, 0):>3}  {k}")
        return
    print(json.dumps(results, ensure_ascii=False, indent=2))


def cmd_add(args):
    fields = read_input_fields(args)
    with jobs_lock():
        data = load()
        existing = find_matches(data["jobs"], query=fields.get("company", ""))
        if existing and not args.force_new:
            print("ERROR: company already tracked (use upsert to update, or "
                  "--force-new for a genuinely distinct role):", file=sys.stderr)
            for j in existing:
                print(f"  id={j['id']}  {j['date']}  {j['status']}  "
                      f"{j['company']} — {j['role']}", file=sys.stderr)
            sys.exit(1)
        job = new_job(data, fields)
        data["jobs"].append(job)
        save(data)
    print(f"  ✓ Added id={job['id']}: {job['company']} — {job['role']} "
          f"({job['date']}, {job['status']})")


def cmd_upsert(args):
    fields = read_input_fields(args)
    with jobs_lock():
        data = load()
        matches = find_matches(data["jobs"], query=fields.get("company", ""),
                               job_id=args.id, role=fields.get("role") if args.id is None else None)
        if args.id is not None and not matches:
            sys.exit(f"ERROR: no job with id {args.id}")
        if len(matches) > 1:
            # same company twice (distinct roles) — force the caller to pick
            print(f"ERROR: {fields.get('company')!r} is ambiguous — "
                  f"{len(matches)} matches (re-run with --id):", file=sys.stderr)
            for j in matches:
                print(f"  id={j['id']}  {j['company']} — {j['role']}", file=sys.stderr)
            sys.exit(1)
        if matches:
            job = matches[0]
            # date/channel/status are structurally untouchable here: date is the
            # first-analysis date, channel is where it was found, status is
            # application progress — a re-analysis must never reset them.
            for f in ANALYSIS_FIELDS:
                if f in fields:
                    job[f] = fields[f]
            if "company" in fields and fields["company"].strip():
                job["company"] = fields["company"].strip()
                job["company_key"] = normalize_company(job["company"])
            save(data)
            print(f"  ✓ Updated id={job['id']}: {job['company']} — {job['role']} "
                  f"(preserved date/channel/status: {job['date']}, "
                  f"{job.get('channel')}, {job['status']})")
        else:
            job = new_job(data, fields)
            data["jobs"].append(job)
            save(data)
            print(f"  ✓ Added id={job['id']}: {job['company']} — {job['role']} "
                  f"({job['date']}, {job['status']})")


def apply_status(job: dict, status: str, date: str, force: bool = False) -> str | None:
    """Move one job to `status` in place. Returns the old status, or None when
    nothing changed. Raises JobTrackError on a refused downgrade.

    Never-downgrade only guards active→active moves down the ladder. Terminal
    targets are always allowed; any move FROM 🚫 No Response is allowed (a late
    reply revives the application)."""
    if status not in ALL_STATUSES:
        raise JobTrackError(f"unknown status {status!r}")
    old = job["status"]
    if old == status:
        return None
    if (not force and old in ACTIVE_LADDER and status in ACTIVE_LADDER
            and ACTIVE_LADDER.index(status) < ACTIVE_LADDER.index(old)):
        raise JobTrackError(f"refusing status downgrade {old} → {status} for "
                            f"{job['company']} (use --force if intentional)")
    job["status"] = status
    job.setdefault("status_history", []).append({"status": status, "date": date})
    return old


def cmd_set_status(args):
    status = validate_status(args.status)
    date = validate_date(args.date) if args.date else today()
    with jobs_lock():
        data = load()
        if args.query.isdigit():
            matches = find_matches(data["jobs"], job_id=int(args.query),
                                   include_archived=True)
        else:
            matches = find_matches(data["jobs"], query=args.query,
                                   include_archived=True)
        if not matches:
            sys.exit(f"ERROR: no job matches {args.query!r}")
        if len(matches) > 1:
            print(f"ERROR: {args.query!r} is ambiguous — use the id:", file=sys.stderr)
            for j in matches:
                print(f"  id={j['id']}  {j['company']} — {j['role']}  ({j['status']})",
                      file=sys.stderr)
            sys.exit(1)
        job = matches[0]
        try:
            old = apply_status(job, status, date, force=args.force)
        except JobTrackError as e:
            sys.exit(f"ERROR: {e}")
        if old is None:
            print(f"  ℹ id={job['id']} {job['company']} already {status} — no change")
            return
        save(data)
    note = " [archived row]" if job.get("archived") else ""
    print(f"  ✓ id={job['id']} {job['company']}: {old} → {status} ({date}){note}")


def _days_between(from_iso: str, to_iso: str) -> int | None:
    try:
        return (datetime.strptime(to_iso, "%Y-%m-%d")
                - datetime.strptime(from_iso, "%Y-%m-%d")).days
    except (ValueError, TypeError):
        return None


def archive_eligible(job: dict, today_iso: str, days: int = ARCHIVE_AFTER_DAYS) -> str | None:
    """Reason string if the job may be archived, else None."""
    if job.get("archived"):
        return None
    status = job.get("status")
    if status in IMMEDIATE_ARCHIVE:
        return f"terminal status {status}"
    verdict = str(job.get("verdict") or "").strip()
    if verdict.startswith(("❌", "⛔")) and status == "—":
        return "skip verdict, never applied"
    if status in NEVER_ARCHIVE:
        return None
    age = _days_between(job.get("date"), today_iso)
    if age is not None and age > days:
        return f"{age}d old, not in flight ({status})"
    return None


def set_archived(job: dict, archived: bool, on: str | None):
    job["archived"] = archived
    job["archived_on"] = on if archived else None


def cmd_archive(args):
    now = today()
    with jobs_lock():
        data = load()
        if args.id is not None:
            hits = [j for j in data["jobs"] if j["id"] == args.id]
            if not hits:
                sys.exit(f"ERROR: no job with id {args.id}")
            reason = archive_eligible(hits[0], now) or ("forced" if args.force else None)
            if not reason:
                sys.exit(f"ERROR: id={args.id} is not archive-eligible ({hits[0]['status']}); "
                         f"use --force to archive anyway")
            picks = [(hits[0], reason)]
        elif args.eligible:
            picks = [(j, r) for j in data["jobs"] if (r := archive_eligible(j, now))]
        else:
            sys.exit("ERROR: pass a job id or --eligible")
        for j, r in picks:
            print(f"  {'(dry-run) ' if args.dry_run else ''}archive id={j['id']} "
                  f"{j['company']} — {r}")
        if args.dry_run or not picks:
            print(f"  — {len(picks)} row(s)")
            return
        for j, _ in picks:
            set_archived(j, True, now)
        save(data)
    print(f"  ✓ archived {len(picks)} row(s)")


def cmd_unarchive(args):
    with jobs_lock():
        data = load()
        hits = [j for j in data["jobs"] if j["id"] == args.id]
        if not hits:
            sys.exit(f"ERROR: no job with id {args.id}")
        set_archived(hits[0], False, None)
        save(data)
    print(f"  ✓ unarchived id={args.id} {hits[0]['company']}")


def _month_of(job):
    return job["date"][:7]


def _verdict_bucket(verdict: str) -> str:
    v = (verdict or "").strip()
    if v.startswith("✅"):
        return "✅ Apply"
    if v.startswith("🟡"):
        return "🟡 Maybe"
    if v.startswith("⚠"):
        return "⚠️ Practice"
    if v.startswith(("❌", "⛔")):
        return "❌ Skip"
    if v.startswith("⏳"):
        return "⏳ Pending"
    return "? Unanalyzed"


def _tier_bucket(tier: str) -> str:
    t = (tier or "?").strip()
    for b in ("Tier-1", "Tier-2", "Tier-3", "GCC", "MNC", "Startup",
              "Consultancy", "Staffing"):
        if t.lower().startswith(b.lower()):
            return b
    if t.startswith(("❌", "⛔")):
        return "❌ Excluded"
    return "Other" if t not in ("?", "—", "") else "?"


def statuses_seen(job) -> set:
    seen = {h["status"] for h in job.get("status_history", [])}
    seen.add(job["status"])
    return seen


def cmd_stats(args):
    data = load()
    jobs = data["jobs"]
    if args.month:
        jobs = [j for j in jobs if _month_of(j) == args.month]
    if not jobs:
        print("No jobs tracked" + (f" in {args.month}" if args.month else "") + ".")
        return

    def count_by(fn):
        out = {}
        for j in jobs:
            out[fn(j)] = out.get(fn(j), 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    total = len(jobs)
    archived = sum(1 for j in jobs if j.get("archived"))
    active_status = sum(1 for j in jobs if j["status"] in ACTIVE_STATUSES)

    applied = [j for j in jobs if j["status"] not in NOT_APPLIED]
    responded = [j for j in applied
                 if statuses_seen(j) - NO_RESPONSE_YET - NOT_APPLIED]
    interviewed = [j for j in applied if statuses_seen(j) & INTERVIEW_SET]
    offers = [j for j in applied if statuses_seen(j) & OFFER_SET]
    rejected = sum(1 for j in applied if j["status"] in ("❌ Rejected", "❌ Failed Assessment"))

    def pct(n, d):
        return f"{100 * n / d:.0f}%" if d else "—"

    title = f"Job Tracker Stats{' — ' + args.month if args.month else ''}"
    print(f"# {title}\n")
    print(f"**Overview:** {total} tracked ({total - archived} open, "
          f"{archived} archived) · {active_status} in-flight statuses\n")

    print("**Funnel:**")
    print(f"  Applied {len(applied)} → Response {len(responded)} "
          f"({pct(len(responded), len(applied))}) → Interview {len(interviewed)} "
          f"({pct(len(interviewed), len(applied))}) → Offer {len(offers)} "
          f"({pct(len(offers), len(applied))}) · Rejected {rejected}\n")

    print("**By status:**")
    for s, n in count_by(lambda j: j["status"]).items():
        print(f"  {n:>3}  {s}")

    print("\n**Verdict distribution:**")
    for v, n in count_by(lambda j: _verdict_bucket(j.get("verdict"))).items():
        print(f"  {n:>3}  {v}  ({pct(n, total)})")

    print("\n**By tier (applied → response rate):**")
    tiers = {}
    for j in applied:
        b = _tier_bucket(j.get("tier"))
        got = bool(statuses_seen(j) - NO_RESPONSE_YET - NOT_APPLIED)
        a, r = tiers.get(b, (0, 0))
        tiers[b] = (a + 1, r + (1 if got else 0))
    for b, (a, r) in sorted(tiers.items(), key=lambda kv: -kv[1][0]):
        print(f"  {a:>3} applied, {r} responses ({pct(r, a)})  {b}")

    print("\n**By channel:**")
    for c, n in count_by(lambda j: j.get("channel") or "?").items():
        print(f"  {n:>3}  {c}")

    # Days to first response — from real status_history transitions.
    lags = []
    for j in applied:
        for h in j.get("status_history", []):
            if h["status"] in NO_RESPONSE_YET or h["status"] in NOT_APPLIED:
                continue
            lag = (datetime.strptime(h["date"], "%Y-%m-%d")
                   - datetime.strptime(j["date"], "%Y-%m-%d")).days
            lags.append(lag)
            break
    if lags:
        print(f"\n**Days to first response:** avg {sum(lags) / len(lags):.1f} · "
              f"min {min(lags)} · max {max(lags)}  (n={len(lags)})")
    else:
        print("\n**Days to first response:** n/a — no responses yet")


def add_field_flags(p):
    p.add_argument("--company")
    p.add_argument("--role")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p.add_argument("--tier")
    p.add_argument("--yoe")
    p.add_argument("--tech-stack", dest="tech_stack")
    p.add_argument("--location")
    p.add_argument("--ctc")
    p.add_argument("--score", help='e.g. "12/14", "?", "— (HF capped)"')
    p.add_argument("--verdict")
    p.add_argument("--apply-via", dest="apply_via")
    p.add_argument("--priority")
    p.add_argument("--channel")
    p.add_argument("--recommendation")
    p.add_argument("--analysis-md", dest="analysis_md",
                   help="full analysis markdown (prefer --stdin-json for this)")
    p.add_argument("--status", help="enum value; default — on add")
    p.add_argument("--posted-date", dest="posted_date",
                   help="YYYY-MM-DD the company posted the req (drives staleness)")
    p.add_argument("--jd-text", dest="jd_text",
                   help="cached JD text (prefer --stdin-json for this)")
    p.add_argument("--url", dest="urls", action="append", metavar="URL")
    p.add_argument("--url-note", dest="url_note")
    p.add_argument("--stdin-json", action="store_true",
                   help="read a JSON object of fields from stdin (flags override)")


def main():
    ap = argparse.ArgumentParser(description="job tracker (data/jobs_data.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("find", help="print job(s) matching a company / url / id")
    p.add_argument("query")
    p.add_argument("--url", action="store_true", help="match by exact URL instead of company")
    p.add_argument("--id", type=int)
    p.add_argument("--role")
    p.add_argument("--include-archived", action="store_true")
    p.set_defaults(func=cmd_find)

    p = sub.add_parser("list", help="list jobs (compact table or --json)")
    p.add_argument("--json", action="store_true")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--archived", action="store_true", help="only archived rows")
    g.add_argument("--all", action="store_true", help="archived + active rows")
    p.add_argument("--status-group", choices=("active", "terminal"))
    p.add_argument("--fields", help="comma-separated field list (with --json)")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("dedup", help="batch URL-first dedup for /job-feed (stdin JSON)")
    p.add_argument("--stdin-json", action="store_true",
                   help="(implied) read [{company, url}, …] from stdin")
    p.add_argument("--today", help="YYYY-MM-DD override for age math (tests)")
    p.add_argument("--summary", action="store_true",
                   help="print counts only instead of the full JSON")
    p.add_argument("--cooloff-days", type=int, default=STALE_COMPANY_DAYS,
                   dest="cooloff_days",
                   help=f"days a dead end blocks its company (default {STALE_COMPANY_DAYS})")
    p.add_argument("--explain", action="store_true",
                   help="show the cooloff sensitivity curve over the real tracker "
                        "and which companies it unblocks (reads no stdin)")
    p.set_defaults(func=cmd_dedup)

    p = sub.add_parser("add", help="add a new job (fails if company already tracked)")
    add_field_flags(p)
    p.add_argument("--force-new", action="store_true",
                   help="allow a second row for the same company (distinct role)")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("upsert", help="update analysis fields by company/--id, or add")
    add_field_flags(p)
    p.add_argument("--id", type=int, help="target a specific row")
    p.set_defaults(func=cmd_upsert)

    p = sub.add_parser("set-status", help="change a job's status (enum-validated)")
    p.add_argument("query", help="job id or company")
    p.add_argument("status")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p.add_argument("--force", action="store_true", help="allow an active-ladder downgrade")
    p.set_defaults(func=cmd_set_status)

    p = sub.add_parser("stats", help="funnel / distribution / response-time stats")
    p.add_argument("--month", help="YYYY-MM filter")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("archive", help="archive one job by id, or every eligible job")
    p.add_argument("id", nargs="?", type=int)
    p.add_argument("--eligible", action="store_true", help="archive every eligible row")
    p.add_argument("--dry-run", action="store_true", dest="dry_run")
    p.add_argument("--force", action="store_true", help="archive an id even if not eligible")
    p.set_defaults(func=cmd_archive)

    p = sub.add_parser("unarchive", help="bring an archived job back")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_unarchive)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
