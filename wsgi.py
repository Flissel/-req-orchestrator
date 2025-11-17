# -*- coding: utf-8 -*-
"""
WSGI-Einstiegspunkt für Gunicorn.
Exportiert die Variable 'app' aus backend_app.
"""

import os
from backend.core import app as app  # Gunicorn Entry: wsgi:app

if __name__ == "__main__":
    # Optionaler Direktstart (Entwicklung)
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8081"))
    app.run(host=host, port=port, debug=True)