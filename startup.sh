#!/bin/bash

# Startup script für Requirements Evaluator Backend
# Stellt sicher, dass die Datenbank korrekt initialisiert wird

echo "Starting Requirements Evaluator Backend..."

# Ensure data directory exists
mkdir -p /data

# Initialize database if it doesn't exist
if [ ! -f "/data/app.db" ]; then
    echo "Initializing database..."
    python -c "
from backend_app.db import init_db
try:
    init_db()
    print('Database initialized successfully')
except Exception as e:
    print(f'Database initialization failed: {e}')
    exit(1)
"
else
    echo "Database already exists"
fi

# Start the application
echo "Starting Gunicorn server..."
exec gunicorn -w 2 -b 0.0.0.0:5000 --timeout 300 wsgi:app