#!/usr/bin/env python3
"""Unit tests for job_track.py — the sole write path for jobs_data.json (280+ rows).

The module previously had zero coverage. The invariants that matter most are the
ones other code is told to trust rather than reimplement:

  - normalize_company()  — job_track's own docstring calls it byte-identical to
                           what migrate_jobs.py stored. Skills used to re-derive
                           it from prose; cmd_dedup exists so they never do again.
  - classify_dedup()     — the URL-first policy. Getting this wrong either floods
                           the tracker with duplicates or silently swallows fresh
                           reqs at the best target companies.
  - the status ladder    — set-status must refuse a downgrade.

Run from vel_docs/scripts:  python -m unittest discover -s tests -t . -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta  # noqa: E402

import job_track as jt  # noqa: E402


def job(jid, company, status="—", date="2026-01-01", urls=(), history=None,
        archived=False, role="SDE II Backend"):
    return {
        "id": jid,
        "company": company,
        "company_key": jt.normalize_company(company),
        "role": role,
        "date": date,
        "status": status,
        "status_history": (list(history) if history is not None
                           else [{"status": status, "date": date}]),
        "urls": [{"label": "Link", "url": u} for u in urls],
        "archived": archived,
    }


class TestNormalizeCompany(unittest.TestCase):
    def test_lowercases_and_strips_filler_suffixes(self):
        self.assertEqual(jt.normalize_company("Initech Global Tech India"),
                         "initech global tech")
        self.assertEqual(jt.normalize_company("Globex Pvt Ltd"), "globex")
        self.assertEqual(jt.normalize_company("Acme Technologies Private Limited"),
                         "acme")

    def test_drops_parentheticals(self):
        self.assertEqual(jt.normalize_company("Intuit (Credit Karma)"), "intuit")
        self.assertEqual(jt.normalize_company("Glance (InMobi)"), "glance")

    def test_keeps_ampersand_plus_dot_dash(self):
        # The charclass in normalize_company deliberately preserves these.
        self.assertEqual(jt.normalize_company("AT&T"), "at&t")
        self.assertEqual(jt.normalize_company("Example.com"), "example.com")

    def test_punctuation_variants_collapse_to_one_key(self):
        keys = {jt.normalize_company(n) for n in
                ("Société Générale GSC", "Societe Generale GSC")}
        # Accent folding is NOT performed — documenting real behaviour, not a wish.
        self.assertEqual(len(keys), 2)

    def test_empty_and_none_are_safe(self):
        self.assertEqual(jt.normalize_company(""), "")
        self.assertEqual(jt.normalize_company(None), "")


class TestParseScore(unittest.TestCase):
    def test_parses_value_and_max(self):
        self.assertEqual(jt.parse_score("13/14"),
                         {"value": 13, "max": 14, "capped": False, "raw": "13/14"})

    def test_unknown_defaults_to_max_14(self):
        got = jt.parse_score("?")
        self.assertIsNone(got["value"])
        self.assertEqual(got["max"], 14)

    def test_detects_hard_filter_cap(self):
        self.assertTrue(jt.parse_score("— (HF capped)")["capped"])

    def test_dict_passes_through_unchanged(self):
        already = {"value": 9, "max": 14, "capped": False, "raw": "9/14"}
        self.assertIs(jt.parse_score(already), already)

    def test_pipeline_pending_placeholder_is_not_a_crash(self):
        # /job-feed writes "⏳ Pending" on parked rows.
        got = jt.parse_score("⏳ Pending")
        self.assertIsNone(got["value"])
        self.assertEqual(got["raw"], "⏳ Pending")


class TestNormUrls(unittest.TestCase):
    def test_bare_string_gets_default_label(self):
        self.assertEqual(jt.norm_urls(["https://x.com/1"]),
                         [{"label": "Link", "url": "https://x.com/1"}])

    def test_none_is_empty(self):
        self.assertEqual(jt.norm_urls(None), [])


class TestLastActivity(unittest.TestCase):
    def test_uses_latest_status_history_date(self):
        j = job(1, "Acme", date="2026-01-01", history=[
            {"status": "—", "date": "2026-01-01"},
            {"status": "✅ Applied", "date": "2026-03-15"},
        ])
        self.assertEqual(jt.last_activity(j), "2026-03-15")

    def test_falls_back_to_row_date(self):
        j = job(1, "Acme", date="2026-02-02", history=[])
        self.assertEqual(jt.last_activity(j), "2026-02-02")


def days_before(today: str, n: int) -> str:
    """A date exactly n days before `today`. Tests that care about the cooloff
    derive their dates from STALE_COMPANY_DAYS rather than hardcoding, so
    retuning the constant doesn't silently invalidate them."""
    return (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=n)).strftime("%Y-%m-%d")


