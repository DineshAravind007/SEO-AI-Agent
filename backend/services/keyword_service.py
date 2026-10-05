import json
import logging
from sqlalchemy.orm import Session
from backend.database.models import Audit, Page, KeywordAnalysis, SEOIssue, CompetitorAnalysis
from backend.schemas.keywords import KeywordAnalysisResult, KeywordUsage, KeywordGap
from backend.ai.provider import get_llm_provider

logger = logging.getLogger(__name__)

def _calculate_opportunity_score(usage: KeywordUsage, total_pages: int) -> int:
    score = 100
    if total_pages == 0:
        return 0

    # Penalties
    if usage.title_matches == 0:
        score -= 20
    if usage.h1_matches == 0:
        score -= 20
    if usage.meta_matches == 0:
        score -= 10
    
    coverage = usage.pages_containing / total_pages
    if coverage == 0:
        score -= 30
    elif coverage < 0.1:
        score -= 15
        
    return max(0, min(100, score))

def analyze_keyword(db: Session, audit: Audit, keyword: str) -> KeywordAnalysisResult:
    kw_lower = keyword.lower()
    pages = db.query(Page).filter(Page.audit_id == audit.id, Page.crawl_status == "success").all()
    
    usage = KeywordUsage(
        title_matches=0,
        meta_matches=0,
        h1_matches=0,
        h2_matches=0,
        body_matches=0, # We don't store raw body text in the database to save space
        pages_containing=0,
        total_pages_crawled=len(pages)
    )
    
    for page in pages:
        found_on_page = False
        
        if page.title and kw_lower in page.title.lower():
            usage.title_matches += 1
            found_on_page = True
            
        if page.meta_description and kw_lower in page.meta_description.lower():
            usage.meta_matches += 1
            found_on_page = True
            
        h1_list = json.loads(page.h1_list) if page.h1_list else []
        if any(kw_lower in h1.lower() for h1 in h1_list):
            usage.h1_matches += 1
            found_on_page = True
            
        h2_list = json.loads(page.h2_list) if page.h2_list else []
        if any(kw_lower in h2.lower() for h2 in h2_list):
            usage.h2_matches += 1
            found_on_page = True
            
        if found_on_page:
            usage.pages_containing += 1

    score = _calculate_opportunity_score(usage, len(pages))
    
    gaps = []
    if usage.title_matches == 0:
        gaps.append(KeywordGap(type="Missing in Title", description=f"The keyword '{keyword}' is missing from all page titles."))
    if usage.h1_matches == 0:
        gaps.append(KeywordGap(type="Missing in H1", description=f"The keyword '{keyword}' is missing from all H1 tags."))
    if usage.pages_containing == 0:
        gaps.append(KeywordGap(type="No Coverage", description=f"The keyword '{keyword}' does not appear in any key HTML tags on your site."))
    elif (usage.pages_containing / len(pages)) < 0.1:
        gaps.append(KeywordGap(type="Low Coverage", description=f"The keyword '{keyword}' appears on less than 10% of your pages."))

    # Try to use AI for intent and suggestions
    intent = "Informational"
    suggestions = [f"{keyword} tips", f"best {keyword}", f"{keyword} guide"]
    
    try:
        provider = get_llm_provider()
        prompt = f"""
        Analyze the SEO keyword: "{keyword}".
        1. Classify its search intent (Informational, Commercial, Transactional, Navigational).
        2. Provide 3-5 related long-tail keyword suggestions.
        
        Respond ONLY in JSON format:
        {{
            "intent": "classification",
            "suggestions": ["sug1", "sug2"]
        }}
        """
        response_text = provider.generate(prompt)
        # very basic json extraction
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start != -1 and end != -1:
            data = json.loads(response_text[start:end])
            intent = data.get("intent", intent)
            suggestions = data.get("suggestions", suggestions)
    except Exception as e:
        logger.warning(f"AI Provider failed for keyword analysis, using fallback. Error: {e}")

    # Persist the analysis
    db_analysis = KeywordAnalysis(
        user_id=audit.user_id,
        audit_id=audit.id,
        keyword=keyword,
        opportunity_score=score,
        intent=intent,
        analysis_data=json.dumps({
            "title_matches": usage.title_matches,
            "meta_matches": usage.meta_matches,
            "h1_matches": usage.h1_matches,
            "h2_matches": usage.h2_matches,
            "body_matches": usage.body_matches,
            "pages_containing": usage.pages_containing,
            "total_pages_crawled": usage.total_pages_crawled,
            "gaps": [{"type": g.type, "description": g.description} for g in gaps]
        }),
        suggestions_data=json.dumps(suggestions)
    )
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)

    return KeywordAnalysisResult(
        id=db_analysis.id,
        audit_id=db_analysis.audit_id,
        keyword=db_analysis.keyword,
        opportunity_score=db_analysis.opportunity_score,
        intent=db_analysis.intent,
        usage=usage,
        gaps=gaps,
        suggestions=suggestions
    )
