#!/usr/bin/env python3
"""Tests for interview_track.py — the interview debrief log.

The rule that matters most: a lesson's repeats (seen_in) are only ever ADDED
to. That count is the whole point of the log — it shows a habit.

Run from scripts/:  python3 -m unittest tests.test_interview_track
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import job_track as jt  # noqa: E402
import interview_track as it  # noqa: E402


def fresh():
    return {"version": 1, "lessons": [], "interviews": []}


ROUND = {"name": "Round 1", "date": "2026-03-02", "format": "DSA",
         "interviewer": "Senior engineer", "result": "passed",
         "questions": [{"q": "Two sum variant", "topic": "Arrays",
                        "my_answer": "Hash map", "better_answer": "Hash map, O(n)",
                        "verdict": "🟢"}],
         "went_well": ["Talked through the approach"], "went_wrong": []}


class TestAddInterview(unittest.TestCase):
    def test_add_and_dates_from_rounds(self):
        d = fresh()
        iv = it.add_interview(d, {"slug": "acme-backend", "company": "Acme",
                                  "role": "Backend Engineer", "rounds": [ROUND]})
        self.assertEqual(iv["first_date"], "2026-03-02")
        self.assertEqual(iv["last_date"], "2026-03-02")
        self.assertEqual(iv["outcome"], "in-progress")
        self.assertEqual(iv["stage_reached"], "Round 1")

    def test_duplicate_slug_fails(self):
        d = fresh()
        it.add_interview(d, {"slug": "acme", "company": "Acme", "role": "SWE"})
        with self.assertRaises(jt.JobTrackError):
            it.add_interview(d, {"slug": "acme", "company": "Acme", "role": "SWE"})

    def test_bad_slug_and_enums(self):
        d = fresh()
        with self.assertRaises(jt.JobTrackError):
            it.add_interview(d, {"slug": "Acme Backend", "company": "A", "role": "B"})
        with self.assertRaises(jt.JobTrackError):
            it.add_interview(d, {"slug": "a", "company": "A", "role": "B", "outcome": "won"})
        bad = dict(ROUND, questions=[{"q": "x", "verdict": "ok"}])
        with self.assertRaises(jt.JobTrackError):
            it.add_interview(d, {"slug": "a", "company": "A", "role": "B", "rounds": [bad]})
        with self.assertRaises(jt.JobTrackError):
            it.add_interview(d, {"slug": "a", "company": "A", "role": "B", "nope": 1})

    def test_add_round_updates_dates_and_stage(self):
        d = fresh()
        it.add_interview(d, {"slug": "acme", "company": "Acme", "role": "SWE", "rounds": [ROUND]})
        it.add_round(d, "acme", dict(ROUND, name="System design", date="2026-03-09",
                                     result="failed"))
        iv = it.find_interview(d, "acme")
        self.assertEqual(iv["last_date"], "2026-03-09")
        self.assertEqual(iv["stage_reached"], "System design")
        self.assertEqual(len(iv["rounds"]), 2)


class TestLessons(unittest.TestCase):
    def setUp(self):
        self.d = fresh()
        for s in ("acme", "globex"):
            it.add_interview(self.d, {"slug": s, "company": s.title(), "role": "SWE"})

    def test_upsert_creates_then_merges_repeats(self):
        lesson, created = it.lesson_upsert(self.d, {
            "id": "ask-questions", "title": "Ask each interviewer a question",
            "category": "communication", "seen_in": "acme"})
        self.assertTrue(created)
        self.assertEqual(it.repeats(lesson), 1)
        lesson, created = it.lesson_upsert(self.d, {"id": "ask-questions", "seen_in": ["globex"]})
        self.assertFalse(created)
        self.assertEqual(lesson["seen_in"], ["acme", "globex"])
        # same slug again is not a new repeat
        it.lesson_upsert(self.d, {"id": "ask-questions", "seen_in": "acme"})
        self.assertEqual(it.repeats(lesson), 2)
        self.assertIn("ask-questions", it.find_interview(self.d, "globex")["lessons"])

    def test_merge_never_drops_seen_in(self):
        it.lesson_upsert(self.d, {"id": "x", "title": "X", "seen_in": ["acme", "globex"]})
        lesson, _ = it.lesson_upsert(self.d, {"id": "x", "detail": "more", "seen_in": []})
        self.assertEqual(it.repeats(lesson), 2)

    def test_new_lesson_needs_title_and_known_slug(self):
        with self.assertRaises(jt.JobTrackError):
            it.lesson_upsert(self.d, {"id": "x"})
        with self.assertRaises(jt.JobTrackError):
            it.lesson_upsert(self.d, {"id": "x", "title": "X", "seen_in": "nope"})
        with self.assertRaises(jt.JobTrackError):
            it.lesson_upsert(self.d, {"id": "x", "title": "X", "category": "luck"})

    def test_ranked_by_repeats_and_open_filter(self):
        it.lesson_upsert(self.d, {"id": "once", "title": "Once", "seen_in": "acme"})
        it.lesson_upsert(self.d, {"id": "twice", "title": "Twice", "seen_in": ["acme", "globex"]})
        it.lesson_upsert(self.d, {"id": "fixed", "title": "Fixed", "status": "fixed",
                                  "seen_in": ["acme", "globex"]})
        self.assertEqual([l["id"] for l in it.ranked_lessons(self.d)], ["twice", "fixed", "once"])
        self.assertEqual([l["id"] for l in it.ranked_lessons(self.d, open_only=True)],
                         ["twice", "once"])

    def test_interview_referencing_unknown_lesson_fails(self):
        with self.assertRaises(jt.JobTrackError):
            it.add_interview(self.d, {"slug": "z", "company": "Z", "role": "R",
                                      "lessons": ["missing"]})


class TestStats(unittest.TestCase):
    def test_topics_and_stats(self):
        d = fresh()
        r2 = dict(ROUND, result="failed", questions=[
            {"q": "Design a URL shortener", "topic": "System design", "verdict": "🔴"},
            {"q": "Two sum again", "topic": "Arrays", "verdict": "🟡"}])
        it.add_interview(d, {"slug": "a", "company": "A", "role": "R", "rounds": [ROUND, r2]})
        topics = {t["topic"]: t for t in it.topic_stats(d)}
        self.assertEqual(topics["Arrays"]["asked"], 2)
        self.assertEqual(topics["System design"]["red_share"], 100)
        s = it.stats(d)
        self.assertEqual((s["rounds"], s["rounds_passed"], s["rounds_failed"]), (2, 1, 1))
        self.assertEqual(s["verdicts"]["🔴"], 1)


class TestCli(unittest.TestCase):
    """End to end through the real CLI against a temp data dir."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = dict(os.environ, JOB_HUNT_DATA_DIR=self.tmp.name, PYTHONIOENCODING="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, stdin=None, ok=True):
        p = subprocess.run([sys.executable, str(SCRIPTS / "interview_track.py"), *args],
                           input=stdin, capture_output=True, text=True, env=self.env,
                           encoding="utf-8")
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def test_round_trip_and_file_format(self):
        self.run_cli("add-interview", stdin=json.dumps(
            {"slug": "acme", "company": "Acme", "role": "SWE", "rounds": [ROUND]}))
        self.run_cli("lesson-upsert", stdin=json.dumps(
            {"id": "slow-down", "title": "Slow down", "seen_in": "acme"}))
        self.run_cli("set-outcome", "acme", "rejected")
        p = self.run_cli("lessons", "--json")
        self.assertEqual(json.loads(p.stdout)[0]["repeats"], 1)
        raw = Path(self.tmp.name, "interviews_data.json").read_bytes()
        self.assertTrue(raw.endswith(b"}\n"))
        self.assertNotIn(b"\r\n", raw)
        dup = self.run_cli("add-interview", stdin=json.dumps(
            {"slug": "acme", "company": "Acme", "role": "SWE"}), ok=False)
        self.assertNotEqual(dup.returncode, 0)

    def test_link_job_must_exist(self):
        p = self.run_cli("add-interview", "--link-job", "99", stdin=json.dumps(
            {"slug": "acme", "company": "Acme", "role": "SWE"}), ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("no job with id 99", p.stderr)


if __name__ == "__main__":
    unittest.main()
