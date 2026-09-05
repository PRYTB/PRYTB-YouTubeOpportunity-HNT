"""Sprint 8 production feasibility and risk analysis."""
from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timezone
from statistics import mean, median
from typing import Any, Dict, List, Mapping, Optional, Sequence

from app.config.production_risk_config import ProductionRiskConfig, production_risk_config
from app.models.production_risk import (
    ClusterProductionRisk,
    ProductionComplexity,
    RiskLevel,
    Sprint8AnalysisResult,
    Sprint8QualityMetrics,
    FacelessFeasibility,
    AIAssistancePotential,
    ExpertiseRequirement,
    RepeatabilityBand,
)

_RESEARCH_TERMS = {
    "analysis", "case study", "documentary", "explained", "facts", "history",
    "investigation", "science", "research", "review", "tutorial", "why",
}
_FOOTAGE_TERMS = {
    "anime", "celebrity", "clip", "clips", "film", "football", "gameplay",
    "highlights", "movie", "music", "reaction", "recap", "sports", "trailer",
}
_EDITING_TERMS = {
    "animation", "cinematic", "compilation", "documentary", "explained",
    "highlights", "montage", "reaction", "recap", "top 10", "visualization",
}
_COPYRIGHT_TERMS = {
    "anime", "clip", "clips", "film", "football", "highlights", "movie",
    "music", "reaction", "recap", "song", "sports", "trailer",
}
_REUSED_TERMS = {"clip", "clips", "compilation", "highlights", "reaction", "recap", "reupload"}
_SENSITIVE_TERMS = {
    "alcohol", "crime", "drug", "finance", "financial", "gambling", "gun",
    "health", "legal", "medical", "politics", "suicide", "violence", "war", "weapon",
}

