# Scamurai Usage Guide (Hinglish)

Poora platform browser se chalता hai. Backend `:8000` (FastAPI) aur frontend `:5173`
(React/Vite) dono alag services hain; frontend apne aap API calls ko backend par proxy
kar deta hai.

---

## 1. Ek baar ki setup (sirf nayi machine par)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python fixtures/make_fixture_images.py      # synthetic demo images
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (doosra terminal)
cd frontend
npm install
npm run dev
```

Docker se sab kuch ek saath: `docker compose up --build` (Postgres + Redis + MinIO + API + worker + UI).

Band ho gaye servers ko dobara start karna:

```bash
make run-api     # terminal 1
make run-web     # terminal 2
```

---

## 2. Login

Browser me frontend kholo (`http://localhost:5173` ya sandbox preview link).
Development ke 4 role-based demo tokens:

| Role | Token | Kar sakte hain |
|---|---|---|
| Owner | `dev-token-owner` | sab kuch + members + export |
| Analyst | `dev-token-analyst` | inputs, runs, transforms, export |
| Reviewer | `dev-token-reviewer` | findings accept/reject/need-more |
| Viewer | `dev-token-viewer` | sirf dekhna (read-only) |

> Production me ye screen real identity provider (OAuth/SSO) se replace hogi.

---

## 3. Pehla investigation — 7 goals

Start screen par 7 goal cards hain: **Check a post, Find image source, Estimate photo
location, Analyze comments, Compare accounts, Investigate coordination, Empty graph**.

1. Goal card click karo → case scope form aata hai (title, purpose, languages).
2. Case banne par 4-panel workspace khulta hai:
   - **Left** — case stats, relationship filters, connector capabilities
   - **Center** — Cytoscape evidence graph (node shape = entity type, line style = fact/signal/hypothesis)
   - **Right** — evidence drawer (kisi bhi node/edge par click karo)
   - **Bottom** — jobs & timeline (live stage updates)

---

## 4. Data daalna (import-first — koi live platform credential nahi chahiye)

Workspace ke top par 3 tareeke hain:

- **URL box** — `http/https` post/account link. SSRF policy automatically check hoti hai;
  internal/metadata addresses block ho jaate hain. Instagram jaise platform bina connector ke
  honestly `not_configured / access_required` record karte hain.
- **Text box** — post text/claim paste karo; normalized record + evidence snippet banta hai.
- **File upload** —
  - Images: `.png/.jpg/...` (magic-byte signature check hota hai, extension par bharosa nahi)
  - `.json` — posts bundle (`fixtures/posts.json` jaisa) ya fact-check library
  - `.csv` — comments export (coverage metadata ke saath)

Ready-made demo files: `backend/fixtures/` me hain — `posts.json`, `comments.csv`,
`factchecks.json`, aur `fixtures/images/` ke 8 synthetic images.

Demo case ek command me populate karna (server chalu hona chahiye):

```bash
make seed        # ya: cd backend && python scripts/seed_demo.py
```

---

## 5. Analysis chalana (bounded jobs)

Toolbar par 6 workflow buttons hain. Har ek HTTP 202 return karta hai aur bottom **Jobs
panel** me stage-wise progress dikhta hai (`queued → running → completed`, outcome
`complete / partial / insufficient_evidence`):

1. **Fetch permitted URLs** — public pages, SSRF-safe, login-wall honestly recorded
2. **Run image pipeline** — SHA-256 exact match → pHash candidates → sliding-window region
   verification → 5 match categories (`exact_file`, `likely_same_visual_source`,
   `partial_region_match`, `related_scene`, `no_match`)
3. **Analyze comments** — Hindi/English/Hinglish multilabel: insult, threat, spam, hate,
   quotation, sarcasm, negation, prompt-injection-as-data; har result uncalibrated labeled
4. **Detect coordination** — repeated aligned episodes, rarity aur timing precision;
   viral hashtag/breaking-news negative controls `insufficient_evidence` hi rehte hain
