# GuidanceLedger

Evidence-backed earnings-claim and guidance auditor. Full design in
`GuidanceLedger_FINAL_Proposal.pdf`; build-time reference in `CLAUDE.md`.

## Week 1 status

Repo skeleton, Docker + Postgres wiring, and a health-check endpoint that
confirms the API can reach the database. SEC client and everything else
comes next.

## Running it

1. Copy `.env.example` to `.env` and fill in `SEC_USER_AGENT` at minimum.
2. `docker compose up --build`
3. Visit http://localhost:8000/health — should return
   `{"status": "ok", "database": "reachable"}`.

## Tests

```
pip install -r requirements-dev.txt
pytest
```
