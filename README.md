# Agentic AI Dispute Handling System

A FastAPI web app that uses a pipeline of AI agents to triage, evaluate, and recommend
resolutions for customer payment disputes (fraud, billing errors, duplicate charges,
subscription cancellations, and merchant delivery disputes) — with a case-management UI,
document upload/verification, and an in-app assistant ("JUNO") for agents to work from.

## What problem it solves

When a customer disputes a transaction, a human agent normally has to:

1. Read the customer's statement and guess what kind of dispute it is.
2. Look up the bank's policy for that dispute type.
3. Decide what to do (refund, partial refund, block the card, escalate, etc.) and justify it.
4. Review whatever evidence the customer uploads (receipts, screenshots, delivery proof) and
   judge whether it's genuine and actually relevant to the case.
5. Track the case status until it's resolved.

This app automates steps 1–4 with a small pipeline of specialized agents, and gives the
agent a dashboard to review and act on the result in step 5, rather than doing all of it by
hand for every case.

## How it works: the agent pipeline

When a dispute is created for a transaction (`POST /api/disputes`), four agents run in
sequence, each handing its output to the next:

| Agent | File | Role |
|---|---|---|
| **Classification Agent** | [agents/classification_agent.py](agents/classification_agent.py) | Reads the customer's statement + transaction risk signals and classifies the dispute into one of `Fraud`, `Billing Error`, `Duplicate Charge`, `Subscription`, or `Merchant Dispute`, with a confidence score. Uses an LLM prompt, with keyword-based fallback logic (e.g. "unauthorized" → Fraud, "twice"/"duplicate" → Duplicate Charge) if the LLM call fails or is unavailable. |
| **Policy Agent** | [agents/policy_agent.py](agents/policy_agent.py) | Looks up the bank's relevant policy clause(s) for that dispute type — e.g. card-network zero-liability rules for fraud, 90-day billing-error correction windows, subscription cancellation rules — so every recommendation is backed by a citable clause instead of an opaque decision. |
| **Resolution Agent** | [agents/resolution_agent.py](agents/resolution_agent.py) | Recommends the concrete action(s) to take (refund, partial refund, block card, escalate) along with the amount, currency, a plain-language rationale, and a citation back to the policy clause used. |
| **Document Analysis Agent** | [agents/document_analysis_agent.py](agents/document_analysis_agent.py) | Runs when the customer/agent uploads supporting documents to a case. Assesses whether each document looks authentic, whether it's relevant to the dispute, and whether it matches the transaction (amount, merchant, date) — producing a 0–100 trust score and reasoning per document, then a composite trust score across all documents for the case. |

The result of all four agents is stored together as a **case** (`cases_db`), so the full
reasoning trail (classification → policy → recommendation → evidence trust score) is
attached to the case for the human agent to review, not just a final verdict.

### How this aids dispute handling, concretely

- **Faster triage** — every new dispute is classified and given a recommended resolution
  within seconds of creation, instead of waiting in an unsorted queue for manual review.
- **Consistency** — the same dispute type always maps to the same policy clause and
  baseline resolution, reducing agent-to-agent variance in how similar cases are handled.
- **Explainability / auditability** — every recommendation carries a `rationale` and a
  `citations` field pointing at the specific policy clause it's based on
  ([models/schemas.py](models/schemas.py): `ResolutionRecommendation`), so an agent (or an
  auditor) can see *why* a refund was recommended, not just that it was.
- **Automated evidence screening** — instead of an agent manually eyeballing uploaded
  receipts/screenshots, the Document Analysis Agent scores each document's authenticity and
  relevance, and the case's `media_trust_score` automatically drives its status:
  - `> 90` → auto-escalated for senior review (high-trust evidence, often means the claim is
    strongly supported and may need higher-authority sign-off)
  - `60–90` → moved to `in_review` for a human agent
  - `< 60` → `pending_docs` (insufficient/weak evidence, more documentation requested)
- **Resilience** — every agent has deterministic fallback logic (keyword matching for
  classification, a fixed policy/resolution map, a safe default trust score) so the pipeline
  still produces a usable, reviewable result even if the LLM call fails or no API key is
  configured — it degrades gracefully instead of blocking the workflow.
