import copy
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import sprint13_gate2b_runner as gate2b


pytestmark = pytest.mark.integration


class FakePostgresClient:
    def __init__(self, state):
        self.state = state

    def execute(self, query, params=None):
        if "cluster_profitability_analyses" in query:
            cluster_id = params[1]
            row = self.state["profitability"].get(cluster_id)
            return [copy.deepcopy(row)] if row else []
        if "production_risk_analyses" in query:
            cluster_id = params[1]
            row = self.state["production"].get(cluster_id)
            return [copy.deepcopy(row)] if row else []
        raise AssertionError(f"Unexpected direct SQL in Gate 2B test: {query}")


class FakeRepository:
    def __init__(self, state):
        self.state = state
        self.client = FakePostgresClient(state)

    def get_analytical_run(self, run_id):
        if run_id != gate2b.AUTHORITATIVE_RUN_ID or self.state["run"] is None:
            return None
        return self.state["run"]

    def get_gate7_semantic_definitions(self, run_id):
        assert run_id == gate2b.AUTHORITATIVE_RUN_ID
        return copy.deepcopy(self.state["definitions"])

    def get_rpm_benchmarks(self):
        return copy.deepcopy(self.state["rpm_benchmarks"])

    def get_production_cost_benchmarks(self):
        return copy.deepcopy(self.state["cost_benchmarks"])

    def upsert_candidate_economics(self, records):
        for record in records:
            key = (record["run_id"], record["candidate_id"])
            stored = copy.deepcopy(record)
            stored["economics_payload"] = json.dumps(
                stored["economics_payload"], sort_keys=True, separators=(",", ":")
            )
            stored["provenance_payload"] = json.dumps(
                stored["provenance_payload"], sort_keys=True, separators=(",", ":")
            )
            self.state["economics"][key] = stored
        return len(records)

    def get_candidate_economics(self, run_id):
        rows = [
            copy.deepcopy(row)
            for (stored_run_id, _), row in self.state["economics"].items()
            if stored_run_id == run_id
        ]
        return sorted(rows, key=lambda row: (row["candidate_rank"], row["candidate_id"]))


def _top20():
    with gate2b.GATE1E_JSON_PATH.open("r", encoding="utf-8") as source:
        return json.load(source)


def _state(rpm_benchmarks=None, cost_benchmarks=None):
    top20 = _top20()
    mapping = [
        {"definition_id": item["stable_id"], "evaluation_cluster_id": 1000 + index}
        for index, item in enumerate(top20["items"], start=1)
    ]
    profitability = {}
    production = {}
    for index, row in enumerate(mapping, start=1):
        cluster_id = row["evaluation_cluster_id"]
        profitability[cluster_id] = {
            "source_cluster_run_id": gate2b.AUTHORITATIVE_RUN_ID,
            "cluster_id": cluster_id,
            "metrics": {
                "expected_views_range": {
                    "low": 1000.0 * index,
                    "base": 2000.0 * index,
                    "high": 3000.0 * index,
                    "method": "authoritative_fixture",
                    "confidence": 91.0,
                    "warnings": [],
                }
            },
        }
        production[cluster_id] = {
            "source_cluster_run_id": gate2b.AUTHORITATIVE_RUN_ID,
            "cluster_id": cluster_id,
            "estimated_hours_low": 4.0,
            "estimated_hours_high": 8.0,
        }
    return {
        "run": SimpleNamespace(
            status="SPRINT12_FINAL_ANALYTICS_APPROVED",
            notes=json.dumps({"top20_evaluation_mapping": mapping}),
        ),
        "definitions": [{"definition_id": row["definition_id"]} for row in mapping],
        "profitability": profitability,
        "production": production,
        "rpm_benchmarks": list(rpm_benchmarks or []),
        "cost_benchmarks": list(cost_benchmarks or []),
        "economics": {},
    }


def _factory(state, instances):
    def create_repository():
        repository = FakeRepository(state)
        instances.append(repository)
        return repository

    return create_repository


