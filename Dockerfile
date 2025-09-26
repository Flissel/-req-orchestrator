FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies
COPY requirements.txt .
# Upgrade pip first to improve resolver stability and speed
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

# App
COPY . .

# Default Konfiguration für Prototyp
ENV API_HOST=0.0.0.0
ENV API_PORT=8081

# Ensure data directory exists and has proper permissions
RUN mkdir -p /data && chmod 755 /data


EXPOSE 8081

# Start gunicorn with extended timeout and concurrency
CMD ["sh","-lc","exec gunicorn -b 0.0.0.0:8081 wsgi:app --timeout 300 --workers 2 --threads 4"]