import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.postgres_client import PostgresClient
from app.database.repositories import YouTubeRepository
from scripts.sprint5_reproducibility_runner import (
    APPROVED_ALGORITHM,
    APPROVED_ASSIGNMENTS_HASH,
    APPROVED_DATASET_HASH,
    APPROVED_K,
    APPROVED_RANDOM_STATE,
    APPROVED_REPRESENTATION,
    APPROVED_SEMANTIC_TEXT_VERSION,
    APPROVED_SILHOUETTE,
    APPROVED_TFIDF_PARAMETERS,
    audit_production_videos,
    canonical_dataset_rows,
    compute_assignments_hash,
    compute_dataset_hash,
)

TERMINAL_STATUS = "SPRINT12_FINAL_ANALYTICS_APPROVED"
EXPECTED_RAW = 10613
EXPECTED_FIXTURES = 28
EXPECTED_PROD = 10585
EXPECTED_CHANNELS = 6487
EXPECTED_TOP20 = 20
SILHOUETTE_TOLERANCE = 1e-12


def _json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}


def _ranking_hash(ids: List[str]) -> str:
    return hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()


def _assignment_hash(assignments: List[Tuple[str, int]]) -> str:
    return compute_assignments_hash(
        [str(video_id) for video_id, _ in assignments],
        [int(cluster_id) for _, cluster_id in assignments],
    )