def _rpm_fixture():
    return {
        "benchmark_id": "test-rpm-source",
        "market": "GLOBAL",
        "language": "en",
        "content_category": "general",
        "content_type": "LONG_FORM",
        "rpm_low": 1.25,
        "rpm_base": 2.5,
        "rpm_high": 4.75,
        "currency": "USD",
        "source_name": "Test-only documented RPM source",
        "source_type": "external_benchmark",
        "source_version": "test-2026.1",
        "source_date": "2026-09-01",
        "retrieved_at": datetime(2026, 9, 15, tzinfo=timezone.utc),
        "confidence": 80.0,
        "notes": "Integration fixture only",
    }


def _cost_fixture():
    return {
        "benchmark_id": "test-cost-source",
        "hourly_rate_low": 10.0,
        "hourly_rate_base": 20.0,
        "hourly_rate_high": 30.0,
        "currency": "USD",
        "evidence_type": "EXTERNAL_BENCHMARK",
        "source_name": "Test-only documented cost source",
        "source_version": "test-2026.1",
        "source_date": "2026-09-01",
        "retrieved_at": datetime(2026, 9, 15, tzinfo=timezone.utc),
        "assumptions": ["Labor only"],
        "cost_components": {"overhead": {"included": False}},
        "confidence": 85.0,
        "notes": "Integration fixture only",
    }


def _payload(row):
    value = row["economics_payload"]
    return json.loads(value) if isinstance(value, str) else value


