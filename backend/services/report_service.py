"""
HTML SEO Report Generator.
Produces a self-contained, print-ready HTML file from audit data.
No external PDF libraries required — users can File > Print > Save as PDF.
"""
from __future__ import annotations
import json
import datetime
from typing import Optional
from backend.database.models import Audit, Page, SEOIssue, AIRecommendation
from sqlalchemy.orm import Session


# ── Severity helpers ──────────────────────────────────────────────────────────

_SEV_COLOR = {
    "CRITICAL": "#dc2626",
    "HIGH":     "#ea580c",
    "MEDIUM":   "#ca8a04",
    "LOW":      "#2563eb",
}

_GRADE_COLOR = {
    "Excellent":        "#16a34a",
    "Good":             "#16a34a",
    "Fair":             "#d97706",
    "Needs Improvement": "#dc2626",
}


def _sev_color(sev: str) -> str:
    return _SEV_COLOR.get(sev.upper(), "#6b7280")


def _grade_color(grade: str) -> str:
    return _GRADE_COLOR.get(grade, "#6b7280")


# ── Main generator ────────────────────────────────────────────────────────────

def generate_html_report(audit: Audit, db: Session) -> str:
    """Build and return a complete HTML SEO report as a string."""

    # Collect data
    score_data: Optional[dict] = None
    if audit.score_data:
        try:
            score_data = json.loads(audit.score_data)
        except Exception:
            pass

    pages = db.query(Page).filter(Page.audit_id == audit.id).all()

    issues = (
        db.query(SEOIssue)
        .join(Page, SEOIssue.page_id == Page.id)
        .filter(Page.audit_id == audit.id)
        .order_by(SEOIssue.severity)
        .all()
    )

    recommendations = (
        db.query(AIRecommendation)
        .filter(AIRecommendation.audit_id == audit.id)
        .all()
    )

    generated_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    created_at = (
        audit.created_at.strftime("%Y-%m-%d %H:%M UTC")
        if audit.created_at else "—"
    )

    # ── Score section ─────────────────────────────────────────────────────────
    score_html = ""
    if score_data:
        sev = score_data.get("severity_counts", {})
        cat = score_data.get("category_counts", {})
        grade = score_data.get("grade", "—")
        g_color = _grade_color(grade)
        score_html = f"""
        <section>
          <h2>SEO Health Score</h2>
          <div class="score-row">
            <div class="score-circle" style="border-color:{g_color}">
              <span class="score-num" style="color:{g_color}">{score_data.get('score', '—')}</span>
              <span class="score-denom">/100</span>
            </div>
            <div class="score-detail">
              <p><strong>Grade:</strong> <span style="color:{g_color}">{grade}</span></p>
              <p class="explanation">{score_data.get('explanation', '')}</p>
              <table class="mini-table">
                <tr>
                  <th>Severity</th><th>Count</th>
                  <th>Category</th><th>Count</th>
                </tr>
                <tr>
                  <td><span class="sev-dot" style="background:{_SEV_COLOR['CRITICAL']}"></span> Critical</td>
                  <td>{sev.get('CRITICAL', 0)}</td>
                  <td>On-page</td>
                  <td>{cat.get('on_page', 0)}</td>
                </tr>
                <tr>
                  <td><span class="sev-dot" style="background:{_SEV_COLOR['HIGH']}"></span> High</td>
                  <td>{sev.get('HIGH', 0)}</td>
                  <td>Technical</td>
                  <td>{cat.get('technical', 0)}</td>
                </tr>
                <tr>
                  <td><span class="sev-dot" style="background:{_SEV_COLOR['MEDIUM']}"></span> Medium</td>
                  <td>{sev.get('MEDIUM', 0)}</td>
                  <td></td><td></td>
                </tr>
                <tr>
                  <td><span class="sev-dot" style="background:{_SEV_COLOR['LOW']}"></span> Low</td>
                  <td>{sev.get('LOW', 0)}</td>
                  <td></td><td></td>
                </tr>
              </table>
            </div>
          </div>
        </section>
        """

    # ── Issues section ────────────────────────────────────────────────────────
    issue_rows = ""
    for iss in issues:
        color = _sev_color(iss.severity)
        issue_rows += f"""
        <tr>
          <td><span class="badge" style="background:{color}20;color:{color};border:1px solid {color}40">{iss.severity}</span></td>
          <td>{_esc(iss.title)}</td>
          <td>{_esc(iss.category)}</td>
          <td class="url-cell">{_esc(iss.page_url)}</td>
          <td>{_esc(iss.description)}</td>
          <td>{_esc(iss.recommendation_summary)}</td>
        </tr>"""

    issues_html = f"""
    <section>
      <h2>Detected Issues ({len(issues)})</h2>
      {"<p class='muted'>No issues were detected.</p>" if not issues else f'''
      <table>
        <thead>
          <tr>
            <th>Severity</th><th>Issue</th><th>Category</th>
            <th>Page URL</th><th>Description</th><th>Recommendation</th>
          </tr>
        </thead>
        <tbody>{issue_rows}</tbody>
      </table>'''}
    </section>
    """

    # ── Pages section ─────────────────────────────────────────────────────────
    page_rows = ""
    for p in pages[:50]:  # cap at 50 for readability
        status_color = "#16a34a" if p.status_code == 200 else "#dc2626"
        page_rows += f"""
        <tr>
          <td class="url-cell">{_esc(p.url)}</td>
          <td style="color:{status_color}">{p.status_code or p.crawl_status}</td>
          <td>{_esc(p.title or '—')}</td>
          <td>{p.word_count or '—'}</td>
          <td>{'Yes' if p.meta_description else 'No'}</td>
        </tr>"""

    pages_html = f"""
    <section>
      <h2>Crawled Pages ({len(pages)})</h2>
      {"<p class='muted'>No pages crawled.</p>" if not pages else f'''
      <table>
        <thead>
          <tr>
            <th>URL</th><th>HTTP Status</th><th>Title</th>
            <th>Words</th><th>Meta Description</th>
          </tr>
        </thead>
        <tbody>{page_rows}</tbody>
      </table>{"<p class='muted'>Showing first 50 pages.</p>" if len(pages) > 50 else ""}'''}
    </section>
    """

    # ── AI Recommendations section ────────────────────────────────────────────
    rec_cards = ""
    for r in recommendations:
        color = _sev_color(r.severity)
        example_block = (
            f"<div class='example-block'><strong>Example:</strong><pre>{_esc(r.example)}</pre></div>"
            if r.example else ""
        )
        rec_cards += f"""
        <div class="rec-card">
          <div class="rec-header">
            <h3>{_esc(r.title)}</h3>
            <span class="badge" style="background:{color}20;color:{color};border:1px solid {color}40">{r.severity}</span>
          </div>
          <p class="muted" style="margin:0 0 8px"><em>Issue type: {_esc(r.issue_type)}</em></p>
          <p><strong>Explanation:</strong> {_esc(r.explanation)}</p>
          <div class="rec-action">
            <p><strong>Recommendation:</strong> {_esc(r.recommendation)}</p>
            <p><strong>Suggested action:</strong> {_esc(r.suggested_action)}</p>
          </div>
          {example_block}
        </div>"""

    recs_html = f"""
    <section>
      <h2>AI Recommendations ({len(recommendations)})</h2>
      {"<p class='muted'>No AI recommendations generated for this audit.</p>" if not recommendations else rec_cards}
    </section>
    """

    # ── Full HTML document ────────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>SEO Report — {_esc(audit.url)}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 13px; color: #111827; background: #fff;
      padding: 32px; max-width: 1100px; margin: 0 auto;
    }}
    h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; color: #111827; }}
    h2 {{ font-size: 16px; font-weight: 700; margin: 0 0 16px; padding-bottom: 6px;
          border-bottom: 2px solid #e5e7eb; color: #111827; }}
    h3 {{ font-size: 14px; font-weight: 600; color: #111827; }}
    section {{ margin-bottom: 40px; }}
    p {{ margin-bottom: 8px; line-height: 1.55; }}
    .muted {{ color: #6b7280; font-size: 12px; }}
    /* Header */
    .report-header {{ background: #111827; color: #fff; padding: 24px 28px;
                      border-radius: 10px; margin-bottom: 32px; }}
    .report-header h1 {{ color: #fff; }}
    .report-header .meta {{ margin-top: 8px; font-size: 12px; color: #9ca3af;
                             display: flex; gap: 24px; flex-wrap: wrap; }}
    /* Score */
    .score-row {{ display: flex; gap: 32px; align-items: flex-start; flex-wrap: wrap; }}
    .score-circle {{ width: 110px; height: 110px; border-radius: 50%;
                     border: 8px solid #e5e7eb; display: flex; flex-direction: column;
                     align-items: center; justify-content: center; flex-shrink: 0; }}
    .score-num {{ font-size: 34px; font-weight: 800; line-height: 1; }}
    .score-denom {{ font-size: 12px; color: #6b7280; }}
    .score-detail {{ flex: 1; }}
    .explanation {{ color: #4b5563; font-style: italic; margin: 8px 0 12px; }}
    /* Tables */
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    th {{ background: #f9fafb; padding: 8px 10px; text-align: left;
          font-weight: 600; border-bottom: 1px solid #e5e7eb; color: #374151; }}
    td {{ padding: 8px 10px; border-bottom: 1px solid #f3f4f6; vertical-align: top; }}
    tr:last-child td {{ border-bottom: none; }}
    .mini-table {{ max-width: 440px; margin-top: 12px; }}
    .url-cell {{ max-width: 200px; word-break: break-all; color: #2563eb; }}
    /* Badges */
    .badge {{ display: inline-block; font-size: 10px; font-weight: 700;
               padding: 2px 7px; border-radius: 99px; text-transform: uppercase;
               letter-spacing: 0.05em; white-space: nowrap; }}
    .status-badge {{ display: inline-block; padding: 4px 10px; border-radius: 6px;
                     font-weight: 600; font-size: 12px; }}
    .sev-dot {{ display: inline-block; width: 8px; height: 8px;
                border-radius: 50%; margin-right: 4px; vertical-align: middle; }}
    /* Recommendations */
    .rec-card {{ border: 1px solid #e5e7eb; border-radius: 8px;
                  padding: 18px; margin-bottom: 16px; }}
    .rec-header {{ display: flex; justify-content: space-between;
                    align-items: flex-start; margin-bottom: 10px; gap: 12px; }}
    .rec-action {{ background: #f9fafb; border: 1px solid #e5e7eb;
                    border-radius: 6px; padding: 12px; margin: 10px 0; }}
    .example-block {{ margin-top: 10px; }}
    pre {{ background: #1f2937; color: #e5e7eb; padding: 12px; border-radius: 6px;
           font-size: 11px; overflow-x: auto; white-space: pre-wrap;
           word-break: break-word; margin-top: 6px; }}
    /* Footer */
    .report-footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid #e5e7eb;
                       color: #9ca3af; font-size: 11px; text-align: center; }}
    @media print {{
      body {{ padding: 16px; }}
      section {{ page-break-inside: avoid; }}
      .rec-card {{ page-break-inside: avoid; }}
    }}
  </style>
</head>
<body>

  <div class="report-header">
    <h1>SEO Audit Report</h1>
    <p style="color:#d1d5db;margin-top:4px;font-size:14px;word-break:break-all">{_esc(audit.url)}</p>
    <div class="meta">
      <span>Audit ID: #{audit.id}</span>
      <span>Status: {audit.status.title()}</span>
      <span>Audited: {created_at}</span>
      <span>Report generated: {generated_at}</span>
    </div>
  </div>

  {score_html}
  {issues_html}
  {recs_html}
  {pages_html}

  <div class="report-footer">
    Generated by SEO Agent &mdash; AI-Powered SEO Analysis Platform &mdash; {generated_at}
  </div>

</body>
</html>"""


def _esc(text) -> str:
    """Minimal HTML escaping for report content."""
    if text is None:
        return "—"
    s = str(text)
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )
