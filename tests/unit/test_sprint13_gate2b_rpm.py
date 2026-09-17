from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.analytics.benchmark_provider import (
    FALLBACK_CONTENT_TYPE,
    FALLBACK_GLOBAL_CATEGORY,
    FALLBACK_GLOBAL_MARKET,
    EmptyBenchmarkProvider,
    PostgresBenchmarkProvider,
    PostgresProductionCostBenchmarkProvider,
)
from app.database.postgres_client import PostgresClient
from app.database.repositories import YouTubeRepository
from app.models.geography import ContentType
from scripts.migrate_sprint13_gate2b_rpm_schema import MIGRATION_SQL


def benchmark_record(
    benchmark_id: str,
    market: str = "CL",
    language: str = "es",
    category: str = "education",
    content_type: str = "LONG_FORM",
    confidence: float = 80.0,
):
    return {
        "benchmark_id": benchmark_id,
        "market": market,
        "language": language,
        "content_category": category,
        "content_type": content_type,
        "rpm_low": 1.25,
        "rpm_base": 2.5,
        "rpm_high": 4.75,
        "currency": "USD",
        "source_name": "Documented source",
        "source_type": "external_benchmark",
        "source_version": "2026.1",
        "source_date": "2026-09-01",
        "retrieved_at": datetime(2026, 9, 15, tzinfo=timezone.utc),
        "confidence": confidence,
        "notes": "Source notes",
    }


def provider_with(records):
    repository = MagicMock(spec=YouTubeRepository)
    repository.get_rpm_benchmarks.return_value = records
    return PostgresBenchmarkProvider(repository)


def production_cost_record(
    benchmark_id: str,
    confidence: float = 80.0,
    source_name: str = "Published labor survey",
    source_version=None,
    source_date=None,
):
    return {
        "benchmark_id": benchmark_id,
        "hourly_rate_low": 10.0,
        "hourly_rate_base": 20.0,
        "hourly_rate_high": 30.0,
        "currency": "USD",
        "evidence_type": "EXTERNAL_BENCHMARK",
        "source_name": source_name,
        "source_version": source_version,
        "source_date": source_date,
        "retrieved_at": datetime(2026, 9, 15, tzinfo=timezone.utc),
        "assumptions": ["Labor only"],
        "cost_components": {"overhead": {"included": False}},
        "confidence": confidence,
        "notes": "",
    }


def cost_provider_with(records):
    repository = MagicMock(spec=YouTubeRepository)
    repository.get_production_cost_benchmarks.return_value = records
    return PostgresProductionCostBenchmarkProvider(repository)


def test_migration_has_canonical_tables_constraints_and_no_seed_data():
    assert "CREATE TABLE IF NOT EXISTS public.rpm_benchmarks" in MIGRATION_SQL
    assert "CREATE TABLE IF NOT EXISTS public.production_cost_benchmarks" in MIGRATION_SQL
    assert "CREATE TABLE IF NOT EXISTS public.candidate_economics" in MIGRATION_SQL
    assert "uq_rpm_benchmarks_provenance" in MIGRATION_SQL
    assert "ck_rpm_benchmarks_currency CHECK (currency = 'USD')" in MIGRATION_SQL
    assert "ck_rpm_benchmarks_source CHECK" in MIGRATION_SQL
    assert "ck_production_cost_benchmarks_currency CHECK (currency = 'USD')" in MIGRATION_SQL
    assert "evidence_type = 'EXTERNAL_BENCHMARK'" in MIGRATION_SQL
    assert "ADD COLUMN IF NOT EXISTS cost_benchmark_id TEXT" in MIGRATION_SQL
    assert "ADD COLUMN IF NOT EXISTS cost_available BOOLEAN" in MIGRATION_SQL
    assert "REFERENCES public.production_cost_benchmarks (benchmark_id)" in MIGRATION_SQL
    assert "rpm_available = (benchmark_id IS NOT NULL)" in MIGRATION_SQL
    assert "cost_available = (cost_benchmark_id IS NOT NULL)" in MIGRATION_SQL
    assert "DROP CONSTRAINT IF EXISTS ck_candidate_economics_benchmark" in MIGRATION_SQL
    assert "uq_candidate_economics_candidate" in MIGRATION_SQL
    assert "INSERT INTO" not in MIGRATION_SQL


def test_provider_prefers_exact_match_and_preserves_values():
    wildcard = benchmark_record("wild", content_type="*", confidence=100)
    exact_low = benchmark_record("exact-b", confidence=70)
    exact_high = benchmark_record("exact-a", confidence=90)
    result = provider_with([wildcard, exact_low, exact_high]).get_benchmark(
        "CL", ContentType.LONG_FORM, language="es", content_category="education"
    )
    assert result.id == "exact-a"
    assert result.fallback_level is None
    assert (result.rpm_low, result.rpm_base, result.rpm_high) == (1.25, 2.5, 4.75)
    assert result.confidence == 90


@pytest.mark.parametrize(
    ("record", "expected_level", "expected_confidence"),
    [
        (benchmark_record("type", content_type="*"), FALLBACK_CONTENT_TYPE, 72),
        (benchmark_record("market", market="*"), FALLBACK_GLOBAL_MARKET, 64),
        (
            benchmark_record("global", market="*", language="*", content_type="*"),
            FALLBACK_GLOBAL_CATEGORY,
            56,
        ),
    ],
)
def test_provider_fallback_is_explicit_reduced_and_does_not_change_rpm(
    record, expected_level, expected_confidence
):
    result = provider_with([record]).get_benchmark(
        "CL", ContentType.LONG_FORM, language="es", content_category="education"
    )
    assert result.fallback_level == expected_level
    assert result.confidence == expected_confidence
    assert (result.rpm_low, result.rpm_base, result.rpm_high) == (1.25, 2.5, 4.75)


