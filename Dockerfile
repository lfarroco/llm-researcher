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

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
