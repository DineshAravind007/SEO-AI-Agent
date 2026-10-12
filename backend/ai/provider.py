import os
import json
import httpx
import logging
from typing import List
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
            "temperature": 0.2  # low temperature for deterministic structured output
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


class GeminiProvider(LLMProvider):
    """Calls the Google Gemini REST API (generateContent) via httpx.

    Environment variables read:
        GEMINI_API_KEY  - required; your Google AI Studio / Vertex AI key.
        LLM_MODEL       - optional; defaults to ``gemini-2.5-flash-lite``.
        LLM_TIMEOUT     - optional int seconds; defaults to 60.

    The Gemini ``generateContent`` endpoint is called with a three-turn
    contents list (user system prompt -> model ack -> user data prompt) so
    the existing system-prompt / user-prompt contract is preserved
    identically to the OpenAI provider without requiring the OpenAI SDK.
    """

    BASE_URL = (
        "https://generativelanguage.googleapis.com/v1beta/models"
        "/{model}:generateContent"
    )

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash-lite",
        timeout: int = 60,
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_url(self) -> str:
        return self.BASE_URL.format(model=self.model)

    def _build_payload(self, system_prompt: str, user_prompt: str) -> dict:
        """Build the generateContent request body.

        We send the system prompt as the first *user* turn, include a
        minimal *model* acknowledgement turn, then send the actual user
        prompt as the second *user* turn.  This gives the model a clear
        structural separation without relying on system_instruction (which
        is not available in all Gemini API versions / tiers).
        """
        return {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": system_prompt}],
                },
                {
                    "role": "model",
                    "parts": [{"text": "Understood. I will respond with valid JSON only."}],
                },
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                },
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }

    @staticmethod
    def _extract_text(data: dict) -> str:
        """Pull the raw response text out of a Gemini generateContent response.

        Raises ``ValueError`` if the expected fields are absent.
        """
        try:
            candidates = data["candidates"]
            if not candidates:
                raise ValueError("Gemini returned an empty candidates list.")
            content = candidates[0]["content"]
            parts = content["parts"]
            if not parts:
                raise ValueError("Gemini candidate has no parts.")
            return parts[0]["text"]
        except (KeyError, IndexError) as exc:
            raise ValueError(
                f"Unexpected Gemini response structure: {exc}"
            ) from exc

    @staticmethod
    def _parse_recommendations(text: str) -> List[AIRecommendationItem]:
        """Parse and validate JSON text returned by Gemini.

        Expects ``{"recommendations": [ ... ]}`` matching the prompt schema.
        Raises ``json.JSONDecodeError`` on bad JSON.  Individual items that
        fail Pydantic validation are logged and skipped rather than crashing
        the entire response.
        """
        # Gemini with responseMimeType=application/json may still wrap the
        # JSON in a markdown code fence - strip it defensively.
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            stripped = "\n".join(lines[1:-1]).strip()

        parsed = json.loads(stripped)  # raises json.JSONDecodeError on failure

        recs_data = parsed.get("recommendations", [])
        recommendations: List[AIRecommendationItem] = []
        for item in recs_data:
            try:
                recommendations.append(AIRecommendationItem(**item))
            except Exception as exc:
                logger.warning(
                    "Skipping malformed recommendation item %r: %s", item, exc
                )
        return recommendations

    # ------------------------------------------------------------------
    # LLMProvider interface
    # ------------------------------------------------------------------

    def generate_recommendations(
        self, system_prompt: str, user_prompt: str
    ) -> List[AIRecommendationItem]:
        url = self._build_url()
        params = {"key": self.api_key}
        headers = {"Content-Type": "application/json"}
        payload = self._build_payload(system_prompt, user_prompt)

        raw_text: str = ""  # captured for error logging before it is assigned

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=headers, params=params, json=payload)
                resp.raise_for_status()
                data = resp.json()

            raw_text = self._extract_text(data)
            recommendations = self._parse_recommendations(raw_text)

            if not recommendations:
                logger.warning(
                    "GeminiProvider received a valid response but found zero "
                    "parseable recommendation items."
                )
            return recommendations

        except httpx.TimeoutException as exc:
            logger.error("Gemini API request timed out after %ss.", self.timeout)
            raise Exception("Gemini API request timed out.") from exc

        except httpx.HTTPStatusError as exc:
            logger.error(
                "Gemini API HTTP error: %s - %s",
                exc.response.status_code,
                exc.response.text,
            )
            raise Exception(
                f"Gemini API error: {exc.response.status_code}"
            ) from exc

        except json.JSONDecodeError as exc:
            logger.error("Failed to parse JSON from Gemini response: %r", raw_text)
            raise Exception("Gemini returned malformed JSON.") from exc

        except ValueError as exc:
            logger.error("Unexpected Gemini response structure: %s", exc)
            raise Exception(f"Gemini response structure error: {exc}") from exc

        except Exception as exc:
            logger.error("Unexpected error communicating with Gemini: %s", exc)
            raise


def get_llm_provider() -> LLMProvider:
    provider_type = os.getenv("LLM_PROVIDER", "mock").lower()
    timeout = int(os.getenv("LLM_TIMEOUT", "60"))

    if provider_type == "openai":
        api_key = os.getenv("LLM_API_KEY")
        if not api_key:
            raise ValueError(
                "LLM_API_KEY environment variable is required for the OpenAI provider."
            )
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        return OpenAIProvider(api_key=api_key, model=model, timeout=timeout)

    if provider_type == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is required for the Gemini provider."
            )
        model = os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")
        return GeminiProvider(api_key=api_key, model=model, timeout=timeout)

    # Default to mock
    return MockLLMProvider()