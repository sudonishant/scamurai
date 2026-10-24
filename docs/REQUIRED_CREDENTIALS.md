# Credentials Guide (Hinglish) — kya chahiye, kahan milega, kaise lagega

_Sab kuch October 2026 ke current free-tier rules ke hisaab se verify kiya gaya hai._

Platform bina kisi key ke bhi poora kaam karta hai (local import, image matching, coordination,
agent, exports). Keys sirf **live provider** features on karti hain. Key na ho to UI honestly
`not configured` dikhata hai — koi fake data kabhi nahi.

---

## 1. LLM / Agent ke liye free API (3 options, koi bhi ek)

### Option A — Groq (recommended: sabse simple, no credit card)
- **Kya milta hai:** OpenAI-compatible chat API, free models `gpt-oss-20b`, `gpt-oss-120b`,
  `qwen3.8-27b`. Limit ~30 requests/min, 1,000 requests/day per model, 200k tokens/day.
- **Kaise:**
  1. https://console.groq.com pe Google/GitHub se sign up (card nahi maangta).
  2. Left menu → **API Keys → Create API Key** → key copy kar lo (`gsk_...` se start hoti hai).
- **`.env` me daalo:**
  ```
  SCAMURAI_LLM_PROVIDER=groq
  SCAMURAI_LLM_API_KEY=gsk_...yahan...
  SCAMURAI_LLM_BASE_URL=https://api.groq.com/openai/v1
  SCAMURAI_LLM_MODEL_ID=gpt-oss-20b
  ```

### Option B — Google Gemini AI Studio (free, ek caveat)
- **Kya milta hai:** Flash/Flash-Lite models free; RPM ~10–30, daily quota 250–1500 requests
  (midnight Pacific time reset). Image/"Nano Banana" wale paid hain.
- **Caveat:** free-tier prompts Google ki training me use ho sakte hain — isliye sensitive case
  data ke liye Groq behtar hai.
- **Kaise:** https://aistudio.google.com → **Get API key** → `AIza...` key.
- **`.env` me daalo:**
  ```
  SCAMURAI_LLM_PROVIDER=gemini
  SCAMURAI_GEMINI_API_KEY=AIza...yahan...
  SCAMURAI_LLM_MODEL_ID=gemini-flash
  ```

### Option C — OpenRouter (ek key, bahut saare free models)
- **Kya milta hai:** `:free` wale model IDs (e.g. `deepseek/deepseek-chat-v3.1:free`), OpenAI-
  compatible. Limit 20 RPM / 50 requests/day bina payment ke; $10 ek baar top-up karo to 1,000/day.
- **Kaise:** https://openrouter.ai → sign up → **Keys → Create Key**.
- **`.env` me daalo:**
  ```
  SCAMURAI_LLM_PROVIDER=openrouter
  SCAMURAI_LLM_API_KEY=sk-or-...
  SCAMURAI_LLM_BASE_URL=https://openrouter.ai/api/v1
  SCAMURAI_LLM_MODEL_ID=deepseek/deepseek-chat-v3.1:free
  ```

> Safety by design: koi bhi LLM call me analyzed material hamesha **data** ke roop me jaata hai,
> system prompt use instruction maanne se rokta hai. Key kabhi browser bundle, logs ya exports me
> nahi jaati.

---

## 2. YouTube connector (comments live import) — free, API key only
- **Kya milta hai:** kisi bhi public video ke comments + replies, official Data API v3 se.
  Quota 10,000 units/day; ek comment page = sirf 1 unit (100 comments/page). OAuth nahi chahiye.
- **Kaise:**
  1. https://console.cloud.google.com → naya project banao (e.g. "scamurai").
  2. **APIs & Services → Enable APIs and Services → "YouTube Data API v3" → Enable.**
  3. **Credentials → Create Credentials → API key** → key copy karo.
  4. (Recommended) key pe **Edit → API restrictions → YouTube Data API v3** select kar do.
