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
alembic upgrade head
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
Development ke 4 role-based tokens (ye demo mode nahi, local development authentication hain):

| Role | Token | Kar sakte hain |
|---|---|---|
| Owner | `dev-token-owner` | sab kuch + members + export |
| Analyst | `dev-token-analyst` | inputs, runs, transforms, export |
| Reviewer | `dev-token-reviewer` | findings accept/reject/need-more |
| Viewer | `dev-token-viewer` | sirf dekhna (read-only) |

Token paste karte waqt `dev-token-owner` ya poora `Bearer dev-token-owner` dono chalenge; client prefix normalize karta hai. **Open live workspace** real cases API se token validate karta hai. Invalid token, 401 ya network failure par visible error milta hai—koi demo/offline evidence fallback nahi. GitHub Pages jaise static host par pehle **Live API connection** me separately deployed HTTPS FastAPI URL save karo; backend CORS me UI ka exact origin allow hona chahiye. 401 ke baad configured API URL preserve hota hai.

> Production me verified OIDC bearer tokens supported hain, lekin issuer/audience/JWKS configure karke user ko pehle provision karna hota hai. Browser abhi access token paste karta hai; interactive Authorization Code + PKCE/refresh-token login implemented nahi hai. Public rollout se pehle trusted token flow/session gateway aur [`DEPLOYMENT.md`](DEPLOYMENT.md) checklist use karo.

---

## 3. Pehla investigation — goals aur mission views

Start screen par 4 goal cards hain: **Monitor a campaign, Verify a post or claim, Inspect
media, Investigate infrastructure**. Existing case ko **Open case** se bhi khola ja sakta hai.

1. Goal card click karo → selected goal retain hota hai aur case scope form aata hai
   (title, authorized purpose, languages).
2. Case banne par grouped investigation workspace khulta hai:
   - **Monitor** — Overview, persistent Alerts, Narratives aur Geospatial map/baselines
   - **Investigate** — Live OSINT, Accounts, Network & behavior, Evidence graph, Entity explorer, Media lab
   - **Evidence** — Comments, Findings & review, Compare accounts, Exports
   - **System** — Connectors aur bounded Agent
3. Top bar ka **Collect & run** data intake/workflows kholta hai; **Jobs** progress aur
   failures dikhata hai. Analytics current collected corpus par on-demand refresh hote hain.
4. Top-bar global search current case ke accounts, posts, findings, alerts aur evidence me bounded
   grouped results deta hai. Result select karne par focused view aur URL deep link banta hai; reload/back
   navigation par case, tab aur selected entity restore hote hain. Cross-case global read-all search nahi hai.

---

## 4. Data daalna (import-first — koi live platform credential nahi chahiye)

**Collect & run** drawer me 3 intake tareeke hain:

- **URL box** — `http/https` post/account link. SSRF policy automatically check hoti hai;
  internal/metadata addresses block ho jaate hain. Instagram jaise platform bina connector ke
  honestly `not_configured / access_required` record karte hain.
- **Text box** — post text/claim paste karo; normalized record + evidence snippet banta hai.
- **File upload** —
  - Images: `.png/.jpg/...` (magic-byte signature check hota hai, extension par bharosa nahi)
  - `.json` — posts bundle (`fixtures/posts.json` jaisa) ya fact-check library
  - `.csv` — comments export (coverage metadata ke saath)

`backend/fixtures/` ke labelled synthetic records sirf automated tests/evaluation ke liye hain. Inhe investigation evidence ya live-source result ki tarah present mat karo. Product runtime me demo case seed karne ka workflow nahi hai; real investigation ke liye authorized import ya permitted live connector use karo.

---

## 5. Analysis chalana (bounded jobs)

