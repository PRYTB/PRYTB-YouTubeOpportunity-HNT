"""
Unit tests for Dashboard Internationalization (i18n) and Outlier metric semantic consistency (Sprint 11).
"""

import pytest

from dashboard.i18n import (
    t,
    format_enum_presentation,
    translate_column_header,
    format_number,
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    TRANSLATIONS,
    ENUM_TRANSLATIONS,
    COLUMN_HEADERS,
)
from dashboard.data_service import DashboardDataService, CANONICAL_VIDEOS
from app.models.validation import ValidationStatus
from app.models.profitability import ProfitabilityClassification
from app.models.production_risk import RiskLevel, ProductionComplexity


def test_default_language_and_supported_languages():
    """Verify Spanish is default and supported languages are correct."""
    assert DEFAULT_LANGUAGE == "es"
    assert "es" in SUPPORTED_LANGUAGES
    assert "en" in SUPPORTED_LANGUAGES
    assert SUPPORTED_LANGUAGES["es"] == "Español"
    assert SUPPORTED_LANGUAGES["en"] == "English"


def test_translation_key_completeness_between_es_and_en():
    """Verify all keys present in Spanish dictionary are also present in English dictionary."""
    es_keys = set(TRANSLATIONS["es"].keys())
    en_keys = set(TRANSLATIONS["en"].keys())

    missing_in_en = es_keys - en_keys
    missing_in_es = en_keys - es_keys

    assert not missing_in_en, f"Keys missing in EN translation dictionary: {missing_in_en}"
    assert not missing_in_es, f"Keys missing in ES translation dictionary: {missing_in_es}"


def test_navigation_labels_in_both_languages():
    """Verify all page navigation labels exist and return valid strings in both languages."""
    nav_keys = [
        "nav.overview",
        "nav.opportunities",
        "nav.opportunity_detail",
        "nav.outliers",
        "nav.channels",
        "nav.costs",
    ]
    for key in nav_keys:
        es_val = t(key, lang="es")
        en_val = t(key, lang="en")
        assert es_val != key and len(es_val) > 0
        assert en_val != key and len(en_val) > 0


def test_all_page_section_labels_exist():
    """Verify section titles and key labels for all 6 pages exist in both languages."""
    page_keys = [
        # Overview
        "overview.title",
        "overview.videos_analyzed",
        "overview.channels_analyzed",
        "overview.clusters_subniches",
        "overview.outliers_identified",
        "overview.validated_candidates",
        "overview.pass_pass_warnings",
        "overview.validation_status_dist",
        "overview.profitability_class_dist",
        "overview.api_resource_usage",
        "overview.score_distributions",
        # Opportunities
        "opportunities.title",
        "opportunities.filters",
        "opportunities.filter_val_status",
        "opportunities.filter_prof_class",
        # Opportunity Detail
        "detail.title",
        "detail.select_cluster",
        # Detail tabs
        "tab.executive_summary",
        "tab.profitability",
        "tab.validator_sensitivity",
        "tab.market_competition",
        "tab.production_risk",
        "tab.economic_geography",
        "tab.supporting_videos",
        # Outliers
        "outliers.title",
        "outliers.filters",
        # Channels
        "channels.title",
        "channels.caption",
        # Costs
        "costs.title",
        "costs.financial_status_header",
    ]
    for key in page_keys:
        assert t(key, lang="es") != key, f"Missing ES translation for {key}"
        assert t(key, lang="en") != key, f"Missing EN translation for {key}"


def test_canonical_analytical_enums_unchanged_internally():
    """Verify canonical enums preserve exact database/model values without modification."""
    assert ValidationStatus.PASS_WITH_WARNINGS.value == "PASS_WITH_WARNINGS"
    assert ValidationStatus.WATCH.value == "WATCH"
    assert ValidationStatus.FAIL.value == "FAIL"

    assert ProfitabilityClassification.STRONG.value == "STRONG"
    assert ProfitabilityClassification.WATCH.value == "WATCH"
    assert ProfitabilityClassification.DISCARD.value == "DISCARD"

    assert RiskLevel.HIGH.value == "HIGH"
    assert ProductionComplexity.MEDIUM.value == "MEDIUM"


