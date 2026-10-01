FROM python:3.12-slim

WORKDIR /app

# Install system dependencies.
#
# Pandoc's default LaTeX template needs more than texlive-latex-base: the base
# package omits xcolor.sty and friends, so PDF export failed with
# "! LaTeX Error: File `xcolor.sty' not found." once the pandoc outputfile bug
# was fixed. -recommended plus -fonts-recommended covers the default template
# (lmodern is a separate small package). texlive-latex-extra is still
# deliberately excluded because it is very large; add it, or switch
# --pdf-engine, if a template needs a package from it.
RUN apt-get update && apt-get install -y \
	pandoc \
	texlive-latex-base \
	texlive-latex-recommended \
	texlive-fonts-recommended \
	lmodern \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run pending Alembic migrations on every container start, then launch the
# API. `alembic upgrade head` is idempotent (no-op when up to date), and the
# `exec` ensures uvicorn becomes PID 1 so it receives signals directly.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
