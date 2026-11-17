# Profile & Filters — <<YOUR_NAME>>

> **How to use this file**
>
> 1. Copy it: `cp .claude/skills/_shared/PROFILE_AND_FILTERS.template.md .claude/skills/_shared/PROFILE_AND_FILTERS.md`
>    — or run `/setup-profile` in Claude Code and answer its questions.
> 2. Replace every `<<…>>` placeholder. Delete example rows you don't want.
> 3. The real `PROFILE_AND_FILTERS.md` is **gitignored**. It stays on your machine, and
>    `git pull` never conflicts with it.
>
> Every skill (`/job-match`, `/job-feed`, `/discover-companies`, `/resume-check`,
> `/resume-tailor`) reads this file at the start of each run. **Change a value here and every
> skill picks it up.** Skills must never copy values out of this file into their own text.
>
> Section headings are read by the skills by name. Keep the `## N.` headings as they are;
> change only the content under them.

---

## 1. Profile

| Field | Value |
|---|---|
| **Name** | <<Your Name>> |
| **Current role** | <<e.g. SDE II / Software Engineer 2>> at <<current company>> |
| **YOE** | <<e.g. ~5 years (Nov 2021 – present)>> |
| **Notice period** | <<e.g. 60 days / serving notice, last day DD Mon YYYY>> |
| **Domain** | <<e.g. Fintech / lending, E-commerce, SaaS>> |
| **Certifications** | <<e.g. AWS Solutions Architect – Associate (Dec 2025) — or "none">> |
| **One-line pitch** | <<e.g. Java/Spring backend engineer, ~5y, building payment microservices on AWS>> |

---

## 2. Target band

| Field | Value |
|---|---|
| **Target levels (in scope)** | <<e.g. SDE II, SDE III / Senior SWE>> |
| **Stretch levels (flag, never drop)** | <<e.g. SDE III when the JD asks 6–9 yrs>> |
| **Above band (skip)** | <<e.g. Staff, Principal, Architect, explicit 10+ years>> |
| **Below band (skip)** | <<e.g. SDE I, Associate, 0–2 years>> |
| **YOE gate** | Skip if the JD's YOE floor is **≥ <<e.g. 9>>** or its ceiling is **≤ <<e.g. 2>>** |

---

## 3. Compensation

All numbers are **total CTC per year**. Use one unit everywhere (e.g. `LPA` = lakhs per annum).

| Field | Value | Used for |
|---|---|---|
| **Current CTC** | <<e.g. 18 LPA>> | What you quote to recruiters |
| **Floor** | <<e.g. 25 LPA>> | Below this a role scores **0** on CTC potential |
| **Target** | <<e.g. 32 LPA>> | At or above this a role scores **2** on CTC potential |
| **Hard CTC gate** | <<yes / no>> | `yes` = a role with CTC score 0 is `❌ Skip` whatever its total (use this when you hold an offer already) |

> Between Floor and Target a role scores **1**.

---

## 4. Locations

| Field | Value |
|---|---|
| **Preferred** | <<e.g. Bengaluru / Remote India / Delhi NCR>> |
| **Acceptable** | <<e.g. Hyderabad / Pune / Mumbai (with relocation)>> |
| **Country** | <<e.g. India>> — roles with no presence here are skipped |
| **Work mode preference** | <<hybrid / remote / onsite / no preference>> — a **tiebreaker only**, never a filter |

---

## 5. Skills

| Area | What you have |
|---|---|
| **Primary language** | <<e.g. Java>> |
| **Core stack** | <<e.g. Spring Boot, Spring Cloud, Microservices, Hibernate, JPA>> |
| **Cloud** | <<e.g. AWS (EC2, RDS, S3, Lambda, SQS)>> |
| **DevOps** | <<e.g. Docker, Kubernetes, Jenkins, GitHub Actions>> |
| **Databases** | <<e.g. MySQL, PostgreSQL, MongoDB, Redis>> |
| **Messaging** | <<e.g. Kafka, RabbitMQ>> |
| **Testing** | <<e.g. JUnit, Mockito>> |
| **Other** | <<anything else real>> |

### Skills I have but my resume does not show

> `/resume-check` and `/resume-tailor` use this list to put a missing JD word in the
> "✅ have it, add the word" bucket. List only things you have really used.

- <<e.g. Redis — used it as a cache in the order service>>
- <<e.g. DynamoDB — one service, 2024>>

### Tech-stack match rule (for `/job-match` scoring)

| Score | When |
|---|---|
| **2** | <<e.g. Java + Spring Boot + (AWS or Microservices)>> |
| **1** | <<e.g. Java with another framework, or Spring with another JVM language>> |
| **0** | <<e.g. no Java at all — Go / Python / Node primary>> |

