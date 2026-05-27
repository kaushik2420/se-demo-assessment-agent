# SurveySparrow SE Demo Assessment Agent

An AI agent that joins Zoom / Google Meet / MS Teams calls (via Recall.ai), transcribes them, scores Solution Engineer (SE) performance against a configurable rubric, extracts deal-intelligence signals, and emails monthly performance reports to each SE plus a CEO-level executive summary.

---

## What it does

1. **Joins the call** as a silent participant (Recall.ai bot) OR **ingests recordings** from HubSpot / Avoma / manual upload.
2. **Transcribes & diarizes** speakers (Recall.ai → Deepgram / AssemblyAI). Identifies SE vs Account Executive (AE) vs Prospect using HubSpot attendee data + voice fingerprints.
3. **Scores the SE** against your 7-criteria, 100-point rubric (Communication, Presentation, Audience Engagement, Solution Skills, Consultative Approach, Pain Points, Craftsmanship).
4. **Extracts 9 deal-intelligence signals** from every call:
   - Use case being asked for
   - CX Maturity classification (Form / Low / Potential High / High) per your framework
   - Feature requests
   - Competitor mentions
   - Trial issues
   - Loss reasons (references, support, pricing, etc.)
   - AE interruption / barge-in count against the SE
   - Feature-selling vs value-selling ratio
   - Sentiment & prospect engagement
5. **Generates monthly reports**:
   - Per-SE Word doc: scores, trends, strengths, gaps, **industry benchmark comparison**, coaching plan
   - CEO executive summary: top 5 product gaps, top 5 process gaps, AE-quality risk signals
6. **Emails** each SE (CC: kaushikn2416@gmail.com) and a separate exec email to the CEO.

---

## Quick start (local prototype)

```bash
# 1. Install
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure (.env)
cp .env.example .env
# Add ANTHROPIC_API_KEY, RECALL_API_KEY, HUBSPOT_TOKEN, AWS_SES creds

# 3. Run the demo end-to-end on the sample transcript
python -m src.main --demo

# Produces:
#   out/se_report_<name>_<month>.docx
#   out/exec_summary_<month>.docx
#   out/raw_analysis.json
```

By default the demo uses a **mocked Claude response** so it runs without API keys. Set `ANTHROPIC_API_KEY` in `.env` and pass `--live` to call the real Claude API.

---

## Repo layout

```
se-demo-assessment-agent/
├── src/
│   ├── ingestion/          # Recall.ai bot, HubSpot, Avoma fetchers
│   ├── analysis/           # Scoring engine, insight extractor, CX maturity classifier
│   ├── reports/            # SE monthly + CEO exec summary generators (.docx)
│   ├── notifications/      # SES email sender
│   ├── storage/            # DynamoDB / Postgres models
│   └── utils/              # Industry benchmark store, config, logging
├── prompts/                # Versioned Claude prompts (scoring, insights, exec summary)
├── sample_data/            # Synthetic transcript + sample HubSpot payload for demo
├── infra/                  # Terraform: ECS Fargate, Lambda, DynamoDB, SES, S3, Secrets Manager
├── .github/workflows/      # CI/CD + auto-sync to SurveySparrow internal Bitbucket
├── tests/                  # Pytest unit + integration tests
└── docs/
    └── ARCHITECTURE.md     # System design, data flow, deployment, security
```

---

## How the prototype maps to production AWS

| Local prototype                | AWS production                                            |
| ------------------------------ | --------------------------------------------------------- |
| `python src/main.py --demo`    | EventBridge cron → ECS Fargate task (monthly)             |
| Recall.ai webhook handler      | API Gateway → Lambda → SQS → ECS analyzer                 |
| Local files in `out/`          | S3 (`s3://ss-se-reports/{month}/{se}/`)                   |
| In-memory benchmark store      | DynamoDB `se_industry_benchmarks` table                   |
| Mock LLM client                | Anthropic API (Claude Sonnet 4.6) via Secrets Manager     |
| Local SMTP test                | AWS SES with verified `coaching@surveysparrow.com` sender |
| `.env` file                    | AWS Secrets Manager + ECS task role                       |

See `docs/ARCHITECTURE.md` for the full design.

---

## GitHub → SurveySparrow internal Bitbucket flow

SurveySparrow keeps prod code in an internal Bitbucket repo. Development happens here in GitHub, and a CI job mirrors `main` to Bitbucket after security checks pass. See `.github/workflows/sync-to-bitbucket.yml`.

```
GitHub (dev)  ──PR + CI──▶  main  ──[security scan + signed mirror]──▶  Bitbucket (prod)  ──▶  AWS deploy
```