5. **Extract & check claims** — propositions, query plans, imported fact-checks se
   supported/refuted/insufficient
6. **Photo-to-location** — EXIF GPS ko "metadata-reported", generic scenes ko "insufficient";
   koi invented pin/university nahi

Kisi bhi job ko **Cancel** kar sakte ho — collected evidence delete nahi hota.

---

## 6. Graph padhna

- **Shapes**: account = rounded rectangle, post = rectangle, comment = diamond,
  media = circle, claim = hexagon, evidence = tag, place = pentagon, coordination = octagon
- **Lines**: solid green = source fact, dashed blue = algorithmic similarity,
  dotted purple = hypothesis, amber = analyst note
- Edge par click → right drawer me: exact statement, evidence IDs, method/version,
  limitations, review status. Hypothesis edge kabhi confident prose se fact nahi ban sakta.
- Left panel se relationship filters; graph toolbar se zoom/fit; **Compare tab** me
  2–4 accounts ka pairwise matrix (shared content, cross-links, timing, contradictions).
- **Shortest known evidence path** navigation aid hai — ownership/intent ka proof nahi.

---

## 7. Findings, review aur tabs

- **Findings tab** — 4 buckets: Established → Signals/hypotheses → Unknowns/insufficient →
  Conflicts/rejected. Reviewer/owner har finding par *Accept / Need more / Reject* kar sakte hain.
- **Comments tab** — coverage statement (non-comparable denominator kabhi 100% nahi banta),
  har row par **Explain** button, permalink status honestly shown.
- **Connectors tab** — live providers (YouTube comments import, Google Fact Check search).
  Key na ho to honestly `not configured`; free keys lene ki poori guide
  [`REQUIRED_CREDENTIALS.md`](REQUIRED_CREDENTIALS.md) me hai.
- **Agent tab** — goal choose karo; bounded agent allowlisted tools plan→policy→execute karta
  hai. External provider (OCR etc.) na ho to step honestly ruk jaata hai — koi fake evidence nahi.
- **Exports tab** — PDF/HTML/CSV/JSON, scope (all/selected/flagged), redaction mode
  (redacted vs full). Har artifact ka SHA-256 manifest hota hai aur download link expire hota hai.

---

## 8. API se bhi use kar sakte hain

Interactive docs: `http://localhost:8000/docs` (Swagger) — har endpoint try karne ke liye
`Authorize` me `dev-token-owner` daalo.

```bash
# case banao
curl -X POST localhost:8000/api/v1/cases -H "Authorization: Bearer dev-token-owner" \
  -H "Content-Type: application/json" -d '{"title":"Test","languages":["en","hi"]}'

# bounded agent chalao
curl -X POST localhost:8000/api/v1/cases/$CID/agent/run \
  -H "Authorization: Bearer dev-token-owner" -H "Content-Type: application/json" \
  -d '{"goal":"coordination","client_idempotency_key":"demo-0001"}'
```

Job progress SSE se milta hai: `GET /api/v1/cases/{id}/events` (reconnect `Last-Event-ID` se).

---

## 9. Testing aur evaluation

```bash
make test       # 30 pytest tests — acceptance gates, security, agent, adversarial fixtures
make eval       # fixture-based evaluation harness (label recall, match categories, controls)
```

## 10. Yaad rakhne wali limitations (honest by design)

- Live Instagram/Facebook/YouTube connectors, OCR, reverse image search, LLM, Jev **disabled**
  hain — UI unhe "not configured" dikhata hai; mock ko real evidence nahi banaya gaya.
- Comment classifier transparent but **uncalibrated** hai — production accuracy claim se pehle
  representative Hindi/Hinglish labeled data par precision/recall/calibration maapo.
- Dev tokens real auth nahi; deployment se pehle IdP, TLS, DPDP/legal review zaroori.
- Export PDFs integrity evidence hain, court-certified evidence nahi.
