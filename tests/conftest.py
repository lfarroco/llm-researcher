"""
Pytest bootstrap for the LLM Researcher test suite.

Ensures tests use a shared in-memory SQLite database by default so the
suite runs without a live PostgreSQL server:

- ``app.database`` binds its engine/SessionLocal at import time from
  ``settings.database_url``. Plain in-memory SQLite creates a fresh empty
  database per connection; the app engine uses StaticPool for ``:memory:``
  URLs (see ``app/database.py``), so all connections share one database.
- ``os.environ.setdefault`` means an explicitly provided ``DATABASE_URL``
  (e.g. CI's ``sqlite:///:memory:`` or a Docker/Postgres URL) always wins.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
