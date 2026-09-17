"""Sprint 13 Gate 2A final artifact integration tests."""

import json
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SCORE_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate2a_final_score_integrity.json"
RANK20_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate2a_final_rank20.json"
TOP5_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate2a_final_top5.json"
ECONOMIC_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate2a_final_economic_rank.json"
REPORT_PATH = ROOT_DIR / "docs" / "sprint13_gate2a_final_economic_validation.md"

EXPECTED_TOP20_HASH = "df53c661f8b0bd61e300d7f364095d399331026245f4c0ce3b80fa9d3b2a090a"
EXPECTED_PERSISTED_TOP20_HASH = "85a543baf63afad339c1643b8f25cadd2b8d7d4ca316ce6e182c130fe39d98e4"
EXPECTED_ECONOMIC_HASH = "4f31ba9ecd635f448e8f413fdfabb31dc233d07c38deba96053b5d45a8954c40"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_final_artifacts_exist():
    assert all(path.exists() for path in (SCORE_PATH, RANK20_PATH, TOP5_PATH, ECONOMIC_PATH, REPORT_PATH))


def test_integrity_is_go_with_derived_hard_prerequisites():
    data = load(SCORE_PATH)
    rank20 = load(RANK20_PATH)["items"]
    top5 = load(TOP5_PATH)["items"]
    economic = load(ECONOMIC_PATH)["items"]
    loop = data["closed_loop"]

    # Validate hard prerequisites for GO status
    assert len(data["checks"]) >= 27
    assert data["checks_failed"] == 0
    assert len(rank20) == 20
    assert len(top5) == 5
    assert len(economic) == 20
    assert data["top20_hash"] == EXPECTED_TOP20_HASH
    assert data["persisted_top20_hash"] == EXPECTED_PERSISTED_TOP20_HASH
    assert data["economic_hash"] == EXPECTED_ECONOMIC_HASH

    # Fix counters must be exact 0
    assert loop["corrections"] == 0
    assert loop["mapping_fixes"] == 0
    assert loop["persistence_fixes"] == 0
    assert loop["scoring_fixes"] == 0

    # Overall Gate status must be GO
    assert data["status"] == "GO"
    assert data["database_mutations"] == 0


def test_closed_loop_two_pass_lifecycle_and_state_discard():
    data = load(SCORE_PATH)
    loop = data["closed_loop"]

    assert loop["fresh_connections"] == 2
    assert loop["state_discarded_before_second"] is True
    assert loop["first_economic_hash"] == loop["second_economic_hash"]
    assert loop["first_result_hash"] == loop["second_result_hash"]
    assert loop["first_economic_rank_hash"] == loop["second_economic_rank_hash"]


def test_readiness_conditions_and_top3_unmet():
    data = load(SCORE_PATH)
    readiness = data["readiness_conditions"]

    assert len(readiness) == 8
    assert data["top3_readiness"] == "NO"

    # Search for at_least_three_qualified condition
    qual_cond = next((c for c in readiness if c["name"] == "at_least_three_qualified"), None)
    assert qual_cond is not None
    assert qual_cond["status"] == "UNMET"
    assert "qualified candidates" in qual_cond["detail"]


def test_benchmark_snapshot_integrity():
    data = load(SCORE_PATH)
    snapshot = data["benchmark_snapshot"]

    assert snapshot["exact_rpm_match"] is True
    assert snapshot["exact_cost_match"] is True

    rpm = snapshot["rpm_benchmarks"]
    assert rpm["Finance / Investing"] == {"low": 4.0, "base": 8.0, "high": 12.0}
    assert rpm["Digital Marketing / Business"] == {"low": 4.0, "base": 6.5, "high": 9.0}
    assert rpm["Technology / Software"] == {"low": 4.0, "base": 7.0, "high": 10.0}
    assert rpm["Education / How-To"] == {"low": 2.0, "base": 4.0, "high": 6.0}

    cost = snapshot["cost_benchmarks"]
    assert cost["cost_bench_upwork_video_editor_2026"] == {"low": 6.0, "base": 15.5, "high": 25.0}
    assert cost["cost_bench_upwork_content_creator_2026"] == {"low": 25.0, "base": 40.0, "high": 55.0}


