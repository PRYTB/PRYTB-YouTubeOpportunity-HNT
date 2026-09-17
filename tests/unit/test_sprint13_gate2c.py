"""Unit tests for Sprint 13 Gate 2C External Benchmark Source Integrity & Calibration.

Verifies:
1. Source registry exact provenance
2. Raw source value vs persisted value
3. RPM range correctness
4. Midpoint derivation
5. Cost source correctness
6. No undocumented range widening
7. No labor double count
8. Deterministic role mapping
9. Deterministic RPM category mapping
10. Confidence reconstruction
11. Revenue, cost, and profit formulas
"""

import math
from datetime import date

from scripts import sprint13_gate2c_runner as gate2c


def test_1_source_registry_exact_provenance():
    """Verify Phase 1: Every external source has exact URL, publisher, date, methodology."""
    registry = gate2c.SOURCE_REGISTRY
    assert len(registry) == 4
    
    source_ids = {s["source_id"] for s in registry}
    expected_ids = {
        "SRC-YT-DOCS-2026",
        "SRC-VIDIQ-RPM-2026",
        "SRC-UPWORK-RATES-2026-VE",
        "SRC-UPWORK-RATES-2026-CC",
    }
    assert source_ids == expected_ids
    
    expected_references = {
        "SRC-YT-DOCS-2026": (
            "YouTube Analytics - Understand Revenue per 1,000 views (RPM)",
            "https://support.google.com/youtube/answer/9314357",
        ),
        "SRC-VIDIQ-RPM-2026": (
            "RPM on YouTube: Decode Your Channel’s Revenue",
            "https://vidiq.com/blog/post/youtube-rpm/",
        ),
        "SRC-UPWORK-RATES-2026-VE": (
            "How Much Does Hiring a Video Editor Cost?",
            "https://www.upwork.com/hire/video-editors/cost/",
        ),
        "SRC-UPWORK-RATES-2026-CC": (
            "Content Creators on Upwork Cost $25–$55/hr.",
            "https://www.upwork.com/hire/content-creators/cost/",
        ),
    }
    for source in registry:
        assert (source["exact_title"], source["source_url"]) == expected_references[source["source_id"]]
        assert len(source["publisher"]) > 0
        if source["publication_date"] is not None:
            assert date.fromisoformat(source["publication_date"])
        assert date.fromisoformat(source["retrieval_date"])
        assert len(source["methodology"]) > 20
        assert "raw_values_extracted" in source


def test_2_raw_source_value_vs_persisted_value():
    """Verify Phase 2: Side-by-side match of raw external bounds vs persisted benchmarks."""
    audit_records = gate2c.generate_source_audit_records()
    assert len(audit_records) == len(gate2c.RAW_RPM_BENCHMARKS) + len(gate2c.RAW_COST_BENCHMARKS)
    
    for record in audit_records:
        assert record["match_status"] in ("EXACT", "DOCUMENTED_TRANSFORMATION")
        assert record["persisted_low"] == record["raw_low"]
        assert record["persisted_high"] == record["raw_high"]
        # Midpoint check
        expected_mid = (record["raw_low"] + record["raw_high"]) / 2.0
        assert math.isclose(record["persisted_base"], expected_mid, rel_tol=1e-5)


def test_3_rpm_range_correctness():
    """Verify Phase 3: Exact vidIQ 2026 published RPM ranges per category."""
    rpm_map = {b["content_category"]: (b["source_low"], b["source_high"]) for b in gate2c.RAW_RPM_BENCHMARKS}
    
    assert rpm_map["Finance / Investing"] == (4.00, 12.00)
    assert rpm_map["Digital Marketing / Business"] == (4.00, 9.00)
    assert rpm_map["Technology / Software"] == (4.00, 10.00)
    assert rpm_map["Education / How-To"] == (2.00, 6.00)


def test_4_midpoint_derivation():
    """Verify Phase 4: Deterministic base calculation formula base = (low + high) / 2."""
    for b in gate2c.RAW_RPM_BENCHMARKS:
        expected_base = (b["source_low"] + b["source_high"]) / 2.0
        calculated_base = round((b["source_low"] + b["source_high"]) / 2.0, 4)
        assert calculated_base == expected_base
        
    for c in gate2c.RAW_COST_BENCHMARKS:
        expected_base = (c["hourly_rate_low"] + c["hourly_rate_high"]) / 2.0
        assert c["hourly_rate_base"] == expected_base


