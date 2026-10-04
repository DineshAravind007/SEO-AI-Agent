# Website SEO AI Agent

**Phase 1:** Website Crawler + Basic SEO Analysis  
**Phase 2:** Technical SEO Analysis + SEO Scoring Engine  
**Phase 3:** AI-Powered SEO Recommendation Engine

---

## Architecture

```
Phase 1 — Website Crawling
      ↓  Structured page data
Phase 2 — Deterministic Technical SEO Analysis
      ↓  SEO issues + SEO score (source of truth)
Phase 3 — AI Recommendation Engine
      ↓  LLM Provider (abstracted)
      ↓  Validated structured recommendations
```

**Important:** The LLM does NOT replace the crawler or the deterministic analyzer. Phase 2 is the source of truth for detected issues. Phase 3 interprets and explains those findings with actionable guidance.

---

## Setup & Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   ```
2. Activate it:
   - Windows: `.\venv\Scripts\activate`
   - Mac/Linux: `source venv/bin/activate`
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. (Phase 3) Configure the LLM provider via environment variables:
   ```bash
   # Default: uses mock provider (no API key required)
   LLM_PROVIDER=mock

   # To use OpenAI:
   LLM_PROVIDER=openai
   LLM_API_KEY=sk-...
   LLM_MODEL=gpt-4o-mini     # optional, default: gpt-4o-mini
   LLM_TIMEOUT=30             # optional, default: 30 seconds
   ```
   Use a `.env` file (never commit it — it is in `.gitignore`).

---

## Running the Application

```bash
python -m uvicorn backend.main:app --reload
```
Swagger UI: http://127.0.0.1:8000/docs

---

## API Reference

### Phase 1 — Crawl & On-Page Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/audits` | Start a new audit |
| `GET`  | `/api/audits/{id}` | Get audit status and score |
| `GET`  | `/api/audits/{id}/pages` | Get all crawled pages with SEO data |
| `GET`  | `/api/audits/{id}/issues` | Get all on-page + technical SEO issues |

**Start an audit:**
```bash
curl -X POST "http://127.0.0.1:8000/api/audits" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "max_pages": 10, "max_depth": 2}'
```

### Phase 2 — SEO Score

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/audits/{id}/score` | Get deterministic SEO score |

```bash
curl "http://127.0.0.1:8000/api/audits/1/score"
```

Example response:
```json
{
  "score": 85,
  "grade": "Good",
  "severity_counts": {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 1, "LOW": 0},
  "category_counts": {"technical": 2},
  "explanation": "Score is 85/100. Deductions made for 2 unique issue types across 10 crawled pages."
}
```

### Phase 3 — AI Recommendations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/audits/{id}/recommendations` | Generate AI recommendations (or return cached) |
| `GET`  | `/api/audits/{id}/recommendations` | Retrieve existing recommendations |

**Generate recommendations:**
```bash
curl -X POST "http://127.0.0.1:8000/api/audits/1/recommendations"
```

Example response:
```json
{
  "audit_id": 1,
  "recommendations": [
    {
      "issue_type": "MISSING_META_DESCRIPTION",
      "severity": "HIGH",
      "title": "Add Meta Descriptions",
      "explanation": "Meta descriptions appear in search results and strongly influence click-through rates...",
      "recommendation": "Write a unique, compelling meta description for every page.",
      "suggested_action": "Add <meta name='description' content='...'> to each page's <head>.",
      "example": "<meta name='description' content='Buy premium widgets — fast shipping, 30-day returns.'>",
      "confidence": 95
    }
  ]
}
```

---

## AI Provider Architecture

```
AIRecommendationService
        ↓
LLMProvider (abstract interface)
        ├── MockLLMProvider   ← used in automated tests (no API key)
        └── OpenAIProvider    ← production use via LLM_PROVIDER=openai
```

The provider is selected at runtime via `LLM_PROVIDER` environment variable. Swapping providers requires no changes to business logic.

**Security:**
- API keys are read from environment variables only — never hard-coded or stored in the database.
- Crawled website content is treated as untrusted and is explicitly separated from system instructions in all prompts to prevent prompt injection.
- Raw HTML is never forwarded to the LLM — only structured, compact issue summaries are sent.

---

## Testing

Run the full test suite:
```bash
python -m pytest backend/tests
```

**Test coverage includes:**
- Phase 1: Crawler, extractor, URL queue, on-page analyzers
- Phase 2: Technical analyzers, scoring engine, XML sitemap checker
- Phase 3: Mock provider, prompt builder, service layer (dedup, idempotency, error handling), API endpoints

No real LLM API calls are made during automated tests. The `MockLLMProvider` is used throughout.

---

## Manual End-to-End Test (Phase 3)

1. Start the server: `python -m uvicorn backend.main:app --reload`
2. Open Swagger: http://127.0.0.1:8000/docs
3. `POST /api/audits` → note the `id`
4. `GET /api/audits/{id}` → wait for `"status": "completed"`
5. `GET /api/audits/{id}/issues` → verify on-page and technical issues
6. `GET /api/audits/{id}/score` → verify SEO score and grade
7. `POST /api/audits/{id}/recommendations` → verify AI recommendations returned
8. `GET /api/audits/{id}/recommendations` → verify cached results returned (no duplicate DB rows)
9. `GET /api/audits/{id}` → verify audit status is still `"completed"` (AI failure cannot corrupt audit)

---

## Known Limitations

- SQLite is suitable for development only; PostgreSQL recommended for production (Phase 4).
- Authentication not yet implemented (Phase 4).
- SPA pages relying on JavaScript rendering are not fully crawled (Playwright support planned).
- AI recommendations are generated on-demand; there is no background pre-generation.
- Only OpenAI is implemented as a production provider; additional providers (Gemini, etc.) can be added by implementing the `LLMProvider` interface.