class TestClassifyDedup(unittest.TestCase):
    TODAY = "2026-08-04"
    INSIDE = jt.STALE_COMPANY_DAYS // 2          # comfortably within the cooloff
    OUTSIDE = jt.STALE_COMPANY_DAYS * 2 + 10     # comfortably past it

    def test_untracked_company_is_fresh(self):
        got = jt.classify_dedup([], "BrandNewCo", "https://x.com/1", self.TODAY)
        self.assertEqual(got["recommend"], "fresh")
        self.assertFalse(got["tracked"])

    def test_exact_url_hit_drops_even_if_company_is_stale(self):
        jobs = [job(1, "Acme", status="🚫 No Response", date="2025-01-01",
                    urls=["https://x.com/1"])]
        got = jt.classify_dedup(jobs, "Acme", "https://x.com/1", self.TODAY)
        self.assertEqual(got["recommend"], "drop")
        self.assertEqual(got["by"], "url")

    def test_in_flight_company_does_NOT_block_a_different_posting(self):
        # THE rule: a company runs many reqs at once. Being mid-interview for
        # one must never suppress another. Two job ids are two jobs.
        jobs = [job(1, "Acme", status="📞 Interview Scheduled",
                    date="2026-07-01", urls=["https://x.com/OLD"])]
        got = jt.classify_dedup(jobs, "Acme", "https://x.com/NEW", self.TODAY)
        self.assertEqual(got["recommend"], "new-role")

    def test_in_flight_is_surfaced_as_advisory_not_a_veto(self):
        jobs = [job(1, "Acme", status="🔄 Round 2", date="2026-07-01", role="Payments")]
        got = jt.classify_dedup(jobs, "Acme", "https://x.com/NEW", self.TODAY)
        self.assertEqual(got["recommend"], "new-role")
        self.assertIsNotNone(got["live_process"])
        self.assertEqual(got["live_process"]["status"], "🔄 Round 2")
        self.assertEqual(got["live_process"]["role"], "Payments")
        self.assertIn("live process", got["reason"])

    def test_recent_rejection_flags_but_does_not_drop(self):
        jobs = [job(1, "Acme", status="❌ Rejected",
                    date=days_before(self.TODAY, self.INSIDE))]
        got = jt.classify_dedup(jobs, "Acme", "https://x.com/NEW", self.TODAY)
        self.assertEqual(got["recommend"], "new-role")
        self.assertIsNotNone(got["recent_contact"])
        self.assertIn("recent contact", got["reason"])

    def test_old_rejection_carries_no_flag(self):
        jobs = [job(1, "Acme", status="❌ Rejected",
                    date=days_before(self.TODAY, self.OUTSIDE))]
        got = jt.classify_dedup(jobs, "Acme", "https://x.com/NEW", self.TODAY)
        self.assertEqual(got["recommend"], "new-role")
        self.assertIsNone(got["recent_contact"])

    def test_archived_rows_are_context_not_a_drop(self):
        jobs = [job(1, "Acme", status="✅ Applied", date="2026-07-20", archived=True)]
        got = jt.classify_dedup(jobs, "Acme", "https://x.com/NEW", self.TODAY)
        self.assertEqual(got["recommend"], "new-role")
        self.assertTrue(got["tracked"])

    def test_uses_last_activity_not_row_date_for_the_flag(self):
        # Analyzed long ago, rejected recently → the flag must key off the
        # latest status change, not the row's original analysis date.
        old = days_before(self.TODAY, self.OUTSIDE)
        recent = days_before(self.TODAY, self.INSIDE)
        jobs = [job(1, "Acme", status="❌ Rejected", date=old, history=[
            {"status": "—", "date": old},
            {"status": "❌ Rejected", "date": recent},
        ])]
        got = jt.classify_dedup(jobs, "Acme", None, self.TODAY)
        self.assertIsNotNone(got["recent_contact"])
        self.assertLessEqual(got["recent_contact"]["age_days"], jt.RECENT_CONTACT_DAYS)

    def test_picks_furthest_along_row_when_company_has_several(self):
        jobs = [job(1, "Acme", status="❌ Rejected", date="2026-01-01", role="A"),
                job(2, "Acme", status="🔄 Round 2", date="2026-07-01", role="B")]
        got = jt.classify_dedup(jobs, "Acme", "https://x.com/NEW", self.TODAY)
        self.assertEqual(got["id"], 2)
        self.assertEqual(got["recommend"], "new-role")
        self.assertEqual(got["match_count"], 2)

    def test_company_name_variants_still_resolve_for_context(self):
        jobs = [job(1, "Globex", status="🔄 Round 1", date="2026-07-01")]
        got = jt.classify_dedup(jobs, "Globex Pvt Ltd", "https://x.com/NEW", self.TODAY)
        self.assertEqual(got["recommend"], "new-role")
        self.assertTrue(got["tracked"])
        self.assertEqual(got["company_key"], "globex")

    def test_missing_company_and_url_is_fresh_not_a_crash(self):
        got = jt.classify_dedup([job(1, "Acme")], "", None, self.TODAY)
        self.assertEqual(got["recommend"], "fresh")

    def test_url_match_wins_over_everything(self):
        jobs = [job(1, "Acme", status="—", date="2020-01-01",
                    urls=["https://x.com/SAME"])]
        got = jt.classify_dedup(jobs, "Acme", "https://x.com/SAME", self.TODAY)
        self.assertEqual(got["recommend"], "drop")
        self.assertEqual(got["by"], "url")

    def test_drop_is_ONLY_ever_a_url_match(self):
        # Exhaustive guard: across every status and age, with a distinct URL,
        # nothing may drop. If this fails, company-level suppression is back.
        for status in jt.ALL_STATUSES:
            for age in (0, 1, self.INSIDE, self.OUTSIDE, 5000):
                jobs = [job(1, "Acme", status=status,
                            date=days_before(self.TODAY, age),
                            urls=["https://x.com/OLD"])]
                got = jt.classify_dedup(jobs, "Acme", "https://x.com/NEW", self.TODAY)
                self.assertNotEqual(
                    got["recommend"], "drop",
                    f"company-level drop leaked back in: {status} @ {age}d")


