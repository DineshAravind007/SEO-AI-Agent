# Website SEO AI Agent

Phase 1: Website Crawler + Basic SEO Analysis.
Phase 2: Technical SEO Analysis + SEO Scoring Engine.

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

## Running the Application

Start the backend:
```bash
python -m uvicorn backend.main:app --reload
```
The API documentation (Swagger UI) will be available at: http://127.0.0.1:8000/docs

## API Usage

1. **Start an Audit**
   ```bash
   curl -X POST "http://127.0.0.1:8000/api/audits" \
   -H "Content-Type: application/json" \
   -d '{"url": "https://example.com", "max_pages": 10, "max_depth": 2}'
   ```
   Returns: `{"id": 1, "url": "https://example.com/", "status": "pending", "max_pages": 10, "max_depth": 2, "error_message": null, "score": null}`

2. **Check Audit Status**
   ```bash
   curl "http://127.0.0.1:8000/api/audits/1"
   ```

3. **Get Crawled Pages**
   ```bash
   curl "http://127.0.0.1:8000/api/audits/1/pages"
   ```

4. **Get SEO Issues**
   Includes on-page and technical SEO issues.
   ```bash
   curl "http://127.0.0.1:8000/api/audits/1/issues"
   ```

5. **Get SEO Score (Phase 2)**
   Available once the audit is completed.
   ```bash
   curl "http://127.0.0.1:8000/api/audits/1/score"
   ```
   Example Response:
   ```json
   {
     "score": 85,
     "grade": "Good",
     "severity_counts": {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 1, "LOW": 0},
     "category_counts": {"technical": 2},
     "explanation": "Score is 85/100. Deductions made for 2 unique issue types across 10 crawled pages."
   }
   ```

## Testing

Run the full test suite with:
```bash
python -m pytest backend/tests
```

## Known Limitations (Phase 1 & 2)
- The SQLite database is local and suitable only for development.
- AI Recommendations are not yet implemented (Phase 3).
- Authentication and Dashboard are not included (Phase 4).
- SPA (Single Page Applications) relying heavily on JS to render links may not be fully crawled as Playwright/headless browsers are not yet integrated.
