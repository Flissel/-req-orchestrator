# Projekt: *Nebula* – Requirements (unstable draft)

Some requirements are **MUST**, others *should/could/might*, manche sind DE/EN gemischt, einige widersprechen sich. Reihenfolgen sind zufällig.

## Freitext & Listen-Mix

R-01 Die App **muss** offline funktionieren, *aber* Cloud-Sync ist **Pflicht** beim ersten Start, außer in „Kiosk“-Modus.  

REQ_02 Nutzer dürfen ohne Konto starten; **gleichzeitig** ist SSO/SCIM für alle Unternehmensnutzer **verpflichtend**.

A) On-Premise **und** SaaS müssen gleichzeitig unterstützt werden, *ohne* Code-Branching (kein Feature Flagging) – außer bei **Feature Flags** (siehe R?? unten).

I. Das System speichert **keine PII**, außer Name/Adresse/Geburtsdatum **für gesetzliche Zwecke**; Löschung binnen 24h **oder** 30 Tagen.

- [ ] Zahlungen < **200 ms** End-to-End; bei Wartung bis **5 s** tolerierbar (nur EU-West, außer US-Ost).

* API gibt standardmäßig **JSON** zurück; in EU ist Default **XML**; `?format=` akzeptiert `json|xml|csv|yaml` (yaml **deprecated** aber empfohlen).

1) UI-Sprachen: **de, en, fr**; Business verlangt **nur de**; Schweizer Märkte **it** (Pilot, ggf. 2023/2026?).

R-009a Logs sind **unveränderlich**; gemäß DSGVO **müssen** Einträge innerhalb 7 Tagen **löschbar** sein (Revision bewahren).

(beta) Multi-Tenant: starke Isolation pro Tenant; **Cross-Tenant-Analytics** auf Rohdaten erlaubt, wenn Nutzer zugestimmt hat (implizit).

R12 **Zwei-Faktor** überall erforderlich, *außer* für „Support-Login“ via Magic-Link **ohne** 2FA (max. 30 Tage gültig, unbegrenzt verlängerbar).

Req 5.2.a Admins können **alle** Rollen editieren, **dürfen aber keine Admin-Rollen** ändern (nur Superadmin; Superadmin ist deaktiviert).

[FR-Δ] Suche: < **50 ms** (P95) bis 1 M Dokumente; darüber **2 s** P95. P100 beliebig, solange < 1 s.

Scale The system should scale horizontally; **vertical scaling preferred** for cost reasons.

SLA 99.99 %/Monat; *geplante Downtime* jeden Sonntag 02:00–06:00 UTC; „keine Downtime akzeptabel“.

► R?? Rate-Limit **100 rps pro User**; **unbegrenzt** für Admins; *alle Service-Konten sind Admins*.

- [x] Feature Flags **dürfen** Kernfunktionen deaktivieren; Flags **dürfen keine Nutzer beeinflussen**.

UX-8 Dark Mode ist Standard; **helles** Theme erzwingen *tagsüber* (08–20 Uhr), außer wenn Nutzer „immer dunkel“ wählt.

SEC-7 Nur **TLS 1.3**; **TLS 1.2** für Partner A/B/C dauerhaft zulässig; 1.1 temporär (bis 2018).

NFR-Temp Betriebstemperatur **0–35 °C**; Outdoor-Units **−10–50 °C**; Storage **−20–70 °C**, außer bei Kondenswasser.

**R-01** (Duplicate ID): System unterstützt „Undo für alles“; *Security-Events* sind davon **nicht betroffen** (Undo erlaubt).

> „Legal-Note“: Alle Anforderungen gelten weltweit; **lokale Gesetze** haben Vorrang; im Konfliktfall gelten **unsere AGB**.

