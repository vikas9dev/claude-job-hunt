# ATS Feeds — company career-board registry

> Used by **`/job-feed watch`**. Your own watchlist (which companies to check) is in your
> profile, `PROFILE_AND_FILTERS.md` §13. This file is the shared lookup: for each company,
> which applicant-tracking system (ATS) it uses and how to read its job feed.
>
> Everything here is public information. **Pull requests that add or fix tokens are welcome.**
> Tokens rot when a company changes its ATS, so each row has the date it was last checked.

---

## Why native ATS feeds, not search-page URLs

A careers **search URL** (e.g. `jobs.<co>.com/search?l=Bengaluru&orgIds=…`) is a trap:

- The location filter often runs **in the browser (JavaScript)**. A server-side fetch ignores it
  and returns the global, unfiltered list.
- Opaque params (`orgIds=…`) break when the company changes its site.

The ATS's **JSON feed** is static. You filter it in code, so it works every time.

### Fetch types

| Mark | Meaning | How `/job-feed watch` handles it |
|---|---|---|
| ✅ **API** | Clean JSON endpoint (Greenhouse, Lever, Ashby, SmartRecruiters, some custom) | Fetch the JSON, parse titles / locations — reliable |
| ✅ **Scrape** | Server-rendered HTML where the filter works server-side | Fetch and regex — fairly reliable |
| ⚠️ **JS-scrape** | JS-rendered page (Workday without a known site, Eightfold) | Best effort only — treat results as unreliable |
| ❌ **Paste-only** | Login-walled or hard JS | No automation — paste the JD into `/job-match` |

### ATS API URL templates

Replace `{token}` with the company's board slug (the last path segment of its public board URL).

| ATS | JSON feed template |
|---|---|
| **Greenhouse** | `https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` |
| **Lever** | `https://api.lever.co/v0/postings/{token}?mode=json` |
| **Ashby** | `https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true` |
| **SmartRecruiters** | `https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100` |
| **Workday** | `https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` — **POST** with body `{"appliedFacets":{},"limit":20,"offset":0,"searchText":"software engineer India"}`. Returns `jobPostings[]` (`.title`, `.locationsText`, `.postedOn`, `.externalPath` → prefix `https://{tenant}.{dc}.myworkdayjobs.com/en-US/{site}`). **Proven 26 Sep 2026** for Visa + Salesforce. `{tenant}/{site}` come straight from the public job URL; a wrong `{site}` returns **422**. WebFetch can't POST — use `curl` |
| **Amazon** (custom) | `https://www.amazon.jobs/en/search.json?offset=0&result_limit=100&sort=recent&category%5B%5D=software-development&normalized_country_code%5B%5D=IND&base_query={q}` (GET). `jobs[]` → `.title`, `.normalized_location`, `.posted_date`, `.job_path`, `.basic_qualifications`. ⚠️ The web page's `country[]=IND` param is **ignored** by the JSON — filter `country_code == "IND"` in code. Proven 26 Sep 2026 |
| **Google** (custom) | `https://www.google.com/about/careers/applications/jobs/results/?location=India&q={q}&page={n}` (GET, HTML). Location filter **is** applied server-side; ~20 records/page embedded as `["<id>","<title>","https://www.google.com/about/careers/applications/signin…` — regex those. Job URL = `…/jobs/results/<id>`. Proven 26 Sep 2026 |

> `WebFetch` cannot send a POST and summarizes large pages. Use `curl` for Workday and for the
> large custom feeds, then parse the JSON in code.

---

## Registry

> Columns: **Token** = board slug for the template above (`—` = no public board found).
> **Last checked** = when the feed was last probed. Re-probe anything older than ~3 months.