def test_presentation_enum_translations():
    """Verify presentation layer correctly formats enums in ES and EN without mutating enums."""
    assert format_enum_presentation("PASS_WITH_WARNINGS", lang="es") == "APROBADO CON ADVERTENCIAS"
    assert format_enum_presentation("PASS_WITH_WARNINGS", lang="en") == "PASS WITH WARNINGS"

    assert format_enum_presentation(ValidationStatus.WATCH, lang="es") == "EN OBSERVACIÓN"
    assert format_enum_presentation(ValidationStatus.WATCH, lang="en") == "WATCH"

    assert format_enum_presentation("FAIL", lang="es") == "DESCARTADO / FALLA DE VALIDACIÓN"
    assert format_enum_presentation("FAIL", lang="en") == "FAIL"

    assert format_enum_presentation("DISCARD", lang="es") == "DESCARTADO"
    assert format_enum_presentation("DISCARD", lang="en") == "DISCARD"

    assert format_enum_presentation("UNKNOWN", lang="es") == "DESCONOCIDO"
    assert format_enum_presentation("UNKNOWN", lang="en") == "UNKNOWN"

    assert format_enum_presentation("UNDETERMINED", lang="es") == "INDETERMINADO"
    assert format_enum_presentation("UNDETERMINED", lang="en") == "UNDETERMINED"

    # None fallback
    assert format_enum_presentation(None, lang="es") == "N/A"
    assert format_enum_presentation(None, lang="en") == "N/A"


def test_missing_translation_key_fallback():
    """Verify missing key returns the key itself or falls back safely."""
    missing_key = "non_existent.key.12345"
    assert t(missing_key, lang="es") == missing_key
    assert t(missing_key, lang="en") == missing_key


def test_column_header_translation():
    """Verify table column headers translate dynamically."""
    cols = [
        ("ValidationScore", "Puntaje de validación", "Validation Score"),
        ("FragilityScore", "Puntaje de fragilidad", "Fragility Score"),
        ("FalsePositiveRisk", "Riesgo de falso positivo", "False Positive Risk"),
        ("ValidationConfidence", "Confianza de validación", "Validation Confidence"),
        ("ProfitabilityScore", "Puntaje de rentabilidad", "Profitability Score"),
        ("Expected Views", "Vistas esperadas", "Expected Views"),
    ]
    for col, expected_es, expected_en in cols:
        assert translate_column_header(col, lang="es") == expected_es
        assert translate_column_header(col, lang="en") == expected_en

    # Unknown column header returns itself
    assert translate_column_header("CustomUnknownCol", lang="es") == "CustomUnknownCol"


def test_numeric_formatting():
    """Verify numeric formatting functions without altering raw values."""
    assert format_number(1234567, lang="es") == "1.234.567"
    assert format_number(1234567, lang="en") == "1,234,567"
    assert format_number(1234.56, lang="es") == "1.234,6"
    assert format_number(1234.56, lang="en") == "1,234.6"
    assert format_number(None) == "N/A"


@pytest.mark.integration
def test_outliers_overview_metric_semantic_correctness():
    """
    Verify total_outliers metric in DashboardDataset equals distinct production video_ids
    satisfying the single-source-of-truth outlier predicate (is_actual_outlier() -> 8).
    """
    service = DashboardDataService()
    dataset = service.get_dashboard_data()

    assert dataset.total_videos == CANONICAL_VIDEOS
    assert "VID_TEST_INTEGRATION_99" not in [v.video_id for v in dataset.videos]
    assert "VID_TEST_INTEGRATION_99" not in [o.video_id for o in dataset.outliers]

    # Verify exact predicate reconciliation
    actual_outliers = [o for o in dataset.outliers if o.is_actual_outlier()]
    distinct_outlier_video_ids = set(o.video_id for o in actual_outliers)

    assert dataset.total_outliers == len(actual_outliers)
    assert dataset.total_outliers == len(distinct_outlier_video_ids)
    assert dataset.total_outliers == 8

    # Unfiltered page count with only_actual=True must equal dataset.total_outliers (8)
    actual_video_ids = set(o.video_id for o in dataset.outliers if o.is_actual_outlier())
    outlier_vms = [v for v in dataset.videos if v.video_id in actual_video_ids]
    assert len(outlier_vms) == dataset.total_outliers
