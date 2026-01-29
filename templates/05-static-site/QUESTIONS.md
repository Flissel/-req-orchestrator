# 📋 Static Site - Projekt-Fragebogen
## Template: 05-static-site (Next.js Static Export + MDX)

> **Ziel**: Durch Beantwortung dieser Fragen wird genug Kontext für die automatische Code-Generierung gesammelt.

---

## 🚀 QUICK-START

| Feld | Antwort |
|------|---------|
| **Site Name** | |
| **Domain** | |
| **Typ** | Blog, Docs, Landing, Portfolio |

---

## A. SITE-TYP & ZWECK

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| A1 | Primärer Zweck? | [ ] Blog [ ] Dokumentation [ ] Landing Page [ ] Portfolio [ ] Marketing | |
| A2 | Content-Menge? | 5-10 Seiten, 50+, 100+ | |
| A3 | Update-Frequenz? | Täglich, Wöchentlich, Monatlich | |
| A4 | Mehrere Autoren? | [ ] Ja [ ] Nein | |

---

## B. CONTENT STRUKTUR

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| B1 | Haupt-Seiten? | Home, About, Contact | |
| B2 | Content-Typen? | Blog Posts, Docs, Changelog | |
| B3 | Kategorien/Tags? | Themen-Gruppierung | |
| B4 | Hierarchie? | Docs mit Sections | |
| B5 | Search benötigt? | Volltext-Suche | |

---

## C. CONTENT MANAGEMENT

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| C1 | Content Source? | [ ] MDX Files (default) [ ] CMS (Contentlayer) [ ] Notion | |
| C2 | Headless CMS? | [ ] Keins [ ] Sanity [ ] Contentful [ ] Strapi | |
| C3 | Git-based? | [ ] Ja (MDX in Repo) [ ] Nein | |
| C4 | Draft Mode? | [ ] Ja [ ] Nein | |

---

## D. DESIGN & BRANDING

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| D1 | Primär-Farbe? | Hex-Code | |
| D2 | Sekundär-Farbe? | Hex-Code | |
| D3 | Font? | Inter, System, Custom | |
| D4 | Logo vorhanden? | SVG, PNG | |
| D5 | Dark Mode? | [ ] Ja [ ] Nein [ ] System | |

---

## E. TECH-STACK ENTSCHEIDUNGEN

### Framework & Build

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E1 | Framework? | [ ] Next.js Static (default) [ ] Astro [ ] 11ty | |
| E2 | MDX Plugins? | [ ] rehype-highlight [ ] remark-gfm [ ] Custom | |
| E3 | Image Optimization? | [ ] Next/Image [ ] Sharp [ ] External CDN | |

### Styling

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E4 | CSS Framework? | [ ] Tailwind CSS (default) [ ] CSS Modules [ ] Vanilla | |
| E5 | Component Library? | [ ] Custom [ ] shadcn/ui [ ] DaisyUI | |
| E6 | Animations? | [ ] Minimal [ ] Framer Motion [ ] CSS only | |

### Features

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E7 | Search? | [ ] Keins [ ] Algolia DocSearch [ ] Pagefind [ ] Custom | |
| E8 | Comments? | [ ] Keins [ ] Giscus [ ] Disqus | |
| E9 | Newsletter? | [ ] Keins [ ] Buttondown [ ] ConvertKit | |
| E10 | Analytics? | [ ] Keins [ ] Vercel Analytics [ ] Plausible [ ] Umami | |

---

## F. SEO & PERFORMANCE

| # | Frage | Antwort |
|---|-------|---------|
| F1 | Meta Description Template? | |
| F2 | Open Graph Images? | Auto-generiert, Custom | |
| F3 | Sitemap? | Ja (default) | |
| F4 | RSS Feed? | Ja/Nein | |
| F5 | Canonical URLs? | Domain-Struktur | |
| F6 | Structured Data? | Schema.org (Article, FAQ) | |

---

## G. DEPLOYMENT

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| G1 | Hosting? | [ ] Vercel (empfohlen) [ ] Netlify [ ] GitHub Pages [ ] Cloudflare | |
| G2 | Domain? | [ ] Eigene [ ] Subdomain | |
| G3 | Preview Deployments? | [ ] Ja [ ] Nein | |
| G4 | Edge Functions? | [ ] Nein [ ] Ja (Forms, etc.) | |

---

## H. INTERNATIONALISIERUNG

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| H1 | Mehrsprachig? | [ ] Nein [ ] DE + EN [ ] Weitere | |
| H2 | URL Struktur? | /de/, /en/ oder Subdomains | |
| H3 | Default Sprache? | | |

---

# 📊 GENERIERUNGSOPTIONEN

- [ ] Page Templates
- [ ] MDX Components
- [ ] Navigation
- [ ] Footer
- [ ] SEO Config
- [ ] Sitemap
- [ ] RSS Feed
- [ ] Theme Config
- [ ] Deploy Config

---

# 🔧 TECH-STACK ZUSAMMENFASSUNG

```json
{
  "template": "05-static-site",
  "frontend": {
    "framework": "Next.js 14 (Static Export)",
    "content": "MDX",
    "styling": "Tailwind CSS",
    "language": "TypeScript"
  },
  "features": {
    "seo": "next-seo",
    "sitemap": "next-sitemap",
    "search": "Pagefind"
  },
  "deployment": {
    "platform": "Vercel / Netlify",
    "output": "Static HTML/CSS/JS"
  }
}
```
