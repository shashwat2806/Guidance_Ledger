"""FastAPI application entrypoint.

Week 1 scope: a health-check endpoint that confirms the API can reach Postgres.
Claim, verification, and guidance routers are added from Week 5 onward \u2014
see the week-by-week checklist in CLAUDE.md.
"""
from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.session import get_db

app = FastAPI(
    title="GuidanceLedger",
    description="Evidence-backed earnings claim and guidance auditor",
    version="0.1.0",
)


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Confirms the API process is up and can reach Postgres."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}


@app.get("/")
def root():
    return {"service": "guidanceledger", "status": "Week 1 skeleton \u2014 see /health"}
