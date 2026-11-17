#!/usr/bin/env python3
"""resume_match.py — deterministic JD ↔ resume keyword score + resume PDF render.

Used by the /resume-check and /resume-tailor skills. The score is a keyword
proxy, the same idea as Jobscan: which hard skills the JD names, and how many
of them the resume also names. It is NOT a fit verdict — /job-match does that.

The vocabulary is fixed (VOCAB below), so the same JD + resume always gives the
same number, and scores can be compared across jobs and across edits. A term
the JD uses that is not in VOCAB is not scored; the skill lists those by hand.

    python resume_match.py score --jd jd.txt --resume resume.pdf [--json]
    python resume_match.py init  --slug acme-backend [--force]
    python resume_match.py render <resume.html> <out.pdf>

`init` copies resume/master.html into resume/tailored/<slug>/ and is the only
sanctioned way to start a tailored resume: the master is never edited by the
skills. `render` prints an HTML resume to PDF with headless Chrome/Edge and
reports the page count.

Start your master from resume/master.template.html (copy it to
resume/master.html and fill it in, or run /setup-profile).
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser

import console_utf8  # noqa: F401  (side effect: UTF-8 console on Windows)

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPTS_DIR)
RESUME_DIR = os.path.join(REPO_ROOT, "resume")
MASTER_HTML = os.path.join(RESUME_DIR, "master.html")
TEMPLATE_HTML = os.path.join(RESUME_DIR, "master.template.html")
TAILORED_DIR = os.path.join(RESUME_DIR, "tailored")
DEFAULT_PDF_NAME = "Resume.pdf"

# canonical term -> (category, [aliases]). The canonical name is matched too.
# Aliases are plain lowercase strings; matching is boundary-aware, so "java"
# never matches inside "javascript" and "c++" keeps its plus signs.
VOCAB: dict[str, tuple[str, list[str]]] = {
    # languages
    "Java": ("language", []),
    "Python": ("language", []),
    "Golang": ("language", ["go lang"]),  # bare "go" is an English verb — not matched
    "Kotlin": ("language", []),
    "Scala": ("language", []),
    "C++": ("language", ["cpp"]),
    "C#": ("language", [".net", "dotnet"]),
    "JavaScript": ("language", ["js", "node.js", "nodejs", "node"]),
    "TypeScript": ("language", []),
    "SQL": ("language", []),
    "Rust": ("language", []),
    "Ruby": ("language", []),
    "PHP": ("language", []),
    # frameworks / libs
    "Spring Boot": ("framework", ["springboot"]),
    "Spring Cloud": ("framework", []),
    "Spring": ("framework", ["spring framework", "spring mvc"]),
    "Spring Security": ("framework", []),
    "Hibernate": ("framework", []),
    "JPA": ("framework", ["spring data jpa"]),
    "React": ("framework", ["react.js", "reactjs"]),
    "Angular": ("framework", []),
    "Vue": ("framework", ["vue.js", "vuejs"]),
    "Next.js": ("framework", ["nextjs"]),
    "Express.js": ("framework", ["expressjs"]),  # bare "express" is an English verb
    "Django": ("framework", []),
    "Flask": ("framework", []),
    "FastAPI": ("framework", []),
    "Ruby on Rails": ("framework", ["rails framework"]),  # bare "rails" is too common
    ".NET Core": ("framework", ["asp.net core", "dotnet core"]),
    "Drools": ("framework", []),
    "gRPC": ("framework", ["grpc"]),
    "GraphQL": ("framework", []),
    "JUnit": ("testing", []),
    "Mockito": ("testing", []),
    "TDD": ("testing", ["test driven development", "test-driven development"]),
    "Unit Testing": ("testing", ["unit tests", "unit test"]),
    "Integration Testing": ("testing", ["integration tests"]),
    # architecture / concepts
    "Microservices": ("architecture", ["microservice", "micro-services", "micro services"]),
    "Distributed Systems": ("architecture", ["distributed system", "distributed computing"]),
    "System Design": ("architecture", []),
    "Event-Driven": ("architecture", ["event driven", "event-driven architecture", "eda"]),
    "REST": ("architecture", ["restful", "rest api", "rest apis", "restful apis"]),
    "SOAP": ("architecture", []),
    "API Design": ("architecture", ["api development", "apis"]),
    "Scalability": ("architecture", ["scalable", "high scale", "large scale"]),
    "High Availability": ("architecture", ["highly available", "fault tolerance", "fault-tolerant", "resilience", "resilient"]),
    "Low Latency": ("architecture", ["low-latency", "latency"]),
    "Concurrency": ("architecture", ["multithreading", "multi-threading", "multithreaded", "concurrent"]),
    "Caching": ("architecture", ["cache", "caches"]),
    "Design Patterns": ("architecture", ["design pattern"]),
    "OOP": ("architecture", ["ood", "ooad", "object oriented", "object-oriented"]),
    "Data Structures": ("architecture", ["algorithms", "data structures and algorithms", "dsa"]),
    "Domain-Driven Design": ("architecture", ["ddd", "domain driven design"]),
    "Observability": ("architecture", ["monitoring", "logging", "tracing"]),
    "Performance Tuning": ("architecture", ["performance optimization", "performance optimisation", "query optimization"]),
    "Security": ("architecture", ["secure coding", "owasp"]),
    # messaging / streaming
    "Kafka": ("messaging", ["apache kafka"]),
    "RabbitMQ": ("messaging", []),
    "SQS": ("messaging", []),
    "SNS": ("messaging", []),
    "Kinesis": ("messaging", []),
    "Spark": ("data", ["apache spark", "pyspark"]),
    "Flink": ("data", []),
    "Airflow": ("data", ["apache airflow"]),
    "Pandas": ("data", []),
    "Snowflake": ("data", []),
    "BigQuery": ("data", []),
    "ETL": ("data", ["data pipeline", "data pipelines"]),
    # databases
    "MySQL": ("database", []),
    "PostgreSQL": ("database", ["postgres"]),
    "YugabyteDB": ("database", ["yugabyte"]),
    "Oracle": ("database", []),
    "MongoDB": ("database", ["mongo"]),
    "DynamoDB": ("database", []),
    "Cassandra": ("database", []),
    "Redis": ("database", []),
    "Elasticsearch": ("database", ["elastic search", "opensearch"]),
    "NoSQL": ("database", []),
    "RDBMS": ("database", ["relational database", "relational databases", "relational"]),
    "Data Modeling": ("database", ["data modelling", "schema design"]),
    # cloud / devops
    "AWS": ("cloud", ["amazon web services"]),
    "GCP": ("cloud", ["google cloud"]),
    "Azure": ("cloud", []),
    "EC2": ("cloud", []),
    "S3": ("cloud", []),
    "Lambda": ("cloud", ["serverless"]),
    "RDS": ("cloud", []),
    "IAM": ("cloud", []),
    "VPC": ("cloud", []),
    "CloudWatch": ("cloud", []),
    "Docker": ("devops", ["containers", "containerization", "containerized"]),
    "Kubernetes": ("devops", ["k8s", "eks"]),
    "Helm": ("devops", []),
    "Istio": ("devops", []),
    "ArgoCD": ("devops", ["argo cd"]),
    "OpenTelemetry": ("devops", ["otel"]),
    "Terraform": ("devops", ["infrastructure as code", "iac"]),
    "Ansible": ("devops", []),
    "Jenkins": ("devops", []),
    "GitHub Actions": ("devops", []),
    "CI/CD": ("devops", ["ci cd", "continuous integration", "continuous delivery", "continuous deployment"]),
    "Git": ("devops", []),
    "Linux": ("devops", ["unix"]),
    "Prometheus": ("devops", []),
    "Grafana": ("devops", []),
    "Datadog": ("devops", []),
    "Splunk": ("devops", []),
    # ways of working
    "Agile": ("process", ["scrum"]),
    "Code Review": ("process", ["code reviews"]),
    "Mentoring": ("process", ["mentor", "mentorship"]),
    "Ownership": ("process", ["end-to-end ownership", "own end-to-end", "owned end-to-end"]),
    # AI
    "LLM": ("ai", ["llms", "large language model", "large language models", "genai", "generative ai"]),
    "Machine Learning": ("ai", ["ml"]),
    "PyTorch": ("ai", []),
    "TensorFlow": ("ai", []),
    # domain
    "Fintech": ("domain", ["payments", "lending", "banking", "financial services"]),
    "E-commerce": ("domain", ["ecommerce", "e commerce"]),
    "Healthcare": ("domain", ["healthtech", "health tech"]),
    "SaaS": ("domain", []),
}

# JD term -> resume words that are EVIDENCE for it but not the same keyword.
# An ATS search for "Redis" does not find "ElastiCache", so these never count
# as a match — they are reported so the skill can suggest adding the real word.
RELATED: dict[str, list[str]] = {
    "Redis": ["elasticache"],
    "Kafka": ["msk"],
    "Kubernetes": ["eks"],
    "Observability": ["cloudwatch"],
    "Caching": ["elasticache", "redis"],
    "Concurrency": ["completablefuture", "executorservice"],
    "Event-Driven": ["kafka"],
    "Low Latency": ["response times"],
}

# Lines that mark a "must have" block; terms on them weigh double.
_REQUIRED_HINT = re.compile(
    r"\b(required|requirements|must|mandatory|minimum|qualifications|what you.ll need|you have|you bring)\b",
    re.I,
)
_YOE = re.compile(r"(?<![\d.,])(\d{1,2})(?!\d)\s*(?:\+|plus)?\s*(?:-|–|to)?\s*(\d{1,2})?\s*\+?\s*years?", re.I)


def _pattern(term: str) -> re.Pattern:
    """Boundary-aware: a term never matches inside a longer word."""
    return re.compile(r"(?<![\w+#.])" + re.escape(term.lower()) + r"(?![\w+#])")


_PATTERNS = {
    canon: [_pattern(t) for t in dict.fromkeys(x.lower() for x in [canon, *aliases])]
    for canon, (_cat, aliases) in VOCAB.items()
}


class _TextOnly(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "svg", "title"):
            self._skip += 1
        elif tag in ("p", "div", "li", "h1", "h2", "h3", "br"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script", "svg", "title") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(src: str) -> str:
    p = _TextOnly()
    p.feed(src)
    return html.unescape("".join(p.parts))


def read_text(path: str) -> str:
    """Plain text from .pdf (pdftotext), .html/.htm, or any text file."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        exe = shutil.which("pdftotext")
        if not exe:
            sys.exit("pdftotext not found — install poppler, or pass the .html source instead")
        out = subprocess.run([exe, "-layout", path, "-"], capture_output=True, check=True)
        return out.stdout.decode("utf-8", "replace")
    with open(path, encoding="utf-8", errors="replace") as f:
        src = f.read()
    return html_to_text(src) if ext in (".html", ".htm") else src