# New term sets for Sprint 8 components
_FACELESS_POSITIVE_TERMS = {
    "screen", "recording", "screencast", "capture", "demo", "walkthrough",
    "tutorial", "guide", "how to", "slide", "slides", "presentation",
    "voiceover", "narration", "explainer", "animation", "motion graphics",
    "whiteboard", "diagram", "chart", "graph", "code", "coding", "programming",
    "software", "app", "tool", "dashboard", "interface", "ui", "ux",
    "terminal", "command", "script", "automation", "workflow",
}
_FACELESS_NEGATIVE_TERMS = {
    "vlog", "face", "camera", "on camera", "in person", "interview",
    "talking head", "personal", "my journey", "my story", "behind the scenes",
    "day in the life", "travel", "irl", "real life", "live", "stream",
    "reaction", "facecam", "webcam", "selfie", "meet", "event", "conference",
    "stage", "audience", "crowd", "public", "meetup",
}
_AI_ASSISTANCE_TERMS = {
    "research", "outline", "script", "translate", "translation", "voice",
    "tts", "text to speech", "voiceover", "graphics", "animation", "edit",
    "editing", "subtitle", "caption", "metadata", "title", "description",
    "tag", "thumbnail", "chapter", "summary", "fact check", "fact-check",
}
_EXPERTISE_TERMS_LOW = {
    "commentary", "opinion", "review", "reaction", "thoughts", "discussion",
    "talk", "chat", "casual", "beginner", "intro", "introduction", "basics",
    "overview", "summary", "recap", "news", "update", "announcement",
}
_EXPERTISE_TERMS_MEDIUM = {
    "tutorial", "guide", "how to", "walkthrough", "explained", "demo",
    "demo", "walkthrough", "workshop", "course", "lesson", "training",
    "tips", "tricks", "best practices", "workflow", "process", "method",
    "technique", "strategy", "setup", "configuration", "install", "usage",
}
_EXPERTISE_TERMS_HIGH = {
    "advanced", "expert", "masterclass", "deep dive", "internals", "architecture",
    "optimization", "performance", "scaling", "security", "vulnerability",
    "exploit", "penetration", "reverse engineering", "malware", "cryptography",
    "compiler", "kernel", "distributed systems", "concurrency", "parallel",
    "machine learning", "deep learning", "neural network", "transformer",
    "llm", "fine-tuning", "training", "inference", "quantization",
}
_EXPERTISE_TERMS_SPECIALIST = {
    "certification", "certified", "license", "accredited", "professional",
    "medical", "legal", "financial", "investment", "tax", "accounting",
    "engineering", "architecture", "structural", "civil", "mechanical",
    "electrical", "aerospace", "biomedical", "pharmaceutical", "clinical",
    "surgery", "diagnosis", "treatment", "therapy", "prescription",
    "regulation", "compliance", "audit", "forensic", "patent", "intellectual property",
}
_PLATFORM_RISK_REUSED_TERMS = {
    "clip", "clips", "compilation", "highlights", "reaction", "recap", "reupload",
    "montage", "top 10", "countdown", "best of", "worst of", "moments",
}
_PLATFORM_RISK_MISLEADING_TERMS = {
    "secret", "hidden", "exposed", "revealed", "shocking", "unbelievable",
    "miracle", "instant", "overnight", "guaranteed", "proven", "scientifically proven",
    "doctors hate", "they don't want", "banned", "censored", "suppressed",
    "get rich", "make money", "passive income", "easy money", "no work",
    "click here", "link in bio", "subscribe now", "smash like",
}
_PLATFORM_RISK_SENSITIVE_TERMS = {
    "alcohol", "crime", "drug", "finance", "financial", "gambling", "gun",
    "health", "legal", "medical", "politics", "suicide", "violence", "war", "weapon",
    "adult", "nsfw", "sexual", "porn", "erotic", "fetish", "extreme",
    "self-harm", "eating disorder", "depression", "anxiety", "mental health",
}
_PLATFORM_RISK_SPAM_TERMS = {
    "sub4sub", "sub for sub", "like4like", "follow4follow", "view4view",
    "bot", "fake", "generator", "hack", "cheat", "exploit", "crack",
    "keygen", "serial", "license key", "activation", "free premium",
    "mod apk", "unlimited", "unlocked", "premium free",
}
_ACCURACY_RISK_TECHNICAL_TERMS = {
    "tutorial", "guide", "how to", "walkthrough", "install", "setup",
    "configure", "command", "code", "script", "api", "sdk", "framework",
    "library", "function", "class", "method", "parameter", "variable",
    "debug", "error", "exception", "bug", "fix", "patch", "update",
    "version", "release", "deprecated", "breaking change", "migration",
}
_ACCURACY_RISK_STATS_TERMS = {
    "statistic", "statistics", "data", "study", "research", "survey",
    "poll", "report", "analysis", "finding", "result", "correlation",
    "causation", "significant", "p-value", "confidence interval",
    "sample size", "population", "demographic", "percentage", "percent",
    "ratio", "average", "mean", "median", "mode", "standard deviation",
}
_ACCURACY_RISK_PREDICTION_TERMS = {
    "prediction", "forecast", "future", "will", "going to", "expected",
    "projected", "estimate", "trend", "outlook", "prediction", "prophecy",
    "crystal ball", "next year", "coming", "upcoming", "soon", "2025",
    "2026", "2027", "roadmap", "plan", "strategy", "vision",
}
_ACCURACY_RISK_RAPID_CHANGE_TERMS = {
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "llm", "gpt", "claude", "gemini", "copilot", "chatgpt", "openai",
    "anthropic", "midjourney", "stable diffusion", "dall-e", "sora",
    "software", "update", "release", "version", "patch", "hotfix",
    "api change", "breaking", "deprecated", "sunset", "migration",
    "framework", "library", "dependency", "package", "npm", "pip",
    "cargo", "maven", "gradle", "docker", "kubernetes", "cloud",
}
_UPDATE_BURDEN_DATE_TERMS = {
    "2024", "2025", "2026", "2027", "2028", "january", "february", "march",
    "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "q1", "q2", "q3", "q4", "quarter", "year",
    "annual", "monthly", "weekly", "daily", "today", "now", "current",
    "latest", "new", "updated", "recent", "fresh",
}
_UPDATE_BURDEN_NEWS_TERMS = {
    "news", "breaking", "announcement", "release", "launch", "reveal",
    "unveil", "announce", "press", "media", "journal", "article",
    "report", "coverage", "headline", "story", "event", "happening",
    "occurred", "happened", "just in", "developing", "live",
}
_UPDATE_BURDEN_PRODUCT_TERMS = {
    "version", "release", "update", "patch", "hotfix", "upgrade",
    "downgrade", "migration", "deprecated", "sunset", "eol", "end of life",
    "new feature", "feature", "enhancement", "improvement", "change",
    "breaking change", "changelog", "release notes", "roadmap",
}
_UPDATE_BURDEN_SOFTWARE_TERMS = {
    "ui", "ux", "interface", "dashboard", "menu", "button", "dialog",
    "screen", "page", "view", "layout", "design", "theme", "dark mode",
    "light mode", "responsive", "mobile", "desktop", "web app",
    "progressive web app", "pwa", "electron", "tauri", "flutter",
    "react", "vue", "angular", "svelte", "next.js", "nuxt",
}
_UPDATE_BURDEN_PREDICTION_TERMS = {
    "prediction", "forecast", "future", "will", "going to", "expected",
    "projected", "estimate", "trend", "outlook", "roadmap", "plan",
    "vision", "hypothesis", "speculation", "guess", "assumption",
}
_SOURCE_DEPENDENCY_THIRD_PARTY_TERMS = {
    "clip", "clips", "footage", "video", "movie", "film", "trailer",
    "teaser", "preview", "scene", "moment", "highlight", "recap",
    "reaction", "commentary", "review", "analysis", "breakdown",
}
_SOURCE_DEPENDENCY_NEWS_TERMS = {
    "news", "article", "report", "journal", "press", "media",
    "publisher", "outlet", "correspondent", "reporter", "journalist",
    "source", "citation", "reference", "according to", "said", "reported",
}
_SOURCE_DEPENDENCY_INTERVIEW_TERMS = {
    "interview", "interviewed", "guest", "expert", "specialist",
    "professional", "authority", "leader", "ceo", "cto", "founder",
    "creator", "developer", "engineer", "researcher", "scientist",
    "doctor", "professor", "analyst", "consultant", "advisor",
}
_SOURCE_DEPENDENCY_VENDOR_TERMS = {
    "documentation", "docs", "manual", "guide", "reference", "api",
    "sdk", "specification", "spec", "whitepaper", "datasheet",
    "brochure", "marketing", "press kit", "vendor", "supplier",
    "manufacturer", "official", "authorized", "partner",
}
_SOURCE_DEPENDENCY_EXTERNAL_TERMS = {
    "data", "dataset", "database", "api", "endpoint", "feed",
    "stream", "webhook", "integration", "third-party", "external",
    "public", "open data", "government", "census", "statistics",
    "registry", "repository", "archive", "library", "catalog",
}
_SOURCE_DEPENDENCY_ORIGINAL_TERMS = {
    "original", "own", "my", "i created", "i made", "i built",
    "i developed", "i designed", "i wrote", "i recorded", "i filmed",
    "self-created", "self-made", "first-party", "proprietary",
    "exclusive", "unique", "never before", "first look",
}
_SOURCE_DEPENDENCY_SCREEN_TERMS = {
    "screen", "recording", "screencast", "capture", "demo", "walkthrough",
    "terminal", "command", "code", "coding", "programming", "ide",
    "editor", "browser", "dashboard", "interface", "ui", "app",
}
_REPEATABILITY_POSITIVE_TERMS = {
    "series", "episode", "part", "chapter", "lesson", "module",
    "template", "format", "structure", "workflow", "process", "pipeline",
    "batch", "automation", "script", "tool", "recurring", "regular",
    "weekly", "daily", "monthly", "consistent", "standardized", "repeatable",
}
_REPEATABILITY_NEGATIVE_TERMS = {
    "exclusive", "one-off", "unique", "never before", "first time",
    "only", "singular", "special", "event", "live", "conference",
    "travel", "field", "on location", "on site", "in person",
    "interview", "guest", "celebrity", "vip", "access", "behind the scenes",
    "limited", "rare", "once", "historic", "unprecedented",
}

