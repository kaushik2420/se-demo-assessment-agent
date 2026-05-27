# Backend — FastAPI + analyzer
FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg + bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Backend deps
COPY web/backend/requirements.txt /tmp/backend-requirements.txt
RUN pip install --no-cache-dir -r /tmp/backend-requirements.txt

# Analysis pipeline deps (rubric, llm client, etc.)
COPY requirements.txt /tmp/core-requirements.txt
RUN pip install --no-cache-dir -r /tmp/core-requirements.txt

# Copy app code
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY web/backend/ ./web/backend/

WORKDIR /app/web/backend

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/web/backend

EXPOSE 8000

# Render injects $PORT — honor it
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
