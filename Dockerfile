FROM python:3.11-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# -------- Frontend Build (Node/Vite) --------
FROM node:20-slim AS frontend-builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --silent
COPY src/ ./src/
COPY public/ ./public/
COPY index.html vite.config.js ./
RUN npm run build

# -------- Dependencies --------
FROM base AS deps
COPY requirements_fastapi.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements_fastapi.txt \
 && pip install --no-cache-dir uvicorn

# -------- Production --------
FROM base AS production
ENV API_HOST=0.0.0.0 \
    BACKEND_PORT=8087 \
    SQLITE_PATH=/app/data/app.db \
    LLM_PROVIDER=openrouter \
    OPENAI_MODEL=anthropic/claude-haiku-4.5
COPY --from=deps /usr/local /usr/local
COPY . .
COPY --from=frontend-builder /app/dist /app/dist
RUN useradd --create-home --shell /bin/bash app \
 && mkdir -p /app/data /app/debug /app/projects \
 && chown -R app:app /app/data /app/debug /app/projects
USER app
ARG BACKEND_PORT=8087
EXPOSE ${BACKEND_PORT}
HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
  CMD curl -sf http://localhost:${BACKEND_PORT}/health || exit 1
CMD sh -c "uvicorn backend.main:fastapi_app --host 0.0.0.0 --port ${BACKEND_PORT:-8087} --workers 4"

# -------- Worker (optional, distributed agents) --------
FROM base AS worker
COPY --from=deps /usr/local /usr/local
COPY . .
CMD ["python", "-m", "agent_worker.app"]
