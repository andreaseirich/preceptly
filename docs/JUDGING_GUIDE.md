# TutorFlow – Judging Guide

Single-page orientation for reviewers/judges (CodeCraze Hackathon). Focus: fast-start demo, clear core flows, safety notes.

## Start in < 2 minutes
- **Setup:**
  ```bash
  cp .env.example .env
  ./scripts/run_demo.sh
  ```
- **Health check:** `curl http://127.0.0.1:8000/health/` → `{ "status": "ok" }`
- **Logins:**
  - Premium (AI): `demo_premium` / `demo123`
  - Standard: `demo_user` / `demo123`
- **Mock safety:** `MOCK_LLM=1` prevents external API calls; all AI responses come from `docs/llm_samples.json`.

## Judging shortcuts by category
- **Best UI/Creativity:** Interactive week view (click-to-create, conflict icons, blocked times); mention dark/light design if enabled.
- **Best AI/ML:** AI lesson plan flow with mock mode + PII sanitizer; note retries on rate limits.
- **Best Solo Build:** Highlight solo scope, deterministic demo + CI (MOCK_LLM, Django check/tests, Ruff) as quality signals.
- **Overall Excellence:** Clear problem/solution story, end-to-end flow (plan → conflict → billing → AI plan), stable demo without external dependencies.

## Troubleshooting
- Health check fails → run `./scripts/smoke_demo.sh` and inspect container logs.
- Missing translations → `python manage.py compilemessages` (already in the demo setup).
- Reset data → `python manage.py loaddata fixtures/demo_data.json`.