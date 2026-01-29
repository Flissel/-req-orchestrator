# 📋 Realtime App (Socket.io) - Projekt-Fragebogen
## Template: 12-realtime-socketio (Socket.io + Express + Next.js)

> **Ziel**: Durch Beantwortung dieser Fragen wird genug Kontext für die automatische Code-Generierung gesammelt.

---

## 🚀 QUICK-START

| Feld | Antwort |
|------|---------|
| **App Name** | |
| **Realtime Use Case** | Chat, Gaming, Collaboration, Live Updates |
| **Erwartete Connections** | 100, 1.000, 10.000+ |

---

## A. USE CASE

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| A1 | Haupt-Use-Case? | [ ] Chat [ ] Gaming [ ] Collaboration [ ] Dashboard [ ] Notifications | |
| A2 | Bidirektional? | [ ] Ja (Chat) [ ] Hauptsächlich Push [ ] Hauptsächlich Pull | |
| A3 | Latency-kritisch? | [ ] Ja (<50ms) [ ] Moderat (<200ms) [ ] Tolerant | |
| A4 | Persistence nötig? | [ ] Messages speichern [ ] Ephemeral | |

---

## B. REALTIME FEATURES

| # | Frage | Benötigt? |
|---|-------|-----------|
| B1 | Private Messaging? | [ ] Ja [ ] Nein |
| B2 | Group/Room Chat? | [ ] Ja [ ] Nein |
| B3 | Typing Indicator? | [ ] Ja [ ] Nein |
| B4 | Presence (Online/Offline)? | [ ] Ja [ ] Nein |
| B5 | Read Receipts? | [ ] Ja [ ] Nein |
| B6 | File Sharing? | [ ] Ja [ ] Nein |
| B7 | Reactions/Emoji? | [ ] Ja [ ] Nein |
| B8 | Voice/Video? | [ ] Ja [ ] Nein |

---

## C. ROOMS & CHANNELS

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| C1 | Room-Konzept? | Channels, Conversations, Games | |
| C2 | Max Users pro Room? | 2, 10, 100, unbegrenzt | |
| C3 | Private Rooms? | Invite-only | |
| C4 | Room Persistence? | Rooms bleiben nach Disconnect | |
| C5 | Room Events? | Join, Leave, Kick | |

---

## D. TECH-STACK ENTSCHEIDUNGEN

### Realtime Backend

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D1 | Transport? | [ ] Socket.io (empfohlen) [ ] Native WebSocket [ ] SSE | |
| D2 | Server Runtime? | [ ] Node.js (default) [ ] Bun | |
| D3 | Framework? | [ ] Express [ ] Fastify [ ] Hono | |
| D4 | TypeScript? | [ ] Ja (empfohlen) [ ] JavaScript | |

### Scaling

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D5 | Horizontal Scaling? | [ ] Nein (single instance) [ ] Redis Adapter [ ] Kafka | |
| D6 | Load Balancer? | [ ] Nein [ ] Nginx [ ] HAProxy [ ] Cloud LB | |
| D7 | Sticky Sessions? | [ ] Ja [ ] Nein (Redis Adapter) | |

### Database & Persistence

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D8 | Message Storage? | [ ] Keine [ ] PostgreSQL [ ] MongoDB [ ] Redis | |
| D9 | Presence Storage? | [ ] In-Memory [ ] Redis | |
| D10 | Session Storage? | [ ] In-Memory [ ] Redis | |

### Frontend

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D11 | Frontend Framework? | [ ] Next.js (default) [ ] React [ ] Vue | |
| D12 | Socket.io Client? | [ ] socket.io-client [ ] Native WebSocket | |
| D13 | UI Library? | [ ] shadcn/ui [ ] Custom | |

---

## E. AUTHENTICATION

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E1 | Auth Required? | [ ] Ja [ ] Optional [ ] Nein | |
| E2 | Auth Method? | [ ] JWT [ ] Session [ ] API Key | |
| E3 | Socket Auth? | [ ] Connection Handshake [ ] First Message | |
| E4 | Reconnect Auth? | Token Refresh Strategy | |

---

## F. PERFORMANCE & RELIABILITY

| # | Frage | Antwort |
|---|-------|---------|
| F1 | Max Concurrent Connections? | |
| F2 | Message Rate Limit? | Per User/Second |
| F3 | Reconnection Strategy? | Exponential Backoff |
| F4 | Heartbeat Interval? | 25s (default) |
| F5 | Connection Timeout? | |
| F6 | Message Queue? | Bei Disconnect |

---

## G. MONITORING

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| G1 | Connection Metrics? | [ ] Custom [ ] Prometheus [ ] None | |
| G2 | Message Metrics? | [ ] Ja [ ] Nein | |
| G3 | Error Tracking? | [ ] Sentry [ ] Custom [ ] None | |
| G4 | Logging? | [ ] Winston [ ] Pino | |

---

## H. DEPLOYMENT

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| H1 | Hosting? | [ ] Railway [ ] Render [ ] AWS [ ] Self-hosted | |
| H2 | Container? | [ ] Docker [ ] None | |
| H3 | HTTPS/WSS? | [ ] Ja (required) | |
| H4 | CORS Config? | Allowed Origins | |

---

# 📊 GENERIERUNGSOPTIONEN

- [ ] Socket.io Server
- [ ] Event Handlers
- [ ] Room Management
- [ ] Auth Middleware
- [ ] Message Persistence
- [ ] Frontend Client
- [ ] Chat UI Components
- [ ] Redis Adapter Config
- [ ] Docker Compose

---

# 🔧 TECH-STACK ZUSAMMENFASSUNG

```json
{
  "template": "12-realtime-socketio",
  "backend": {
    "runtime": "Node.js",
    "framework": "Express + Socket.io",
    "language": "TypeScript"
  },
  "scaling": {
    "adapter": "Redis Adapter",
    "sessions": "Sticky Sessions / Redis"
  },
  "frontend": {
    "framework": "Next.js 14",
    "client": "socket.io-client"
  },
  "storage": {
    "messages": "PostgreSQL",
    "sessions": "Redis"
  }
}
```
