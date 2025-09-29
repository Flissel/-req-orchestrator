FROM python:3.11-slim AS base
# System-Pakete (schlank halten)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# -------- Dependencies: Legacy (Flask/Gunicorn) --------
FROM base AS deps_legacy
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# -------- Dependencies: FastAPI (Uvicorn/Gunicorn) --------
FROM base AS deps_fastapi
COPY requirements_fastapi.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements_fastapi.txt \
 && pip install --no-cache-dir gunicorn[gthread] uvicorn

# -------- Production: Legacy (Flask/Gunicorn) --------
FROM base AS production-legacy
ENV API_HOST=0.0.0.0 \
    API_PORT=8081 \
    SQLITE_PATH=/data/app.db
# Runtime-Dependencies aus deps_legacy übernehmen
COPY --from=deps_legacy /usr/local /usr/local
# App-Code
COPY . .
# Datenverzeichnis
RUN mkdir -p /data && chmod 755 /data
EXPOSE 8081
HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
  CMD curl -sf http://localhost:8081/health || exit 1
# Start (Gunicorn, WSGI Entry muss vorhanden sein)
CMD ["sh","-lc","exec gunicorn -b 0.0.0.0:8081 wsgi:app --timeout 300 --workers 2 --threads 4"]

# -------- Production: FastAPI (Uvicorn) --------
FROM base AS production-fastapi
ENV API_HOST=0.0.0.0 \
    API_PORT=8000 \
    SQLITE_PATH=/app/data/app.db
# Runtime-Dependencies aus deps_fastapi übernehmen
COPY --from=deps_fastapi /usr/local /usr/local
# App-Code
COPY . .
# Unprivilegierter User + Datenverzeichnis
RUN useradd --create-home --shell /bin/bash app \
 && mkdir -p /app/data \
 && chown -R app:app /app/data
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
  CMD curl -sf http://localhost:8000/health || exit 1
# Start (Uvicorn mit FastAPI v2 App)
CMD ["uvicorn","backend_app_v2.main:fastapi_app","--host","0.0.0.0","--port","8000","--workers","4"]

# -------- Worker (optional, gRPC/Agents) --------
FROM base AS worker
# Dependencies aus deps_fastapi (gemeinsame Abhängigkeiten)
COPY --from=deps_fastapi /usr/local /usr/local
COPY . .
CMD ["python","worker_startup.py"]