---

## 6. Role families

| | Families |
|---|---|
| **In scope** | <<e.g. Backend, Platform, full-stack with backend focus>> |
| **Out of scope (auto-skip)** | <<e.g. Frontend, QA / SDET, Data, ML, DevOps / SRE, .NET, Embedded, Mobile, Engineering Manager>> |

---

## 7. Job search defaults (`/job-feed`)

| Field | Value |
|---|---|
| **Search terms** | <<e.g. "java backend engineer spring boot"; "java microservices kafka"; "backend engineer java aws">> |
| **Default location** | <<e.g. Bengaluru, India>> |
| **Remote location** | <<e.g. India>> |
| **Sites** | <<e.g. indeed,naukri>> (add `linkedin`, `glassdoor`, `google` only if you want them — LinkedIn is often blocked) |
| **Hours old** | <<e.g. 72>> |
| **Country for Indeed** | <<e.g. India>> |

---

## 8. Keyword pre-score (`/job-feed` triage)

A cheap 0–10 rank from the JD text only. Not a verdict. Clamp the total at 0.

| Positive signal | Points |
|---|---|
| <<Primary language, e.g. Java / JVM>> | +3 |
| <<Main framework, e.g. Spring Boot / Spring>> | +2 |
| <<e.g. Microservices>> | +1 |
| <<e.g. Kafka / messaging / event-driven>> | +1 |
| <<e.g. AWS (or Azure / GCP)>> | +1 |
| <<e.g. Docker / Kubernetes>> | +1 |
| <<Your domain, e.g. fintech / payments / lending>> | +1 |

| Negative signal | Points |
|---|---|
| US / night / rotational shift, "overlap with PST/EST" | −3 |
| Contract / C2H / "on payroll of" / fixed-term | −3 |
| <<A different primary language, e.g. Go / Python / Node / .NET named as primary>> | −2 |
| Above-band framing (see §2 *Above band*) | −2 |

---

## 9. Outreach hooks (`/job-match` referral packet)

Pick the **one** hook the JD rewards most. Each hook must be true and short.

| JD signal | Hook |
|---|---|
| <<e.g. Kafka / event-driven>> | <<e.g. Built Kafka consumers with exactly-once handling in production>> |
| <<e.g. Payments / fintech>> | <<e.g. Owned the loan-approval service end to end>> |
| <<e.g. AWS / cloud>> | <<e.g. AWS SA-Associate certified, run services on ECS + RDS>> |
| <<e.g. Scale / distributed systems>> | <<e.g. Split a monolith into 6 microservices>> |

**Connection-note opener** (≤ 120 characters, used before the hook):
<<e.g. "Hi <Name> — I'm a Java/Spring backend engineer (~5y).">>

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
| **Personal skip-list** | <<companies you never want to see, or "none">> |

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
| **Tier-1** | <<e.g. Google, Microsoft, Amazon, Atlassian, Razorpay, PhonePe, CRED, Swiggy, Zepto, Walmart Global Tech>> | <<e.g. 30–80 LPA>> |
| **Tier-2** | <<e.g. Meesho, BrowserStack, Freshworks, Groww, Urban Company, ServiceNow>> | <<e.g. 22–35 LPA>> |
| **Tier-3** | Mid-funded startups, MNC product divisions (non-consulting) | <<e.g. 15–25 LPA>> |
| **GCC** | Foreign company's own India engineering centre, hiring direct FTE | <<e.g. 30–60 LPA>> |

**Tiers in scope right now:** <<e.g. all / Tier-1 + GCC only>>

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
| MNC / GCC | — | — | — | 2 |
| Tier-1 | — | — | — | 2 |
| Tier-2 | — | — | — | 1 |
| Startup (funded, passes filters) | — | — | — | 1 |
| Tier-3 | — | — | — | 0 |

**Calibrated on:** <<never — defaults in use>>

---

## 13. Watchlist (`/job-feed watch`)

Companies whose own career feeds you want checked. Keep it short — real targets only.
Board tokens for many companies are already in [`ATS_FEEDS.md`](ATS_FEEDS.md); add a company
there too if its token is missing.

- <<e.g. Swiggy>>
- <<e.g. Databricks>>
- <<e.g. MongoDB>>

---

## 14. Resume

| Field | Value |
|---|---|
| **Master resume (HTML)** | `resume/master.html` |
| **PDF file name** | <<e.g. Firstname Lastname - Resume.pdf>> |
| **Lines that must never be removed** | <<e.g. notice-period line, certification line>> |
