#!/usr/bin/env python3
"""ui/server.py — a small local web UI for the job tracker and the interview log
(data/jobs_data.json, data/interviews_data.json).

Stdlib only. Every write goes through scripts/job_track.py (same lockfile, same
status ladder, same archive rule), so the UI and the CLI can never disagree.

    python3 ui/server.py            # http://127.0.0.1:8765
    python3 ui/server.py --port 9000 --open
    python3 ui/server.py --demo     # sample data in a temp copy; data/ is never touched

The server binds 127.0.0.1 only and rejects requests whose Host header is not
localhost (a guard against DNS-rebinding attacks from other web pages).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

UI_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(UI_DIR.parent / "scripts"))

import job_track as jt  # noqa: E402
import interview_track as it  # noqa: E402

INDEX_HTML = UI_DIR / "index.html"
DEMO_DATA = UI_DIR.parent / "examples" / "demo_data"
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
LIGHT_DROP = ("jd_text", "analysis_md")
ADD_FIELDS = ("company", "role", "url", "status", "channel", "location", "ctc", "notes")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _find(data: dict, job_id: int) -> dict:
    for j in data["jobs"]:
        if j["id"] == job_id:
            return j
    raise ApiError(404, f"no job with id {job_id}")


def _light(job: dict, today: str) -> dict:
    out = {k: v for k, v in job.items() if k not in LIGHT_DROP}
    out["has_analysis"] = bool(job.get("analysis_md"))
    out["has_jd"] = bool(job.get("jd_text"))
    out["archive_reason"] = jt.archive_eligible(job, today)
    return out


def _full(job: dict, today: str) -> dict:
    out = dict(job)
    out["archive_reason"] = jt.archive_eligible(job, today)
    return out


def _clean_str(value, field: str, required: bool = False, limit: int = 20000) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ApiError(400, f"{field} must be a string")
    value = value.strip()
    if required and not value:
        raise ApiError(400, f"{field} is required")
    if len(value) > limit:
        raise ApiError(400, f"{field} is too long")
    return value


# ── API handlers ─────────────────────────────────────────────────────────────

def api_list(query: dict) -> dict:
    view = (query.get("view") or ["open"])[0]
    if view not in ("open", "archived", "all"):
        raise ApiError(400, "view must be open, archived or all")
    data = jt.load()
    today = jt.today()
    jobs = data["jobs"]
    if view == "open":
        jobs = [j for j in jobs if not j.get("archived")]
    elif view == "archived":
        jobs = [j for j in jobs if j.get("archived")]
    jobs = sorted(jobs, key=lambda j: (j.get("date") or "", j["id"]), reverse=True)
    return {
        "jobs": [_light(j, today) for j in jobs],
        "statuses": {"active": list(jt.ACTIVE_LADDER) + [jt.NO_RESPONSE],
                     "terminal": list(jt.TERMINAL_STATUSES)},
        "today": today,
    }


def api_get(job_id: int) -> dict:
    return _full(_find(jt.load(), job_id), jt.today())


def api_stats() -> dict:
    jobs = jt.load()["jobs"]
    applied = [j for j in jobs if j["status"] not in jt.NOT_APPLIED]
    responded = [j for j in applied
                 if jt.statuses_seen(j) - jt.NO_RESPONSE_YET - jt.NOT_APPLIED]
    interviewed = [j for j in applied if jt.statuses_seen(j) & jt.INTERVIEW_SET]
    offers = [j for j in applied if jt.statuses_seen(j) & jt.OFFER_SET]
    rejected = sum(1 for j in applied
                   if j["status"] in ("❌ Rejected", "❌ Failed Assessment"))
    by_status: dict[str, int] = {}
    for j in jobs:
        by_status[j["status"]] = by_status.get(j["status"], 0) + 1
    return {
        "tracked": len(jobs),
        "archived": sum(1 for j in jobs if j.get("archived")),
        "applied": len(applied),
        "responses": len(responded),
        "interviews": len(interviewed),
        "offers": len(offers),
        "rejected": rejected,
        "by_status": dict(sorted(by_status.items(), key=lambda kv: -kv[1])),
    }


def api_add(body: dict) -> dict:
    unknown = set(body) - set(ADD_FIELDS)
    if unknown:
        raise ApiError(400, f"unknown field(s): {', '.join(sorted(unknown))}")
    fields = {
        "company": _clean_str(body.get("company"), "company", required=True, limit=200),
        "role": _clean_str(body.get("role"), "role", required=True, limit=200),
    }
    status = _clean_str(body.get("status"), "status") or "—"
    if status not in jt.ALL_STATUSES:
        raise ApiError(400, f"unknown status {status!r}")
    fields["status"] = status
    for key in ("channel", "location", "ctc"):
        val = _clean_str(body.get(key), key, limit=300)
        if val:
            fields[key] = val
    notes = _clean_str(body.get("notes"), "notes")
    if notes:
        fields["recommendation"] = notes
    url = _clean_str(body.get("url"), "url", limit=2000)
    if url:
        if not re.match(r"^https?://", url, re.I):
            raise ApiError(400, "url must start with http:// or https://")
        fields["urls"] = jt.norm_urls([url])
    with jt.jobs_lock():
        data = jt.load()
        job = jt.new_job(data, fields)
        data["jobs"].append(job)
        jt.save(data)
    return _full(job, jt.today())


def api_status(job_id: int, body: dict) -> dict:
    status = _clean_str(body.get("status"), "status", required=True)
    date = _clean_str(body.get("date"), "date") or jt.today()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ApiError(400, "date must be YYYY-MM-DD")
    force = bool(body.get("force"))
    with jt.jobs_lock():
        data = jt.load()
        job = _find(data, job_id)
        try:
            old = jt.apply_status(job, status, date, force=force)
        except jt.JobTrackError as e:
            raise ApiError(400, str(e)) from None
        if old is not None:
            jt.save(data)
    out = _full(job, jt.today())
    out["changed"] = old is not None
    out["previous_status"] = old
    return out


def api_archive(job_id: int, body: dict, archive: bool) -> dict:
    today = jt.today()
    with jt.jobs_lock():
        data = jt.load()
        job = _find(data, job_id)
        if archive:
            if job.get("archived"):
                raise ApiError(400, "already archived")
            if not jt.archive_eligible(job, today) and not body.get("force"):
                raise ApiError(400, f"not archive-eligible ({job['status']}) — "
                                    f"send force to archive anyway")
            jt.set_archived(job, True, today)
        else:
            jt.set_archived(job, False, None)
        jt.save(data)
    return _full(job, today)


def api_patch(job_id: int, body: dict) -> dict:
    if set(body) != {"recommendation"}:
        raise ApiError(400, "only the recommendation (notes) field can be edited here")
    notes = _clean_str(body.get("recommendation"), "recommendation")
    with jt.jobs_lock():
        data = jt.load()
        job = _find(data, job_id)
        job["recommendation"] = notes
        jt.save(data)
    return _full(job, jt.today())


def set_data_dir(path) -> None:
    """Point both stores (and their lockfiles) at another folder. interview_track
    reads jt.DATA_DIR at call time, so this covers it too."""
    path = Path(path)
    jt.DATA_DIR = path
    jt.JOBS_DATA = path / "jobs_data.json"
    jt.JOBS_LOCK = path / ".jobs.lock"


def make_demo_dir() -> Path:
    """Copy the sample stores into a fresh temp folder and return it."""
    tmp = Path(tempfile.mkdtemp(prefix="job-hunt-demo-"))
    for f in DEMO_DATA.glob("*.json"):
        shutil.copyfile(f, tmp / f.name)
    return tmp


# ── interviews ───────────────────────────────────────────────────────────────

def api_interviews() -> dict:
    data = it.load()
    ivs = sorted(data["interviews"], key=lambda i: i.get("last_date") or "", reverse=True)
    return {
        "interviews": ivs,
        "lessons": [dict(l, repeats=it.repeats(l)) for l in it.ranked_lessons(data)],
        "topics": it.topic_stats(data),
        "stats": it.stats(data),
    }


def api_interview(slug: str) -> dict:
    try:
        return it.find_interview(it.load(), slug)
    except jt.JobTrackError as e:
        raise ApiError(404, str(e)) from None


def api_lesson_status(lesson_id: str, body: dict) -> dict:
    status = _clean_str(body.get("status"), "status", required=True)
    with it.interviews_lock():
        data = it.load()
        try:
            lesson = it.set_lesson_status(data, lesson_id, status)
        except jt.JobTrackError as e:
            raise ApiError(404 if "no lesson" in str(e) else 400, str(e)) from None
        it.save(data)
    return dict(lesson, repeats=it.repeats(lesson))


# ── HTTP plumbing ────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    server_version = "JobTrackerUI/1.0"

    def log_message(self, fmt, *args):  # quieter console
        if getattr(self.server, "quiet", False):
            return
        sys.stderr.write("  %s %s\n" % (self.command, self.path))

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").strip().lower()
        if host.startswith("["):
            return False
        return host.rsplit(":", 1)[0] in ALLOWED_HOSTS

    def _send(self, status: int, payload, ctype="application/json; charset=utf-8"):
        body = payload if isinstance(payload, bytes) else \
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if ctype.startswith("text/html"):
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                             "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                             "connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            raise ApiError(415, "Content-Type must be application/json")
        length = int(self.headers.get("Content-Length") or 0)
        if length > 2_000_000:
            raise ApiError(413, "request too large")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(400, "body is not valid JSON") from None
        if not isinstance(body, dict):
            raise ApiError(400, "body must be a JSON object")
        return body

    def _dispatch(self, method: str):
        if not self._host_ok():
            return self._send(403, {"error": "forbidden host"})
        url = urlparse(self.path)
        path = url.path.rstrip("/") or "/"
        try:
            if method == "GET" and path in ("/", "/index.html"):
                return self._send(200, INDEX_HTML.read_bytes(), "text/html; charset=utf-8")
            if method == "GET" and path == "/api/jobs":
                return self._send(200, api_list(parse_qs(url.query)))
            if method == "GET" and path == "/api/stats":
                return self._send(200, api_stats())
            if method == "GET" and path == "/api/meta":
                return self._send(200, {"demo": bool(getattr(self.server, "demo", False))})
            if method == "GET" and path == "/api/interviews":
                return self._send(200, api_interviews())
            m = re.fullmatch(r"/api/interviews/([a-z0-9]+(?:-[a-z0-9]+)*)", path)
            if m and method == "GET":
                return self._send(200, api_interview(m.group(1)))
            m = re.fullmatch(r"/api/lessons/([a-z0-9]+(?:-[a-z0-9]+)*)/status", path)
            if m and method == "POST":
                return self._send(200, api_lesson_status(m.group(1), self._body()))
            if method == "POST" and path == "/api/jobs":
                return self._send(201, api_add(self._body()))
            m = re.fullmatch(r"/api/jobs/(\d+)(?:/(status|archive|unarchive))?", path)
            if m:
                job_id, action = int(m.group(1)), m.group(2)
                if method == "GET" and action is None:
                    return self._send(200, api_get(job_id))
                if method == "PATCH" and action is None:
                    return self._send(200, api_patch(job_id, self._body()))
                if method == "POST" and action == "status":
                    return self._send(200, api_status(job_id, self._body()))
                if method == "POST" and action in ("archive", "unarchive"):
                    return self._send(200, api_archive(job_id, self._body(),
                                                       action == "archive"))
            raise ApiError(404, "not found")
        except ApiError as e:
            return self._send(e.status, {"error": e.message})
        except TimeoutError as e:
            return self._send(503, {"error": str(e)})
        except SystemExit as e:  # job_track helpers exit on bad input / unreadable store
            return self._send(400, {"error": str(e.code)})

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PATCH(self):
        self._dispatch("PATCH")


def make_server(port: int = 8765, quiet: bool = False, demo: bool = False) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    srv.quiet = quiet
    srv.demo = demo
    return srv


def main():
    ap = argparse.ArgumentParser(description="Local web UI for the job tracker")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--open", action="store_true", help="open the browser")
    ap.add_argument("--demo", action="store_true",
                    help="serve sample data from a temp copy (data/ is never touched)")
    args = ap.parse_args()
    demo_dir = None
    if args.demo:
        demo_dir = make_demo_dir()
        set_data_dir(demo_dir)
    srv = make_server(args.port, demo=args.demo)
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    where = "DEMO — temp copy, deleted on exit" if args.demo else str(jt.DATA_DIR)
    print(f"Job tracker UI → {url}   (data: {where})   Ctrl+C to stop", flush=True)
    if args.open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        srv.server_close()
        if demo_dir:
            shutil.rmtree(demo_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