def _spans(low: str, canon: str) -> list[tuple[int, int, str]]:
    """Non-overlapping (start, end, form) hits — the longest form wins, so
    "data structures and algorithms" is one hit, not three."""
    raw = sorted(
        ((m.start(), m.end()) for p in _PATTERNS[canon] for m in p.finditer(low)),
        key=lambda se: (se[0], -se[1]),
    )
    out: list[tuple[int, int, str]] = []
    for st, en in raw:
        if out and st < out[-1][1]:
            continue
        out.append((st, en, low[st:en]))
    return out


def _norm(text: str) -> str:
    """Lowercase, one space for any whitespace run — a PDF line break inside
    "high availability" must not hide the phrase."""
    return re.sub(r"\s+", " ", text.lower())


def find_terms(text: str) -> dict[str, int]:
    """canonical term -> number of hits in text."""
    low = _norm(text)
    hits = {}
    for canon in _PATTERNS:
        n = len(_spans(low, canon))
        if n:
            hits[canon] = n
    # "Spring" is implied by Spring Boot/Cloud/Security; don't count it twice.
    if "Spring" in hits and any(k in hits for k in ("Spring Boot", "Spring Cloud", "Spring Security")):
        sub = sum(hits.get(k, 0) for k in ("Spring Boot", "Spring Cloud", "Spring Security"))
        hits["Spring"] -= sub
        if hits["Spring"] <= 0:
            del hits["Spring"]
    # Same for "Ruby" inside "Ruby on Rails".
    if "Ruby" in hits and "Ruby on Rails" in hits:
        hits["Ruby"] -= hits["Ruby on Rails"]
        if hits["Ruby"] <= 0:
            del hits["Ruby"]
    return hits