def verify_gate7(target_run_id: Optional[str] = None) -> None:
    client = PostgresClient()
    repo = YouTubeRepository(client)
    errors: List[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    terminal_rows = client.execute(
        "SELECT run_id FROM public.analytical_runs WHERE status = %s ORDER BY updated_at DESC",
        [TERMINAL_STATUS],
    )
    check(
        len(terminal_rows) == 1,
        f"Expected exactly one terminal run, found {len(terminal_rows)}",
    )

    if target_run_id is None:
        approved = repo.get_approved_gate7_run()
        if approved is None:
            print(f"[FAIL] No {TERMINAL_STATUS} run found in analytical_runs.")
            sys.exit(1)
        target_run_id = approved.run_id

    print(f"Verifying Gate 7 DB state for run_id: {target_run_id}")
    run_row = repo.get_analytical_run(target_run_id)
    if run_row is None:
        print(f"[FAIL] Analytical run {target_run_id} is missing.")
        sys.exit(1)

    check(run_row.status == TERMINAL_STATUS, f"Invalid terminal status: {run_row.status}")
    check(
        len(terminal_rows) == 1 and terminal_rows[0]["run_id"] == target_run_id,
        "The requested run is not the unique terminal run",
    )
    notes = _json_object(run_row.notes)

    all_videos = repo.get_all_videos()
    production_videos, dataset_audit = audit_production_videos(all_videos)
    prod_rows = canonical_dataset_rows(production_videos)
    dataset_hash_1 = compute_dataset_hash(prod_rows)
    dataset_hash_2 = compute_dataset_hash(prod_rows)
    production_ids = [row["video_id"] for row in prod_rows]
    production_id_set = set(production_ids)
    production_channels = {row["channel_id"] for row in prod_rows if row["channel_id"]}

    dataset_counts = {
        "raw": len(all_videos),
        "fixtures": dataset_audit["test_records_excluded"],
        "production": len(prod_rows),
        "channels": len(production_channels),
    }
    print(f"Dataset counts: {dataset_counts}")
    check(dataset_counts["raw"] == EXPECTED_RAW, f"Raw count mismatch: {dataset_counts['raw']}")
    check(dataset_counts["fixtures"] == EXPECTED_FIXTURES, f"Fixture count mismatch: {dataset_counts['fixtures']}")
    check(dataset_counts["production"] == EXPECTED_PROD, f"Production count mismatch: {dataset_counts['production']}")
    check(dataset_counts["channels"] == EXPECTED_CHANNELS, f"Channel count mismatch: {dataset_counts['channels']}")
    check(len(production_ids) == len(production_id_set), "Canonical production dataset has duplicate video IDs")
    check(dataset_hash_1 == dataset_hash_2, "Dataset hash is not deterministic")
    check(dataset_hash_1 == APPROVED_DATASET_HASH, f"Dataset hash mismatch: {dataset_hash_1}")
    check(run_row.dataset_hash == APPROVED_DATASET_HASH, f"Root dataset hash mismatch: {run_row.dataset_hash}")
    check(run_row.video_count == EXPECTED_PROD, f"Root video count mismatch: {run_row.video_count}")
    check(run_row.channel_count == EXPECTED_CHANNELS, f"Root channel count mismatch: {run_row.channel_count}")

    assignment_sql = (
        "SELECT video_id, cluster_id FROM public.cluster_videos "
        "WHERE run_id = %s ORDER BY video_id"
    )
    assignment_reads = [
        client.execute(assignment_sql, [target_run_id]),
        client.execute(assignment_sql, [target_run_id]),
    ]
    assignment_hashes: List[str] = []
    for read_number, rows in enumerate(assignment_reads, start=1):
        ids = [str(row["video_id"]) for row in rows]
        check(len(rows) == EXPECTED_PROD, f"Assignment read {read_number} has {len(rows)} rows")
        check(len(ids) == len(set(ids)) == EXPECTED_PROD, f"Assignment read {read_number} does not contain 10585 unique videos")
        check(set(ids) == production_id_set, f"Assignment read {read_number} does not exactly cover the production dataset")
        check(len({int(row["cluster_id"]) for row in rows}) == APPROVED_K, f"Assignment read {read_number} does not contain K=35 clusters")
        assignment_hashes.append(_assignment_hash([(row["video_id"], row["cluster_id"]) for row in rows]))
    check(len(set(assignment_hashes)) == 1, "Assignment hash differs across independent PostgreSQL reads")
    persisted_assignment_hash = assignment_hashes[0] if assignment_hashes else ""
    check(persisted_assignment_hash == APPROVED_ASSIGNMENTS_HASH, f"Canonical assignment hash mismatch: {persisted_assignment_hash}")

    methodology_checks = {
        "dataset_hash": APPROVED_DATASET_HASH,
        "assignments_hash": APPROVED_ASSIGNMENTS_HASH,
        "selected_k": APPROVED_K,
        "algorithm": APPROVED_ALGORITHM,
        "random_state": APPROVED_RANDOM_STATE,
        "representation": APPROVED_REPRESENTATION,
        "semantic_text_version": APPROVED_SEMANTIC_TEXT_VERSION,
        "tfidf_parameters": APPROVED_TFIDF_PARAMETERS,
        "fit_method": "ClusterOptimizer._fit_single",
    }
    for key, expected in methodology_checks.items():
        check(notes.get(key) == expected, f"Methodology metadata {key} mismatch: {notes.get(key)!r}")
    try:
        silhouette = float(notes.get("silhouette"))
        check(abs(silhouette - APPROVED_SILHOUETTE) <= SILHOUETTE_TOLERANCE, f"Silhouette mismatch: {silhouette}")
    except (TypeError, ValueError):
        errors.append(f"Invalid silhouette metadata: {notes.get('silhouette')!r}")
    check(notes.get("top3_selected") is False, f"top3_selected must be False, got {notes.get('top3_selected')!r}")

    outlier_counts = client.execute(
        """
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE is_strong_outlier OR is_major_outlier OR is_extreme_outlier) AS actual,
               COUNT(*) FILTER (WHERE small_channel_outlier) AS small_channel
        FROM public.video_outlier_analyses
        WHERE run_id = %s
        """,
        [target_run_id],
    )[0]
    definition_counts = client.execute(
        """
        SELECT COUNT(*) AS definitions,
               COUNT(DISTINCT normalized_intent) AS distinct_intents
        FROM public.gate7_semantic_definitions
        WHERE run_id = %s
        """,
        [target_run_id],
    )[0]
    membership_counts = client.execute(
        """
        SELECT COUNT(*) AS memberships,
               COUNT(DISTINCT (m.definition_id, m.video_id)) AS unique_memberships,
               COUNT(*) FILTER (WHERE d.definition_id IS NULL) AS orphan_definitions,
               COUNT(*) FILTER (WHERE v.video_id IS NULL) AS orphan_videos
        FROM public.gate7_semantic_memberships m
        LEFT JOIN public.gate7_semantic_definitions d
          ON d.run_id = m.run_id AND d.definition_id = m.definition_id
        LEFT JOIN public.videos v ON v.video_id = m.video_id
        WHERE m.run_id = %s
        """,
        [target_run_id],
    )[0]
    real_counts = {
        "outlier_analysis_count": int(outlier_counts["total"]),
        "actual_outlier_count": int(outlier_counts["actual"]),
        "small_channel_outlier_count": int(outlier_counts["small_channel"]),
        "semantic_definition_count": int(definition_counts["definitions"]),
        "distinct_normalized_intent_count": int(definition_counts["distinct_intents"]),
        "semantic_membership_count": int(membership_counts["memberships"]),
    }
    print(f"Run-derived analytical counts: {real_counts}")
    check(real_counts["outlier_analysis_count"] == EXPECTED_PROD, f"Outlier analysis count mismatch: {real_counts['outlier_analysis_count']}")
    check(real_counts["semantic_definition_count"] > 0, "No semantic definitions were persisted")
    check(real_counts["semantic_definition_count"] == real_counts["distinct_normalized_intent_count"], "Definitions are not globally deduplicated by normalized_intent")
    check(int(membership_counts["memberships"]) == int(membership_counts["unique_memberships"]), "Duplicate semantic memberships found")
    check(int(membership_counts["orphan_definitions"]) == 0, "Semantic memberships reference missing definitions")
    check(int(membership_counts["orphan_videos"]) == 0, "Semantic memberships reference missing videos")
    for metadata_key, actual in real_counts.items():
        check(notes.get(metadata_key) == actual, f"Metadata {metadata_key}={notes.get(metadata_key)!r}, PostgreSQL={actual}")

    top100_rows = repo.get_gate7_top100_outliers(target_run_id)
    check(len(top100_rows) == 100, f"Top100 count mismatch: {len(top100_rows)}")
    check([int(row["outlier_rank"]) for row in top100_rows] == list(range(1, 101)), "Top100 ranks are not exactly 1..100")
    check(all(row["is_strong_outlier"] or row["is_major_outlier"] or row["is_extreme_outlier"] for row in top100_rows), "Top100 contains a non-actual outlier")
    top100_hash = _ranking_hash([str(row["video_id"]) for row in top100_rows])
    check(bool(top100_rows) and all(row["dataset_hash"] == APPROVED_DATASET_HASH for row in top100_rows), "Top100 dataset hash mismatch")
    check(bool(top100_rows) and all(row["ranking_hash"] == top100_hash for row in top100_rows), "Top100 ranking hash mismatch")
    check(notes.get("top100_ranking_hash") == top100_hash, "Root Top100 ranking hash mismatch")

    semantic_definitions = repo.get_gate7_semantic_definitions(target_run_id)
    semantic_by_id = {row["definition_id"]: row for row in semantic_definitions}
    top20_rows = repo.get_gate7_top20_definitions(target_run_id)
    top20_ids = [str(row["definition_id"]) for row in top20_rows]
    top20_hash = _ranking_hash(top20_ids)
    check(len(top20_rows) == EXPECTED_TOP20, f"Top20 count mismatch: {len(top20_rows)}")
    check([int(row["rank"]) for row in top20_rows] == list(range(1, 21)), "Top20 ranks are not exactly 1..20")
    check(len(top20_ids) == len(set(top20_ids)), "Top20 contains duplicate definitions")
    check(all(definition_id in semantic_by_id for definition_id in top20_ids), "Top20 references a missing semantic definition")
    check(bool(top20_rows) and all(row["ranking_hash"] == top20_hash for row in top20_rows), "Top20 ranking hash mismatch")
    check(notes.get("top20_definition_ids") == top20_ids, "Root Top20 definition IDs mismatch")
    check(notes.get("top20_ranking_hash") == top20_hash, "Root Top20 ranking hash mismatch")

    mappings = notes.get("top20_evaluation_mapping") or []
    check(len(mappings) == EXPECTED_TOP20, f"Top20 evaluation mapping count mismatch: {len(mappings)}")
    check([mapping.get("evaluation_cluster_id") for mapping in mappings] == list(range(1, 21)), "Evaluation cluster IDs are not exactly 1..20")
    check([mapping.get("definition_id") for mapping in mappings] == top20_ids, "Top20 evaluation mapping order does not match persisted ranking")
    for mapping in mappings:
        definition = semantic_by_id.get(mapping.get("definition_id"))
        if definition is None:
            continue
        evidence = _json_object(definition.get("evidence_payload"))
        parent_ids = evidence.get("parent_cluster_ids") or []
        check(mapping.get("parent_cluster_id") == definition["parent_cluster_id"], f"Primary parent mismatch for {definition['definition_id']}")
        check(mapping.get("parent_cluster_ids") == parent_ids, f"Merged parent traceability mismatch for {definition['definition_id']}")
        check(definition["parent_cluster_id"] in parent_ids, f"Primary parent absent from merged parents for {definition['definition_id']}")
        check(bool(evidence.get("source_definition_ids")), f"Missing source definition traceability for {definition['definition_id']}")
        check(bool(evidence.get("source_pattern_ids")), f"Missing source pattern traceability for {definition['definition_id']}")

    sprint_ids = notes.get("sprint_run_ids") or {}
    required_sprints = (
        "sprint5_clustering",
        "sprint6_revenue",
        "sprint7_market",
        "sprint8_production",
        "sprint9_profitability",
        "sprint10_validation",
    )
    for key in required_sprints:
        check(bool(sprint_ids.get(key)), f"Missing {key} run ID")
    check(sprint_ids.get("sprint5_clustering") == target_run_id, "Sprint 5 clustering provenance must point to the Gate 7 root")

    provenance_specs = [
        (
            "market_structure_analyses",
            sprint_ids.get("sprint7_market"),
            {"source_cluster_run_id": target_run_id},
        ),
        (
            "production_risk_analyses",
            sprint_ids.get("sprint8_production"),
            {
                "source_market_structure_run_id": sprint_ids.get("sprint7_market"),
                "source_cluster_run_id": target_run_id,
            },
        ),
        (
            "cluster_profitability_analyses",
            sprint_ids.get("sprint9_profitability"),
            {
                "source_cluster_run_id": target_run_id,
                "source_revenue_run_id": sprint_ids.get("sprint6_revenue"),
                "source_market_run_id": sprint_ids.get("sprint7_market"),
                "source_production_run_id": sprint_ids.get("sprint8_production"),
                "dataset_hash": APPROVED_DATASET_HASH,
                "assignments_hash": APPROVED_ASSIGNMENTS_HASH,
            },
        ),
        (
            "cluster_validation_analyses",
            sprint_ids.get("sprint10_validation"),
            {
                "source_profitability_run_id": sprint_ids.get("sprint9_profitability"),
                "source_cluster_run_id": target_run_id,
                "source_revenue_run_id": sprint_ids.get("sprint6_revenue"),
                "source_market_run_id": sprint_ids.get("sprint7_market"),
                "source_production_run_id": sprint_ids.get("sprint8_production"),
                "dataset_hash": APPROVED_DATASET_HASH,
                "assignments_hash": APPROVED_ASSIGNMENTS_HASH,
            },
        ),
    ]
    for table, run_id, expected_links in provenance_specs:
        if not run_id:
            continue
        columns = ["cluster_id", *expected_links]
        rows = client.execute(
            f"SELECT {', '.join(columns)} FROM public.{table} WHERE run_id = %s ORDER BY cluster_id",
            [run_id],
        )
        check(len(rows) == EXPECTED_TOP20, f"{table} has {len(rows)} rows instead of 20")
        check([int(row["cluster_id"]) for row in rows] == list(range(1, 21)), f"{table} evaluation IDs are not exactly 1..20")
        for column, expected in expected_links.items():
            check(all(row[column] == expected for row in rows), f"{table}.{column} provenance mismatch")

    if errors:
        print("\n[FAIL] Gate 7 Database Verification Failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    print("\n[PASS] Gate 7 Database Verification Passed completely.")


if __name__ == "__main__":
    verify_gate7(sys.argv[1] if len(sys.argv) > 1 else None)