def test_provider_returns_unavailable_when_no_documented_match():
    provider = provider_with([benchmark_record("other", category="gaming")])
    assert provider.get_benchmark(
        "CL", ContentType.LONG_FORM, language="es", content_category="education"
    ) is None
    assert EmptyBenchmarkProvider().get_benchmark(
        "CL", ContentType.LONG_FORM, language="es", content_category="education"
    ) is None


def test_legacy_two_argument_lookup_remains_supported():
    record = benchmark_record("legacy", market="US", language="en", category="general")
    assert provider_with([record]).get_benchmark("US", ContentType.LONG_FORM).id == "legacy"


def test_repository_benchmark_upsert_and_read_are_deterministic():
    client = MagicMock(spec=PostgresClient)
    cursor = MagicMock()
    client.get_cursor.return_value.__enter__.return_value = cursor
    repository = YouTubeRepository(client)
    record = benchmark_record("benchmark-1")

    assert repository.upsert_rpm_benchmarks([record]) == 1
    query, parameters = cursor.execute.call_args.args
    assert "ON CONFLICT (benchmark_id) DO UPDATE" in query
    assert parameters == record

    client.execute.return_value = [record]
    assert repository.get_rpm_benchmarks() == [record]
    read_query = client.execute.call_args.args[0]
    assert "confidence DESC, benchmark_id ASC" in read_query


def test_repository_production_cost_upsert_normalizes_and_serializes():
    client = MagicMock(spec=PostgresClient)
    cursor = MagicMock()
    client.get_cursor.return_value.__enter__.return_value = cursor
    repository = YouTubeRepository(client)
    record = production_cost_record("cost-1")
    record["assumptions"] = ["second", "first"]
    record["cost_components"] = {"z": 1, "a": {"b": 2}}

    assert repository.upsert_production_cost_benchmarks([record]) == 1
    query, parameters = cursor.execute.call_args.args
    assert "ON CONFLICT (benchmark_id) DO UPDATE" in query
    assert parameters["source_version"] == ""
    assert parameters["source_date"] == ""
    assert parameters["assumptions"] == '["second","first"]'
    assert parameters["cost_components"] == '{"a":{"b":2},"z":1}'

    client.execute.return_value = [record]
    assert repository.get_production_cost_benchmarks() == [record]
    read_query = client.execute.call_args.args[0]
    assert (
        "ORDER BY confidence DESC, source_name ASC, source_version ASC, "
        "source_date ASC, benchmark_id ASC"
    ) in read_query


def test_postgres_production_cost_provider_selects_deterministically_and_converts():
    lower_confidence = production_cost_record("low", confidence=79)
    later_source = production_cost_record("later", source_name="Z source")
    later_id = production_cost_record("b", source_name="A source")
    selected = production_cost_record("a", source_name="A source")
    selected["assumptions"] = '["Persisted assumption"]'
    selected["cost_components"] = '{"overhead":{"included":false}}'

    cost = cost_provider_with(
        [later_id, lower_confidence, later_source, selected]
    ).estimate_cost(4.0, 8.0)

    assert cost.available
    assert cost.benchmark_id == "a"
    assert (cost.low, cost.base, cost.high) == (40.0, 120.0, 240.0)
    assert cost.source_version is None
    assert cost.source_date is None
    assert cost.assumptions == ["Persisted assumption"]
    assert cost.cost_components["overhead"] == {"included": False}


def test_postgres_production_cost_provider_uses_provenance_tie_breaks():
    records = [
        production_cost_record("a", source_name="Source", source_version="2"),
        production_cost_record("z", source_name="Source", source_version="1", source_date="2026-02-01"),
        production_cost_record("b", source_name="Source", source_version="1", source_date="2026-01-01"),
    ]

    cost = cost_provider_with(records).estimate_cost(1.0, 1.0)

    assert cost.benchmark_id == "b"


def test_postgres_production_cost_provider_returns_unavailable_without_records():
    cost = cost_provider_with([]).estimate_cost(4.0, 8.0)

    assert not cost.available
    assert cost.low is None
    assert cost.warnings


def test_repository_candidate_economics_serializes_json_and_orders_readback():
    client = MagicMock(spec=PostgresClient)
    cursor = MagicMock()
    client.get_cursor.return_value.__enter__.return_value = cursor
    repository = YouTubeRepository(client)
    record = {
        "run_id": "run-1",
        "candidate_id": "candidate-1",
        "candidate_rank": 1,
        "benchmark_id": None,
        "rpm_available": False,
        "cost_benchmark_id": "cost-1",
        "cost_available": True,
        "fallback_level": None,
        "economics_payload": {"rpm_range": {"available": False}},
        "provenance_payload": {"source": "unavailable"},
        "methodology_version": "gate2b-v1",
        "source_dataset_hash": "abc",
        "calculated_at": datetime(2026, 9, 15, tzinfo=timezone.utc),
    }

    assert repository.upsert_candidate_economics([record]) == 1
    query, parameters = cursor.execute.call_args.args
    assert "ON CONFLICT (run_id, candidate_id) DO UPDATE" in query
    assert "cost_benchmark_id = EXCLUDED.cost_benchmark_id" in query
    assert "cost_available = EXCLUDED.cost_available" in query
    assert parameters["cost_benchmark_id"] == "cost-1"
    assert parameters["cost_available"] is True
    assert parameters["economics_payload"] == '{"rpm_range":{"available":false}}'
    assert parameters["provenance_payload"] == '{"source":"unavailable"}'

    repository.get_candidate_economics("run-1")
    read_query, read_parameters = client.execute.call_args.args
    assert "ORDER BY candidate_rank ASC, candidate_id ASC" in read_query
    assert read_parameters == ["run-1"]