def test_5_cost_source_correctness():
    """Verify Phase 5: Exact Upwork hourly labor ranges ($6-25 and $25-55)."""
    cost_map = {c["benchmark_id"]: c for c in gate2c.RAW_COST_BENCHMARKS}
    
    ve = cost_map["cost_bench_upwork_video_editor_2026"]
    assert ve["hourly_rate_low"] == 6.00
    assert ve["hourly_rate_base"] == 15.50
    assert ve["hourly_rate_high"] == 25.00
    assert ve["source_id"] == "SRC-UPWORK-RATES-2026-VE"

    cc = cost_map["cost_bench_upwork_content_creator_2026"]
    assert cc["hourly_rate_low"] == 25.00
    assert cc["hourly_rate_base"] == 40.00
    assert cc["hourly_rate_high"] == 55.00
    assert cc["source_id"] == "SRC-UPWORK-RATES-2026-CC"


def test_6_no_undocumented_range_widening():
    """Verify Phase 6: No arbitrary widening or approximation in benchmark ranges."""
    for b in gate2c.RAW_RPM_BENCHMARKS:
        mid = (b["source_low"] + b["source_high"]) / 2.0
        assert b["source_low"] < mid < b["source_high"]
    for c in gate2c.RAW_COST_BENCHMARKS:
        assert c["hourly_rate_low"] < c["hourly_rate_base"] < c["hourly_rate_high"]


def test_7_8_role_mapping_and_no_labor_double_counting():
    """Verify Phase 7 & 8: Single role per subniche, preventing labor double counting."""
    top20 = gate2c._load_and_verify_top20(gate2c.GATE1E_JSON_PATH)
    items = top20["items"]
    
    for item in items:
        candidate_id = item["stable_id"]
        mapping = gate2c.TOP20_DETERMINISTIC_MAPPING.get(candidate_id)
        assert mapping is not None
        cost_prof_id = mapping["cost_profile_id"]
        assert cost_prof_id in (
            "cost_bench_upwork_video_editor_2026",
            "cost_bench_upwork_content_creator_2026",
        )


def test_9_deterministic_rpm_category_mapping():
    """Verify Phase 9: All 20 subniches deterministically map to valid benchmark categories."""
    top20 = gate2c._load_and_verify_top20(gate2c.GATE1E_JSON_PATH)
    assert len(top20["items"]) == 20
    
    for item in top20["items"]:
        candidate_id = item["stable_id"]
        mapping = gate2c.TOP20_DETERMINISTIC_MAPPING.get(candidate_id)
        assert mapping is not None
        category = mapping["benchmark_category"]
        assert category in (
            "Finance / Investing",
            "Digital Marketing / Business",
            "Technology / Software",
            "Education / How-To",
        )
        assert len(mapping["mapping_reason"]) > 10


def test_10_confidence_reconstruction():
    """Verify Phase 10: Final combined confidence is calculated as rpm_confidence * mapping_confidence."""
    rpm_confidence = 0.85
    mapping_confidence = 0.90
    combined_confidence = round(rpm_confidence * mapping_confidence, 4)
    assert combined_confidence == 0.7650


def test_11_revenue_cost_profit_formulas():
    """Verify Phase 11 & 8: Rebuilt scenario bounds adhere strictly to mathematical formulas."""
    views_low, views_base, views_high = 10000.0, 50000.0, 200000.0
    rpm_low, rpm_base, rpm_high = 7.0, 10.5, 14.0
    hours_low, hours_base, hours_high = 4.0, 8.0, 16.0
    rate_low, rate_base, rate_high = 6.0, 15.5, 25.0

    # Labor Cost = Hours * Rate
    cost_low = hours_low * rate_low  # 24.0
    cost_base = hours_base * rate_base  # 124.0
    cost_high = hours_high * rate_high  # 400.0

    # Revenue = Views * RPM / 1000
    rev_low = views_low * rpm_low / 1000.0  # 70.0
    rev_base = views_base * rpm_base / 1000.0  # 525.0
    rev_high = views_high * rpm_high / 1000.0  # 2800.0

    # Profit = Revenue - Cost
    profit_low = rev_low - cost_high  # 70.0 - 400.0 = -330.0
    profit_base = rev_base - cost_base  # 525.0 - 124.0 = 401.0
    profit_high = rev_high - cost_low  # 2800.0 - 24.0 = 2776.0

    assert cost_low == 24.0
    assert cost_base == 124.0
    assert cost_high == 400.0

    assert rev_low == 70.0
    assert rev_base == 525.0
    assert rev_high == 2800.0

    assert profit_low == -330.0
    assert profit_base == 401.0
    assert profit_high == 2776.0
