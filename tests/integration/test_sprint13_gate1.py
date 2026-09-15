"""
Sprint 13 Gate 1 Validation & Integrity Tests.
Validates:
1. PostgreSQL real connection
2. Authoritative Sprint 12 run exists
3. Exact terminal status SPRINT12_FINAL_ANALYTICS_APPROVED
4. Final dataset invariants (video count, channel count, dataset hash)
5. Exactly 20 canonical candidates
6. Candidate IDs are unique
7. Deterministic Top 20 ordering & ranking hash
8. Score range validation (0..100)
9. Evidence linkage validation
10. Deterministic hash repeatability across independent PostgreSQL reads
"""

import sys
import hashlib
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

import pytest
from app.database.postgres_client import PostgresClient
from app.database.repositories import YouTubeRepository
from scripts.sprint12_reproducibility_constants import (
    EXPECTED_DATASET_HASH,
    EXPECTED_PROD_VIDEOS,
    EXPECTED_PROD_CHANNELS,
)

AUTHORITATIVE_RUN_ID = "sprint12_gate7_reconciled_20260914_211554"
TERMINAL_STATUS = "SPRINT12_FINAL_ANALYTICS_APPROVED"


def compute_top20_hash(candidate_ids):
    payload = "\n".join(str(i) for i in candidate_ids)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_postgres_connection():
    client = PostgresClient()
    db_info = client.execute("SELECT current_database(), current_user;")
    assert len(db_info) == 1
    assert db_info[0]["current_database"] == "prytb"
    assert db_info[0]["current_user"] == "prytb_app"


def test_sprint12_authoritative_run_and_status():
    client = PostgresClient()
    repo = YouTubeRepository(client)

    # 1. Unique terminal run
    terminal_rows = client.execute(
        "SELECT run_id FROM public.analytical_runs WHERE status = %s",
        [TERMINAL_STATUS],
    )
    assert len(terminal_rows) == 1
    assert terminal_rows[0]["run_id"] == AUTHORITATIVE_RUN_ID

    # 2. Run record details
    run_row = repo.get_analytical_run(AUTHORITATIVE_RUN_ID)
    assert run_row is not None
    assert run_row.status == TERMINAL_STATUS
    assert run_row.dataset_hash == EXPECTED_DATASET_HASH
    assert run_row.video_count == EXPECTED_PROD_VIDEOS
    assert run_row.channel_count == EXPECTED_PROD_CHANNELS


def test_canonical_top20_count_uniqueness_and_determinism():
    client = PostgresClient()
    repo = YouTubeRepository(client)

    top20_rows_1 = repo.get_gate7_top20_definitions(AUTHORITATIVE_RUN_ID)
    top20_rows_2 = repo.get_gate7_top20_definitions(AUTHORITATIVE_RUN_ID)

    # Exactly 20
    assert len(top20_rows_1) == 20
    assert len(top20_rows_2) == 20

    # Ranks are 1..20
    ranks_1 = [int(r["rank"]) for r in top20_rows_1]
    assert ranks_1 == list(range(1, 21))

    # Unique candidate IDs
    candidate_ids_1 = [r["definition_id"] for r in top20_rows_1]
    candidate_ids_2 = [r["definition_id"] for r in top20_rows_2]
    assert len(set(candidate_ids_1)) == 20

    # Deterministic order and hash repeatability across independent reads
    hash_1 = compute_top20_hash(candidate_ids_1)
    hash_2 = compute_top20_hash(candidate_ids_2)
    assert hash_1 == hash_2
    assert top20_rows_1[0]["ranking_hash"] == hash_1


def test_top20_score_ranges_and_evidence_linkage():
    client = PostgresClient()
    repo = YouTubeRepository(client)

    run_row = repo.get_analytical_run(AUTHORITATIVE_RUN_ID)
    notes = json.loads(run_row.notes)
    mapping = notes["top20_evaluation_mapping"]
    assert len(mapping) == 20

    top20_defs = repo.get_gate7_top20_definitions(AUTHORITATIVE_RUN_ID)
    sem_defs = {d["definition_id"]: d for d in repo.get_gate7_semantic_definitions(AUTHORITATIVE_RUN_ID)}

    validations = {v["cluster_id"]: v for v in client.execute("SELECT * FROM public.cluster_validation_analyses WHERE source_cluster_run_id = %s", [AUTHORITATIVE_RUN_ID])}
    profitabilities = {p["cluster_id"]: p for p in client.execute("SELECT * FROM public.cluster_profitability_analyses WHERE source_cluster_run_id = %s", [AUTHORITATIVE_RUN_ID])}
    markets = {m["cluster_id"]: m for m in client.execute("SELECT * FROM public.market_structure_analyses WHERE source_cluster_run_id = %s", [AUTHORITATIVE_RUN_ID])}
    prods = {pr["cluster_id"]: pr for pr in client.execute("SELECT * FROM public.production_risk_analyses WHERE source_cluster_run_id = %s", [AUTHORITATIVE_RUN_ID])}

    for row in top20_defs:
        def_id = row["definition_id"]
        assert def_id in sem_defs

        m_item = next(m for m in mapping if m["definition_id"] == def_id)
        eval_id = m_item["evaluation_cluster_id"]

        prof = profitabilities[eval_id]
        mkt = markets[eval_id]
        prd = prods[eval_id]
        val = validations[eval_id]

        # Valid score ranges
        assert 0.0 <= float(prof["profitability_score"]) <= 100.0
        assert 0.0 <= float(mkt["competition_score"]) <= 100.0
        assert 0.0 <= float(mkt["evergreen_score"]) <= 100.0
        assert 0.0 <= float(prd["overall_risk_score"]) <= 100.0
        assert 0.0 <= float(val["validation_confidence"]) <= 100.0

        # Linkage verification
        assert prof["source_cluster_run_id"] == AUTHORITATIVE_RUN_ID
        assert mkt["source_cluster_run_id"] == AUTHORITATIVE_RUN_ID
        assert prd["source_cluster_run_id"] == AUTHORITATIVE_RUN_ID
        assert val["source_cluster_run_id"] == AUTHORITATIVE_RUN_ID