- **`.env` me daalo:** `SCAMURAI_YOUTUBE_API_KEY=AIza...`
- UI: case kholo → **Connectors tab → YouTube comments import**. Video URL ya 11-char ID do.
  Comments disabled / quota khatam hone par system honestly `permission_denied` / `rate_limited`
  record karta hai — chup-chaap khaali result nahi dikhata.

## 3. Google Fact Check Tools API — free, claim verification
- **Kya milta hai:** published fact-checkers ke ratings (False/Misleading/etc.) unke source URL ke
  saath. Result na milna = "koi published fact-check nahi", ye kabhi proof nahi ki claim jhooth hai.
- **Kaise:** same Google Cloud project → **Enable "Fact Check Tools API"** → ek nayi API key banao
  ya upar wali key me dono APIs allow kar do.
- **`.env` me daalo:** `SCAMURAI_GOOGLE_FACTCHECK_API_KEY=AIza...`
- UI: Connectors tab → **Fact Check search**.

## 4. Instagram (Meta Graph API) — free, par conditions hain
- Sirf **Business/Creator** accounts ke liye. Personal account pe nahi chalega.
- **Standard Access** turant milta hai aur apne/tester accounts ke liye kaam karta hai (demo ke liye
  perfect). Kisi bhi random account ke comments API se nahi milte — ye Meta ki 2026 policy hai.
- **Advanced Access** (production, saare accounts) ke liye App Review (~20 din) + Business
  Verification + privacy-policy URL + screencast chahiye.
- **Kaise:** https://developers.facebook.com → App banao → **Instagram Graph API** add karo →
  Instagram Business/Creator account connect karo → access token (60-din refresh cycle).
- Agar aapka use-case sirf apne brand account ke comments monitor karna hai to ye viable hai;
  arbitrary OSINT scraping ke liye nahi. Batana, adapter wire kar denge.

## 5. Reddit — technically free, practically approval-gated
- 2025 ke **Responsible Builder Policy** ke baad self-serve app registration band hai; naye apps ko
  manual approval (2–4 hafte, kabhi-kabhi silent reject) chahiye. Free tier non-commercial,
  100 queries/min. Unauthenticated access May 2026 se poori tarah blocked.
- **Kaise (agar phir bhi chahiye):** https://www.reddit.com/prefs/apps → **are you a developer?
  create an app… → script type** → client ID + secret + descriptive User-Agent.
- **`.env`:** `SCAMURAI_REDDIT_CLIENT_ID`, `SCAMURAI_REDDIT_CLIENT_SECRET`, `SCAMURAI_REDDIT_USER_AGENT`.
- Mera recommendation: Reddit ko primary source mat banao; CSV/JSON import se kaam chal jayega.

---

## Aapko mujhe kya dena hai (minimum useful set)

1. **Groq API key** (`gsk_...`) — agent ke LLM steps ke liye. _(ya Gemini/OpenRouter key — koi ek)_
2. **YouTube Data API key** (`AIza...`) — live comment import ke liye.
3. **Fact Check API key** (`AIza...`) — claim verification ke liye. (2 aur 3 alag keys ho ya ek
   restricted key — dono chalega.)

Bas itne se platform ke saare free live features chalu ho jayenge. Instagram/Reddit optional hain.

## Key kaise lagti hai (security)
- Saari keys `/home/user/scamurai/.env` me jaati hain (file `.gitignore` me hai — git me kabhi commit
  nahi hogi, GitHub repo me nahi jayegi).
- Key sirf backend process ke paas rehti hai; frontend kabhi usse touch nahi karta.
- Backend restart (`make run-api`) ke baad Connectors tab me status `configured` dikhega.
- Agar key chat me bhejte ho to main use seedha `.env` me likh dunga, kisi file me nahi; baad me
  provider dashboard se rotate/revoke kar sakte ho.