| Company | ATS | Token | Feed / URL | Fetch | Last checked |
|---|---|---|---|---|---|
| Airbnb | Greenhouse | `airbnb` | `https://boards-api.greenhouse.io/v1/boards/airbnb/jobs?content=true` | ✅ API | 4 Aug 2026 |
| Amazon | Custom JSON | — | `amazon.jobs/en/search.json` (see template) | ✅ API | 26 Sep 2026 |
| Atlan | Ashby | `atlan` | `https://api.ashbyhq.com/posting-api/job-board/atlan?includeCompensation=true` | ✅ API | 4 Aug 2026 |
| Atlassian | Custom JSON | — | `https://www.atlassian.com/endpoint/careers/listings` (GET) | ✅ API | — |
| BrowserStack | Workday | — | `browserstack.com/careers` (→ `…myworkdayjobs.com/External`) | ⚠️ JS-scrape | — |
| Camunda | Ashby | `camunda` | `https://api.ashbyhq.com/posting-api/job-board/camunda?includeCompensation=true` | ✅ API | 4 Aug 2026 |
| Confluent | Ashby | `confluent` | `https://api.ashbyhq.com/posting-api/job-board/confluent?includeCompensation=true` | ✅ API | 4 Aug 2026 |
| CRED | Lever | `cred` | `https://api.lever.co/v0/postings/cred?mode=json` | ✅ API | 4 Aug 2026 |
| Databricks | Greenhouse | `databricks` | `https://boards-api.greenhouse.io/v1/boards/databricks/jobs?content=true` | ✅ API | 12 Sep 2026 |
| Freshworks | SmartRecruiters | `freshworks` | `https://api.smartrecruiters.com/v1/companies/freshworks/postings?limit=100` | ✅ API | 4 Aug 2026 |
| GitLab | Greenhouse | `gitlab` | `https://boards-api.greenhouse.io/v1/boards/gitlab/jobs?content=true` | ✅ API | 12 Sep 2026 |
| Google | Custom HTML | — | `google.com/about/careers/applications/jobs/results/?location=India` | ✅ Scrape | 26 Sep 2026 |
| Groww | Greenhouse | `groww` | `https://boards-api.greenhouse.io/v1/boards/groww/jobs?content=true` | ✅ API | 4 Aug 2026 |
| HighRadius | Greenhouse | `highradius` | `https://boards-api.greenhouse.io/v1/boards/highradius/jobs?content=true` | ✅ API | 12 Sep 2026 |
| Innovaccer | Custom/JS | — | `innovaccer.com/careers` | ❌ Paste-only | 4 Aug 2026 |
| Instabase | Greenhouse | `instabase` | `https://boards-api.greenhouse.io/v1/boards/instabase/jobs?content=true` | ✅ API | 4 Aug 2026 |
| Juspay | Custom/JS | — | `juspay.io/careers` | ❌ Paste-only | 4 Aug 2026 |
| Meesho | Lever | `meesho` | `https://api.lever.co/v0/postings/meesho?mode=json` | ✅ API | 4 Aug 2026 |
| Metropolis | Greenhouse | `metropolis` | `https://boards-api.greenhouse.io/v1/boards/metropolis/jobs?content=true` | ✅ API | 4 Aug 2026 |
| Microsoft | Eightfold | — | `apply.careers.microsoft.com/careers?location=India` | ❌ Paste-only | 26 Sep 2026 |
| Mindtickle | Lever | `mindtickle` | `https://api.lever.co/v0/postings/mindtickle?mode=json` | ✅ API | 12 Sep 2026 |
| MongoDB | Greenhouse | `mongodb` | `https://boards-api.greenhouse.io/v1/boards/mongodb/jobs?content=true` | ✅ API | 12 Sep 2026 |
| Notion | Ashby | `notion` | `https://api.ashbyhq.com/posting-api/job-board/notion?includeCompensation=true` | ✅ API | 12 Sep 2026 |
| Okta | Greenhouse | `okta` | `https://boards-api.greenhouse.io/v1/boards/okta/jobs?content=true` | ✅ API | 12 Sep 2026 |
| Paytm | Lever | `paytm` | `https://api.lever.co/v0/postings/paytm?mode=json` | ✅ API | 12 Sep 2026 |
| PhonePe | Custom/Darwinbox | — | `phonepe.com/careers` | ❌ Paste-only | — |
| Postman | Greenhouse | `postman` | `https://boards-api.greenhouse.io/v1/boards/postman/jobs?content=true` | ✅ API | 4 Aug 2026 |
| Rubrik | Greenhouse | `rubrik` | `https://boards-api.greenhouse.io/v1/boards/rubrik/jobs?content=true` | ✅ API | 12 Sep 2026 |
| Salesforce | Workday | `salesforce.wd12` / `salesforce` / `External_Career_Site` | `https://salesforce.wd12.myworkdayjobs.com/wday/cxs/salesforce/External_Career_Site/jobs` (POST) | ✅ API | — |
| ServiceNow | SmartRecruiters | `servicenow` | `https://api.smartrecruiters.com/v1/companies/servicenow/postings?limit=100` | ✅ API | 4 Aug 2026 |
| Swiggy | SmartRecruiters | `swiggy` | `https://api.smartrecruiters.com/v1/companies/swiggy/postings?limit=100` | ✅ API | 4 Aug 2026 |
| Uber | Workday | — | `uber.com/careers` | ⚠️ JS-scrape | — |
| Visa | Workday | `visa.wd5` / `visa` / `Visa` | `https://visa.wd5.myworkdayjobs.com/wday/cxs/visa/Visa/jobs` (POST) | ✅ API | — |
| Walmart Global Tech | Workday | — | `careers.walmart.com` | ⚠️ JS-scrape | 26 Sep 2026 |
| Wise | Greenhouse | `wise` | `https://boards-api.greenhouse.io/v1/boards/wise/jobs?content=true` | ✅ API | 12 Sep 2026 |
| Zepto | Custom/JS | — | `zeptonow.com/careers` | ❌ Paste-only | 4 Aug 2026 |

