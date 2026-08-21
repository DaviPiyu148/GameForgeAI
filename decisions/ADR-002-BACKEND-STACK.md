# ADR-002 — Backend Stack

**Status:** Accepted

## Decision
Python + FastAPI + Pydantic + SQLAlchemy + SQLite + Alembic, structured as a modular monolith.

## Rationale
Strong AI/data ecosystem, fast API development, typed validation, low infrastructure cost, straightforward local deployment.

## Deferred
Celery, Redis, PostgreSQL, microservices, and other infrastructure require explicit justification and a new decision. Local LLMs are explicitly rejected per ADR-006 (Hosted LLM Provider).
