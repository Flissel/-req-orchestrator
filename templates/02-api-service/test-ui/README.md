# API Service Test Dashboard

Ein vollständiges Test-Dashboard für die FastAPI-Anwendung.

## Features

- **Request Builder**: GET, POST, PUT, PATCH, DELETE mit Headers und Body
- **Auth Support**: Bearer Token, Basic Auth, API Key
- **Swagger UI Integration**: Direkter Link zu `/docs`
- **Response Viewer**: Syntax Highlighting, Copy, Download
- **Request History**: Letzte 50 Requests mit Quick-Replay
- **Health Check**: Automatischer Status-Check
- **OpenAPI Schema**: Lädt Endpoints aus `/openapi.json`
- **Dark/Light Mode**: Theme Toggle

## Verwendung

1. API-Service starten:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. Test-UI öffnen:
   ```
   Öffne test-ui/index.html im Browser
   ```

3. Base URL konfigurieren (Standard: `http://localhost:8000`)

4. Endpoints aus der Sidebar auswählen oder manuell eingeben

## Keyboard Shortcuts

- `Ctrl+Enter` - Request senden
- `Ctrl+L` - Body leeren

## Tech Stack

- Vanilla HTML/CSS/JS (keine Build-Dependencies)
- Tailwind CSS (CDN)
- Highlight.js für Syntax Highlighting