### More confirmed tokens (no table row yet)

These boards answered at the last sweep. Copy one into the registry table when you add it to
your watchlist. Key: `gr` = Greenhouse, `le` = Lever, `as` = Ashby, `sm` = SmartRecruiters.

`adyen` (gr), `affirm` (gr), `airtable` (gr), `airwallex` (as), `anthropic` (gr), `asana` (gr), `block` (gr), `brex` (gr), `canva` (sm), `carta` (gr), `chime` (gr), `cloudflare` (gr), `datadog` (gr), `elastic` (gr), `figma` (gr), `grab` (sm), `gusto` (gr), `instacart` (gr), `jfrog` (gr), `linear` (as), `lyft` (gr), `miro` (as), `navi` (as), `netlify` (gr), `nubank` (as), `openai` (as), `plaid` (as), `ramp` (as), `robinhood` (gr), `samsara` (gr), `scaleai` (gr), `slice` (gr), `snowflake` (as), `sofi` (gr), `stripe` (gr), `supabase` (as), `toast` (gr), `tripadvisor` (gr), `turtlemint` (sm), `twilio` (gr), `uber` (sm), `vercel` (gr), `wayfair` (sm), `whatfix` (sm), `zeta` (le), `zscaler` (gr)

### Probed — no public board

`doordash` - `netflix` - `nutanix` - `rippling` - `hashicorp`. All four ATS templates returned 404. Treat these as paste-only.

---

## Maintenance

- **Never add a token without probing it.** Open the feed URL; it must return JSON with jobs.
  Wrong ATS is as common as a wrong slug.
- **Find a token:** open the company's careers page, find the board URL
  (`boards.greenhouse.io/<token>`, `jobs.lever.co/<token>`, `jobs.ashbyhq.com/<token>`,
  `careers.smartrecruiters.com/<token>`), and copy the slug.
- **Workday:** `{tenant}`, `{dc}` and `{site}` come from a real job URL on that company's
  Workday site. A wrong `{site}` returns **422**.
- A feed that starts returning **404** means the company moved ATS. Mark it and re-probe.
