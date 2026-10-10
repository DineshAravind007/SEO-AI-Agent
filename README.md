# Website SEO AI Agent

An automated, intelligent website SEO analysis, monitoring, and recommendation platform.

---

## Architecture & System Overview

```
Frontend (React 19 + Vite + Recharts)
   │  JWT Bearer Authentication
   ▼
Backend API (FastAPI + SQLAlchemy + SQLite/PostgreSQL)
   ├── Security & Multi-Tenant Isolation (JWT + bcrypt + audit ownership verification)
   ├── Web Crawler & On-Page Extractor (polite, respects robots.txt, SSRF protected)
   ├── Technical SEO Analyzer & Deterministic Scorer (100-pt rule-based engine)
   ├── AI Recommendation Engine (abstract provider: Mock default, OpenAI production)
   ├── Competitor Benchmarking (side-by-side gap and strength analysis)
   ├── Keyword Intelligence (keyword density, intent classification, opportunity ranking)
   ├── Google Search Console (OAuth 2.0 integration for clicks, impressions, CTR, position)
   ├── Monitoring & Alerting (scheduled automated re-auditing + SMTP notifications)
   ├── Performance & CWV Analyzer (HTTP latency, compression, caching, document size)
   └── Report Generation (standalone, branded HTML report export)
```

---

## Features

1. **Core SEO Auditing & Scoring:** Deterministic, reproducible scoring engine measuring on-page metadata, headings, canonicals, links, images, Open Graph, and robots.txt.
2. **AI-Powered Recommendations:** Translates deterministic issues into actionable steps with code examples, priority rankings, and confidence ratings.
3. **Competitor Comparison:** Benchmark domain performance against competitors to identify ranking gaps and technical advantages.
4. **Keyword Research:** Discover high-impact keyword opportunities, analyze on-page keyword density, and assess search intent.
5. **Google Search Console Integration:** Authenticate via OAuth 2.0 to access verified search traffic, top query impressions, and indexation metrics.
6. **Automated SEO Monitoring & Alerts:** Schedule automated daily, weekly, or monthly re-audits with change detection and email alert dispatch on score drops.
7. **Performance & Core Web Vitals:** Measure server latency, document transfer size, text compression, HTTP caching, and responsive viewport readiness. Core Web Vitals (LCP, INP, CLS) are clearly flagged as unavailable without a live browser environment.
8. **Authentication & Multi-Tenant Security:** Secure user registration, bcrypt password hashing, JWT session expiration, and strict user-level audit ownership enforcement.
9. **History & Reports:** Track audit progression over time, filter issues across audits, and download self-contained HTML audit reports.

---

## Local Development Setup

### 1. Backend Setup

Prerequisites: Python 3.10+

```bash
# Clone the repository and navigate to project root
cd website-seo-ai-agent

# Create and activate virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Run database migrations / initialize SQLite schema
python -c "from backend.database.migration import run_migrations; run_migrations()"

# Start FastAPI development server
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```
- API Base: `http://127.0.0.1:8000`
- Swagger Interactive Documentation: `http://127.0.0.1:8000/docs`

### 2. Frontend Setup

Prerequisites: Node.js 18+

```bash
cd frontend

# Install frontend dependencies
npm install

# Start Vite development server
npm run dev
```
- Frontend UI: `http://localhost:5173`

---

## Environment Variables

Copy `.env.example` to `.env`. Key configuration keys:

| Variable | Default | Purpose |
|----------|---------|---------|
| `JWT_SECRET` | *(development default)* | Secret key for signing JWT tokens (min 32 chars in production) |
| `SESSION_SECRET` | *(development default)* | Session middleware secret key |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Allowed CORS origins (comma-separated for multiple) |
| `DATABASE_URL` | `sqlite:///./seo_agent.db` | Database connection string (SQLite or PostgreSQL) |
| `LLM_PROVIDER` | `mock` | `mock` (no API key needed) or `openai` |
| `LLM_API_KEY` | *(empty)* | OpenAI API key when `LLM_PROVIDER=openai` |
| `GOOGLE_CLIENT_ID` | *(empty)* | Google OAuth client ID for Search Console |
| `GOOGLE_CLIENT_SECRET` | *(empty)* | Google OAuth client secret for Search Console |
| `EMAIL_HOST` | `smtp.mailtrap.io` | SMTP server host for alert notifications |
| `EMAIL_PORT` | `587` | SMTP server port |
| `EMAIL_USERNAME` | *(empty)* | SMTP authentication username |
| `EMAIL_PASSWORD` | *(empty)* | SMTP authentication password |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend API URL for frontend client |

---

## Testing & Quality Assurance

### Run Backend Test Suite
```bash
.\venv\Scripts\python.exe -m pytest backend/tests -q --tb=short
```
*Current test suite: 159 tests covering all modules, authentication, security boundaries, and end-to-end workflows.*

### Build Frontend
```bash
cd frontend
npm run build
```

### Run Frontend Linter
```bash
cd frontend
npm run lint
```

---

## Security Features

- **SSRF Prevention:** The crawler validates all target domains via `is_safe_url()`, rejecting private IP blocks (RFC 1918), loopback, link-local / AWS metadata (`169.254.169.254`), and reserved addresses.
- **Strict Ownership Checks:** Every audit, competitor comparison, keyword analysis, and monitoring project verifies `audit.user_id == current_user.id` with HTTP 403 Forbidden on mismatch.
- **Password Security:** Salted bcrypt hashing with zero plain-text storage or logging.
- **JWT Authentication:** Cryptographically signed tokens with expiration and signature verification.
- **Safe Secrets Handling:** `.env`, `*.db`, tokens, and credentials are excluded from Git tracking via `.gitignore`.

---

## Known Limitations & External Integration Status

1. **Google Search Console:** In development without Google Cloud credentials, the GSC interface displays clean unconfigured states (`connected: false`). Real OAuth requires registering credentials in Google Cloud Console.
2. **AI Provider:** Configured to `mock` by default for zero-cost local execution. Set `LLM_PROVIDER=openai` and provide `LLM_API_KEY` for live GPT-4o-mini recommendations.
3. **JavaScript Rendering:** Crawling uses `requests` and `BeautifulSoup` (HTTP response parsing). Single-page apps requiring client-side JS rendering are not fully parsed.
4. **Core Web Vitals:** Metrics like LCP, INP, and CLS require a real browser rendering environment; they are clearly flagged as `UNAVAILABLE` in the UI and reports with guidance to use Google PageSpeed Insights.
