# Credentials and access guide (Hinglish)

Scamurai ka core investigation workflow bina external API key ke chal sakta hai: authorized
CSV/JSON/text/image imports, local media matching/screening, narrative/network/geo analytics,
coordination candidates, claims, deterministic agent tools aur exports. Provider key ya approval
na ho to UI `not configured`, `access required`, ya actual failure dikhata hai—synthetic result nahi.

> Provider pricing, free tiers, quotas aur approval policies badal sakte hain. Neeche di gayi official
> documentation ko current source of truth maano; kisi free quota ya approval timeline ki guarantee nahi.

## Access requirements at a glance

| Capability | Kya chahiye |
|---|---|
| Authorized imports, local analytics, graph, geo, early-warning rules | Koi API key nahi |
| DNS, RDAP, bounded web metadata, crt.sh, Wayback | Koi API key nahi; public-provider limits apply |
| Mastodon public hashtag | Instance public preview allow kare to key nahi |
| YouTube comments/replies | YouTube Data API v3 key + available quota |
| Google published fact-check search | Fact Check Tools API key |
| External LLM for bounded agent | Optional Groq/OpenRouter/Gemini credential; deterministic local tools keyless |
| Synthetic-image classifier | Local Hugging Face model + optional `transformers`/`torch`; API key by default nahi |
| Instagram/Facebook/Reddit restricted collection | Official reviewed permissions/OAuth/approval; unconfigured build live access claim nahi karti |
| OCR, reverse image search, video deepfake pipeline | Is build me available nahi; koi substitute output nahi |

## 1. YouTube Data API v3 — public comments/replies

Official guide: <https://developers.google.com/youtube/v3/getting-started>

1. Google Cloud project banao aur **YouTube Data API v3** enable karo.
2. **Credentials → API key** se key banao; possible ho to key ko required API tak restrict karo.
3. Backend `.env` me set karo:
   ```dotenv
   SCAMURAI_YOUTUBE_API_KEY=your_key_here
   ```
4. Case → **Connectors → YouTube public comments** me video URL ya 11-character ID do.

Disabled comments, permission failure, quota/rate limit aur transport failure alag outcomes rehte hain.
Inhe successful empty result nahi maana jata. Actual quota/cost ke liye official quota documentation dekho:
<https://developers.google.com/youtube/v3/determine_quota_cost>

## 2. Google Fact Check Tools API — published reviews

Official guide: <https://developers.google.com/fact-check/tools/api/>

1. Google Cloud project me **Fact Check Tools API** enable karo.
2. API key banao/restrict karo aur backend `.env` me set karo:
   ```dotenv
   SCAMURAI_GOOGLE_FACTCHECK_API_KEY=your_key_here
   ```
3. Case → **Connectors → Published fact-check search** use karo.

Published match source evidence hai, automatic truth verdict nahi. No match ka matlab claim false ya true
nahi; claim undetermined rehta hai.

## 3. Optional external LLM — bounded agent

Local deterministic agent tools ke liye LLM key zaroori nahi. External model use karna ho to exactly one
provider configure karo. Model ID aur endpoint provider ke current docs se lo; examples ko availability
guarantee mat samjho.

### Groq (OpenAI-compatible)

Official docs: <https://console.groq.com/docs/quickstart>

```dotenv
SCAMURAI_LLM_PROVIDER=groq
SCAMURAI_LLM_API_KEY=your_groq_key
SCAMURAI_LLM_BASE_URL=https://api.groq.com/openai/v1
SCAMURAI_LLM_MODEL_ID=provider_supported_model_id
```

### OpenRouter (OpenAI-compatible)

Official docs: <https://openrouter.ai/docs/quickstart>

```dotenv
SCAMURAI_LLM_PROVIDER=openrouter
SCAMURAI_LLM_API_KEY=your_openrouter_key
SCAMURAI_LLM_BASE_URL=https://openrouter.ai/api/v1
SCAMURAI_LLM_MODEL_ID=provider_supported_model_id
```

### Gemini

Official docs: <https://ai.google.dev/gemini-api/docs/quickstart>

```dotenv
SCAMURAI_LLM_PROVIDER=gemini
SCAMURAI_GEMINI_API_KEY=your_gemini_key
SCAMURAI_LLM_MODEL_ID=provider_supported_model_id
```

Sensitive case material bhejne se pehle provider ka data-use/retention policy, region, contract aur
organizational approval check karo. Provider content untrusted **data** hai, agent instruction nahi.

## 4. Optional local image classifier

Deterministic hashes/metadata/pixel screening keyless chalti hai. Synthetic-image labels chahiye to:

1. `transformers` aur compatible `torch` optional dependencies install karo.
2. Image-classification model ka model card, license, labels aur intended use review karo.
3. Backend `.env` me configure karo:
   ```dotenv
   SCAMURAI_DEEPFAKE_MODEL_ID=exact_hugging_face_model_id
   SCAMURAI_DEEPFAKE_MODEL_REVISION=optional_pinned_revision
   ```
4. Representative local data, unseen generators aur compressed media par false positives/negatives aur
   calibration measure karo.

No configured model = `not_configured` aur `synthetic_score = null`. Load/inference failure = `unavailable`.
Raw model label manipulation, authenticity ya video-deepfake verdict nahi hai.

## 5. Keyless public sources—fir bhi limits hain

- **Mastodon:** selected instance ki official public hashtag API; ek bounded page, sirf jab public preview
  permitted ho. Private/unlisted coverage nahi. Docs: <https://docs.joinmastodon.org/client/public/>
- **DNS:** Google Public DNS JSON; resolver view point-in-time hai. Docs:
  <https://developers.google.com/speed/public-dns/docs/doh/json>
- **RDAP:** IANA bootstrap + authoritative registry service; website intent prove nahi karta.
- **Web/CT/Wayback:** bounded public observations; login wall, rate limit, no snapshot ya missing CT name
  ko successful empty/negative proof nahi banate.

Publicly accessible hone ka matlab unrestricted scraping, redistribution ya privacy obligation se exemption
nahi. Platform terms, robots/policy, authorization aur applicable law operator ko check karne hain.

## 6. Official approval / currently unavailable

- **Instagram/Facebook:** restricted collection ke liye Meta ke current official permissions, OAuth, App
  Review aur account-type requirements apply hote hain. Is build me unconfigured live success claim nahi.
  Start: <https://developers.facebook.com/docs/instagram-platform/>
- **Reddit:** credentials alone approved access establish nahi karte. Current official API terms/approval
  verify karo: <https://developers.reddit.com/docs>. Is build me full live Reddit collector available nahi.
- **OCR/reverse image search:** actual provider/pipeline configured nahi; transcript ya search result invent
  nahi hota.
- **Video deepfakes:** image classifier ko video support kehna galat hoga; built-in video pipeline nahi.

Authorized JSON/CSV import in cases me available reh sakta hai, lekin wo live platform collection nahi hai.

## 7. Key kaise lagti hai (security)

1. Repository root ki `.env.example` ko `.env` me copy karke backend environment configure karo. `.env` ko
   commit mat karo.
2. Saare runtime settings `SCAMURAI_` prefix use karte hain.
3. Key sirf backend process ke paas rehti hai; browser bundle, prompts, exports aur logs me nahi daalo.
4. Backend restart karke **Connectors → Source health** me non-secret configured state verify karo.
5. Key kabhi chat/ticket/screenshot me share mat karo. Expose ho jaye to provider dashboard se rotate/revoke karo.
6. Production me secret manager, least privilege, TLS, IdP aur provider-specific data-governance review use karo.
