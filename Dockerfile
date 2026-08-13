FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
# Using texlive-latex-base instead of -extra to reduce size
# Most PDF features will work with just the base package
RUN apt-get update && apt-get install -y \
	pandoc \
	texlive-latex-base \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run pending Alembic migrations on every container start, then launch the
# API. `alembic upgrade head` is idempotent (no-op when up to date), and the
# `exec` ensures uvicorn becomes PID 1 so it receives signals directly.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
