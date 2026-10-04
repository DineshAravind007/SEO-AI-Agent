import json
from sqlalchemy.orm import Session
from backend.database.models import Audit, Page, SEOIssue
from backend.schemas.competitors import ComparisonData, MetricComparison, GapAnalysis

def _get_metric_counts(pages: list, key: str, boolean: bool = False) -> int:
    if boolean:
        return sum(1 for p in pages if getattr(p, key))
    return sum(getattr(p, key) or 0 for p in pages)

def compare_audits(db: Session, base: Audit, comp: Audit) -> ComparisonData:
    base_pages = db.query(Page).filter(Page.audit_id == base.id).all()
    comp_pages = db.query(Page).filter(Page.audit_id == comp.id).all()
    
    base_score_data = json.loads(base.score_data) if base.score_data else {}
    comp_score_data = json.loads(comp.score_data) if comp.score_data else {}
    
    base_issues = db.query(SEOIssue).join(Page).filter(Page.audit_id == base.id).all()
    comp_issues = db.query(SEOIssue).join(Page).filter(Page.audit_id == comp.id).all()
    
    # Calculate simple page level metrics for comparison
    def agg_metrics(pages):
        return {
            "titles": sum(1 for p in pages if p.title),
            "meta_descriptions": sum(1 for p in pages if p.meta_description),
            "h1s": sum(p.h1_count or 0 for p in pages),
            "words": sum(p.word_count or 0 for p in pages),
            "images": sum(p.image_count or 0 for p in pages),
            "missing_alt": sum(p.images_missing_alt or 0 for p in pages),
            "internal_links": sum(p.internal_link_count or 0 for p in pages),
            "structured_data": sum(1 for p in pages if p.structured_data_presence),
        }
        
    b_agg = agg_metrics(base_pages)
    c_agg = agg_metrics(comp_pages)
    
    metrics = []
    gaps = []
    
    def add_metric(name, b_val, c_val, lower_is_better=False, is_bool=False):
        diff = ""
        gap = None
        
        if is_bool:
            b_pct = (b_val / max(len(base_pages), 1))
            c_pct = (c_val / max(len(comp_pages), 1))
            
            b_str = f"{b_val}/{len(base_pages)}"
            c_str = f"{c_val}/{len(comp_pages)}"
            
            if abs(b_pct - c_pct) < 0.1:
                diff = "Equal"
            elif b_pct > c_pct:
                diff = "You are better" if not lower_is_better else "Competitor better"
            else:
                diff = "Competitor better" if not lower_is_better else "You are better"
                
            if (c_pct > b_pct) and not lower_is_better:
                gap = True
            elif (b_pct > c_pct) and lower_is_better:
                gap = True
                
        else:
            b_avg = b_val / max(len(base_pages), 1)
            c_avg = c_val / max(len(comp_pages), 1)
            
            b_str = f"{b_avg:.1f} avg"
            c_str = f"{c_avg:.1f} avg"
            
            if b_avg == 0 and c_avg == 0:
                diff = "Equal"
            elif abs(b_avg - c_avg) / max(b_avg, c_avg, 1) < 0.1:
                diff = "Equal"
            elif b_avg > c_avg:
                diff = "You are better" if not lower_is_better else "Competitor better"
            else:
                diff = "Competitor better" if not lower_is_better else "You are better"
                
            if (c_avg > b_avg) and not lower_is_better:
                gap = True
            elif (b_avg > c_avg) and lower_is_better:
                gap = True

        metrics.append(MetricComparison(
            metric=name,
            user_value=b_str,
            competitor_value=c_str,
            difference=diff
        ))
        
        return gap, b_str, c_str
        
    def check_gap(name, b_val, c_val, lower_is_better=False, is_bool=False, severity="MEDIUM", rec=""):
        gap, b_str, c_str = add_metric(name, b_val, c_val, lower_is_better, is_bool)
        if gap:
            gaps.append(GapAnalysis(
                category="On-Page" if "SEO" not in name else "Technical",
                metric=name,
                user_value=b_str,
                competitor_value=c_str,
                difference="Competitor is outperforming you.",
                severity=severity,
                explanation=f"Your website performs worse on {name} compared to the competitor.",
                recommended_action=rec
            ))

    check_gap("Meta Description", b_agg["meta_descriptions"], c_agg["meta_descriptions"], is_bool=True, severity="HIGH", rec="Add unique meta descriptions to all pages.")
    check_gap("H1 Tags", b_agg["h1s"], c_agg["h1s"], severity="HIGH", rec="Ensure all pages have exactly one H1 tag.")
    check_gap("Word Count", b_agg["words"], c_agg["words"], severity="LOW", rec="Increase content depth on key pages.")
    check_gap("Missing Image Alt", b_agg["missing_alt"], c_agg["missing_alt"], lower_is_better=True, severity="MEDIUM", rec="Add descriptive alt text to all images.")
    check_gap("Structured Data", b_agg["structured_data"], c_agg["structured_data"], is_bool=True, severity="MEDIUM", rec="Implement structured data (JSON-LD) to enhance search visibility.")
    
    # Issue gaps
    b_crit = sum(1 for i in base_issues if i.severity == "CRITICAL")
    c_crit = sum(1 for i in comp_issues if i.severity == "CRITICAL")
    if b_crit > c_crit:
        gaps.append(GapAnalysis(
            category="Technical",
            metric="Critical Issues",
            user_value=str(b_crit),
            competitor_value=str(c_crit),
            difference="You have more critical issues.",
            severity="CRITICAL",
            explanation="Critical issues severely impact SEO and usability.",
            recommended_action="Prioritize fixing critical issues immediately."
        ))

    return ComparisonData(
        competitor_url=comp.url,
        competitor_audit_id=comp.id,
        seo_score=comp.score,
        seo_grade=comp_score_data.get("grade"),
        total_issues=len(comp_issues),
        severity_counts=comp_score_data.get("severity_counts", {}),
        category_counts=comp_score_data.get("category_counts", {}),
        metrics=metrics,
        gaps=gaps
    )