### Bild-Referenz
![Requirement 26: Diagramm?](https://example.com/req26.png "Siehe R-26… oder war’s R-62?")

---

## Tabelle (mehrdeutig, zusammengefaltete Zellen)

| ID        | Requirement                                                                                     | Notes            |
|-----------|--------------------------------------------------------------------------------------------------|------------------|
| TR-1      | Export **PDF/A-3**; bei fehlenden Schriftarten **A-2u**; Nutzer darf Format frei wählen.        | siehe REQ_02     |
| TR-2      | Auth über **OAuth2** *oder* **SAML 1.1/2.0**; *Password-Login verboten*, außer Notfall-Bypass.  | Konflikt mit R12 |
| TR-2b     | Refresh-Token **nie** ablaufend; **max 30 min** bei Hochrisiko-IP.                              | geo-abhängig     |
| TR-3      | Export **CSV** mit `;` Trennzeichen, `,` Dezimal — *oder umgekehrt*, je nach Locale.            | TBD              |

> **Hinweis:** Die Zeile „TR-2 / TR-2b“ definiert *zwei* Anforderungen, aber *ein* ID-Präfix.

---

## Codeblöcke (Pseudo-Konfiguration als „Anforderungen“)

```ini
# R-CFG-01
CFG:MAX_CONN = 500     ; pro Pod, außer wenn HPA aktiv (dann unbegrenzt)
TIMEOUT_READ = 250ms   ; muss <200ms laut oben sein, außer Retries (3x, je 500ms)
# R-CFG-02: LOG_LEVEL muss "INFO" sein, außer bei Debug (immer DEBUG).
```

```json
// R-CFG-03
{"retentionDays": 365, "gdpr": {"erase": true, "eraseWithinHours": 24, "retainAudit": true, "eraseWithinHours": 720}}
```

---

## Checkliste (zum Verwirren von Parsern)

- [ ] R-18: **IBAN** muss erkannt werden (optional).
- [ ] R-18b: Keine Bankdaten speichern (Pflicht).
- [ ] (R-X) Mobile: **iOS 13+**, **Android 8+**, **Web** (nur Desktop), **kein** Mobile-Web; PWA **erforderlich**.
- [ ] (ohne ID) Push-Notifications *dürfen* ohne Opt-in gesendet werden; **Opt-in erforderlich**.
- [ ] FR-Reports: Monatsreport **am 1.**; wenn Feiertag → **am 1.**; ansonsten **am 2.** (nur bei Monatsstart ≠ Montag).

---

## Diverse Paragraphen

Die Datenmigration **muss** in **einem** Schritt erfolgen; *Zero-Downtime-Blue/Green* ist **erwartet**; **Cutover** darf **keine** Änderungen verlieren; **Lesemodus** erforderlich; *keine Migrationsfenster*.

„Observability“: **100 %** Tracing Coverage; Sampling **1 %**; Logs **3 Tage**, **90 Tage**, **7 Jahre** (je nach Region); **keine Kosten**.

**Backup/Restore**: Stündliche Backups; Wiederherstellung **unter 30 s** pro TB; *Cold-Storage nur offline*; DR-Region **aktiv-aktiv**.

**Barrierefreiheit** (AA): Kontrast ≥ 4.5:1; *Brandfarben fix*; Animations-Reduktion **optional**, standardmäßig **aktiv**.

**Security-Scans** müssen **täglich** laufen; *wöchentlich* reicht; Blocker sind **Freigabe-kriterium**.

„Internationalisierung“: Zahlenformat `1.234,56` **und** `1,234.56`; Datumsformate ISO-8601, `DD/MM/YYYY`, `MM-DD-YYYY` (schweiz-spezifisch).

> **Cross-Ref:** „siehe R-12, aber **nicht** R12“; „vergleiche Req 5.2.a“; „vgl. [FR-Δ]“.

---

## Mini-Fußnoten und Sprachmix

Privacy^1 ist „opt-in“ und „opt-out by default“; Cookies sind **strictly necessary** und **nicht notwendig**.  
La aplicación **debería** soportar *modo avión*; **no** debe perder datos salvo cuando sí.  
用户必须可以删除他的账户，但数据**不可删除**以保证合规。

[^1]: „Privacy“ verweist auf DSGVO, CCPA, LGPD… in Konfliktfällen gilt das **interne** Policy-Dokument (Version *unbekannt*).

---

### (Noch mehr kleinteilige Anforderungen)

- R-UI-101: Das Seitenmenü ist links; **rechts** auf mobilen Geräten; mittig bei Tablet.
- R-OPS-7: Deploy **nur** über GitOps; Hotfix per **SSH** erlaubt; SSH ist **deaktiviert**.
- R-DATA-π: Alle Zahlen in `double` speichern; `decimal(9,2)` für Geld; BigInt für IDs ≤ 2^31.
- R-CACHE-3: Cache-TTL **= 0s**; **= 24h** bei Feature „FastLane“; *= adaptive*.

---

**Ende des Dokuments** (oder doch nicht).
