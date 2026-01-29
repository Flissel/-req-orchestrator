# 📋 AI Chatbot - Projekt-Fragebogen
## Template: 11-chatbot (LangChain + FastAPI + Next.js)

> **Ziel**: Durch Beantwortung dieser Fragen wird genug Kontext für die automatische Code-Generierung gesammelt.

---

## 🚀 QUICK-START

| Feld | Antwort |
|------|---------|
| **Bot Name** | |
| **Bot Persona** | Assistent, Experte, Freundlich |
| **Primärer Use Case** | Support, Q&A, Sales, Custom |

---

## A. BOT-TYP & ZWECK

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| A1 | Was macht der Bot? | Customer Support, FAQ, Tutor | |
| A2 | Domäne? | Allgemein, Produkt-spezifisch, Firma | |
| A3 | Zielgruppe? | Kunden, Mitarbeiter, Entwickler | |
| A4 | Sprachen? | DE, EN, Multi-lingual | |
| A5 | Tone of Voice? | Formell, Casual, Humorvoll | |

---

## B. KONVERSATIONS-FEATURES

| # | Frage | Benötigt? |
|---|-------|-----------|
| B1 | Multi-Turn Conversations? | [ ] Ja [ ] Nein |
| B2 | Context Memory? | [ ] Session [ ] Persistent [ ] None |
| B3 | Conversation History? | [ ] Ja [ ] Nein |
| B4 | Suggested Responses? | [ ] Ja [ ] Nein |
| B5 | Typing Indicator? | [ ] Ja [ ] Nein |
| B6 | Rich Messages? | [ ] Markdown [ ] HTML [ ] Plain |
| B7 | File/Image Upload? | [ ] Ja [ ] Nein |
| B8 | Voice Input/Output? | [ ] Ja [ ] Nein |

---

## C. RAG (Retrieval-Augmented Generation)

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| C1 | Knowledge Base nötig? | [ ] Ja [ ] Nein | |
| C2 | Datenquellen? | [ ] Docs [ ] Website [ ] Database [ ] API | |
| C3 | Update-Frequenz? | Einmalig, Täglich, Real-time | |
| C4 | Vector Database? | [ ] ChromaDB [ ] Pinecone [ ] Qdrant [ ] Weaviate | |
| C5 | Embedding Model? | [ ] OpenAI [ ] Cohere [ ] Local | |
| C6 | Chunk Size? | 500, 1000, 2000 tokens | |

---

## D. TECH-STACK ENTSCHEIDUNGEN

### LLM Provider

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D1 | Primärer LLM? | [ ] OpenAI GPT-4 [ ] Claude [ ] Gemini [ ] Local (Ollama) | |
| D2 | Fallback LLM? | [ ] Keins [ ] GPT-3.5 [ ] Andere | |
| D3 | Streaming? | [ ] Ja (empfohlen) [ ] Nein | |
| D4 | Function Calling? | [ ] Ja [ ] Nein | |
| D5 | Multi-Modal? | [ ] Nein [ ] Vision [ ] Audio | |

### Backend

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D6 | Framework? | [ ] LangChain (empfohlen) [ ] LlamaIndex [ ] Custom | |
| D7 | API Framework? | [ ] FastAPI (default) [ ] Flask | |
| D8 | Agent/Chain Type? | [ ] Conversational [ ] ReAct [ ] Plan-and-Execute | |
| D9 | Tools/Functions? | Web Search, Calculator, API Calls | |

### Frontend

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D10 | Chat UI? | [ ] Next.js (default) [ ] React [ ] Widget | |
| D11 | UI Library? | [ ] Custom [ ] shadcn/ui [ ] AI SDK UI | |
| D12 | Deployment? | [ ] Standalone [ ] Embedded Widget [ ] API only | |

### Storage

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D13 | Chat History? | [ ] SQLite [ ] PostgreSQL [ ] Redis | |
| D14 | Session Management? | [ ] Server-side [ ] Client-side | |
| D15 | Analytics? | [ ] Keins [ ] Custom [ ] LangSmith | |

---

## E. SAFETY & GUARDRAILS

| # | Frage | Antwort |
|---|-------|---------|
| E1 | Content Filter? | Toxic, NSFW, PII |
| E2 | Prompt Injection Protection? | Ja/Nein |
| E3 | Output Validation? | Schema, Length, Format |
| E4 | Rate Limiting? | Per User/IP |
| E5 | Human Handoff? | Eskalation zu Support |
| E6 | Fallback Responses? | Bei Unsicherheit |

---

## F. INTEGRATIONS

| # | Frage | Benötigt? | Details |
|---|-------|-----------|---------|
| F1 | Web Widget? | [ ] Ja [ ] Nein | Embed in Website | |
| F2 | Slack? | [ ] Ja [ ] Nein | Bot Integration | |
| F3 | Teams? | [ ] Ja [ ] Nein | Bot Framework | |
| F4 | WhatsApp? | [ ] Ja [ ] Nein | Twilio/Meta | |
| F5 | API Access? | [ ] Ja [ ] Nein | Third-party | |

---

## G. MONITORING & ANALYTICS

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| G1 | Conversation Logs? | [ ] Ja [ ] Nein | |
| G2 | User Feedback? | [ ] Thumbs Up/Down [ ] Rating [ ] None | |
| G3 | Performance Metrics? | Latency, Token Usage | |
| G4 | Tracing? | [ ] LangSmith [ ] Langfuse [ ] None | |
| G5 | A/B Testing? | [ ] Ja [ ] Nein | |

---

## H. DEPLOYMENT

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| H1 | Hosting? | [ ] Vercel + Railway [ ] AWS [ ] Self-hosted | |
| H2 | Scaling? | Auto-scale, Fixed | |
| H3 | Cold Start? | Acceptable Latency | |
| H4 | Secrets? | API Keys sicher speichern | |

---

# 📊 GENERIERUNGSOPTIONEN

- [ ] LangChain Pipeline
- [ ] FastAPI Backend
- [ ] Chat UI (Next.js)
- [ ] RAG Setup (optional)
- [ ] Vector Store Config
- [ ] Prompt Templates
- [ ] Safety Middleware
- [ ] Docker Compose
- [ ] Deployment Config

---

# 🔧 TECH-STACK ZUSAMMENFASSUNG

```json
{
  "template": "11-chatbot",
  "llm": {
    "primary": "OpenAI GPT-4 / Claude",
    "framework": "LangChain",
    "streaming": true
  },
  "backend": {
    "framework": "FastAPI",
    "language": "Python 3.12"
  },
  "frontend": {
    "framework": "Next.js 14",
    "ui": "Chat Interface"
  },
  "storage": {
    "history": "SQLite / PostgreSQL",
    "vectors": "ChromaDB"
  },
  "monitoring": {
    "tracing": "LangSmith",
    "analytics": "Custom"
  }
}
```