def required_terms(jd: str) -> set[str]:
    req = set()
    for line in jd.splitlines():
        if _REQUIRED_HINT.search(line):
            req |= set(find_terms(line))
    # a heading like "Requirements:" marks the lines under it too
    block = re.split(r"(?im)^\s*(?:requirements|qualifications|must have|what you.ll need)\b.*$", jd, maxsplit=1)
    if len(block) == 2:
        tail = re.split(r"(?im)^\s*(?:nice to have|good to have|preferred|bonus|benefits|perks)\b", block[1], maxsplit=1)[0]
        req |= set(find_terms(tail))
    return req


def jd_years(jd: str) -> list[int]:
    out = []
    for m in _YOE.finditer(jd):
        lo = int(m.group(1))
        if 0 < lo <= 25:
            out.append(lo)
    return sorted(set(out))


def score(jd: str, resume: str) -> dict:
    jd_hits = find_terms(jd)
    cv_hits = find_terms(resume)
    cv_low = _norm(resume)
    req = required_terms(jd)
    rows = []
    total = got = 0.0
    for canon, n in sorted(jd_hits.items(), key=lambda kv: (-kv[1], kv[0])):
        weight = 2.0 if (canon in req or n >= 3) else 1.0
        present = canon in cv_hits
        total += weight
        got += weight if present else 0
        rows.append({
            "term": canon,
            "category": VOCAB[canon][0],
            "jd_count": n,
            "resume_count": cv_hits.get(canon, 0),
            "required": canon in req,
            "weight": weight,
            "matched": present,
            # the exact words that matched in the resume (ATS searches literally)
            "resume_forms": sorted({f for _s, _e, f in _spans(cv_low, canon)}) if present else [],
            "related_evidence": [] if present else [
                w for w in RELATED.get(canon, []) if _pattern(w).search(cv_low)
            ],
        })
    pct = round(100 * got / total) if total else 0
    return {
        "score": pct,
        "matched": [r["term"] for r in rows if r["matched"]],
        "missing_required": [r["term"] for r in rows if not r["matched"] and r["weight"] == 2.0],
        "missing_other": [r["term"] for r in rows if not r["matched"] and r["weight"] == 1.0],
        "jd_years": jd_years(jd),
        "terms": rows,
    }