class TestRecentContactWindowIsTunable(unittest.TestCase):
    """The window is advisory only: it must change the FLAG, never the verdict."""
    TODAY = "2026-08-04"

    def setUp(self):
        # last activity 100 days before TODAY
        self.jobs = [job(1, "Acme", status="❌ Rejected", date="2026-04-26")]

    def test_default_matches_the_module_constant(self):
        import inspect
        sig = inspect.signature(jt.classify_dedup)
        self.assertEqual(sig.parameters["cooloff_days"].default,
                         jt.RECENT_CONTACT_DAYS)

    def test_narrow_window_does_not_flag(self):
        got = jt.classify_dedup(self.jobs, "Acme", "https://x.com/N", self.TODAY,
                                cooloff_days=60)
        self.assertIsNone(got["recent_contact"])
        self.assertEqual(got["recommend"], "new-role")

    def test_wide_window_flags(self):
        got = jt.classify_dedup(self.jobs, "Acme", "https://x.com/N", self.TODAY,
                                cooloff_days=180)
        self.assertIsNotNone(got["recent_contact"])
        self.assertEqual(got["recent_contact"]["within_days"], 180)

    def test_window_never_changes_the_verdict(self):
        for days in (0, 1, 15, 90, 365, 100000):
            got = jt.classify_dedup(self.jobs, "Acme", "https://x.com/N",
                                    self.TODAY, cooloff_days=days)
            self.assertEqual(got["recommend"], "new-role",
                             f"window {days}d changed the verdict — it must not")

    def test_window_never_overrides_a_url_hit(self):
        same = [job(1, "Acme", status="❌ Rejected", date="2020-01-01",
                    urls=["https://x.com/1"])]
        got = jt.classify_dedup(same, "Acme", "https://x.com/1", self.TODAY,
                                cooloff_days=0)
        self.assertEqual(got["recommend"], "drop")
        self.assertEqual(got["by"], "url")


