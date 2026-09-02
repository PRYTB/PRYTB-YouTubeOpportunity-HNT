import json
import re
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, ValidationError
from app.models.niche import ClusterHierarchy
from app.utils.logger import logger


def validate_label_quality(
    niche: str,
    subniche: str,
    microniche: str,
    representative_titles: List[str]
) -> Tuple[float, List[str]]:
    """
    Validates cluster label quality and hierarchy.
    Rejects generic labels ending in "* Domain", interrogative-only labels, or ungrounded labels.
    Returns:
        (label_quality_score [0..100], label_warnings [List[str]])
    """
    warnings = []
    score = 100.0

    # 1. Reject generic "* Domain"
    if re.search(r"\bDomain\b", niche, re.IGNORECASE) or re.search(r"\bDomain\b", subniche, re.IGNORECASE):
        warnings.append("Label contains generic 'Domain' suffix.")
        score -= 30.0

    # 2. Reject interrogative-only labels (e.g. "What is...", "How to...")
    interrogative_pattern = r"^(what|how|why|where|when|who)\b"
    if re.match(interrogative_pattern, niche, re.IGNORECASE):
        warnings.append("Niche label starts with an interrogative term.")
        score -= 25.0
    if re.match(interrogative_pattern, subniche, re.IGNORECASE):
        warnings.append("Subniche label starts with an interrogative term.")
        score -= 20.0

    # 3. Check for overly broad generic words
    generic_words = {"content", "videos", "topics", "stuff", "general", "analysis", "misc"}
    n_tokens = set(re.sub(r"[^\w\s]", "", niche.lower()).split())
    s_tokens = set(re.sub(r"[^\w\s]", "", subniche.lower()).split())

    if n_tokens.intersection(generic_words):
        warnings.append("Niche label uses generic fallback terms.")
        score -= 25.0
    if s_tokens.intersection(generic_words):
        warnings.append("Subniche label uses generic fallback terms.")
        score -= 15.0

    # 4. Check hierarchy specificity: Niche broad -> Subniche specific -> Microniche topic
    if len(subniche) < 3 or subniche.lower() == niche.lower():
        warnings.append("Subniche lacks distinct specificity relative to Niche.")
        score -= 20.0

    # 5. Support ground check in representative titles
    if representative_titles:
        all_rep = " ".join(representative_titles).lower()
        key_words = [w for w in n_tokens | s_tokens if len(w) > 3 and w not in generic_words]
        matched = sum(1 for kw in key_words if kw in all_rep)
        if key_words and matched == 0:
            warnings.append("Label keywords lack direct support in representative titles.")
            score -= 25.0

    final_score = max(0.0, min(100.0, score))
    return final_score, warnings


class ClusterLabeler:
    """
    Produces structured niche hierarchy (Niche -> Subniche -> Microniche -> Summary)
    from representative cluster titles.
    Supports LLM structured labeling with controlled retry & robust deterministic domain-knowledge fallback.
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
            '  "niche": "High level domain (e.g. Artificial Intelligence, Cybersecurity, Software Engineering)",\n'
            '  "subniche": "Specific category (e.g. AI Productivity Tools, Network Security Training)",\n'
            '  "microniche": "Highly specific topic (e.g. Automating Workflows with AI Agents)",\n'
            '  "summary": "Brief 1-2 sentence summary of what this video cluster is about",\n'
            '  "confidence": 85.0\n'
            "}\n"
            "DO NOT use generic suffixes like 'Domain'. DO NOT use interrogative labels (like 'What Domain'). Respond ONLY with valid raw JSON."
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
        content = re.sub(r"^```json\s*", "", content.strip(), flags=re.IGNORECASE)
        content = re.sub(r"```$", "", content.strip())
        return content.strip()

    def _fallback_label(self, titles: List[str]) -> ClusterHierarchy:
        """
        Domain-aware deterministic fallback labeler.
        Identifies key technical topics (AI, Cybersecurity, Networks, Hardware) instead of generating 'What Domain'.
        """
        if not titles:
            return ClusterHierarchy(
                niche="Technology & Computing",
                subniche="General Tech Topics",
                microniche="Miscellaneous Tech Videos",
                summary="Cluster contains no representative titles.",
                confidence=30.0
            )

        combined_text = " ".join(titles).lower()

        # Rule-based domain pattern matching
        if any(w in combined_text for w in ["cybersecurity", "security", "hacking", "network security", "firewall", "cyber"]):
            if any(w in combined_text for w in ["cert", "training", "beginner", "course", "learn", "study"]):
                niche = "Cybersecurity"
                subniche = "Cybersecurity Education"
                microniche = "Beginner cybersecurity training and certification"
            elif any(w in combined_text for w in ["network", "router", "cisco", "tcp"]):
                niche = "Cybersecurity"
                subniche = "Network Security & Defense"
                microniche = "Network architecture and security fundamentals"
            else:
                niche = "Cybersecurity"
                subniche = "Information Security Fundamentals"
                microniche = titles[0][:60]
        elif any(w in combined_text for w in ["ai", "artificial intelligence", "gpt", "chatgpt", "deepseek", "claude", "llm", "agent"]):
            if any(w in combined_text for w in ["safety", "risk", "warning", "future", "predict", "extinction", "end"]):
                niche = "Artificial Intelligence"
                subniche = "AI Safety & Risk Analysis"
                microniche = "Warnings and predictions about advanced AI"
            elif any(w in combined_text for w in ["agent", "automation", "workflow", "productivity"]):
                niche = "Artificial Intelligence"
                subniche = "AI Automation & Autonomous Agents"
                microniche = "Autonomous AI agents and workflow automation"
            else:
                niche = "Artificial Intelligence"
                subniche = "Artificial Intelligence Fundamentals"
                microniche = titles[0][:60]
        elif any(w in combined_text for w in ["hardware", "rtx", "gpu", "cpu", "windows", "pc", "intel", "amd"]):
            niche = "Computer Hardware & Operating Systems"
            subniche = "PC Hardware & System Optimization"
            microniche = titles[0][:60]
        else:
            # Extract top unigram/bigram
            from sklearn.feature_extraction.text import TfidfVectorizer
            from app.analytics.text_normalizer import GENERIC_STOP_WORDS
            stops = list(GENERIC_STOP_WORDS) + ["the", "and", "for", "with", "this", "that", "from"]
            vec = TfidfVectorizer(max_features=5, stop_words=stops, ngram_range=(1, 2))
            try:
                mat = vec.fit_transform(titles)
                feature_names = vec.get_feature_names_out()
                top_term = feature_names[0].title() if len(feature_names) > 0 else "Technology"
                second_term = feature_names[1].title() if len(feature_names) > 1 else "Analysis"
            except Exception:
                top_term = "Technology"
                second_term = "Analysis"

            niche = f"{top_term} Overview"
            subniche = f"{top_term} & {second_term}"
            microniche = titles[0][:60]

        summary = f"Thematic cluster focusing on {subniche.lower()} supported by representative title: '{titles[0]}'."
        
        return ClusterHierarchy(
            niche=niche,
            subniche=subniche,
            microniche=microniche,
            summary=summary,
            confidence=75.0
        )

