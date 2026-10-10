import logging
from sqlalchemy.orm import Session
from backend.database.models import Audit, Page, SEOIssue
from backend.crawler.spider import Crawler
from backend.crawler.extractor import extract_seo_data
from backend.seo_analyzer.analyzers import run_page_analyzers, analyze_audit_duplicates
from backend.technical.analyzers import run_technical_analyzers, check_xml_sitemap
from backend.technical.scorer import calculate_audit_score
from backend.services.performance_analyzer import analyze_performance
from backend.database.models import AuditPerformance, PagePerformance
from backend.database.connection import SessionLocal
import json

logger = logging.getLogger(__name__)


def run_audit_task(audit_id: int):
    """
    Background task: crawl the target URL, extract SEO data, run analyzers,
    and persist everything to the database.

    Status flow: pending → crawling → analyzing → completed | failed
    """
    db: Session = SessionLocal()
    try:
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if not audit:
            logger.error("run_audit_task: audit %s not found", audit_id)
            return

        logger.info("Starting audit %s for %s", audit_id, audit.url)

        # ── 1. Crawl ─────────────────────────────────────────────────────────
        audit.status = "crawling"
        db.commit()

        crawler = Crawler(audit.url, max_pages=audit.max_pages, max_depth=audit.max_depth)
        crawler.run()

        logger.info("Crawl finished. %s raw results.", len(crawler.results))

        if not crawler.results:
            # robots.txt blocked the start URL or a network error prevented any fetch
            audit.status = "failed"
            audit.error_message = "No pages could be fetched. The start URL may be blocked by robots.txt or unreachable."
            db.commit()
            return

        # ── 2. Extract & persist pages ────────────────────────────────────────
        audit.status = "analyzing"
        db.commit()

        pages_data = []          # accumulated for duplicate-detection analyzers
        valid_html_pages = 0

        for result in crawler.results:
            is_html = (
                result.get("html")
                and result.get("content_type")
                and "text/html" in result["content_type"]
                and result.get("status_code") == 200
            )

            page = Page(
                audit_id=audit.id,
                url=result["url"],
                final_url=result.get("final_url"),
                depth=result["depth"],
                status_code=result.get("status_code"),
                content_type=result.get("content_type"),
                crawl_status="error" if result.get("error") else "success",
                error_message=result.get("error"),
            )

            p_data: dict = {"url": result["url"]}

            if is_html:
                headers = result.get("headers", {})
                extracted = extract_seo_data(result["html"], result["url"], headers)
                for k, v in extracted.items():
                    setattr(page, k, v)
                    p_data[k] = v
                valid_html_pages += 1
                
            p_data["html_length"] = len(result.get("html", ""))
            p_data["duration"] = result.get("duration", 0)
            p_data["status_code"] = result.get("status_code")
            p_data["final_url"] = result.get("final_url")

            db.add(page)
            db.flush()          # assign page.id before we reference it

            p_data["page_id"] = page.id
            pages_data.append(p_data)
            
            # --- Performance Analysis ---
            if result.get("status_code") == 200:
                perf_result = analyze_performance(result)
                m = perf_result["metrics"]
                page_perf = PagePerformance(
                    page_id=page.id,
                    response_time_ms=m.get("response_time_ms"),
                    html_size_bytes=m.get("html_size_bytes"),
                    is_compressed=m.get("is_compressed", False),
                    has_cache_control=m.get("has_cache_control", False),
                    image_count=m.get("image_count", 0),
                    oversized_image_count=0,
                    missing_dimensions_count=m.get("missing_dimensions_count", 0),
                    lcp_status=m.get("lcp_status", "UNAVAILABLE"),
                    inp_status=m.get("inp_status", "UNAVAILABLE"),
                    cls_status=m.get("cls_status", "UNAVAILABLE"),
                    ttfb_ms=m.get("ttfb_ms_approx"),
                    fcp_ms=m.get("fcp_ms"),
                    performance_score=m.get("performance_score"),
                )
                db.add(page_perf)
                
                # Add performance issues (using explicit fields, not splat)
                for issue_data in perf_result["issues"]:
                    issue = SEOIssue(
                        page_id=page.id,
                        page_url=page.url,
                        category=issue_data["category"],
                        severity=issue_data["severity"],
                        issue_code=issue_data["issue_code"],
                        title=issue_data["title"],
                        description=issue_data["description"],
                        recommendation_summary=issue_data["recommendation_summary"],
                        impact=issue_data["impact"],
                    )
                    db.add(issue)

        db.commit()
        logger.info("Persisted %s pages (%s valid HTML).", len(pages_data), valid_html_pages)

        if valid_html_pages == 0:
            # Every fetched URL failed or returned non-HTML — nothing useful to analyse
            audit.status = "failed"
            audit.error_message = (
                f"Crawled {len(pages_data)} URL(s) but none returned valid HTML. "
                "Check status codes and content types stored in /pages."
            )
            db.commit()
            return

        # ── 3. Run per-page analyzers ─────────────────────────────────────────
        all_issues: list = []

        for p_data in pages_data:
            if not p_data.get("title") and not p_data.get("h1_count"):
                # Skip pages with no extracted content (non-HTML / error pages)
                continue
            issues = run_page_analyzers(p_data)
            for issue in issues:
                issue["page_id"] = p_data["page_id"]
            all_issues.extend(issues)

        # Audit-level duplicate detection
        dup_issues = analyze_audit_duplicates(pages_data)
        for d_issue in dup_issues:
            matching = next(
                (p for p in pages_data if p["url"] == d_issue["page_url"]), None
            )
            if matching:
                d_issue["page_id"] = matching["page_id"]
                all_issues.append(d_issue)

        # Technical per-page checks
        for p_data in pages_data:
            tech_issues = run_technical_analyzers(p_data)
            for issue in tech_issues:
                issue["page_id"] = p_data["page_id"]
            all_issues.extend(tech_issues)
            
        # Technical audit-level checks (sitemap)
        # We need the sitemap URLs from the robots.txt parser if they exist
        robots_sitemaps = crawler.rp.site_maps() if hasattr(crawler.rp, "site_maps") and crawler.rp.site_maps() else []
        sitemap_issues = check_xml_sitemap(audit.url, robots_sitemaps)
        for issue in sitemap_issues:
            # associate with the first page (usually base url)
            issue["page_id"] = pages_data[0]["page_id"] if pages_data else None
            if issue["page_id"]:
                all_issues.append(issue)

        for issue_dict in all_issues:
            db_issue = SEOIssue(
                page_id=issue_dict["page_id"],
                page_url=issue_dict["page_url"],
                category=issue_dict["category"],
                severity=issue_dict["severity"],
                issue_code=issue_dict["issue_code"],
                title=issue_dict["title"],
                description=issue_dict["description"],
                recommendation_summary=issue_dict["recommendation_summary"],
                impact=issue_dict["impact"],
            )
            db.add(db_issue)
            
        # 5. Calculate Score
        score_data = calculate_audit_score(all_issues, len(pages_data))
        audit.score = score_data["score"]
        audit.score_data = json.dumps(score_data)

        # 6. Aggregate Performance
        page_performances = db.query(PagePerformance).join(Page).filter(Page.audit_id == audit.id).all()
        if page_performances:
            avg_rt = sum(p.response_time_ms for p in page_performances if p.response_time_ms) / len(page_performances)
            tot_size = sum(p.html_size_bytes for p in page_performances if p.html_size_bytes)
            avg_score = sum(p.performance_score for p in page_performances if p.performance_score is not None) / len(page_performances)
            
            audit_perf = AuditPerformance(
                audit_id=audit.id,
                avg_response_time_ms=int(avg_rt),
                total_page_size_bytes=tot_size,
                performance_score=int(avg_score)
            )
            db.add(audit_perf)

        audit.status = "completed"
        db.commit()
        logger.info(
            "Audit %s completed. pages=%s issues=%s",
            audit_id, len(pages_data), len(all_issues)
        )

    except Exception as exc:
        logger.exception("Unexpected error in run_audit_task(%s)", audit_id)
        try:
            audit.status = "failed"
            audit.error_message = f"Internal error: {exc}"
            db.commit()
        except Exception:
            pass
    finally:
        db.close()
