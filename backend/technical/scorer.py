from typing import List, Dict, Any

SEVERITY_WEIGHTS = {
    "CRITICAL": 20,
    "HIGH": 10,
    "MEDIUM": 5,
    "LOW": 2
}

def calculate_audit_score(issues: List[Dict[str, Any]], total_pages: int) -> Dict[str, Any]:
    score = 100
    
    # Track unique issue codes to avoid penalizing large sites multiple times for the same systemic issue
    unique_issues = {}
    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    category_counts = {}
    
    for issue in issues:
        code = issue.get("issue_code")
        severity = issue.get("severity", "LOW")
        category = issue.get("category", "unknown")
        
        # update counts per issue instance
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        category_counts[category] = category_counts.get(category, 0) + 1
        
        # only deduct points once per issue type to be fair to large sites
        if code not in unique_issues:
            unique_issues[code] = severity
            penalty = SEVERITY_WEIGHTS.get(severity, 0)
            score -= penalty
            
    # Ensure score doesn't drop below 0
    score = max(0, score)
    
    # Determine grade
    if score >= 90:
        grade = "Excellent"
    elif score >= 70:
        grade = "Good"
    elif score >= 50:
        grade = "Fair"
    else:
        grade = "Needs Improvement"
        
    explanation = f"Score is {score}/100. Deductions made for {len(unique_issues)} unique issue types across {total_pages} crawled pages."
    
    return {
        "score": score,
        "grade": grade,
        "severity_counts": severity_counts,
        "category_counts": category_counts,
        "explanation": explanation
    }
