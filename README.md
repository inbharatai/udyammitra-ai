# UdyamMitra AI

**AI alternate-data Financial Health Card for MSMEs — built for IDBI Problem Statement 3.**

New-to-Credit (NTC) and New-to-Bank (NTB) MSMEs are rejected because traditional
credit evaluation relies on financial documents they don't have. UdyamMitra AI
ingests **alternate data — GST, UPI, Account Aggregator (AA), EPFO** — runs a
**10-agent explainable pipeline**, and produces a multidimensional financial
health card that integrates with the **ULI / OCEN / AA** ecosystems for near
real-time credit assessment — onboarding credit-invisible MSMEs without
sacrificing portfolio quality.

---

## What it outputs

- **MSME Financial Health Score** with published sub-scores (vintage, sector
  risk, cash buffer, EMI burden, GST consistency, seasonality-adjusted DSCR).
- **30 / 60 / 90-day cash-flow stress forecast** with projection min-balance.
- **Loan-readiness indicator** — transparent, explainable, **not a CIBIL/bureau
  score**.
- **Early-warning signals** with source-metric provenance + recommended action.
- **Working-capital recommendation** — OD/CC limit (RBI-style sanctioned-limit
  proxy), invoice discounting eligibility, term-loan suitability.
- **Government scheme + IDBI product matching** — CGTMSE, MUDRA, PM Vishwakarma,
  PMEGP, RAMP.
- **RM-copilot brief** — next-best-actions, cross-sell, risk-for-bank, regulatory notes.
- **Bilingual (Hindi + English) explainable report** with provenance footnotes.

## The 10 agents (DAG)

```
L0 (parallel):  Profile · Transaction
L1:             Cash-flow Forecast
L2 (parallel):  Credit Risk · Early Warning
L3 (parallel):  Loan Suitability · Scheme/Product Match
L4:             Compliance & Explainability
L5:             RM Copilot
L6:             Report (bilingual + provenance)
```

The deterministic scoring core (`backend/app/scoring/metrics.py`) is the moat —
every number an agent or the UI shows traces back to it. Real MSME credit
concepts: EMI/income burden, seasonality-adjusted DSCR, cash-buffer days, GST
2A/2B consistency, working-capital gap → RBI-style OD/CC sanctioned-limit
proxy, 30/60/90 stress probabilities.

One engineered **near-miss inclusion** hero MSME (Bharat Textiles) is declined
by naive bureau logic (DSCR < 1.2) but flagged OD-CC-eligible on cash-flow
XAI — the credit-inclusion story.

## Alternate-data connectors (Problem Statement 3)

`backend/app/connectors/` — uniform `fetch(msme_id) → ConnectorResult` interface
so a new source is a drop-in. **Honest status (no faked live pulls):**

| Source | Status | How it lands |
|---|---|---|
| **GST** | spec-ready | GSTR-2A/2B + 3B via a GSP/ASP partner (ClearTax / Masterso / TaxPro). Raises `NotImplementedError` until `GSP_ASP_*` creds are set. |
| **AA** | spec-ready | Sahamati AA gateway, consent-driven FIU fetch of bank statements. Raises until `SAHAMATI_AA_*` + consent handle are set. |
| **UPI** | via AA | UPI has no separate public lender API; UPI rows are parsed from AA-delivered bank statements. |
| **EPFO** | gated / declared-verify | EPFO has no clean open third-party API. Use scoped employer-side access where legitimate; otherwise declared-and-verify. Do **not** fake live EPFO. |

On AWS these run out-of-band: **EventBridge → SQS → Lambda** connector → raw
payload to **S3**, structured rows to **Aurora**, re-score event back to the
pipeline. See `infra/cdk/`.

## Ecosystem integration (ULI / OCEN / AA)

`backend/app/routers/ecosystem.py` exposes spec-shaped endpoints:

- `GET /api/ecosystem/uli/health-card/{msme_id}` — ULI-shaped health-card fetch (lender-side).
- `GET /api/ecosystem/ocen/signal/{msme_id}?product=od_cc` — OCEN credit signal for loan origination.
- `GET /api/ecosystem/status` — honest live-vs-spec-ready summary.

These return **HTTP 501 with `live: false`** until a ULI/OCEN partner is wired.
AA is ingestion-side (see connectors). No live ULI/OCEN/AA integration is claimed.

