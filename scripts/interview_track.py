#!/usr/bin/env python3
"""
interview_track.py — CLI for data/interviews_data.json, the interview debrief log.

Used by the /interview-debrief skill and the tracker UI (Interviews view).
It records what each interview asked, what you said, a better answer, and the
lessons. A lesson seen in several interviews is the signal that matters: it is
a habit, not bad luck. `lessons` ranks them by how often they repeat.

Commands:
  add-interview --stdin-json [--link-job ID]   new interview (fails on a duplicate slug)
  add-round <slug> --stdin-json                append a round, update last_date
  lesson-upsert --stdin-json                   create a lesson, or merge into one;
                                               {"seen_in": "<slug>"} adds a repeat
  set-outcome <slug> <outcome>
  set-lesson-status <id> open|fixed
  list | show <slug> | lessons [--open] | topics | stats
  [--json] on list / show / lessons / topics / stats

Writes are atomic, LF-only, under data/.interviews.lock.
Set JOB_HUNT_DATA_DIR to use another data folder (the tests do this).
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import time

import job_track as jt

OUTCOMES = ("in-progress", "rejected", "offer", "withdrew", "no-response")
ROUND_RESULTS = ("passed", "failed", "pending", "unknown")
VERDICTS = ("🟢", "🟡", "🔴")
CATEGORIES = ("communication", "technical", "preparation", "logistics", "negotiation")
LESSON_STATUSES = ("open", "fixed")

INTERVIEW_FIELDS = ("slug", "company", "role", "job_id", "first_date", "last_date",
                    "outcome", "stage_reached", "summary", "lessons", "rounds")
ROUND_FIELDS = ("name", "date", "format", "interviewer", "result", "questions",
                "went_well", "went_wrong")
QUESTION_FIELDS = ("q", "topic", "my_answer", "better_answer", "verdict")
LESSON_FIELDS = ("id", "title", "category", "status", "detail", "practice", "seen_in")

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_LOCK_STALE_S = 15
_LOCK_TIMEOUT_S = 5


def data_path():
    return jt.DATA_DIR / "interviews_data.json"


def lock_path():
    return jt.DATA_DIR / ".interviews.lock"


@contextlib.contextmanager
def interviews_lock():
    jt.DATA_DIR.mkdir(parents=True, exist_ok=True)
    lp = str(lock_path())
    deadline = time.time() + _LOCK_TIMEOUT_S
    while True:
        try:
            fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {time.time()}\n".encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lp) > _LOCK_STALE_S:
                    os.unlink(lp)
                    continue
            except OSError:
                continue
            if time.time() >= deadline:
                raise TimeoutError("interviews store is locked by another writer — retry in a moment")
            time.sleep(0.05)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            os.unlink(lp)


def load() -> dict:
    data = jt._load_json(data_path(), {"version": 1, "lessons": [], "interviews": []})
    data.setdefault("lessons", [])
    data.setdefault("interviews", [])
    return data


def save(data: dict):
    jt._save_json_atomic(data_path(), data)


# ── validation ───────────────────────────────────────────────────────────────

def _err(msg: str):
    raise jt.JobTrackError(msg)


def _date(value, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        _err(f"{field} must be YYYY-MM-DD — got {value!r}")
    return value


def _str_list(value, field: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        _err(f"{field} must be a list of strings")
    return [x.strip() for x in value if x.strip()]


def _unknown(obj: dict, allowed, what: str):
    extra = set(obj) - set(allowed)
    if extra:
        _err(f"unknown field(s) in {what}: {', '.join(sorted(extra))}")


def clean_question(q: dict) -> dict:
    if not isinstance(q, dict):
        _err("each question must be an object")
    _unknown(q, QUESTION_FIELDS, "question")
    if not str(q.get("q") or "").strip():
        _err("question text 'q' is required")
    verdict = q.get("verdict") or ""
    if verdict and verdict not in VERDICTS:
        _err(f"verdict must be one of {' '.join(VERDICTS)} — got {verdict!r}")
    return {f: (str(q.get(f) or "").strip()) for f in QUESTION_FIELDS}


def clean_round(r: dict) -> dict:
    if not isinstance(r, dict):
        _err("a round must be an object")
    _unknown(r, ROUND_FIELDS, "round")
    name = str(r.get("name") or "").strip()
    if not name:
        _err("round 'name' is required")
    result = r.get("result") or "unknown"
    if result not in ROUND_RESULTS:
        _err(f"round result must be one of {', '.join(ROUND_RESULTS)} — got {result!r}")
    return {
        "name": name,
        "date": _date(r.get("date") or jt.today(), "round date"),
        "format": str(r.get("format") or "").strip(),
        "interviewer": str(r.get("interviewer") or "").strip(),
        "result": result,
        "questions": [clean_question(q) for q in (r.get("questions") or [])],
        "went_well": _str_list(r.get("went_well"), "went_well"),
        "went_wrong": _str_list(r.get("went_wrong"), "went_wrong"),
    }


def find_interview(data: dict, slug: str) -> dict:
    for i in data["interviews"]:
        if i["slug"] == slug:
            return i
    _err(f"no interview with slug {slug!r}")


def find_lesson(data: dict, lesson_id: str) -> dict | None:
    return next((l for l in data["lessons"] if l["id"] == lesson_id), None)


def repeats(lesson: dict) -> int:
    return len(lesson.get("seen_in") or [])


# ── operations (pure on `data`; the CLI and UI wrap them in lock+load+save) ───

def add_interview(data: dict, fields: dict, link_job: int | None = None) -> dict:
    _unknown(fields, INTERVIEW_FIELDS, "interview")
    slug = str(fields.get("slug") or "").strip()
    if not _SLUG.match(slug):
        _err(f"slug must be lowercase-kebab-case (e.g. acme-backend-2026-03) — got {slug!r}")
    if any(i["slug"] == slug for i in data["interviews"]):
        _err(f"interview {slug!r} already exists — use add-round to add to it")
    company = str(fields.get("company") or "").strip()
    role = str(fields.get("role") or "").strip()
    if not company or not role:
        _err("company and role are required")
    outcome = fields.get("outcome") or "in-progress"
    if outcome not in OUTCOMES:
        _err(f"outcome must be one of {', '.join(OUTCOMES)} — got {outcome!r}")
    job_id = link_job if link_job is not None else fields.get("job_id")
    if job_id is not None:
        if not isinstance(job_id, int):
            _err("job_id must be an integer tracker id")
        if not any(j["id"] == job_id for j in jt.load()["jobs"]):
            _err(f"no job with id {job_id} in the job tracker")
    rounds = [clean_round(r) for r in (fields.get("rounds") or [])]
    dates = [r["date"] for r in rounds]
    first = _date(fields.get("first_date") or (min(dates) if dates else jt.today()), "first_date")
    last = _date(fields.get("last_date") or (max(dates) if dates else first), "last_date")
    lessons = _str_list(fields.get("lessons"), "lessons")
    for lid in lessons:
        if not find_lesson(data, lid):
            _err(f"unknown lesson id {lid!r} — create it with lesson-upsert first")
    interview = {
        "slug": slug, "company": company, "role": role, "job_id": job_id,
        "first_date": first, "last_date": last, "outcome": outcome,
        "stage_reached": str(fields.get("stage_reached") or (rounds[-1]["name"] if rounds else "")).strip(),
        "summary": str(fields.get("summary") or "").strip(),
        "lessons": lessons,
        "rounds": rounds,
    }
    data["interviews"].append(interview)
    for lid in lessons:
        _add_seen(find_lesson(data, lid), slug)
    return interview


def add_round(data: dict, slug: str, fields: dict) -> dict:
    interview = find_interview(data, slug)
    rnd = clean_round(fields)
    interview["rounds"].append(rnd)
    interview["last_date"] = max(interview["last_date"], rnd["date"])
    interview["first_date"] = min(interview["first_date"], rnd["date"])
    interview["stage_reached"] = rnd["name"]
    return rnd


def _add_seen(lesson: dict, slug: str):
    seen = lesson.setdefault("seen_in", [])
    if slug not in seen:
        seen.append(slug)


def lesson_upsert(data: dict, fields: dict) -> tuple[dict, bool]:
    """Create or merge a lesson. `seen_in` may be a slug or a list; it is
    ADDED to, never replaced, so a repeat is never lost. Returns (lesson, created)."""
    _unknown(fields, LESSON_FIELDS, "lesson")
    lid = str(fields.get("id") or "").strip()
    if not _SLUG.match(lid):
        _err(f"lesson id must be lowercase-kebab-case — got {lid!r}")
    seen = fields.get("seen_in") or []
    if isinstance(seen, str):
        seen = [seen]
    seen = _str_list(seen, "seen_in")
    for s in seen:
        find_interview(data, s)
    if "category" in fields and fields["category"] not in CATEGORIES:
        _err(f"category must be one of {', '.join(CATEGORIES)}")
    if "status" in fields and fields["status"] not in LESSON_STATUSES:
        _err(f"status must be one of {', '.join(LESSON_STATUSES)}")
    lesson = find_lesson(data, lid)
    created = lesson is None
    if created:
        if not str(fields.get("title") or "").strip():
            _err("a new lesson needs a title")
        lesson = {"id": lid, "title": "", "category": fields.get("category") or "technical",
                  "status": "open", "detail": "", "practice": "", "seen_in": []}
        data["lessons"].append(lesson)
    for f in ("title", "category", "status", "detail", "practice"):
        if f in fields and fields[f] is not None:
            lesson[f] = str(fields[f]).strip()
    for s in seen:
        _add_seen(lesson, s)
        interview = find_interview(data, s)
        if lid not in interview["lessons"]:
            interview["lessons"].append(lid)
    return lesson, created


def set_outcome(data: dict, slug: str, outcome: str) -> dict:
    if outcome not in OUTCOMES:
        _err(f"outcome must be one of {', '.join(OUTCOMES)} — got {outcome!r}")
    interview = find_interview(data, slug)
    interview["outcome"] = outcome
    return interview


def set_lesson_status(data: dict, lesson_id: str, status: str) -> dict:
    if status not in LESSON_STATUSES:
        _err(f"status must be one of {', '.join(LESSON_STATUSES)}")
    lesson = find_lesson(data, lesson_id)
    if not lesson:
        _err(f"no lesson with id {lesson_id!r}")
    lesson["status"] = status
    return lesson


def ranked_lessons(data: dict, open_only: bool = False) -> list:
    pool = [l for l in data["lessons"] if not open_only or l.get("status") == "open"]
    return sorted(pool, key=lambda l: (-repeats(l), l.get("status") != "open", l["id"]))


def topic_stats(data: dict) -> list:
    out: dict[str, dict] = {}
    for i in data["interviews"]:
        for r in i["rounds"]:
            for q in r["questions"]:
                t = q.get("topic") or "(none)"
                row = out.setdefault(t, {"topic": t, "asked": 0, "red": 0, "yellow": 0, "green": 0})
                row["asked"] += 1
                key = {"🔴": "red", "🟡": "yellow", "🟢": "green"}.get(q.get("verdict"))
                if key:
                    row[key] += 1
    rows = list(out.values())
    for r in rows:
        r["red_share"] = round(100 * r["red"] / r["asked"]) if r["asked"] else 0
    return sorted(rows, key=lambda r: (-r["asked"], -r["red"], r["topic"]))


def stats(data: dict) -> dict:
    ivs = data["interviews"]
    rounds = [r for i in ivs for r in i["rounds"]]
    qs = [q for r in rounds for q in r["questions"]]
    by_outcome: dict[str, int] = {}
    for i in ivs:
        by_outcome[i["outcome"]] = by_outcome.get(i["outcome"], 0) + 1
    return {
        "interviews": len(ivs),
        "rounds": len(rounds),
        "rounds_passed": sum(1 for r in rounds if r["result"] == "passed"),
        "rounds_failed": sum(1 for r in rounds if r["result"] == "failed"),
        "questions": len(qs),
        "verdicts": {v: sum(1 for q in qs if q.get("verdict") == v) for v in VERDICTS},
        "by_outcome": by_outcome,
        "lessons_open": sum(1 for l in data["lessons"] if l.get("status") == "open"),
        "lessons_repeated": sum(1 for l in data["lessons"] if repeats(l) >= 2),
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

def _read_stdin_json() -> dict:
    try:
        obj = json.loads(sys.stdin.read().lstrip("﻿"))
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: stdin is not valid JSON — {e}")
    if not isinstance(obj, dict):
        sys.exit("ERROR: stdin must be a JSON object")
    return obj


def _write(fn):
    """lock → load → fn(data) → save; JobTrackError → exit 1."""
    with interviews_lock():
        data = load()
        try:
            result = fn(data)
        except jt.JobTrackError as e:
            sys.exit(f"ERROR: {e}")
        save(data)
    return result


def _print(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_add_interview(args):
    fields = _read_stdin_json()
    iv = _write(lambda d: add_interview(d, fields, args.link_job))
    print(f"  ✓ added interview {iv['slug']}: {iv['company']} — {iv['role']} "
          f"({len(iv['rounds'])} round(s), {iv['outcome']})")


def cmd_add_round(args):
    fields = _read_stdin_json()
    rnd = _write(lambda d: add_round(d, args.slug, fields))
    print(f"  ✓ {args.slug}: added round {rnd['name']!r} ({rnd['date']}, "
          f"{len(rnd['questions'])} question(s), {rnd['result']})")


def cmd_lesson_upsert(args):
    fields = _read_stdin_json()
    lesson, created = _write(lambda d: lesson_upsert(d, fields))
    word = "created" if created else "updated"
    print(f"  ✓ {word} lesson {lesson['id']} — seen in {repeats(lesson)} interview(s)")


def cmd_set_outcome(args):
    iv = _write(lambda d: set_outcome(d, args.slug, args.outcome))
    print(f"  ✓ {iv['slug']}: outcome = {iv['outcome']}")


def cmd_set_lesson_status(args):
    lesson = _write(lambda d: set_lesson_status(d, args.id, args.status))
    print(f"  ✓ lesson {lesson['id']}: {lesson['status']}")


def cmd_list(args):
    ivs = sorted(load()["interviews"], key=lambda i: i["last_date"], reverse=True)
    if args.json:
        return _print([{k: i[k] for k in ("slug", "company", "role", "job_id", "first_date",
                                          "last_date", "outcome", "stage_reached")} for i in ivs])
    for i in ivs:
        print(f"  {i['last_date']}  {i['outcome']:<12} {i['company']} — {i['role']}  "
              f"[{i['slug']}]  {len(i['rounds'])} round(s), reached {i['stage_reached'] or '—'}")
    print(f"  — {len(ivs)} interview(s)")


def cmd_show(args):
    data = load()
    try:
        _print(find_interview(data, args.slug))
    except jt.JobTrackError as e:
        sys.exit(f"ERROR: {e}")


def cmd_lessons(args):
    rows = ranked_lessons(load(), open_only=args.open)
    if args.json:
        return _print([dict(l, repeats=repeats(l)) for l in rows])
    for l in rows:
        print(f"  ×{repeats(l)}  [{l['status']:<5}] {l['id']} — {l['title']}  ({l['category']})")
        if l.get("practice"):
            print(f"        practice: {l['practice']}")
    print(f"  — {len(rows)} lesson(s)")


def cmd_topics(args):
    rows = topic_stats(load())
    if args.json:
        return _print(rows)
    for r in rows:
        print(f"  {r['asked']:>3} asked  🔴 {r['red']:>2} ({r['red_share']:>3}%)  {r['topic']}")


def cmd_stats(args):
    s = stats(load())
    if args.json:
        return _print(s)
    v = s["verdicts"]
    print(f"Interviews {s['interviews']} · rounds {s['rounds']} "
          f"(passed {s['rounds_passed']}, failed {s['rounds_failed']}) · "
          f"questions {s['questions']} (🟢 {v['🟢']} 🟡 {v['🟡']} 🔴 {v['🔴']})")
    print("Outcomes: " + (", ".join(f"{k} {n}" for k, n in s["by_outcome"].items()) or "—"))
    print(f"Lessons: {s['lessons_open']} open, {s['lessons_repeated']} seen in 2+ interviews")


def main():
    ap = argparse.ArgumentParser(description="interview debrief log (data/interviews_data.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add-interview", help="new interview from stdin JSON")
    p.add_argument("--stdin-json", action="store_true", help="(implied) read JSON from stdin")
    p.add_argument("--link-job", type=int, dest="link_job", help="job tracker id to link")
    p.set_defaults(func=cmd_add_interview)

    p = sub.add_parser("add-round", help="append a round from stdin JSON")
    p.add_argument("slug")
    p.add_argument("--stdin-json", action="store_true", help="(implied)")
    p.set_defaults(func=cmd_add_round)

    p = sub.add_parser("lesson-upsert", help="create or merge a lesson from stdin JSON")
    p.add_argument("--stdin-json", action="store_true", help="(implied)")
    p.set_defaults(func=cmd_lesson_upsert)

    p = sub.add_parser("set-outcome")
    p.add_argument("slug")
    p.add_argument("outcome", choices=OUTCOMES)
    p.set_defaults(func=cmd_set_outcome)

    p = sub.add_parser("set-lesson-status")
    p.add_argument("id")
    p.add_argument("status", choices=LESSON_STATUSES)
    p.set_defaults(func=cmd_set_lesson_status)

    for name, fn in (("list", cmd_list), ("topics", cmd_topics), ("stats", cmd_stats)):
        p = sub.add_parser(name)
        p.add_argument("--json", action="store_true")
        p.set_defaults(func=fn)

    p = sub.add_parser("show")
    p.add_argument("slug")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("lessons", help="lessons ranked by how often they repeat")
    p.add_argument("--open", action="store_true", help="only open lessons")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_lessons)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