def _independent_normalize(value):
    if isinstance(value, dict):
        return {
            str(key): _independent_normalize(item)
            for key, item in sorted(value.items())
        }
    if isinstance(value, (list, tuple)):
        return [_independent_normalize(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _independent_rows_hash(rows):
    fields = (
        "run_id",
        "candidate_id",
        "candidate_rank",
        "benchmark_id",
        "rpm_available",
        "cost_benchmark_id",
        "cost_available",
        "fallback_level",
        "economics_payload",
        "provenance_payload",
        "methodology_version",
        "source_dataset_hash",
    )
    values = []
    for row in sorted(rows, key=lambda item: (item["candidate_rank"], item["candidate_id"])):
        values.append(
            {
                field: json.loads(row[field])
                if field in ("economics_payload", "provenance_payload")
                and isinstance(row.get(field), str)
                else row.get(field)
                for field in fields
            }
        )
    encoded = json.dumps(
        _independent_normalize(values),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_no_data_persists_canonical_top20_without_zero_filling_and_stops():
    state = _state()
    instances = []

    result = gate2b.run_gate2b(_factory(state, instances))

    canonical = _top20()["items"]
    assert result["status"] == "FIX / STOP"
    assert result["record_count"] == 20
    assert result["hash_match"]
    assert result["generated_hash"] == result["reread_hash"]
    assert result["reread_hash"] == _independent_rows_hash(result["records"])
    assert len(instances) == 3
    assert len({id(instance) for instance in instances}) == 3
    assert len({id(instance.client) for instance in instances}) == 3
    assert [row["candidate_id"] for row in result["records"]] == [
        item["stable_id"] for item in canonical
    ]
    assert [row["candidate_rank"] for row in result["records"]] == list(range(1, 21))
    assert len(state["economics"]) == 20

    for row in result["records"]:
        payload = _payload(row)
        assert payload["economic_status"] == "ECONOMIC_UNAVAILABLE"
        for section in ("rpm", "revenue", "production_cost", "profit"):
            assert payload[section]["available"] is False
            assert [payload[section][bound] for bound in ("low", "base", "high")] == [
                None,
                None,
                None,
            ]
            assert payload[section]["warnings"]


def test_sourced_postgres_fixture_formulas_provenance_and_complete_status():
    state = _state([_rpm_fixture()], [_cost_fixture()])

    result = gate2b.run_gate2b(_factory(state, []))

    assert result["status"] == "GO"
    first = _payload(result["records"][0])
    assert first["economic_status"] == "ECONOMIC_COMPLETE"
    assert (first["rpm"]["low"], first["rpm"]["base"], first["rpm"]["high"]) == (
        1.25,
        2.5,
        4.75,
    )
    assert (first["revenue"]["low"], first["revenue"]["base"], first["revenue"]["high"]) == (
        1.25,
        5.0,
        14.25,
    )
    assert (
        first["production_cost"]["low"],
        first["production_cost"]["base"],
        first["production_cost"]["high"],
    ) == (40.0, 120.0, 240.0)
    assert (first["profit"]["low"], first["profit"]["base"], first["profit"]["high"]) == (
        -238.75,
        -115.0,
        -25.75,
    )
    provenance = json.loads(result["records"][0]["provenance_payload"])
    assert provenance["rpm"] == {
        "benchmark_id": "test-rpm-source",
        "confidence": 80.0,
        "date": "2026-09-01",
        "fallback_level": None,
        "source": "Test-only documented RPM source",
        "source_type": "external_benchmark",
        "version": "test-2026.1",
    }
    assert provenance["production_cost"]["benchmark_id"] == "test-cost-source"
    assert provenance["production_cost"]["source_type"] == "EXTERNAL_BENCHMARK"
    assert first["assumptions"] and first["methodology"]


def test_rerun_is_idempotent_and_database_reread_hash_is_deterministic():
    state = _state()
    first = gate2b.run_gate2b(_factory(state, []))
    first_calculated_at = first["records"][0]["calculated_at"]

    second = gate2b.run_gate2b(_factory(state, []))

    assert len(state["economics"]) == 20
    assert first["source_dataset_hash"] == second["source_dataset_hash"]
    assert first["reread_hash"] == second["reread_hash"]
    assert second["reread_hash"] == _independent_rows_hash(second["records"])
    assert second["records"][0]["calculated_at"] >= first_calculated_at


@pytest.mark.parametrize("failure", ["missing_run", "wrong_status", "mapping", "definitions"])
def test_authority_and_stable_id_mapping_mismatches_are_rejected(failure):
    state = _state()
    if failure == "missing_run":
        state["run"] = None
    elif failure == "wrong_status":
        state["run"].status = "NOT_APPROVED"
    elif failure == "mapping":
        mapping = json.loads(state["run"].notes)["top20_evaluation_mapping"][:-1]
        state["run"].notes = json.dumps({"top20_evaluation_mapping": mapping})
    else:
        state["definitions"] = state["definitions"][:-1]

    with pytest.raises(ValueError, match="Authority|mapping|definitions"):
        gate2b.run_gate2b(_factory(state, []))


def test_gate1e_source_and_hash_mismatches_are_rejected(tmp_path):
    data = _top20()
    bad_source = copy.deepcopy(data)
    bad_source["source_run_id"] = "non-authoritative"
    source_path = tmp_path / "bad-source.json"
    source_path.write_text(json.dumps(bad_source), encoding="utf-8")

    with pytest.raises(ValueError, match="not authoritative"):
        gate2b.run_gate2b(_factory(_state(), []), source_path)

    bad_hash = copy.deepcopy(data)
    bad_hash["ranking_hashes"]["gate1d"] = "0" * 64
    hash_path = tmp_path / "bad-hash.json"
    hash_path.write_text(json.dumps(bad_hash), encoding="utf-8")

    with pytest.raises(ValueError, match="Gate1E hash mismatch"):
        gate2b.run_gate2b(_factory(_state(), []), hash_path)


def test_gate2b_has_no_top3_output_or_selection(monkeypatch, capsys):
    result = {
        "status": "FIX / STOP",
        "record_count": 20,
        "source_dataset_hash": "b" * 64,
        "reread_hash": "a" * 64,
    }
    monkeypatch.setattr(gate2b, "run_gate2b", lambda: result)
    monkeypatch.setattr(gate2b, "_write_artifacts", lambda first, rerun: None)

    assert gate2b.execute() == result
    output = capsys.readouterr().out.lower()
    assert "top3" not in output
    assert "top 3" not in output
    source = Path(gate2b.__file__).read_text(encoding="utf-8").lower()
    assert "top3" not in source
    assert "top 3" not in source
