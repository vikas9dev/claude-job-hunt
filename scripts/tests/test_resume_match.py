#!/usr/bin/env python3
"""Unit tests for resume_match — the JD ↔ resume keyword score.

Run from scripts/:  python3 -m unittest tests.test_resume_match

The score is only useful if it is stable and does not lie in either direction:
no match inside a longer word, no double count from aliases, and no "match"
from a word an ATS search would not treat as the same keyword.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import resume_match as rm  # noqa: E402


class FindTerms(unittest.TestCase):
    def test_java_not_inside_javascript(self):
        hits = rm.find_terms("We use JavaScript on the front end.")
        self.assertNotIn("Java", hits)
        self.assertIn("JavaScript", hits)

    def test_cpp_keeps_plus_signs(self):
        self.assertIn("C++", rm.find_terms("Strong C++ skills"))
        self.assertNotIn("C++", rm.find_terms("Grade C student"))

    def test_alias_same_as_name_counts_once(self):
        self.assertEqual(rm.find_terms("gRPC services")["gRPC"], 1)

    def test_longest_form_wins(self):
        hits = rm.find_terms("Strong data structures and algorithms")
        self.assertEqual(hits["Data Structures"], 1)

    def test_bare_go_is_not_golang(self):
        self.assertNotIn("Golang", rm.find_terms("Go live in two weeks"))
        self.assertIn("Golang", rm.find_terms("Golang microservices"))

    def test_spring_not_double_counted_with_spring_boot(self):
        hits = rm.find_terms("Spring Boot and Spring Boot")
        self.assertEqual(hits["Spring Boot"], 2)
        self.assertNotIn("Spring", hits)

    def test_phrase_across_line_break(self):
        self.assertIn("High Availability", rm.find_terms("auto-scaling and high\navailability"))

    def test_english_words_are_not_frameworks(self):
        hits = rm.find_terms("Please express interest; we add guard rails")
        self.assertNotIn("Express.js", hits)
        self.assertNotIn("Ruby on Rails", hits)

    def test_ruby_not_double_counted_with_rails(self):
        hits = rm.find_terms("Ruby on Rails")
        self.assertEqual(hits["Ruby on Rails"], 1)
        self.assertNotIn("Ruby", hits)

    def test_spelling_variant_matches(self):
        self.assertIn("Kubernetes", rm.find_terms("Deployed on K8s"))
        self.assertIn("PostgreSQL", rm.find_terms("Postgres tuning"))


class Score(unittest.TestCase):
    JD = (
        "Backend Engineer\n"
        "Requirements:\n"
        "- 5+ years of Java and Redis\n"
        "Nice to have:\n"
        "- Cassandra\n"
    )

    def test_required_weighs_double(self):
        res = rm.score(self.JD, "Java developer")
        # Java (2) found, Redis (2) and Cassandra (1) missing -> 2/5
        self.assertEqual(res["score"], 40)
        self.assertEqual(res["missing_required"], ["Redis"])
        self.assertEqual(res["missing_other"], ["Cassandra"])

    def test_related_word_is_not_a_match(self):
        res = rm.score(self.JD, "Java, AWS ElastiCache")
        redis = next(r for r in res["terms"] if r["term"] == "Redis")
        self.assertFalse(redis["matched"])
        self.assertEqual(redis["related_evidence"], ["elasticache"])

    def test_years(self):
        self.assertEqual(rm.score(self.JD, "")["jd_years"], [5])

    def test_years_ignore_longer_numbers(self):
        self.assertEqual(rm.jd_years("To become a 100 year company. 4+ years of Java."), [4])

    def test_empty_jd_scores_zero(self):
        self.assertEqual(rm.score("Nothing technical here.", "Java")["score"], 0)

    def test_stable(self):
        self.assertEqual(rm.score(self.JD, "Java Redis"), rm.score(self.JD, "Java Redis"))


class ReadText(unittest.TestCase):
    def test_html_drops_style_and_keeps_text(self):
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write("<html><head><style>.java{}</style></head><body><li>Kafka &amp; Redis</li></body></html>")
        try:
            text = rm.read_text(f.name)
        finally:
            os.unlink(f.name)
        self.assertIn("Kafka & Redis", text)
        self.assertNotIn(".java", text)


class PdfName(unittest.TestCase):
    def _write(self, d, body):
        p = os.path.join(d, "r.html")
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)
        return p

    def test_name_from_h1(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._write(d, "<html><body><h1> Jane  Doe </h1></body></html>")
            self.assertEqual(rm.pdf_name_for(p), "Jane Doe - Resume.pdf")

    def test_unsafe_chars_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._write(d, "<h1>A/B: <b>C</b></h1>")
            self.assertEqual(rm.pdf_name_for(p), "AB C - Resume.pdf")

    def test_fallback_without_h1_or_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._write(d, "<p>no heading</p>")
            self.assertEqual(rm.pdf_name_for(p), "Resume.pdf")
            self.assertEqual(rm.pdf_name_for(os.path.join(d, "missing.html")), "Resume.pdf")


class Init(unittest.TestCase):
    def test_init_copies_master_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            master = os.path.join(d, "master.html")
            with open(master, "w", encoding="utf-8") as f:
                f.write("<h1>Jane Doe</h1>")
            old = (rm.MASTER_HTML, rm.TAILORED_DIR)
            rm.MASTER_HTML, rm.TAILORED_DIR = master, os.path.join(d, "tailored")
            try:
                rm.main(["init", "--slug", "Acme Backend!"])
                dest = os.path.join(d, "tailored", "acme-backend", "resume.html")
                self.assertTrue(os.path.exists(dest))
                with self.assertRaises(SystemExit):
                    rm.main(["init", "--slug", "acme-backend"])
                with open(master, encoding="utf-8") as f:
                    self.assertEqual(f.read(), "<h1>Jane Doe</h1>")
            finally:
                rm.MASTER_HTML, rm.TAILORED_DIR = old

    def test_init_without_master_explains_template(self):
        with tempfile.TemporaryDirectory() as d:
            old = (rm.MASTER_HTML, rm.TAILORED_DIR)
            rm.MASTER_HTML, rm.TAILORED_DIR = os.path.join(d, "master.html"), os.path.join(d, "t")
            try:
                with self.assertRaises(SystemExit) as cm:
                    rm.main(["init", "--slug", "acme"])
                self.assertIn("master.template.html", str(cm.exception.code))
                self.assertFalse(os.path.exists(os.path.join(d, "t")))
            finally:
                rm.MASTER_HTML, rm.TAILORED_DIR = old


if __name__ == "__main__":
    unittest.main()
