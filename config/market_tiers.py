"""
Sprint 6: Market Tier Configuration

Configurable country-to-tier mapping representing relative advertiser-market attractiveness.
NOT guaranteed RPM. Editable without changing engine code.
"""

from typing import Dict, Optional
from app.models.geography import MarketTier


# Editable internal assumptions, not sourced revenue facts or guaranteed RPM.
# Country code (ISO 3166-1 alpha-2) to comparative MarketTier mapping.
# UNKNOWN means not mapped or insufficient evidence.

COUNTRY_TO_TIER: Dict[str, MarketTier] = {
    # Tier A assumptions
    "US": MarketTier.TIER_A,
    "GB": MarketTier.TIER_A,
    "CA": MarketTier.TIER_A,
    "AU": MarketTier.TIER_A,
    "DE": MarketTier.TIER_A,
    "FR": MarketTier.TIER_A,
    "JP": MarketTier.TIER_A,
    "NL": MarketTier.TIER_A,
    "CH": MarketTier.TIER_A,
    "SE": MarketTier.TIER_A,
    "NO": MarketTier.TIER_A,
    "DK": MarketTier.TIER_A,
    "FI": MarketTier.TIER_A,
    "IE": MarketTier.TIER_A,
    "BE": MarketTier.TIER_A,
    "AT": MarketTier.TIER_A,
    "SG": MarketTier.TIER_A,
    "HK": MarketTier.TIER_A,
    "AE": MarketTier.TIER_A,
    "IL": MarketTier.TIER_A,
    "NZ": MarketTier.TIER_A,

    # Tier B assumptions
    "ES": MarketTier.TIER_B,
    "IT": MarketTier.TIER_B,
    "KR": MarketTier.TIER_B,
    "BR": MarketTier.TIER_B,
    "MX": MarketTier.TIER_B,
    "PL": MarketTier.TIER_B,
    "CZ": MarketTier.TIER_B,
    "PT": MarketTier.TIER_B,
    "GR": MarketTier.TIER_B,
    "HU": MarketTier.TIER_B,
    "RO": MarketTier.TIER_B,
    "TR": MarketTier.TIER_B,
    "SA": MarketTier.TIER_B,
    "TH": MarketTier.TIER_B,
    "MY": MarketTier.TIER_B,
    "ID": MarketTier.TIER_B,
    "PH": MarketTier.TIER_B,
    "VN": MarketTier.TIER_B,
    "TW": MarketTier.TIER_B,
    "CL": MarketTier.TIER_B,
    "AR": MarketTier.TIER_B,
    "CO": MarketTier.TIER_B,
    "PE": MarketTier.TIER_B,
    "ZA": MarketTier.TIER_B,
    "IN": MarketTier.TIER_B,

    # No country-level Tier C assumptions are currently configured.
}

# Region group to default tier mapping (used when country is unknown but region is known)
REGION_TO_TIER: Dict[str, MarketTier] = {
    "North America": MarketTier.TIER_A,
    "Western Europe": MarketTier.TIER_A,
    "Northern Europe": MarketTier.TIER_A,
    "Australia/NZ": MarketTier.TIER_A,
    "East Asia": MarketTier.TIER_A,
    "Middle East (GCC)": MarketTier.TIER_A,
    "Southern Europe": MarketTier.TIER_B,
    "Eastern Europe": MarketTier.TIER_B,
    "Latin America": MarketTier.TIER_B,
    "Southeast Asia": MarketTier.TIER_B,
    "South Asia": MarketTier.TIER_B,
    "Africa": MarketTier.TIER_C,
    "Central Asia": MarketTier.TIER_C,
    "Caribbean": MarketTier.TIER_C,
    "Pacific Islands": MarketTier.TIER_C,
}

# Language fallback assumptions used only when country and region are unknown.
# These broad mappings reduce geographic specificity and confidence.
LANGUAGE_TO_TIER: Dict[str, MarketTier] = {
    "en": MarketTier.TIER_A,  # English -> primarily US/UK/CA/AU
    "de": MarketTier.TIER_A,  # German -> DE/AT/CH
    "fr": MarketTier.TIER_A,  # French -> FR/BE/CA(CH)
    "ja": MarketTier.TIER_A,  # Japanese -> JP
    "nl": MarketTier.TIER_A,  # Dutch -> NL/BE
    "sv": MarketTier.TIER_A,  # Swedish -> SE
    "no": MarketTier.TIER_A,  # Norwegian -> NO
    "da": MarketTier.TIER_A,  # Danish -> DK
    "fi": MarketTier.TIER_A,  # Finnish -> FI
    "es": MarketTier.TIER_B,  # Spanish -> ES/MX/AR/CO/etc (mixed tiers)
    "pt": MarketTier.TIER_B,  # Portuguese -> PT/BR
    "it": MarketTier.TIER_B,  # Italian -> IT
    "ko": MarketTier.TIER_B,  # Korean -> KR
    "pl": MarketTier.TIER_B,  # Polish -> PL
    "cs": MarketTier.TIER_B,  # Czech -> CZ
    "el": MarketTier.TIER_B,  # Greek -> GR
    "hu": MarketTier.TIER_B,  # Hungarian -> HU
    "ro": MarketTier.TIER_B,  # Romanian -> RO
    "tr": MarketTier.TIER_B,  # Turkish -> TR
    "ar": MarketTier.TIER_B,  # Arabic -> SA/AE/etc
    "th": MarketTier.TIER_B,  # Thai -> TH
    "ms": MarketTier.TIER_B,  # Malay -> MY
    "id": MarketTier.TIER_B,  # Indonesian -> ID
    "tl": MarketTier.TIER_B,  # Tagalog -> PH
    "vi": MarketTier.TIER_B,  # Vietnamese -> VN
    "zh": MarketTier.TIER_B,  # Chinese -> TW/HK/CN (mixed)
    "hi": MarketTier.TIER_B,  # Hindi -> IN
}

# Default tier when nothing else is known
DEFAULT_TIER = MarketTier.UNKNOWN


def get_tier_for_country(country_code: Optional[str]) -> MarketTier:
    """Get market tier for a country code (ISO 3166-1 alpha-2)."""
    if not country_code:
        return DEFAULT_TIER
    return COUNTRY_TO_TIER.get(country_code.upper(), DEFAULT_TIER)


def get_tier_for_region(region_group: Optional[str]) -> MarketTier:
    """Get market tier for a region group."""
    if not region_group:
        return DEFAULT_TIER
    return REGION_TO_TIER.get(region_group, DEFAULT_TIER)


def get_tier_for_language(language_code: Optional[str]) -> MarketTier:
    """Get market tier for a language code."""
    if not language_code:
        return DEFAULT_TIER
    return LANGUAGE_TO_TIER.get(language_code.lower(), DEFAULT_TIER)


def get_best_available_tier(
    country_code: Optional[str] = None,
    region_group: Optional[str] = None,
    language_code: Optional[str] = None
) -> MarketTier:
    """Get the best available tier based on available signals.

    Priority: country > region > language > default
    """
    if country_code:
        tier = get_tier_for_country(country_code)
        if tier != MarketTier.UNKNOWN:
            return tier
    if region_group:
        tier = get_tier_for_region(region_group)
        if tier != MarketTier.UNKNOWN:
            return tier
    if language_code:
        tier = get_tier_for_language(language_code)
        if tier != MarketTier.UNKNOWN:
            return tier
    return DEFAULT_TIER