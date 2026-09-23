"""Integration tests for Sprint 13 Gate 2C External Benchmark Ingestion & Calibration.

Verifies:
1. Top20 complete persistence in PostgreSQL / mock state
2. No UNKNOWN sources
3. Dual DB rereads with independent PostgreSQL connections
4. Deterministic SHA-256 hash matching across dual reads
5. Source audit and integrity documentation consistency
"""

import copy
import json
from types import SimpleNamespace
import pytest

from scripts import sprint13_gate2c_runner as gate2c


pytestmark = pytest.mark.integration


class FakePostgresClient:
    def __init__(self, state):
        self.state = state

    def execute(self, query, params=None):
        if "gate7_semantic_memberships" in query:
            definition_id = params[1]
            rows = self.state["views"].get(definition_id, [])
            return copy.deepcopy(rows)
        if "production_risk_analyses" in query:
            cluster_id = params[1]
            row = self.state["production"].get(cluster_id)
            return [copy.deepcopy(row)] if row else []
        raise AssertionError(f"Unexpected direct SQL in Gate 2C test: {query}")


class FakeRepository:
    def __init__(self, state):
        self.state = state
        self.client = FakePostgresClient(state)

    def get_analytical_run(self, run_id):
        if run_id != gate2c.AUTHORITATIVE_RUN_ID or self.state["run"] is None:
            return None
        return self.state["run"]

    def get_rpm_benchmarks(self):
        return copy.deepcopy(self.state["rpm_benchmarks"])

    def get_production_cost_benchmarks(self):
        return copy.deepcopy(self.state["cost_benchmarks"])

    def upsert_rpm_benchmarks(self, records):
        by_id = {record["benchmark_id"]: record for record in self.state["rpm_benchmarks"]}
        for record in records:
            by_id[record["benchmark_id"]] = copy.deepcopy(record)
        self.state["rpm_benchmarks"] = list(by_id.values())
        return len(records)

    def upsert_production_cost_benchmarks(self, records):
        by_id = {record["benchmark_id"]: record for record in self.state["cost_benchmarks"]}
        for record in records:
            by_id[record["benchmark_id"]] = copy.deepcopy(record)
        self.state["cost_benchmarks"] = list(by_id.values())
        return len(records)

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


def _build_test_state():
    top20 = gate2c._load_and_verify_top20(gate2c.GATE1E_JSON_PATH)
    mapping = [
        {"definition_id": item["stable_id"], "evaluation_cluster_id": 1000 + index}
        for index, item in enumerate(top20["items"], start=1)
    ]
    views = {}
    production = {}
    for index, row in enumerate(mapping, start=1):
        def_id = row["definition_id"]
        cluster_id = row["evaluation_cluster_id"]
        views[def_id] = [
            {"video_views": 1000.0 * index},
            {"video_views": 2000.0 * index},
            {"video_views": 3000.0 * index},
        ]
        production[cluster_id] = {
            "source_cluster_run_id": gate2c.AUTHORITATIVE_RUN_ID,
            "cluster_id": cluster_id,
            "estimated_hours_low": 5.0,
            "estimated_hours_high": 15.0,
        }

    return {
        "run": SimpleNamespace(
            run_id=gate2c.AUTHORITATIVE_RUN_ID,
            status="SPRINT12_FINAL_ANALYTICS_APPROVED",
            notes=json.dumps({"top20_evaluation_mapping": mapping}),
        ),
        "views": views,
        "production": production,
        "rpm_benchmarks": [],
        "cost_benchmarks": [],
        "economics": {},
    }


def test_gate2c_pipeline_and_dual_read_hash_match(tmp_path, monkeypatch):
    """Verify end-to-end Gate 2C pipeline, zero UNKNOWN sources, 20 candidate completion, dual DB read hash match."""
    artifact_names = (
        "SOURCE_REGISTRY_PATH", "SOURCE_AUDIT_PATH", "RPM_ARTIFACT_PATH",
        "COST_ARTIFACT_PATH", "ECONOMICS_ARTIFACT_PATH", "REPORT_PATH",
        "INTEGRITY_DOC_PATH",
    )
    for name in artifact_names:
        monkeypatch.setattr(gate2c, name, tmp_path / getattr(gate2c, name).name)
    state = _build_test_state()
    instances = []

    def create_repository():
        repository = FakeRepository(state)
        instances.append(repository)
        return repository

    # Execute Gate 2C pipeline
    summary = gate2c.execute_gate2c(create_repository)
    assert summary["status"] == "GO"
    assert summary["total_mapped"] == 20
    assert len(state["economics"]) == 20
    assert len(instances) == 3
    assert len({id(instance) for instance in instances}) == 3
    assert len({id(instance.client) for instance in instances}) == 3

    # A clean rerun replaces records by production conflict keys rather than duplicating them.
    rerun_summary = gate2c.execute_gate2c(create_repository)
    assert rerun_summary["status"] == "GO"
    assert len(state["rpm_benchmarks"]) == len(gate2c.RAW_RPM_BENCHMARKS)
    assert len(state["cost_benchmarks"]) == len(gate2c.RAW_COST_BENCHMARKS)
    assert len(state["economics"]) == 20
    assert len(instances) == 6
    assert len({id(instance) for instance in instances}) == 6
    assert len({id(instance.client) for instance in instances}) == 6
    
    # Verify no UNKNOWN sources
    for record in state["rpm_benchmarks"]:
        assert record["source_name"] != "UNKNOWN"
        assert len(record["source_name"]) > 10
        
    for record in state["cost_benchmarks"]:
        assert record["source_name"] != "UNKNOWN"
        assert len(record["source_name"]) > 10

    # Read 1 & Read 2 hash calculation
    records_r1 = instances[1].get_candidate_economics(gate2c.GATE2C_RUN_ID)
    records_r2 = instances[2].get_candidate_economics(gate2c.GATE2C_RUN_ID)
    
    assert len(records_r1) == 20
    assert len(records_r2) == 20

    hash1 = gate2c.canonical_hash(records_r1)
    hash2 = gate2c.canonical_hash(records_r2)

    assert hash1 == hash2
    assert len(hash1) == 64
    assert all(getattr(gate2c, name).is_file() for name in artifact_names)


def test_generated_artifacts_exist_and_consistent():
    """Verify that source audit JSON and source integrity markdown artifacts are written and consistent."""
    assert gate2c.SOURCE_AUDIT_PATH.exists()
    assert gate2c.INTEGRITY_DOC_PATH.exists()

    with gate2c.SOURCE_AUDIT_PATH.open("r", encoding="utf-8") as f:
        audit_records = json.load(f)

    assert isinstance(audit_records, list)
    assert len(audit_records) == 6
    for rec in audit_records:
        assert rec["match_status"] in ("EXACT", "DOCUMENTED_TRANSFORMATION")