## Stack

- **Backend:** FastAPI (Python 3.12), SQLAlchemy, SQLite locally → **Aurora Serverless v2 Postgres** on AWS.
- **Frontend:** Next.js 14 (App Router) + TypeScript + Tailwind + Recharts.
- **AI:** OpenAI API (`OPENAI_MODEL=gpt-4o-mini` by default — a real, cheap public id; env-configurable).
- **Agents:** custom lightweight orchestrator with OpenAI function-calling, structured Pydantic I/O, parallel DAG layers, live SSE reasoning trace, bounded retries + deterministic fallback.
- **Offline mode:** if no `OPENAI_API_KEY`, the full pipeline runs on deterministic math + templated narrative with **zero network** (demo insurance — the demo never breaks).

## Quick start (local)

```bash
# 1. Backend
cd backend
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
#   ./.venv/bin/python -m pip install -r requirements.txt        # macOS/Linux
cp ../.env.example .env   # add OPENAI_API_KEY (optional — works offline without it)
./.venv/Scripts/python.exe -m app.db.seed      # seed 9 synthetic MSMEs (idempotent)
./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev    # http://localhost:3000

# Or run both:  ./dev.ps1   (Windows)   |   ./dev.sh   (macOS/Linux/Git Bash)
```

Open http://localhost:3000 → pick an MSME → "Run analysis" → watch the live
agent trace, scores, cash-flow chart, what-if slider and the bilingual report.

Without an `OPENAI_API_KEY`, the app runs in **offline mode** (deterministic +
templated). Paste a key into `backend/.env` (and set `OPENAI_MODEL` to an id
your key can access) to get live LLM agent narratives.

## API (FastAPI, http://localhost:8000, docs at `/docs`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/msmes` | list demo MSMEs |
| GET | `/api/msmes/{id}` | MSME detail + computed metrics |
| POST | `/api/msmes/{id}/what-if` | deterministic re-forecast with `revenue_delta` |
| POST | `/api/runs` | kick the 10-agent pipeline → `{run_id}` |
| GET | `/api/runs/{id}/events` | **SSE** live agent trace |
| GET | `/api/runs/{id}/status` | poll fallback (includes `msme_id`) |
| GET | `/api/runs/{id}/report` | final assembled report + metrics |
| GET | `/api/ecosystem/status` | ULI/OCEN/AA live-vs-spec summary |
| GET | `/api/ecosystem/uli/health-card/{id}` | ULI health-card (spec-ready, 501) |
| GET | `/api/ecosystem/ocen/signal/{id}` | OCEN credit signal (spec-ready, 501) |

## Tests

```bash
cd backend && ./.venv/Scripts/python.exe -m pytest        # scoring unit tests
cd backend && ./.venv/Scripts/python.exe -m app.db.seed   # regenerate synthetic data
cd frontend && node e2e-check.mjs                         # headless end-to-end flow
```

`e2e-check.mjs` drives a real browser: landing → /msmes → Run analysis → agent
trace → scores + report → −20% what-if slider. Writes `e2e-dashboard.png` on
success (gitignored).

## Deploy on AWS (all-AWS, including the DB)

Everything hosts on AWS — **AWS is a key partner**. Infra is defined as code in
`infra/cdk/` (AWS CDK, TypeScript). One `cdk deploy` provisions the whole stack:

```
                     GitHub repo
                          │
        ┌─────────────────┼──────────────────┐
        ▼                                    ▼
  Amplify Hosting                     CodeBuild → ECR (backend image)
  (Next.js frontend)                         │
        │                                    ▼
        └────────────► Route 53 + CloudFront ◄┐
                          │                   │
              ┌───────────┴────────┐    ┌─────┴───────┐
              ▼                    ▼    ▼             │
        Amplify URL        App Runner (FastAPI)       │
        (NEXT_PUBLIC_      • REST + SSE               │
         API_BASE ─────────►• 10-agent pipeline       │
         App Runner URL)    • VPC connector ──────────┘
                                   │
              ┌────────────────────┼─────────────────────┐
              ▼                    ▼                     ▼
        Aurora Serverless    Secrets Manager       EventBridge→SQS→Lambda
        v2 Postgres          (OpenAI, GSP/ASP,    (GST/AA/UPI/EPFO
        (msmes, runs,         Sahamati AA, EPFO)   ingestion → S3 → Aurora
         events JSON)                              → re-score)
```