Collect & run drawer par analysis workflows hain. Har ek HTTP 202 return karta hai aur **Jobs
drawer** me stage-wise progress dikhta hai (`queued → running → completed`, outcome
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
7. **Media forensics** — integrity, selected metadata, provenance-marker bytes aur bounded
   pixel/JPEG indicators; configured image model ho tab raw output, warna `not_configured`

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

## 7. Mission views, findings aur connectors

- **Overview** — coverage, source gaps, narrative pulse aur unresolved explainable review cues.
- **Alerts** — active/inactive persistent history, evidence IDs, evidence-completeness method aur
  reviewer/owner notes/status. Resolved/dismissed cue analytics refresh par dobara active nahi hota;
  har decision audit event me rehta hai.
- **Accounts** — account inventory, observed handles/platform IDs, behavior indicators, shared URLs aur
  post-level source/first-seen/collection provenance. Network account click aur global search yahin drill down karte hain.
- **Narratives** — representative posts, timelines, earliest-in-corpus aur later observed
  amplification. Isse platform-wide origin ya common ownership prove nahi hota.
- **Geospatial** — bundled offline world map aur supplied/reported locations ke aggregates;
  default 3 distinct subjects se chhoti cell suppress hoti hai. Exact supplied point explicitly labelled
  hai; live/current person location nahi.
- **Live OSINT** — DNS, RDAP, web, CT aur Wayback modules select karo. Har source ka success,
  empty, partial ya failure alag dikhta hai; saved report ka JSON export available hai.
- **Network & behavior** — observed fact/hypothesis account links, alag centrality/community metrics,
  bridge candidates aur transparent behavior formula. Metrics observed graph bounded hain; automation
  indicator ko bot probability ya external reach mat samjho.
- **Media lab** — authenticated preview, hashes, metadata/pixel observations, model availability
  aur limitations. No model = no synthetic score.
- **Findings & review** — Established, Signals, Unknowns, Conflicts ke alawa unmatched categories
  ke liye triage bucket; har finding exactly once dikhti hai. Reviewer/owner *Accept / Need more /
  Reject* kar sakte hain aur decision ke baad list refresh hoti hai.
- **Comments** — coverage statement, per-row explanation aur honest permalink status.
- **Connectors** — 11-row API/access matrix batata hai ki kya keyless hai, kis cheez ko API key,
  official approval ya local model chahiye, aur kya unavailable hai. Neeche bounded Mastodon public
  hashtags, key-gated YouTube comments aur Google Fact Check controls hain. Missing key/access clearly
  shown; [`REQUIRED_CREDENTIALS.md`](REQUIRED_CREDENTIALS.md).
- **Agent** — bounded allowlisted plan→policy→execute; unavailable provider par fake evidence nahi.
- **Exports** — PDF/HTML/CSV/JSON, redaction options, SHA-256 manifest aur expiring downloads.

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
  -d '{"goal":"coordination","client_idempotency_key":"example-0001"}'
```

Job progress SSE se milta hai: `GET /api/v1/cases/{id}/events` (reconnect `Last-Event-ID` se).

---

## 9. Testing aur evaluation

```bash
cd backend
pip install -r requirements-dev.txt
alembic upgrade head && alembic check
python -m pytest tests/ -q
bandit -q -r app -x tests
pip-audit -r requirements.txt
python scripts/evaluate.py  # isolated fixture-based harness; live evidence nahi

cd ../frontend
npm ci && npm run build
npx playwright install chromium
npm run test:e2e  # API :8000 + Vite :5173 aur production build pehle; 10 browser/Pages/accessibility checks
```

Point-in-time results [`VALIDATION.md`](VALIDATION.md) me hain. CI migration downgrade/re-upgrade aur
real disposable PostgreSQL/MinIO/Celery Compose smoke bhi karta hai; local Docker available ho tab hi
`docs/DEPLOYMENT.md` ka smoke manually run karo.

## 10. Yaad rakhne wali limitations (honest by design)

- Instagram/Facebook, approval-gated Reddit, OCR, reverse image search aur unconfigured LLM/model
  capabilities ko UI "not configured / access required" dikhata hai. YouTube/Fact Check real hain
  lekin API key chahiye; Mastodon public hashtag aur passive OSINT keyless ho sakte hain.
- Analytics continuous platform-wide monitor nahi; current collected case corpus par on-demand hain.
  Bot/deepfake probability, video deepfake verdict ya common-owner attribution invent nahi hota.
- Comment classifier transparent but **uncalibrated** hai — production accuracy claim se pehle
  representative Hindi/Hinglish labeled data par precision/recall/calibration maapo.
- Dev tokens production auth nahi. Production OIDC verification implemented hai, lekin IdP config,
  explicit user provisioning, safe browser token flow, TLS, DPDP/legal review aur operational controls phir bhi zaroori hain.
- Export PDFs integrity evidence hain, court-certified evidence nahi.