def print_report(res: dict) -> None:
    print(f"Keyword score: {res['score']}%  ({len(res['matched'])} of {len(res['terms'])} JD terms found)")
    if res["jd_years"]:
        print("JD years mentioned: " + ", ".join(f"{y}+" for y in res["jd_years"]))
    print(f"\n{'term':24} {'cat':12} {'JD':>3} {'CV':>3}  {'wt':>3}  status")
    for r in res["terms"]:
        status = "✅" if r["matched"] else ("❌ MISSING (required)" if r["weight"] == 2.0 else "⚠️ missing")
        if r["matched"] and r["term"].lower() not in r["resume_forms"]:
            status += f"  (as: {', '.join(r['resume_forms'])})"
        if r["related_evidence"]:
            status += f"  — related in resume: {', '.join(r['related_evidence'])}"
        print(f"{r['term']:24} {r['category']:12} {r['jd_count']:>3} {r['resume_count']:>3}  {r['weight']:>3.0f}  {status}")


def sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def find_chrome() -> str | None:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge"):
        exe = shutil.which(name)
        if exe:
            return exe
    for p in (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ):
        if os.path.exists(p):
            return p
    return None


def pdf_pages(path: str) -> int | None:
    exe = shutil.which("pdfinfo")
    if exe:
        out = subprocess.run([exe, path], capture_output=True, text=True).stdout
        m = re.search(r"^Pages:\s+(\d+)", out, re.M)
        if m:
            return int(m.group(1))
    with open(path, "rb") as f:  # rough fallback: count page objects
        return len(re.findall(rb"/Type\s*/Page[^s]", f.read())) or None


