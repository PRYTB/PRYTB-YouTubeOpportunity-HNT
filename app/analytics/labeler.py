import json
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ValidationError
from app.models.niche import ClusterHierarchy
from app.utils.logger import logger


class ClusterLabeler:
    """
    Produces structured niche hierarchy (Niche -> Subniche -> Microniche -> Summary)
    from representative cluster titles.
    Supports LLM structured labeling with controlled retry & robust deterministic fallback.
    """
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model_name = model_name

    def label_cluster(self, representative_titles: List[str]) -> ClusterHierarchy:
        if not representative_titles:
            return self._fallback_label(representative_titles)

        if not self.api_key:
            return self._fallback_label(representative_titles)

        # Attempt structured LLM call
        prompt = self._build_prompt(representative_titles)
        for attempt in range(2):
            try:
                raw_json = self._call_llm(prompt)
                parsed = json.loads(raw_json)
                hierarchy = ClusterHierarchy(**parsed)
                return hierarchy
            except (json.JSONDecodeError, ValidationError, Exception) as exc:
                logger.warning(f"LLM labeling attempt {attempt+1} failed: {exc}")

        return self._fallback_label(representative_titles)

    def _build_prompt(self, titles: List[str]) -> str:
        titles_str = "\n".join(f"- {t}" for t in titles)
        return (
            "Analyze the following video titles from a single thematic cluster:\n"
            f"{titles_str}\n\n"
            "Provide a specific thematic categorization hierarchy in JSON format matching this schema strictly:\n"
            "{\n"
            '  "niche": "High level domain (e.g. Artificial Intelligence, Gaming, Finance)",\n'
            '  "subniche": "Specific category (e.g. AI Productivity Tools, Retro Consoles)",\n'
            '  "microniche": "Highly specific topic (e.g. Automating Excel Workflows with Generative AI)",\n'
            '  "summary": "Brief 1-2 sentence summary of what this video cluster is about",\n'
            '  "confidence": 85.0\n'
            "}\n"
            "Respond ONLY with valid raw JSON, without markdown backticks."
        )

    def _call_llm(self, prompt: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)
        res = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are a professional YouTube market research analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        content = res.choices[0].message.content or ""
        # Strip markdown wrapper if present
        content = re.sub(r"^```json\s*", "", content.strip(), flags=re.IGNORECASE)
        content = re.sub(r"```$", "", content.strip())
        return content.strip()

    def _fallback_label(self, titles: List[str]) -> ClusterHierarchy:
        """
        Deterministic, rule-based labeling fallback when LLM is unavailable or fails.
        Extracts key words/phrases from titles.
        """
        if not titles:
            return ClusterHierarchy(
                niche="Uncategorized",
                subniche="General Content",
                microniche="Misc Videos",
                summary="Cluster contains no representative titles.",
                confidence=30.0
            )

        # Extract words from titles
        all_words = []
        for t in titles:
            clean = re.sub(r"[^\w\s]", "", t).split()
            all_words.extend([w for w in clean if len(w) > 3])

        # Find top 3 frequent words
        counts = {}
        for w in all_words:
            w_lower = w.capitalize()
            counts[w_lower] = counts.get(w_lower, 0) + 1

        sorted_words = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        top_keywords = [w[0] for w in sorted_words[:3]]

        primary = top_keywords[0] if len(top_keywords) > 0 else "Content"
        secondary = top_keywords[1] if len(top_keywords) > 1 else "Topics"
        tertiary = top_keywords[2] if len(top_keywords) > 2 else "Analysis"

        first_title = titles[0] if titles else "General"

        return ClusterHierarchy(
            niche=f"{primary} Domain",
            subniche=f"{primary} & {secondary}",
            microniche=first_title[:60],
            summary=f"Cluster covering topics centered around {', '.join(top_keywords)}.",
            confidence=60.0
        )
