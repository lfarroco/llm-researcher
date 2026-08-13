#!/usr/bin/env python3
"""Run llm-researcher locally without Docker/Postgres.

Boots the FastAPI app against a SQLite database (in-memory by default) and
serves it with uvicorn on http://127.0.0.1:8000. This is the fastest way to
explore the API (http://127.0.0.1:8000/docs) or to run
``scripts/smoke_research.py`` in ``--live`` mode.

Usage:
    python scripts/dev_server.py             # in-memory DB, port 8000
    python scripts/dev_server.py --port 9000
    DATABASE_URL=sqlite:////tmp/dev.db python scripts/dev_server.py

Notes:
- The schema is created with ``Base.metadata.create_all`` — no Alembic is
  needed for SQLite dev runs.
- The default in-memory database is ephemeral: stopping the server resets all
  data.
- File-based SQLite URLs work for single-process use but may raise cross-thread
  errors under heavy concurrent load (the app engine only passes
  ``check_same_thread=False`` for ``:memory:`` URLs).
"""

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.database import Base, engine  # noqa: E402
import app.models  # noqa: E402, F401  (import registers all tables)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)

    import uvicorn

    print(f"[dev_server] DATABASE_URL={os.environ['DATABASE_URL']}")
    print(f"[dev_server] serving on http://{args.host}:{args.port}")

    # Import as string so uvicorn reload/workers keep the same module identity.
    uvicorn.run("app.main:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