def pdf_name_for(html_path: str) -> str:
    """'<H1 text> - Resume.pdf' from the resume's first <h1>, else 'Resume.pdf'.
    The recruiter sees this file name, so it stays neutral (no company)."""
    try:
        with open(html_path, encoding="utf-8", errors="replace") as f:
            src = f.read()
    except OSError:
        return DEFAULT_PDF_NAME
    m = re.search(r"<h1[^>]*>(.*?)</h1>", src, re.I | re.S)
    if not m:
        return DEFAULT_PDF_NAME
    name = " ".join(html_to_text(m.group(1)).split())
    name = re.sub(r'[\\/:*?"<>|]+', "", name).strip()
    return f"{name} - Resume.pdf" if name else DEFAULT_PDF_NAME


def require_master() -> None:
    if not os.path.exists(MASTER_HTML):
        sys.exit(
            f"No master resume at {MASTER_HTML}.\n"
            f"Copy {TEMPLATE_HTML} to resume/master.html and fill it in "
            f"(or run /setup-profile), then try again."
        )


def cmd_score(a) -> None:
    res = score(read_text(a.jd), read_text(a.resume))
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print_report(res)


def cmd_init(a) -> None:
    slug = re.sub(r"[^a-z0-9]+", "-", a.slug.lower()).strip("-")
    if not slug:
        sys.exit("empty slug")
    require_master()
    dest_dir = os.path.join(TAILORED_DIR, slug)
    dest = os.path.join(dest_dir, "resume.html")
    if os.path.exists(dest) and not a.force:
        sys.exit(f"exists: {dest} (pass --force to start over from the master)")
    os.makedirs(dest_dir, exist_ok=True)
    shutil.copyfile(MASTER_HTML, dest)
    print(json.dumps({
        "dir": dest_dir,
        "html": dest,
        "pdf": os.path.join(dest_dir, pdf_name_for(MASTER_HTML)),
        "master_sha256": sha256(MASTER_HTML),
    }, indent=2))


def cmd_render(a) -> None:
    src = os.path.abspath(a.html)
    out = os.path.abspath(a.pdf or os.path.join(os.path.dirname(src), pdf_name_for(src)))
    chrome = find_chrome()
    if not chrome:
        sys.exit("Chrome/Edge/Chromium not found — install one to render the PDF")
    url = "file:///" + src.replace(os.sep, "/").lstrip("/")
    subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={out}", url],
        capture_output=True, check=False, timeout=120,
    )
    if not os.path.exists(out):
        sys.exit("render failed: no PDF written")
    pages = pdf_pages(out)
    print(json.dumps({"pdf": out, "pages": pages}))
    if pages and pages > 1:
        sys.exit(f"WARNING: {pages} pages — the resume must fit on one page")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score", help="keyword score of a resume against a JD")
    s.add_argument("--jd", required=True, help="JD text file (.txt/.md/.html)")
    s.add_argument("--resume", required=True, help="resume .pdf / .html / .txt")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_score)
    i = sub.add_parser("init", help="copy resume/master.html into resume/tailored/<slug>/")
    i.add_argument("--slug", required=True)
    i.add_argument("--force", action="store_true")
    i.set_defaults(fn=cmd_init)
    r = sub.add_parser("render", help="print an HTML resume to PDF")
    r.add_argument("html")
    r.add_argument("pdf", nargs="?",
                   help="output path (default: '<H1 name> - Resume.pdf' next to the HTML)")
    r.set_defaults(fn=cmd_render)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
