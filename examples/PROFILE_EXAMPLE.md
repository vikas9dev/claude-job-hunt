# Profile & Filters — Alex Rivera

> **Fictional example — for reference only.** Alex Rivera, Globex Payments and every number
> here are made up. Use this file to see how much detail each section needs, then fill in
> your own copy: `/setup-profile`, or copy `.claude/skills/_shared/PROFILE_AND_FILTERS.template.md`.
>
> The `## N.` headings are the same as in the template. Skills find sections by these headings.

---

## 1. Profile

| Field | Value |
|---|---|
| **Name** | Alex Rivera |
| **Current role** | Software Engineer 2 (backend) at Globex Payments |
| **YOE** | ~4 years (Jul 2022 – present) |
| **Notice period** | 60 days, can be bought out |
| **Domain** | Fintech / payments |
| **Certifications** | AWS Certified Developer – Associate (Mar 2025) |
| **One-line pitch** | Java/Spring backend engineer, ~4y, building payment APIs and Kafka pipelines on AWS |

---

## 2. Target band

| Field | Value |
|---|---|
| **Target levels (in scope)** | SDE II, Software Engineer 2, Backend Engineer II |
| **Stretch levels (flag, never drop)** | SDE III / Senior Software Engineer when the JD asks 5–7 yrs |
| **Above band (skip)** | Staff, Principal, Architect, Lead, explicit 9+ years |
| **Below band (skip)** | SDE I, Associate, Graduate, 0–2 years |
| **YOE gate** | Skip if the JD's YOE floor is **≥ 8** or its ceiling is **≤ 2** |

---

## 3. Compensation

All numbers are **total CTC per year**. Use one unit everywhere (e.g. `LPA` = lakhs per annum).

| Field | Value | Used for |
|---|---|---|
| **Current CTC** | 18 LPA | What you quote to recruiters |
| **Floor** | 24 LPA | Below this a role scores **0** on CTC potential |
| **Target** | 30 LPA | At or above this a role scores **2** on CTC potential |
| **Hard CTC gate** | no | `yes` = a role with CTC score 0 is `❌ Skip` whatever its total (use this when you hold an offer already) |

> Between Floor and Target a role scores **1**.

---

## 4. Locations

| Field | Value |
|---|---|
| **Preferred** | Bengaluru / Remote India |
| **Acceptable** | Hyderabad / Pune (with relocation) |
| **Country** | India — roles with no presence here are skipped |
| **Work mode preference** | hybrid — a **tiebreaker only**, never a filter |

---

## 5. Skills

| Area | What you have |
|---|---|
| **Primary language** | Java (11, 17) |
| **Core stack** | Spring Boot, Spring Data JPA, Hibernate, Microservices, REST |
| **Cloud** | AWS (ECS, RDS, S3, SQS, Lambda, CloudWatch) |
| **DevOps** | Docker, GitHub Actions, basic Kubernetes |
| **Databases** | PostgreSQL, MySQL, Redis |
| **Messaging** | Kafka |
| **Testing** | JUnit 5, Mockito, Testcontainers |
| **Other** | OpenAPI, Grafana dashboards |

### Skills I have but my resume does not show

> `/resume-check` and `/resume-tailor` use this list to put a missing JD word in the
> "✅ have it, add the word" bucket. List only things you have really used.

- Redis — cache for the merchant-config service (2024)
- Testcontainers — integration tests for the payout service
- gRPC — one internal service, read-only client

### Tech-stack match rule (for `/job-match` scoring)

| Score | When |
|---|---|
| **2** | Java + Spring Boot + (AWS or Kafka or Microservices) |
| **1** | Java with another framework, or Kotlin + Spring |
| **0** | No JVM language — Go / Python / Node / .NET primary |

---

## 6. Role families

| | Families |
|---|---|
| **In scope** | Backend, Platform, full-stack with a backend focus (≥ 70% backend) |
| **Out of scope (auto-skip)** | Frontend, QA / SDET, Data engineering, ML, DevOps / SRE, .NET, Embedded, Mobile, Engineering Manager |

---

## 7. Job search defaults (`/job-feed`)

| Field | Value |
|---|---|
| **Search terms** | "java backend engineer spring boot"; "java microservices kafka"; "backend engineer payments java" |
| **Default location** | Bengaluru, India |
| **Remote location** | India |
| **Sites** | indeed,naukri |
| **Hours old** | 72 |
| **Country for Indeed** | India |

---

## 8. Keyword pre-score (`/job-feed` triage)

A cheap 0–10 rank from the JD text only. Not a verdict. Clamp the total at 0.

| Positive signal | Points |
|---|---|
| Java / JVM | +3 |
| Spring Boot / Spring | +2 |
| Microservices | +1 |
| Kafka / messaging / event-driven | +1 |
| AWS (or Azure / GCP) | +1 |
| Docker / Kubernetes | +1 |
| Fintech / payments / banking | +1 |

| Negative signal | Points |
|---|---|
| US / night / rotational shift, "overlap with PST/EST" | −3 |
| Contract / C2H / "on payroll of" / fixed-term | −3 |
| Go / Python / Node / .NET named as the primary language | −2 |
| Above-band framing (see §2 *Above band*) | −2 |