**Frontend → AWS Amplify Hosting** (Vercel-equivalent for Next.js on AWS).
**Backend → AWS App Runner** (FastAPI, supports SSE/streaming, VPC connector to
private Aurora). **DB → Amazon Aurora Serverless v2 Postgres** (SQLite→Aurora
is a `DATABASE_URL` connection-URL swap; schema is JSON-as-text and portable).
**Secrets → AWS Secrets Manager** (OpenAI key + connector creds, injected as
App Runner env vars — never in git). **Alternate-data → EventBridge + SQS +
Lambda + S3**. See `infra/cdk/README.md` for the deploy sequence.

### Deploy steps (summary)

1. `git push` to GitHub.
2. `cd infra/cdk && npm install && npx cdk bootstrap && npx cdk synth`.
3. Build + push backend image to ECR (or let CodeBuild do it).
4. `FRONTEND_REPO_URL=https://github.com/inbharatai/udyammitra-ai npx cdk deploy`.
5. Wire `DATABASE_URL` (from the `DbClusterEndpoint` + `DbSecretArn` outputs),
   `CORS_ORIGINS` (Amplify domain), and the OpenAI/connector secrets in the
   Secrets Manager console.
6. Set `NEXT_PUBLIC_API_BASE` on the Amplify app to the App Runner URL.
7. Verify: `curl https://<apprunner>/health` → `offline:false`; open the
   Amplify URL → Run analysis → trace shows `✓ done` (not "offline").

### Architecture honesty notes

- **SSE + in-memory run state:** the run manager keeps per-run event queues in
  process memory. On a single min-provisioned App Runner instance (the
  hackathon setting) this is fine. For multi-instance scale, move event
  queues to **ElastiCache Redis pub/sub** — same UX, horizontally scalable.
  Don't claim multi-instance SSE you haven't built.
- **JSON-as-Text, not JSONB:** columns are portable Text today. A future
  optimization is Postgres `JSONB` (indexable) — requires storing dicts
  directly in `app/db/database.py` instead of the current `dumps()`/`loads()`.
- **EPFO + ULI are gated/evolving.** Be the team that says "GST + AA spec-ready,
  EPFO declared-verify, ULI-ready" — not the team that fakes all four.

## Project layout

```
backend/
  app/main.py                      FastAPI app, CORS, routers, startup seed
  app/core/                        config (settings), openai client
  app/scoring/metrics.py           deterministic scoring core (the moat)
  app/agents/                      base AgentRun, tools, schemas, 10 agent defs, orchestrator
  app/connectors/                  alternate-data connectors (GST/AA/UPI/EPFO) — spec-ready
  app/routers/                     msmes, runs (SSE), run_manager, ecosystem (ULI/OCEN)
  app/db/                          SQLAlchemy models, database, synthetic seed generator
  data/seed/*.json                 seeded MSME datasets + schemes.json
  Dockerfile + .dockerignore       App Runner / Fargate image
  tests/test_scoring.py
frontend/
  app/                             landing, /msmes, /runs/[id] dashboard
  components/                       Logo, ScoreTiles, CashflowChart, AgentTrace, WhatIfSlider, ReportView
  lib/api.ts
  e2e-check.mjs                     headless end-to-end harness
infra/cdk/
  bin/udyammitra.ts                 CDK app entry
  lib/udyammitra-stack.ts           VPC + Aurora + Secrets + ECR + App Runner + Amplify + Lambda/SQS/EventBridge
  lambdas/index.py                  connector Lambda stub
  cdk.json, package.json, tsconfig.json, README.md
assets/logo.svg
```

## Honest framing

The loan-readiness indicator is a **prototype** derived from cash-flow and GST
patterns. It is **not** a CIBIL/bureau credit score and is not a substitute for
one. Every recommendation is explainable and traceable to a deterministic
metric. No live ULI/OCEN/AA/EPFO integration is claimed; connectors and
ecosystem endpoints are spec-ready stubs. The OpenAI default model is
`gpt-4o-mini` (a real public id) — fictional model ids are not used.