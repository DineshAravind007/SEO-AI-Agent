# Website SEO AI Agent

Phase 1: Website Crawler + Basic SEO Analysis.

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
   Returns: `{"id": 1, "url": "https://example.com/", "status": "pending", "max_pages": 10, "max_depth": 2, "error_message": null}`

2. **Check Audit Status**
   ```bash
   curl "http://127.0.0.1:8000/api/audits/1"
   ```

3. **Get Crawled Pages**
   ```bash
   curl "http://127.0.0.1:8000/api/audits/1/pages"
   ```

4. **Get SEO Issues**
   ```bash
   curl "http://127.0.0.1:8000/api/audits/1/issues"
   ```

## Testing

Run the full test suite with:
```bash
python -m pytest backend/tests
```

## Known Limitations (Phase 1)
- The SQLite database is local and suitable only for development.
- AI Recommendations and scoring are not yet implemented.
- Authentication is not included.
- SPA (Single Page Applications) relying heavily on JS to render links may not be fully crawled as Playwright/headless browsers are not yet integrated.