- **Single pane of glass for the agent** — the dashboard ([templates/index.html](templates/index.html))
  shows open/in-review/escalated/resolved case counts, lets an agent open a case to see the
  full classification/policy/recommendation/evidence trail, upload more documents, and
  approve, escalate, or reopen the case — all backed by the same case record the agents
  populated.
- **In-app assistant (JUNO)** — a lightweight chatbot (`POST /api/chatbot/ask`) answers
  common agent questions (refund policy, escalation thresholds, required documents, SLAs,
  support contacts) and can list open cases (`GET /api/chatbot/open-cases`), so agents don't
  have to leave the case screen to look up policy basics.

## Tech stack

- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) ([main.py](main.py)) — serves both
  the REST API and the HTML frontend (via Jinja2 templates); there is no separate frontend
  build/server.
- **Agents / LLM**: [crewai](https://www.crewai.com/) + [LangChain](https://www.langchain.com/)
  (`langchain-openai`) calling the OpenAI API.
- **Frontend**: server-rendered Jinja2 templates ([templates/](templates/)) with vanilla
  JS/CSS ([static/](static/)) — dashboard, case detail modal, document upload, and the JUNO
  chatbot widget.
- **Data**: in-memory Python dicts (`cases_db`, `transactions_db`, `sessions`, etc. in
  `main.py`) seeded from [data/sample_data.json](data/sample_data.json) on startup — there is
  no persistent database, so all case data resets when the server restarts.
- **Auth**: simple cookie-based sessions with SHA-256 hashed passwords for two demo users
  (see below). Not production-grade auth — intended for demoing the workflow.

## Project structure

```
main.py                    FastAPI app: routes, session/auth, case lifecycle
agents/
  classification_agent.py  Classifies dispute type from statement + risk signals
  policy_agent.py          Maps dispute type -> relevant policy clause(s)
  resolution_agent.py      Maps dispute type + policy -> recommended action(s)
  document_analysis_agent.py  Scores uploaded evidence for authenticity/relevance/trust
models/
  schemas.py                Pydantic models: Transaction, Case, ClassificationResult, etc.
data/
  sample_data.json          Seed transactions loaded into memory on startup
  policies/                 Reference policy material
templates/
  index.html                 Agent dashboard (cases, case detail, chatbot)
  login.html                 Login page
static/
  script.js, style.css       Frontend behavior and styling
```

## Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables**

   Copy [.env.example](.env.example) to `.env` and fill in a real OpenAI key:
   ```bash
   cp .env.example .env
   ```
   ```
   OPENAI_API_KEY=sk-your-real-key
   APP_HOST=0.0.0.0
   APP_PORT=8000
   ```
   `.env` is gitignored — never commit real keys. Without a valid key, the agents still work
   via their fallback logic (see above), but won't get the LLM's reasoning.

3. **Run the app**
   ```bash
   python main.py
   ```
   or
   ```bash
   uvicorn main:app --reload
   ```
   The app is served at **http://localhost:8000**.

## Logging in

Two demo accounts are seeded in `main.py` (`users_db`):

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | admin |
| `agent1` | `Agent@123` | agent |

## Typical workflow

1. Log in at `/login`.
2. From the dashboard, create a case for a transaction (`transaction_id` from
   [data/sample_data.json](data/sample_data.json), e.g. `TXN30001`) — this triggers
   classification → policy lookup → resolution recommendation automatically.
3. Open the case to review the agent's classification, cited policy, and recommended
   resolution.
4. Upload supporting documents — the Document Analysis Agent scores them and updates the
   case's media trust score and status.
5. Approve, escalate, or reopen the case based on the recommendation and evidence.
6. Ask JUNO (bottom-right chatbot) for quick policy/SLA lookups along the way.

## Known limitations

- All case/transaction/session data is **in-memory only** — restarting the server wipes it
  (transactions are reloaded from `data/sample_data.json`, but cases and sessions are not).
- Auth is intentionally minimal (hardcoded demo users, SHA-256 password hashing, in-memory
  sessions) — not suitable for production as-is.
- The JUNO chatbot is a simple keyword-matching lookup over a small hardcoded knowledge base,
  not a true RAG system over a document store.