def test_rank20_order_classification_reconstruction_and_base_profit_rank():
    items = load(RANK20_PATH)["items"]
    assert len(items) == 20
    assert [item["rank"] for item in items] == list(range(1, 21))
    assert items == sorted(items, key=lambda item: (-item["profitability"], item["id"]))

    for item in items:
        score = item["profitability"]
        expected = (
            "EXCEPTIONAL" if score >= 90
            else "STRONG" if score >= 80
            else "INTERESTING" if score >= 70
            else "OBSERVE" if score >= 50
            else "DISCARD"
        )
        assert item["classification"] == expected
        assert item["score_reconstruction_valid"] is True
        assert abs(score - item["reconstructed_profitability"]) <= 0.001
        assert not item["qualified"] or item["classification"] != "DISCARD"

        # Verify base_profit_rank field presence and valid range 1..20
        assert "base_profit_rank" in item
        assert 1 <= item["base_profit_rank"] <= 20

        # Verify complete validator details and scalar/metrics consistency
        vd = item["validation_details"]
        assert vd["scalar_metrics_consistent"] is True
        assert isinstance(vd["positive_evidence"], list)
        assert isinstance(vd["contradictory_evidence"], list)
        assert isinstance(vd["missing_evidence"], list)
        assert isinstance(vd["warnings"], list)
        assert isinstance(vd["critical_failures"], list)


def test_top5_exactly_five_without_top3_selection():
    data = load(TOP5_PATH)
    rank20 = load(RANK20_PATH)["items"]
    assert data["total_selected_candidates"] == 5
    assert len(data["items"]) == 5
    assert [item["id"] for item in data["items"]] == [item["id"] for item in rank20[:5]]
    assert "top3" not in data["selection_rule"].lower()


def test_economic_rank_mapping_and_formulas():
    econ_items = load(ECONOMIC_PATH)["items"]
    rank20_items = load(RANK20_PATH)["items"]
    rank20_map = {item["id"]: item for item in rank20_items}

    assert len(econ_items) == 20
    assert econ_items == sorted(econ_items, key=lambda item: (-item["profit_base"], item["id"]))

    for item in econ_items:
        c_item = rank20_map[item["id"]]
        # Economic rank must equal candidate's base_profit_rank
        assert item["economic_rank"] == c_item["base_profit_rank"]

        econ = item["economics"]
        assert econ["revenue"]["base"] == pytest.approx(econ["views"]["base"] * econ["rpm"]["base"] / 1000, abs=0.001)
        assert econ["cost"]["base"] == pytest.approx(econ["labor_hours"]["base"] * econ["labor_rates"]["base"], abs=0.001)
        assert econ["profit"]["base"] == pytest.approx(econ["revenue"]["base"] - econ["cost"]["base"], abs=0.001)
        assert item["profit_base"] == econ["profit"]["base"]
        assert item["provenance"]["rpm_source"]["benchmark_id"]
        assert item["provenance"]["cost_source"]["benchmark_id"]


def test_profitability_and_money_are_separate_and_revenue_score_is_proxy():
    items = load(RANK20_PATH)["items"]
    assert all(item["profitability"] != item["profit_base"] for item in items)
    assert all(item["scores"]["revenue_score"] in {45.0, 60.0, 75.0} for item in items)
    semantic = load(SCORE_PATH)["semantic_findings"]
    assert "not monetary profit" in semantic["profitability"]
    assert "money was not injected" in semantic["RevenueScore"]


def test_disk_consistency_results_and_markdown_sections():
    score_data = load(SCORE_PATH)
    disk = score_data.get("disk_consistency", {})

    assert disk.get("all_consistent") is True
    assert disk.get("top5_matches_rank20_first_five") is True
    assert disk.get("econ_rank_mapping_exact") is True
    assert disk.get("qualified_count_matches") is True
    assert disk.get("report_has_all_ids") is True
    assert disk.get("report_has_qualified_section") is True

    report = REPORT_PATH.read_text(encoding="utf-8")
    assert "Ranking canónico completo" in report
    assert "Ranking económico diagnóstico completo" in report
    assert "Qualified Opportunities (Dedicated Section)" in report
    assert "Readiness (8 condiciones)" in report
    assert "Persisted Opportunity Validator Details & Evidence" in report
    assert "Clean Iteration Counters" in report
    assert "Exact Benchmarks Snapshot" in report

    for item in load(RANK20_PATH)["items"]:
        assert f"`{item['id']}`" in report
