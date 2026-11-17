#!/usr/bin/env python3
"""End-to-end tests for ui/server.py against a throwaway data folder.

Run from scripts/:  python3 -m unittest tests.test_ui_server
"""
from __future__ import annotations

import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

_TMP = tempfile.TemporaryDirectory()
os.environ["JOB_HUNT_DATA_DIR"] = _TMP.name  # must be set BEFORE job_track is imported

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "ui"))

import server  # noqa: E402

# If another test module imported job_track first, the env var came too late:
# point the module at the temp folder directly.
if str(server.jt.DATA_DIR) != _TMP.name:
    server.jt.DATA_DIR = Path(_TMP.name)
    server.jt.JOBS_DATA = server.jt.DATA_DIR / "jobs_data.json"
    server.jt.JOBS_LOCK = server.jt.DATA_DIR / ".jobs.lock"


class TestUiServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert str(server.jt.DATA_DIR) == _TMP.name, server.jt.DATA_DIR
        cls.srv = server.make_server(0, quiet=True)
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        _TMP.cleanup()

    def req(self, method, path, body=None, host=None, ctype="application/json"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Host": host or f"127.0.0.1:{self.port}"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = ctype
        conn.request(method, path, body=data, headers=headers)
        res = conn.getresponse()
        raw = res.read()
        conn.close()
        try:
            return res.status, json.loads(raw)
        except json.JSONDecodeError:
            return res.status, raw.decode()

    def test_full_flow(self):
        # index page
        st, page = self.req("GET", "/")
        self.assertEqual(st, 200)
        self.assertIn("Job Tracker", page)

        # add
        st, job = self.req("POST", "/api/jobs", {
            "company": "Acme Corp", "role": "Backend Engineer",
            "url": "https://example.com/jobs/1", "status": "📝 To Do",
            "channel": "LinkedIn", "notes": "looks good"})
        self.assertEqual(st, 201, job)
        jid = job["id"]
        self.assertEqual(job["recommendation"], "looks good")
        self.assertEqual(job["urls"], [{"label": "Link", "url": "https://example.com/jobs/1"}])

        # a second req at the same company is allowed
        st, job2 = self.req("POST", "/api/jobs", {"company": "Acme Corp", "role": "SDE II"})
        self.assertEqual(st, 201, job2)
        self.assertEqual(job2["status"], "—")

        # list (light rows)
        st, lst = self.req("GET", "/api/jobs?view=open")
        self.assertEqual(st, 200)
        self.assertEqual(len(lst["jobs"]), 2)
        self.assertNotIn("jd_text", lst["jobs"][0])
        self.assertNotIn("analysis_md", lst["jobs"][0])
        self.assertIn("archive_reason", lst["jobs"][0])
        self.assertIn("⏳ Pipeline", lst["statuses"]["active"])
        self.assertIn("🚫 No Response", lst["statuses"]["active"])
        self.assertIn("❌ Rejected", lst["statuses"]["terminal"])

        # full row
        st, full = self.req("GET", f"/api/jobs/{jid}")
        self.assertEqual(st, 200)
        self.assertIn("jd_text", full)

        # status up the ladder
        st, res = self.req("POST", f"/api/jobs/{jid}/status", {"status": "🔄 Round 1"})
        self.assertEqual(st, 200, res)
        self.assertEqual(res["status"], "🔄 Round 1")
        self.assertTrue(res["changed"])

        # refused downgrade
        st, res = self.req("POST", f"/api/jobs/{jid}/status", {"status": "✅ Applied"})
        self.assertEqual(st, 400)
        self.assertIn("downgrade", res["error"])

        # unknown status
        st, res = self.req("POST", f"/api/jobs/{jid}/status", {"status": "bogus"})
        self.assertEqual(st, 400)

        # forced downgrade works
        st, res = self.req("POST", f"/api/jobs/{jid}/status",
                           {"status": "✅ Applied", "force": True})
        self.assertEqual(st, 200, res)

        # archive refused (in flight, fresh) …
        st, res = self.req("POST", f"/api/jobs/{jid}/archive", {})
        self.assertEqual(st, 400)
        self.assertIn("not archive-eligible", res["error"])
        # … forced archive works
        st, res = self.req("POST", f"/api/jobs/{jid}/archive", {"force": True})
        self.assertEqual(st, 200, res)
        self.assertTrue(res["archived"])
        st, lst = self.req("GET", "/api/jobs?view=archived")
        self.assertEqual([j["id"] for j in lst["jobs"]], [jid])

        # unarchive
        st, res = self.req("POST", f"/api/jobs/{jid}/unarchive", {})
        self.assertEqual(st, 200)
        self.assertFalse(res["archived"])

        # an eligible archive (terminal status) needs no force
        self.req("POST", f"/api/jobs/{job2['id']}/status", {"status": "⏭️ Skipped"})
        st, res = self.req("POST", f"/api/jobs/{job2['id']}/archive", {})
        self.assertEqual(st, 200, res)

        # notes edit, and only notes
        st, res = self.req("PATCH", f"/api/jobs/{jid}", {"recommendation": "call back Mon"})
        self.assertEqual(st, 200)
        self.assertEqual(res["recommendation"], "call back Mon")
        st, _ = self.req("PATCH", f"/api/jobs/{jid}", {"status": "🎉 Offer"})
        self.assertEqual(st, 400)

        # stats
        st, s = self.req("GET", "/api/stats")
        self.assertEqual(st, 200)
        self.assertEqual(s["tracked"], 2)
        self.assertEqual(s["applied"], 1)      # Skipped job2 never applied
        self.assertEqual(s["responses"], 1)    # Round 1 was reached
        self.assertEqual(s["interviews"], 1)
        self.assertEqual(s["offers"], 0)

    def test_validation_and_guards(self):
        st, _ = self.req("POST", "/api/jobs", {"company": "X"})
        self.assertEqual(st, 400)
        st, _ = self.req("POST", "/api/jobs", {"company": "X", "role": "Y", "url": "javascript:alert(1)"})
        self.assertEqual(st, 400)
        st, _ = self.req("POST", "/api/jobs", {"company": "X", "role": "Y", "status": "nope"})
        self.assertEqual(st, 400)
        st, _ = self.req("POST", "/api/jobs", {"company": "X", "role": "Y"}, ctype="text/plain")
        self.assertEqual(st, 415)
        st, _ = self.req("GET", "/api/jobs", host="evil.example.com")
        self.assertEqual(st, 403)
        st, _ = self.req("GET", "/api/jobs/99999")
        self.assertEqual(st, 404)
        st, _ = self.req("GET", "/api/jobs?view=bogus")
        self.assertEqual(st, 400)

    def test_meta_is_not_demo(self):
        st, m = self.req("GET", "/api/meta")
        self.assertEqual((st, m), (200, {"demo": False}))

    def test_interviews_endpoints(self):
        it = server.it
        with it.interviews_lock():
            d = it.load()
            it.add_interview(d, {"slug": "acme-swe", "company": "Acme", "role": "SWE",
                                 "rounds": [{"name": "Round 1", "date": "2026-03-02",
                                             "result": "failed",
                                             "questions": [{"q": "Design a cache", "topic": "System design",
                                                            "verdict": "🔴"}]}]})
            it.lesson_upsert(d, {"id": "estimate-first", "title": "Estimate first",
                                 "seen_in": "acme-swe"})
            it.save(d)
        st, body = self.req("GET", "/api/interviews")
        self.assertEqual(st, 200)
        self.assertEqual(body["stats"]["interviews"], 1)
        self.assertEqual(body["lessons"][0]["repeats"], 1)
        self.assertEqual(body["topics"][0]["red_share"], 100)
        st, iv = self.req("GET", "/api/interviews/acme-swe")
        self.assertEqual((st, iv["company"]), (200, "Acme"))
        st, _ = self.req("GET", "/api/interviews/nope")
        self.assertEqual(st, 404)
        st, l = self.req("POST", "/api/lessons/estimate-first/status", {"status": "fixed"})
        self.assertEqual((st, l["status"]), (200, "fixed"))
        st, _ = self.req("POST", "/api/lessons/estimate-first/status", {"status": "done"})
        self.assertEqual(st, 400)
        st, _ = self.req("POST", "/api/lessons/missing/status", {"status": "open"})
        self.assertEqual(st, 404)
        st, _ = self.req("POST", "/api/lessons/estimate-first/status", {"status": "open"},
                         ctype="text/plain")
        self.assertEqual(st, 415)


class TestDemoData(unittest.TestCase):
    """examples/demo_data must load through the real code paths."""

    def test_demo_copy_loads_and_is_isolated(self):
        demo = server.make_demo_dir()
        try:
            self.assertNotEqual(demo.resolve(), (REPO / "data").resolve())
            jobs = server.jt._load_json(demo / "jobs_data.json", None)
            ivs = server.jt._load_json(demo / "interviews_data.json", None)
            self.assertGreaterEqual(len(jobs["jobs"]), 10)
            for j in jobs["jobs"]:
                self.assertIn(j["status"], server.jt.ALL_STATUSES, j["company"])
            self.assertEqual(len(ivs["interviews"]), 2)
            slugs = {i["slug"] for i in ivs["interviews"]}
            for l in ivs["lessons"]:
                self.assertTrue(set(l["seen_in"]) <= slugs, l["id"])
            self.assertTrue(any(len(l["seen_in"]) >= 2 for l in ivs["lessons"]))
            for i in ivs["interviews"]:
                if i["job_id"] is not None:
                    self.assertTrue(any(j["id"] == i["job_id"] for j in jobs["jobs"]))
        finally:
            import shutil
            shutil.rmtree(demo, ignore_errors=True)



if __name__ == "__main__":
    unittest.main()