_WORDS = re.compile(r"[^\W_]+", re.UNICODE)


def _signal_score(texts: Sequence[str], terms: set[str]) -> tuple[Optional[float], List[str], int]:
    if not texts:
        return None, [], 0
    matches = [_matches(text, terms) for text in texts]
    matched_items = sum(bool(item) for item in matches)
    found = sorted({term for item in matches for term in item})
    if matched_items == 0:
        return None, found, matched_items
    return _bounded(matched_items * 100.0 / len(texts)), found, matched_items


def _polarity_score(
    texts: Sequence[str],
    positive_terms: set[str],
    negative_terms: set[str],
) -> tuple[Optional[float], Dict[str, Any]]:
    if not texts:
        return None, {
            "positive_matches": 0,
            "negative_matches": 0,
            "positive_terms": [],
            "negative_terms": [],
        }

    positive = [_matches(text, positive_terms) for text in texts]
    negative = [_matches(text, negative_terms) for text in texts]
    positive_matches = sum(bool(item) for item in positive)
    negative_matches = sum(bool(item) for item in negative)
    evidence = {
        "positive_matches": positive_matches,
        "negative_matches": negative_matches,
        "positive_terms": sorted({term for item in positive for term in item}),
        "negative_terms": sorted({term for item in negative for term in item}),
    }
    if positive_matches == 0 and negative_matches == 0:
        return None, evidence

    positive_share = positive_matches / len(texts)
    negative_share = negative_matches / len(texts)
    return _bounded(50.0 + (positive_share - negative_share) * 50.0), evidence


def _weighted_score(components: Sequence[tuple[Optional[float], float]]) -> Optional[float]:
    known = [(value, weight) for value, weight in components if value is not None and weight > 0]
    if not known:
        return None
    return _bounded(
        sum(value * weight for value, weight in known)
        / sum(weight for _, weight in known)
    )


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def _rate(numerator: int, denominator: int) -> Optional[float]:
    return round(numerator * 100.0 / denominator, 4) if denominator else None


