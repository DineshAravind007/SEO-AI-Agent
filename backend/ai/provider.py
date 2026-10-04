import os
import json
import httpx
import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from backend.schemas.ai import AIRecommendationItem

logger = logging.getLogger(__name__)

class LLMProvider(ABC):
    @abstractmethod
    def generate_recommendations(self, system_prompt: str, user_prompt: str) -> List[AIRecommendationItem]:
        """Generate structured SEO recommendations."""
        pass

class MockLLMProvider(LLMProvider):
    def generate_recommendations(self, system_prompt: str, user_prompt: str) -> List[AIRecommendationItem]:
        logger.info("Using MockLLMProvider to generate recommendations.")
        # Simple deterministic parsing of issue codes from the user_prompt for testing
        issues = []
        if "MISSING_META_DESCRIPTION" in user_prompt:
            issues.append(
                AIRecommendationItem(
                    issue_type="MISSING_META_DESCRIPTION",
                    severity="HIGH",
                    title="Add Meta Descriptions",
                    explanation="Meta descriptions improve click-through rates.",
                    recommendation="Write unique, compelling meta descriptions for all pages.",
                    suggested_action="Update the <meta name='description'> tag.",
                    example="<meta name='description' content='Your concise summary here.'>",
                    confidence=95
                )
            )
        if not issues:
            # Fallback mock response
            issues.append(
                AIRecommendationItem(
                    issue_type="GENERAL_ISSUE",
                    severity="MEDIUM",
                    title="General Mock Recommendation",
                    explanation="This is a mock explanation.",
                    recommendation="This is a mock recommendation.",
                    suggested_action="Mock action.",
                    example=None,
                    confidence=100
                )
            )
        return issues

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout: int = 30):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.url = "https://api.openai.com/v1/chat/completions"

    def generate_recommendations(self, system_prompt: str, user_prompt: str) -> List[AIRecommendationItem]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # We enforce structured JSON output using OpenAI's response_format where supported,
        # but passing the schema in the prompt works robustly.
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2 # low temperature for deterministic structured output
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(self.url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                
                content = data["choices"][0]["message"]["content"]
                parsed_json = json.loads(content)
                
                # We expect {"recommendations": [ ... ]} based on prompt instructions
                recs_data = parsed_json.get("recommendations", [])
                
                recommendations = []
                for item in recs_data:
                    # Validate through Pydantic
                    valid_item = AIRecommendationItem(**item)
                    recommendations.append(valid_item)
                    
                return recommendations
                
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"LLM Provider API error: {e.response.status_code}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM: {content}")
            raise Exception("LLM Provider returned malformed JSON.")
        except Exception as e:
            logger.error(f"Error communicating with LLM Provider: {str(e)}")
            raise

def get_llm_provider() -> LLMProvider:
    provider_type = os.getenv("LLM_PROVIDER", "mock").lower()
    
    if provider_type == "openai":
        api_key = os.getenv("LLM_API_KEY")
        if not api_key:
            raise ValueError("LLM_API_KEY environment variable is required for OpenAI provider.")
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        timeout = int(os.getenv("LLM_TIMEOUT", "30"))
        return OpenAIProvider(api_key=api_key, model=model, timeout=timeout)
        
    # Default to mock
    return MockLLMProvider()