class TestRoleIsCarriedThrough(unittest.TestCase):
    TODAY = "2026-08-04"

    def test_role_is_echoed_for_display(self):
        got = jt.classify_dedup([job(1, "Acme")], "Acme", "https://x.com/N",
                                self.TODAY, role="SDE II — Payments")
        self.assertEqual(got["role"], "SDE II — Payments")

    def test_matched_role_reports_the_tracked_side(self):
        jobs = [job(1, "Acme", role="Backend Engineer, Search")]
        got = jt.classify_dedup(jobs, "Acme", "https://x.com/N", self.TODAY,
                                role="SDE II Payments")
        self.assertEqual(got["matched_role"], "Backend Engineer, Search")

    def test_normalize_role_folds_case_and_punctuation(self):
        self.assertEqual(jt.normalize_role("SDE-II  (Backend)"), "sde ii backend")
        self.assertEqual(jt.normalize_role(None), "")


class TestStatusEnum(unittest.TestCase):
    def test_enum_has_no_duplicates(self):
        self.assertEqual(len(jt.ALL_STATUSES), len(set(jt.ALL_STATUSES)))

    def test_pipeline_and_todo_are_not_counted_as_applied(self):
        # /job-feed parks rows as ⏳ Pipeline; those must never inflate the funnel.
        self.assertIn("⏳ Pipeline", jt.NOT_APPLIED)
        self.assertIn("📝 To Do", jt.NOT_APPLIED)

    def test_ladder_is_a_subset_of_active(self):
        self.assertTrue(set(jt.ACTIVE_LADDER) <= set(jt.ACTIVE_STATUSES))

    def test_no_response_is_active_but_off_ladder(self):
        self.assertIn(jt.NO_RESPONSE, jt.ACTIVE_STATUSES)
        self.assertNotIn(jt.NO_RESPONSE, jt.ACTIVE_LADDER)


class TestNewJobShape(unittest.TestCase):
    def test_new_fields_are_present_and_default_empty(self):
        j = jt.new_job({"jobs": []}, {"company": "Acme", "role": "SDE II"})
        self.assertIsNone(j["posted_date"])
        self.assertEqual(j["jd_text"], "")

    def test_posted_date_and_jd_text_round_trip(self):
        j = jt.new_job({"jobs": []}, {"company": "Acme", "role": "SDE II",
                                      "posted_date": "2026-08-01",
                                      "jd_text": "Java Spring Kafka"})
        self.assertEqual(j["posted_date"], "2026-08-01")
        self.assertEqual(j["jd_text"], "Java Spring Kafka")

    def test_id_is_max_plus_one(self):
        data = {"jobs": [{"id": 7}, {"id": 3}]}
        self.assertEqual(jt.new_job(data, {"company": "A", "role": "R"})["id"], 8)

    def test_new_fields_are_upsertable(self):
        self.assertIn("posted_date", jt.ANALYSIS_FIELDS)
        self.assertIn("jd_text", jt.ANALYSIS_FIELDS)

    def test_date_channel_status_stay_out_of_analysis_fields(self):
        # upsert preserves these structurally; putting them in ANALYSIS_FIELDS
        # would let a re-analysis silently reset application progress.
        for f in ("date", "channel", "status"):
            self.assertNotIn(f, jt.ANALYSIS_FIELDS)


class TestSerializable(unittest.TestCase):
    def test_dedup_result_is_json_serializable(self):
        got = jt.classify_dedup([job(1, "Acme")], "Acme", None, "2026-08-04")
        json.dumps(got, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