def _bounded(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def _matches(text: str, terms: set[str]) -> List[str]:
    padded = f" {' '.join(_WORDS.findall(text.lower()))} "
    return sorted(term for term in terms if f" {term} " in padded)


class ProductionRiskEngine:
    """Estimate production effort and policy risk from observable cluster metadata."""

    def __init__(self, config: Optional[ProductionRiskConfig] = None):
        self.config = config or production_risk_config

    def analyze(
        self,
        videos: Sequence[Mapping[str, Any]],
        clusters: Sequence[Mapping[str, Any]],
        source_market_structure_run_id: Optional[str] = None,
        source_cluster_run_id: Optional[str] = None,
        as_of: Optional[datetime] = None,
    ) -> Sprint8AnalysisResult:
        now = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
        videos_by_id = {str(video.get("video_id") or ""): video for video in videos}
        aggregates = [self._analyze_cluster(cluster, videos_by_id) for cluster in clusters]
        total = len(videos)
        quality = Sprint8QualityMetrics(
            total_videos=total,
            total_clusters=len(aggregates),
            title_unknown_rate=_rate(sum(not str(v.get("title") or "").strip() for v in videos), total) or 0.0,
            description_unknown_rate=_rate(sum(not str(v.get("description") or "").strip() for v in videos), total) or 0.0,
            duration_unknown_rate=_rate(sum(_number(v.get("duration_seconds")) is None for v in videos), total) or 0.0,
            clusters_without_risk_evidence=sum(item.overall_risk_score is None for item in aggregates),
            faceless_unknown_rate=_rate(sum(item.faceless_feasibility == FacelessFeasibility.UNKNOWN for item in aggregates), len(aggregates)) or 0.0,
            ai_assistance_unknown_rate=_rate(sum(item.ai_assistance_potential == AIAssistancePotential.UNKNOWN for item in aggregates), len(aggregates)) or 0.0,
            expertise_unknown_rate=_rate(sum(item.expertise_requirement == ExpertiseRequirement.UNKNOWN for item in aggregates), len(aggregates)) or 0.0,
            platform_risk_unknown_rate=_rate(sum(item.platform_policy_risk_level == RiskLevel.UNKNOWN for item in aggregates), len(aggregates)) or 0.0,
            accuracy_risk_unknown_rate=_rate(sum(item.accuracy_risk_level == RiskLevel.UNKNOWN for item in aggregates), len(aggregates)) or 0.0,
            update_burden_unknown_rate=_rate(sum(item.update_burden_level == RiskLevel.UNKNOWN for item in aggregates), len(aggregates)) or 0.0,
            source_dependency_unknown_rate=_rate(sum(item.source_dependency_level == RiskLevel.UNKNOWN for item in aggregates), len(aggregates)) or 0.0,
            repeatability_unknown_rate=_rate(sum(item.repeatability_band == RepeatabilityBand.UNKNOWN for item in aggregates), len(aggregates)) or 0.0,
            attractiveness_unavailable_rate=_rate(sum(not item.production_attractiveness_available for item in aggregates), len(aggregates)) or 0.0,
            low_sample_cluster_count=sum(item.video_count < self.config.minimum_cluster_sample for item in aggregates),
        )
        return Sprint8AnalysisResult(
            run_id=f"sprint8-{uuid.uuid4()}",
            source_market_structure_run_id=source_market_structure_run_id,
            source_cluster_run_id=source_cluster_run_id,
            analyzed_at=now.isoformat(),
            config=self.config.model_dump(),
            clusters=aggregates,
            quality=quality,
        )

    def _analyze_cluster(
        self,
        cluster: Mapping[str, Any],
        videos_by_id: Mapping[str, Mapping[str, Any]],
    ) -> ClusterProductionRisk:
        video_ids = [str(item) for item in cluster.get("video_ids") or []]
        members = [videos_by_id[video_id] for video_id in video_ids if video_id in videos_by_id]
        warnings: List[str] = []
        observed_fields = ["cluster video membership"]
        inferred_fields: List[str] = []
        assumptions = [
            "Scores are metadata-based feasibility estimates, not quoted labor or monetary costs.",
            "Text signals indicate potential production requirements and policy exposure, not confirmed use.",
        ]

        texts = [
            " ".join((str(video.get("title") or ""), str(video.get("description") or ""))).strip()
            for video in members
        ]
        known_texts = [text for text in texts if text]
        durations = [_number(video.get("duration_seconds")) for video in members]
        known_durations = [value for value in durations if value is not None]
        if known_texts:
            observed_fields.append("video titles/descriptions")
        else:
            warnings.append("Titles and descriptions unavailable; textual complexity and risk are UNKNOWN.")
        if known_durations:
            observed_fields.append("video durations")
        else:
            warnings.append("Durations unavailable; hours use the configured output-length assumption.")

        def signal_score(terms: set[str]) -> tuple[Optional[float], List[str], int]:
            if not known_texts:
                return None, [], 0
            matches = [_matches(text, terms) for text in known_texts]
            matched_videos = sum(bool(item) for item in matches)
            found = sorted({term for item in matches for term in item})
            if matched_videos == 0:
                return None, found, matched_videos
            return _bounded(matched_videos * 100.0 / len(known_texts)), found, matched_videos

        def polarity_score(
            positive_terms: set[str],
            negative_terms: set[str],
        ) -> tuple[Optional[float], Dict[str, Any]]:
            if not known_texts:
                return None, {
                    "positive_matches": 0,
                    "negative_matches": 0,
                    "positive_terms": [],
                    "negative_terms": [],
                }
            positive = [_matches(text, positive_terms) for text in known_texts]
            negative = [_matches(text, negative_terms) for text in known_texts]
            positive_matches = sum(bool(item) for item in positive)
            negative_matches = sum(bool(item) for item in negative)
            evidence = {
                "positive_matches": positive_matches,
                "negative_matches": negative_matches,
                "positive_terms": sorted({term for item in positive for term in item}),
                "negative_terms": sorted({term for item in negative for term in item}),
            }
            if positive_matches == 0 and negative_matches == 0:
                return None, evidence
            positive_share = positive_matches / len(known_texts)
            negative_share = negative_matches / len(known_texts)
            return _bounded(50.0 + (positive_share - negative_share) * 50.0), evidence

        # Existing complexity signals
        research, research_terms, research_videos = signal_score(_RESEARCH_TERMS)
        footage, footage_terms, footage_videos = signal_score(_FOOTAGE_TERMS)
        editing_text, editing_terms, editing_videos = signal_score(_EDITING_TERMS)
        copyright_risk, copyright_terms, copyright_videos = signal_score(_COPYRIGHT_TERMS)
        reused_risk, reused_terms, reused_videos = signal_score(_REUSED_TERMS)
        sensitive_risk, sensitive_terms, sensitive_videos = signal_score(_SENSITIVE_TERMS)

        # New Sprint 8 component signals
        # Faceless Feasibility
        faceless_score, faceless_evidence = polarity_score(_FACELESS_POSITIVE_TERMS, _FACELESS_NEGATIVE_TERMS)
        faceless_confidence = 0.0
        faceless_level = FacelessFeasibility.UNKNOWN
        faceless_obs = faceless_evidence.get("positive_terms", [])
        faceless_inf = faceless_evidence.get("negative_terms", [])
        faceless_warns = []
        if faceless_score is not None:
            faceless_confidence = _bounded(faceless_score)
            if faceless_score >= 70:
                faceless_level = FacelessFeasibility.HIGH
            elif faceless_score >= 40:
                faceless_level = FacelessFeasibility.MEDIUM
            else:
                faceless_level = FacelessFeasibility.LOW
            if not faceless_obs and not faceless_inf:
                faceless_warns.append("No clear faceless indicators found; classification uncertain.")
        else:
            faceless_warns.append("Insufficient textual evidence for faceless classification.")

        # AI Assistance Potential
        ai_score, ai_evidence, ai_videos = signal_score(_AI_ASSISTANCE_TERMS)
        ai_confidence = 0.0
        ai_level = AIAssistancePotential.UNKNOWN
        ai_obs = ai_evidence
        ai_inf: List[str] = []
        ai_warns = []
        if ai_score is not None:
            ai_confidence = _bounded(ai_score)
            if ai_score >= 60:
                ai_level = AIAssistancePotential.HIGH
            elif ai_score >= 30:
                ai_level = AIAssistancePotential.MEDIUM
            else:
                ai_level = AIAssistancePotential.LOW
            if not ai_obs:
                ai_warns.append("No clear AI assistance signals found.")
        else:
            ai_warns.append("Insufficient textual evidence for AI assistance classification.")

        # Expertise Requirement
        exp_low, exp_low_terms, exp_low_videos = signal_score(_EXPERTISE_TERMS_LOW)
        exp_med, exp_med_terms, exp_med_videos = signal_score(_EXPERTISE_TERMS_MEDIUM)
        exp_high, exp_high_terms, exp_high_videos = signal_score(_EXPERTISE_TERMS_HIGH)
        exp_spec, exp_spec_terms, exp_spec_videos = signal_score(_EXPERTISE_TERMS_SPECIALIST)
        expertise_score = None
        exp_obs: List[str] = []
        exp_inf: List[str] = []
        exp_warns = []
        expertise_confidence = 0.0
        exp_level = ExpertiseRequirement.UNKNOWN
        if any(v is not None for v in (exp_low, exp_med, exp_high, exp_spec)):
            low_strength = (exp_low or 0.0) * (0.6 + 0.4 * min(1.0, len(exp_low_terms) / 3.0))
            med_strength = (exp_med or 0.0) * (0.6 + 0.4 * min(1.0, len(exp_med_terms) / 3.0))
            high_strength = (exp_high or 0.0) * (0.6 + 0.4 * min(1.0, len(exp_high_terms) / 3.0))
            spec_strength = (exp_spec or 0.0) * (0.6 + 0.4 * min(1.0, len(exp_spec_terms) / 3.0))
            exp_obs = exp_low_terms + exp_med_terms + exp_high_terms + exp_spec_terms
            strongest = max(low_strength, med_strength, high_strength, spec_strength)
            if spec_strength >= 35.0 and (spec_strength >= high_strength or exp_spec_videos >= 1):
                exp_level = ExpertiseRequirement.SPECIALIST
                expertise_score = _bounded(75.0 + min(25.0, spec_strength * 0.25))
            elif high_strength >= 35.0 and (high_strength >= med_strength or exp_high_videos >= 1):
                exp_level = ExpertiseRequirement.HIGH
                expertise_score = _bounded(55.0 + min(19.0, high_strength * 0.19))
            elif med_strength >= 25.0:
                exp_level = ExpertiseRequirement.MEDIUM
                expertise_score = _bounded(30.0 + min(24.0, med_strength * 0.24))
            else:
                exp_level = ExpertiseRequirement.LOW
                expertise_score = _bounded(5.0 + min(24.0, low_strength * 0.24))
            expertise_confidence = _bounded(min(100.0, strongest * 0.8 + len(exp_obs) * 4.0))
            if not exp_obs:
                exp_warns.append("No clear expertise signals found.")
        else:
            exp_warns.append("Insufficient textual evidence for expertise classification.")

        median_minutes = median(known_durations) / 60.0 if known_durations else None
        duration_component = min(100.0, (median_minutes or 0.0) / 20.0 * 100.0) if known_durations else None
        editing_components = [value for value in (editing_text, duration_component) if value is not None]
        editing = _bounded(mean(editing_components)) if editing_components else None
        production_components = [
            (research, self.config.cost_weight_research),
            (footage, self.config.cost_weight_footage),
            (editing, self.config.cost_weight_editing),
        ]
        known_production = [(value, weight) for value, weight in production_components if value is not None]
        if known_production:
            production_cost = _bounded(
                sum(value * weight for value, weight in known_production)
                / sum(weight for _, weight in known_production)
            )
            if production_cost >= self.config.high_complexity_min:
                complexity = ProductionComplexity.HIGH
            elif production_cost >= self.config.medium_complexity_min:
                complexity = ProductionComplexity.MEDIUM
            else:
                complexity = ProductionComplexity.LOW
            inferred_fields.extend([
                "research_complexity_score", "footage_complexity_score",
                "editing_complexity_score", "production_cost_score", "estimated_hours",
            ])
        else:
            production_cost = 0.0
            complexity = ProductionComplexity.UNKNOWN

        output_minutes = median_minutes or self.config.default_output_minutes
        effort_factor = 0.5 + production_cost / 100.0
        hours_low = round(max(self.config.minimum_hours_low, output_minutes * self.config.hours_per_output_minute_low * effort_factor), 1)
        hours_high = round(max(self.config.minimum_hours_high, output_minutes * self.config.hours_per_output_minute_high * effort_factor), 1)

        # New Sprint 8 Risk Components
        # Platform Policy Risk
        platform_reused, pr_reused_terms, _ = signal_score(_PLATFORM_RISK_REUSED_TERMS)
        platform_misleading, pr_misleading_terms, _ = signal_score(_PLATFORM_RISK_MISLEADING_TERMS)
        platform_sensitive, pr_sensitive_terms, _ = signal_score(_PLATFORM_RISK_SENSITIVE_TERMS)
        platform_spam, pr_spam_terms, _ = signal_score(_PLATFORM_RISK_SPAM_TERMS)
        platform_score = None
        platform_level = RiskLevel.UNKNOWN
        platform_obs = pr_reused_terms + pr_misleading_terms + pr_sensitive_terms + pr_spam_terms
        platform_inf: List[str] = []
        platform_warns = []
        if any(v is not None for v in (platform_reused, platform_misleading, platform_sensitive, platform_spam)):
            platform_components = [
                (platform_reused, self.config.platform_risk_weight_reused),
                (platform_misleading, self.config.platform_risk_weight_misleading),
                (platform_sensitive, self.config.platform_risk_weight_sensitive),
                (platform_spam, self.config.platform_risk_weight_spam),
            ]
            known_platform = [(v, w) for v, w in platform_components if v is not None]
            if known_platform:
                platform_score = _bounded(
                    sum(v * w for v, w in known_platform) / sum(w for _, w in known_platform)
                )
                if platform_score >= self.config.high_risk_min:
                    platform_level = RiskLevel.HIGH
                elif platform_score >= self.config.medium_risk_min:
                    platform_level = RiskLevel.MEDIUM
                else:
                    platform_level = RiskLevel.LOW
                if not platform_obs:
                    platform_warns.append("Platform risk detected but specific terms not identified.")
        else:
            platform_warns.append("Insufficient textual evidence for platform policy risk classification.")

        # Accuracy Risk
        acc_technical, acc_tech_terms, _ = signal_score(_ACCURACY_RISK_TECHNICAL_TERMS)
        acc_stats, acc_stats_terms, _ = signal_score(_ACCURACY_RISK_STATS_TERMS)
        acc_predictions, acc_pred_terms, _ = signal_score(_ACCURACY_RISK_PREDICTION_TERMS)
        acc_rapid, acc_rapid_terms, _ = signal_score(_ACCURACY_RISK_RAPID_CHANGE_TERMS)
        accuracy_score = None
        accuracy_level = RiskLevel.UNKNOWN
        accuracy_obs = acc_tech_terms + acc_stats_terms + acc_pred_terms + acc_rapid_terms
        accuracy_inf: List[str] = []
        accuracy_warns = []
        if any(v is not None for v in (acc_technical, acc_stats, acc_predictions, acc_rapid)):
            acc_components = [
                (acc_technical, self.config.accuracy_risk_weight_technical),
                (acc_stats, self.config.accuracy_risk_weight_statistics),
                (acc_predictions, self.config.accuracy_risk_weight_predictions),
                (acc_rapid, self.config.accuracy_risk_weight_rapid_change),
            ]
            known_acc = [(v, w) for v, w in acc_components if v is not None]
            if known_acc:
                accuracy_score = _bounded(
                    sum(v * w for v, w in known_acc) / sum(w for _, w in known_acc)
                )
                if accuracy_score >= self.config.high_risk_min:
                    accuracy_level = RiskLevel.HIGH
                elif accuracy_score >= self.config.medium_risk_min:
                    accuracy_level = RiskLevel.MEDIUM
                else:
                    accuracy_level = RiskLevel.LOW
                if not accuracy_obs:
                    accuracy_warns.append("Accuracy risk detected but specific terms not identified.")
        else:
            accuracy_warns.append("Insufficient textual evidence for accuracy risk classification.")

        # Update Burden
        upd_date, upd_date_terms, _ = signal_score(_UPDATE_BURDEN_DATE_TERMS)
        upd_news, upd_news_terms, _ = signal_score(_UPDATE_BURDEN_NEWS_TERMS)
        upd_product, upd_product_terms, _ = signal_score(_UPDATE_BURDEN_PRODUCT_TERMS)
        upd_software, upd_software_terms, _ = signal_score(_UPDATE_BURDEN_SOFTWARE_TERMS)
        upd_predictions, upd_pred_terms, _ = signal_score(_UPDATE_BURDEN_PREDICTION_TERMS)
        update_score = None
        update_level = RiskLevel.UNKNOWN
        update_obs = upd_date_terms + upd_news_terms + upd_product_terms + upd_software_terms + upd_pred_terms
        update_inf: List[str] = []
        update_warns = []
        if any(v is not None for v in (upd_date, upd_news, upd_product, upd_software, upd_predictions)):
            upd_components = [
                (upd_date, self.config.update_burden_weight_date),
                (upd_news, self.config.update_burden_weight_news),
                (upd_product, self.config.update_burden_weight_product),
                (upd_software, self.config.update_burden_weight_software),
                (upd_predictions, self.config.update_burden_weight_predictions),
            ]
            known_upd = [(v, w) for v, w in upd_components if v is not None]
            if known_upd:
                update_score = _bounded(
                    sum(v * w for v, w in known_upd) / sum(w for _, w in known_upd)
                )
                if update_score >= self.config.high_risk_min:
                    update_level = RiskLevel.HIGH
                elif update_score >= self.config.medium_risk_min:
                    update_level = RiskLevel.MEDIUM
                else:
                    update_level = RiskLevel.LOW
                if not update_obs:
                    update_warns.append("Update burden detected but specific terms not identified.")
        else:
            update_warns.append("Insufficient textual evidence for update burden classification.")

        # Source Dependency
        src_third, src_third_terms, _ = signal_score(_SOURCE_DEPENDENCY_THIRD_PARTY_TERMS)
        src_news, src_news_terms, _ = signal_score(_SOURCE_DEPENDENCY_NEWS_TERMS)
        src_interview, src_interview_terms, _ = signal_score(_SOURCE_DEPENDENCY_INTERVIEW_TERMS)
        src_vendor, src_vendor_terms, _ = signal_score(_SOURCE_DEPENDENCY_VENDOR_TERMS)
        src_external, src_external_terms, _ = signal_score(_SOURCE_DEPENDENCY_EXTERNAL_TERMS)
        src_original, src_original_terms, _ = signal_score(_SOURCE_DEPENDENCY_ORIGINAL_TERMS)
        src_screen, src_screen_terms, _ = signal_score(_SOURCE_DEPENDENCY_SCREEN_TERMS)
        source_score = None
        source_level = RiskLevel.UNKNOWN
        source_obs = src_third_terms + src_news_terms + src_interview_terms + src_vendor_terms + src_external_terms + src_screen_terms
        source_inf = src_original_terms
        source_warns = []
        if any(v is not None for v in (src_third, src_news, src_interview, src_vendor, src_external, src_original, src_screen)):
            src_components = [
                (src_third, self.config.source_dependency_weight_third_party),
                (src_news, self.config.source_dependency_weight_news),
                (src_interview, self.config.source_dependency_weight_interviews),
                (src_vendor, self.config.source_dependency_weight_vendor),
                (src_external, self.config.source_dependency_weight_external),
            ]
            # Original content and screen recording are negative indicators (reduce dependency)
            known_src = [(v, w) for v, w in src_components if v is not None]
            if known_src:
                source_score = _bounded(
                    sum(v * w for v, w in known_src) / sum(w for _, w in known_src)
                )
                # Reduce score if original content or screen recording detected
                if src_original is not None:
                    source_score = _bounded(source_score * (1.0 - 0.3 * min(1.0, src_original / 100.0)))
                if src_screen is not None:
                    source_score = _bounded(source_score * (1.0 - 0.2 * min(1.0, src_screen / 100.0)))
                if source_score >= self.config.high_risk_min:
                    source_level = RiskLevel.HIGH
                elif source_score >= self.config.medium_risk_min:
                    source_level = RiskLevel.MEDIUM
                else:
                    source_level = RiskLevel.LOW
                if not source_obs and not source_inf:
                    source_warns.append("Source dependency detected but specific terms not identified.")
        else:
            source_warns.append("Insufficient textual evidence for source dependency classification.")

        # Repeatability
        rep_structure, rep_struct_terms, _ = signal_score(_REPEATABILITY_POSITIVE_TERMS)
        rep_negative, rep_neg_terms, _ = signal_score(_REPEATABILITY_NEGATIVE_TERMS)
        rep_narration, _, _ = signal_score(_FACELESS_POSITIVE_TERMS)  # narration/screencast indicates repeatability
        repeatability_score = None
        repeat_level = RepeatabilityBand.UNKNOWN
        repeat_confidence = 0.0
        repeat_obs = rep_struct_terms
        repeat_inf = rep_neg_terms
        repeat_warns = []
        if rep_structure is not None or rep_negative is not None or rep_narration is not None:
            pos = rep_structure or 0.0
            pos += (rep_narration or 0.0) * 0.5  # narration contributes to repeatability
            neg = rep_negative or 0.0
            repeatability_score = _bounded(max(0.0, pos - neg))
            repeat_confidence = _bounded(repeatability_score)
            if repeatability_score >= 60:
                repeat_level = RepeatabilityBand.HIGH
            elif repeatability_score >= 30:
                repeat_level = RepeatabilityBand.MEDIUM
            else:
                repeat_level = RepeatabilityBand.LOW
            if not rep_struct_terms and not rep_neg_terms:
                repeat_warns.append("No clear repeatability structure signals found.")
        else:
            repeat_warns.append("Insufficient textual evidence for repeatability classification.")

        # Overall Risk - expanded with new components
        risk_components = [
            (copyright_risk, self.config.risk_weight_copyright),
            (reused_risk, self.config.risk_weight_reused_content),
            (sensitive_risk, self.config.risk_weight_regulatory_sensitive),
            (platform_score, self.config.overall_risk_weight_platform),
            (accuracy_score, self.config.overall_risk_weight_accuracy),
            (update_score, self.config.overall_risk_weight_update),
            (source_score, self.config.overall_risk_weight_source),
            (expertise_score, self.config.overall_risk_weight_expertise) if expertise_score is not None else (None, 0),
        ]
        known_risks = [(value, weight) for value, weight in risk_components if value is not None and weight > 0]
        if known_risks:
            overall_risk = _bounded(
                sum(value * weight for value, weight in known_risks)
                / sum(weight for _, weight in known_risks)
            )
            if overall_risk >= self.config.high_risk_min:
                risk_level = RiskLevel.HIGH
            elif overall_risk >= self.config.medium_risk_min:
                risk_level = RiskLevel.MEDIUM
            else:
                risk_level = RiskLevel.LOW
            inferred_fields.extend([
                "copyright_risk_score", "reused_content_risk_score",
                "regulatory_sensitive_risk_score", "platform_policy_risk_score",
                "accuracy_risk_score", "update_burden_score", "source_dependency_score",
                "overall_risk_score",
            ])
        else:
            overall_risk = None
            risk_level = RiskLevel.UNKNOWN

        # Production Attractiveness
        attractiveness_components = [
            (100.0 - production_cost, self.config.attractiveness_weight_cost) if production_cost is not None else (None, 0),
            (faceless_score, self.config.attractiveness_weight_faceless) if faceless_score is not None else (None, 0),
            (ai_score, self.config.attractiveness_weight_ai) if ai_score is not None else (None, 0),
            (repeatability_score, self.config.attractiveness_weight_repeatability) if repeatability_score is not None else (None, 0),
            (100.0 - overall_risk, self.config.attractiveness_weight_risk) if overall_risk is not None else (None, 0),
        ]
        # feasibility from production complexity
        feasibility_score = None
        if complexity == ProductionComplexity.LOW:
            feasibility_score = 80.0
        elif complexity == ProductionComplexity.MEDIUM:
            feasibility_score = 50.0
        elif complexity == ProductionComplexity.HIGH:
            feasibility_score = 20.0
        if feasibility_score is not None:
            attractiveness_components.insert(0, (feasibility_score, self.config.attractiveness_weight_feasibility))

        known_attr = [(v, w) for v, w in attractiveness_components if v is not None and w > 0]
        attractiveness_score = None
        attractiveness_available = False
        attractiveness_coverage = 0.0
        attractiveness_confidence = 0.0
        attractiveness_warns = []
        if known_attr:
            attractiveness_score = _bounded(
                sum(v * w for v, w in known_attr) / sum(w for _, w in known_attr)
            )
            attractiveness_coverage = _bounded(
                sum(w for _, w in known_attr) * 100.0 /
                (self.config.attractiveness_weight_feasibility +
                 self.config.attractiveness_weight_cost +
                 self.config.attractiveness_weight_faceless +
                 self.config.attractiveness_weight_ai +
                 self.config.attractiveness_weight_repeatability +
                 self.config.attractiveness_weight_risk)
            )
            attractiveness_available = attractiveness_coverage >= self.config.attractiveness_min_coverage
            attractiveness_confidence = _bounded(attractiveness_coverage)
            if not attractiveness_available:
                attractiveness_warns.append(f"Attractiveness coverage {attractiveness_coverage:.1f}% below minimum {self.config.attractiveness_min_coverage}%.")
        else:
            attractiveness_warns.append("Insufficient component coverage for attractiveness scoring.")

        # Risk coverage for confidence
        risk_components_known = sum(
            1 for value in (copyright_risk, reused_risk, sensitive_risk, platform_score, accuracy_score, update_score, source_score) if value is not None
        )
        risk_component_coverage = risk_components_known / 7.0 if members else 0.0
        production_components_known = sum(
            1 for value in (research, footage, editing) if value is not None
        )
        production_component_coverage = production_components_known / 3.0 if members else 0.0
        completeness = mean([
            len(known_texts) / len(members) if members else 0.0,
            len(known_durations) / len(members) if members else 0.0,
        ])
        sample_factor = min(1.0, len(members) / self.config.minimum_cluster_sample)
        evidence_coverage = (completeness + risk_component_coverage + production_component_coverage) / 3.0
        confidence = _bounded(100.0 * evidence_coverage * (0.5 + 0.5 * sample_factor))
        if len(members) < self.config.minimum_cluster_sample:
            warnings.append("Small cluster sample reduces confidence.")
        if len(members) != len(video_ids):
            warnings.append("Some cluster video IDs were absent from the supplied dataset.")

        return ClusterProductionRisk(
            cluster_id=int(cluster.get("cluster_id", 0)),
            niche=str(cluster.get("niche") or ""),
            subniche=str(cluster.get("subniche") or ""),
            microniche=str(cluster.get("microniche") or ""),
            video_count=len(members),
            production_cost_score=production_cost,
            estimated_hours_low=hours_low,
            estimated_hours_high=hours_high,
            research_complexity_score=research,
            footage_complexity_score=footage,
            editing_complexity_score=editing,
            production_complexity=complexity,
            faceless_feasibility=faceless_level,
            faceless_confidence=faceless_confidence,
            faceless_observed_evidence=faceless_obs,
            faceless_inferred_evidence=faceless_inf,
            faceless_warnings=faceless_warns,
            ai_assistance_potential=ai_level,
            ai_assistance_confidence=ai_confidence,
            ai_assistance_observed_evidence=ai_obs,
            ai_assistance_inferred_evidence=ai_inf,
            ai_assistance_warnings=ai_warns,
            expertise_requirement=exp_level,
            expertise_confidence=expertise_confidence,
            expertise_observed_evidence=exp_obs,
            expertise_inferred_evidence=exp_inf,
            expertise_warnings=exp_warns,
            copyright_risk_score=copyright_risk,
            reused_content_risk_score=reused_risk,
            regulatory_sensitive_risk_score=sensitive_risk,
            platform_policy_risk_score=platform_score,
            accuracy_risk_score=accuracy_score,
            update_burden_score=update_score,
            source_dependency_score=source_score,
            copyright_risk_level=RiskLevel.LOW if copyright_risk is not None and copyright_risk < self.config.medium_risk_min else
                (RiskLevel.MEDIUM if copyright_risk is not None and copyright_risk < self.config.high_risk_min else
                 (RiskLevel.HIGH if copyright_risk is not None else RiskLevel.UNKNOWN)),
            platform_policy_risk_level=platform_level,
            accuracy_risk_level=accuracy_level,
            update_burden_level=update_level,
            source_dependency_level=source_level,
            overall_risk_score=overall_risk,
            risk_level=risk_level,
            repeatability_score=repeatability_score,
            repeatability_band=repeat_level,
            repeatability_confidence=repeat_confidence,
            production_attractiveness_score=attractiveness_score if attractiveness_available else None,
            production_attractiveness_available=attractiveness_available,
            production_attractiveness_coverage=attractiveness_coverage,
            production_attractiveness_confidence=attractiveness_confidence,
            production_attractiveness_warnings=attractiveness_warns,
            confidence=confidence,
            observed_fields=observed_fields,
            inferred_fields=inferred_fields,
            assumptions=assumptions,
            evidence={
                "known_text_count": len(known_texts),
                "known_duration_count": len(known_durations),
                "median_duration_minutes": round(median_minutes, 2) if median_minutes is not None else None,
                "research": {"matched_videos": research_videos, "terms": research_terms},
                "footage": {"matched_videos": footage_videos, "terms": footage_terms},
                "editing": {"matched_videos": editing_videos, "terms": editing_terms},
                "copyright": {"matched_videos": copyright_videos, "terms": copyright_terms},
                "reused_content": {"matched_videos": reused_videos, "terms": reused_terms},
                "regulatory_sensitive": {"matched_videos": sensitive_videos, "terms": sensitive_terms},
                "faceless": {"matched_videos": faceless_evidence.get("positive_matches", 0), "terms": faceless_obs},
                "ai_assistance": {"matched_videos": ai_videos, "terms": ai_obs},
                "expertise": {"matched_videos": len(exp_obs), "terms": exp_obs},
                "platform_policy": {"terms": platform_obs},
                "accuracy": {"terms": accuracy_obs},
                "update_burden": {"terms": update_obs},
                "source_dependency": {"terms": source_obs, "negative_terms": source_inf},
                "repeatability": {"positive_terms": rep_struct_terms, "negative_terms": rep_neg_terms},
            },
            warnings=warnings + faceless_warns + ai_warns + exp_warns + platform_warns + accuracy_warns + update_warns + source_warns + repeat_warns + attractiveness_warns,
        )