---

## 9. Outreach hooks (`/job-match` referral packet)

Pick the **one** hook the JD rewards most. Each hook must be true and short.

| JD signal | Hook |
|---|---|
| Kafka / event-driven | Moved the payout pipeline to Kafka with exactly-once handling |
| Payments / fintech | Built the refund API that handles ~40k refunds a day |
| AWS / cloud | Run 6 services on ECS + RDS; AWS Developer – Associate |
| Performance / scale | Cut p99 latency of the merchant API from 900 ms to 180 ms |

**Connection-note opener** (≤ 120 characters, used before the hook):
"Hi <Name> — I'm a Java/Spring backend engineer (~4y) in payments."

---

## 10. Company filters

### Must-have (hard filters — skip if not met)

| Filter | Threshold |
|---|---|
| Company size | > 100 employees |
| Engineering team | > 30 engineers (estimate if not available) |
| Funding stage | Series B+ or profitable or publicly listed |
| Company type | Product company / tech company / platform |

### Exclude (auto-skip)

| Type | Examples |
|---|---|
| **Consultancies** | TCS, Infosys, Wipro, Cognizant, Accenture, HCL, Tech Mahindra, LTIMindtree, Mphasis, Capgemini (non-product) |
| **Body-shopping / staffing** | Any company that mainly supplies "resources" to other companies |
| **Agencies** | Marketing / design agencies with small dev teams |
| **No presence in your country** | No office there and no remote policy for it |
| **Personal skip-list** | Globex Payments (current employer) |

---

## 11. Work-life balance (WLB) signals

| Signal | Good (green flag) | Bad (red flag) |
|---|---|---|
| **AmbitionBox / Glassdoor WLB rating** | > 3.5 | < 3.0 |
| **Overall company rating** | > 3.5 | < 3.0 |
| **On-call** | Defined rotation, shared across team | "You own it end to end, 24/7" |
| **Reviews mention** | "Good WLB", "flexible hours", "no weekend work" | "Hustle culture", "long hours", "weekend deployments" |
| **Eng team size** | > 50 engineers | < 20 engineers |
| **Funding / revenue** | Profitable or well funded | Pre-seed / seed, burning cash, pivoting often |

| Level | Criteria | Action |
|---|---|---|
| 🟢 **Low risk** | WLB rating > 3.5, large eng team, mature company | Apply |
| 🟡 **Medium risk** | WLB rating 3.0–3.5, or mixed reviews | Apply, ask about WLB in interviews |
| 🔴 **High risk** | WLB rating < 3.0, or several red flags | Skip unless CTC is far above Target |

---

## 12. Company tiers

Edit the company names and CTC ranges to fit your level. The tier names
(`Tier-1`, `Tier-2`, `Tier-3`, `MNC`, `GCC`, `Startup`) are used by the tracker stats — keep them.

| Tier | Companies | Typical CTC at your level |
|---|---|---|
| **Tier-1** | Google, Microsoft, Amazon, Atlassian, Razorpay, PhonePe, CRED, Swiggy | 30–55 LPA |
| **Tier-2** | Meesho, Freshworks, Groww, Postman, BrowserStack | 22–32 LPA |
| **Tier-3** | Mid-funded startups, MNC product divisions (non-consulting) | 15–24 LPA |
| **GCC** | Foreign company's own India engineering centre, hiring direct FTE | 28–45 LPA |

**Tiers in scope right now:** all

> **GCC = Global Capability Center.** A foreign company running its own India engineering
> centre. You are a full-time employee (PF, insurance, stock), the work and pay are close to
> global. Signals: "India Development Center", "GCC", foreign HQ + India eng office, direct
> FTE hiring (not through an EOR or contractor). GCCs get a small ranking boost, never a filter.

### Tier calibration (your own response rates)

> Starts empty. After about **30 applications**, run `python scripts/job_track.py stats` and
> copy the per-tier response rates here, with the date. Until then `/job-match` uses the
> default company-tier scores below.

| Tier bucket | Applied | Responses | Rate | Company-tier score |
|---|---|---|---|---|
| MNC / GCC | 9 | 3 | 33% | 2 |
| Tier-1 | 11 | 3 | 27% | 2 |
| Tier-2 | 14 | 2 | 14% | 1 |
| Startup (funded, passes filters) | 6 | 1 | 17% | 1 |
| Tier-3 | 5 | 0 | 0% | 0 |

**Calibrated on:** 2026-10-01 (n = 45 applied)

---

## 13. Watchlist (`/job-feed watch`)

Companies whose own career feeds you want checked. Keep it short — real targets only.
Board tokens for many companies are already in [`ATS_FEEDS.md`](../.claude/skills/_shared/ATS_FEEDS.md); add a company
there too if its token is missing.

- Swiggy
- Groww
- Postman
- MongoDB
- Okta
- Wise

---

## 14. Resume

| Field | Value |
|---|---|
| **Master resume (HTML)** | `resume/master.html` |
| **PDF file name** | Alex Rivera - Resume.pdf |
| **Lines that must never be removed** | Notice-period line, AWS certification line |
