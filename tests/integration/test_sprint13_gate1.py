"""Sprint 13 Gate 1 canonical funnel reconstruction integration tests."""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.postgres_client import PostgresClient
from app.database.repositories import YouTubeRepository
from scripts.sprint12_reproducibility_constants import (
    EXPECTED_DATASET_HASH,
    EXPECTED_PROD_CHANNELS,
    EXPECTED_PROD_VIDEOS,
)
from scripts.sprint13_gate1_reconstruction import ranking_hash, reconstruct_gate1

AUTHORITATIVE_RUN_ID = "sprint12_gate7_reconciled_20260914_211554"
TERMINAL_STATUS = "SPRINT12_FINAL_ANALYTICS_APPROVED"
EXPECTED_COUNTS = {
    "outlier_analyses": 10585,
    "actual_outliers": 754,
    "small_channel_outliers": 282,
    "clusters": 35,
    "cluster_memberships": 10585,
    "semantic_definitions": 58,
    "eligible_semantic_definitions": 58,
    "semantic_memberships": 9603,
}
EXPECTED_TOP100_HASH = "d2df88751980afb7af1e9ecadf145a2a0ff514a0dba6062f8d62e03d980426d2"
EXPECTED_TOP30_HASH = "decc570011b881414202cba3f0c03144c954f0be5c21c4167e756f5ff5780c77"
EXPECTED_TOP20_HASH = "85a543baf63afad339c1643b8f25cadd2b8d7d4ca316ce6e182c130fe39d98e4"
EXPECTED_TOP20_IDS = [
    "def_015", "def_046", "def_055", "def_036", "def_024",
    "def_057", "def_045", "def_030", "def_004", "def_038",
    "def_052", "def_020", "def_053", "def_016", "def_054",
    "def_025", "def_002", "def_009", "def_026", "def_023",
]


def test_postgres_connection_and_authoritative_run():
    client = PostgresClient()
    db_info = client.execute("SELECT current_database(), current_user;")
    assert db_info == [{"current_database": "prytb", "current_user": "prytb_app"}]

    terminal_rows = client.execute(
        "SELECT run_id FROM public.analytical_runs WHERE status = %s",
        [TERMINAL_STATUS],
    )
    assert terminal_rows == [{"run_id": AUTHORITATIVE_RUN_ID}]

    run_row = YouTubeRepository(client).get_analytical_run(AUTHORITATIVE_RUN_ID)
    assert run_row is not None
    assert run_row.status == TERMINAL_STATUS
    assert run_row.dataset_hash == EXPECTED_DATASET_HASH
    assert run_row.video_count == EXPECTED_PROD_VIDEOS
    assert run_row.channel_count == EXPECTED_PROD_CHANNELS


def test_two_independent_source_reconstructions_are_identical():
    first = reconstruct_gate1(PostgresClient(), AUTHORITATIVE_RUN_ID)
    second = reconstruct_gate1(PostgresClient(), AUTHORITATIVE_RUN_ID)

    assert first == second
    assert first["source_counts"] == EXPECTED_COUNTS
    assert first["dataset_hash"] == EXPECTED_DATASET_HASH
    assert first["top100"]["ranking_hash"] == EXPECTED_TOP100_HASH
    assert first["top30"]["ranking_hash"] == EXPECTED_TOP30_HASH
    assert first["top20"]["ranking_hash"] == EXPECTED_TOP20_HASH


def test_top100_is_source_derived_and_matches_persisted_validation():
    client = PostgresClient()
    reconstruction = reconstruct_gate1(client, AUTHORITATIVE_RUN_ID)
    items = reconstruction["top100"]["items"]

    source = client.execute(
        "SELECT id, video_id, outlier_rank_score, is_strong_outlier, "
        "is_major_outlier, is_extreme_outlier FROM public.video_outlier_analyses "
        "WHERE run_id = %s ORDER BY id ASC",
        [AUTHORITATIVE_RUN_ID],
    )
    actual = [
        row for row in source
        if row["is_strong_outlier"] or row["is_major_outlier"] or row["is_extreme_outlier"]
    ]
    expected = sorted(actual, key=lambda row: row["outlier_rank_score"], reverse=True)[:100]
    expected_ids = [row["video_id"] for row in expected]
    persisted = client.execute(
        "SELECT video_id, ranking_hash FROM public.gate7_top100_outliers "
        "WHERE run_id = %s ORDER BY outlier_rank ASC",
        [AUTHORITATIVE_RUN_ID],
    )

    assert len(items) == len(set(expected_ids)) == 100
    assert [row["video_id"] for row in items] == expected_ids
    assert expected_ids == [row["video_id"] for row in persisted]
    assert ranking_hash(expected_ids) == EXPECTED_TOP100_HASH
    assert {row["ranking_hash"] for row in persisted} == {EXPECTED_TOP100_HASH}
    assert expected[99]["outlier_rank_score"] > sorted(
        actual, key=lambda row: row["outlier_rank_score"], reverse=True
    )[100]["outlier_rank_score"]
    assert reconstruction["top100"]["matches_persisted"] is True


def test_top30_metrics_and_stable_ranking_are_reconstructed_from_memberships():
    client = PostgresClient()
    reconstruction = reconstruct_gate1(client, AUTHORITATIVE_RUN_ID)
    items = reconstruction["top30"]["items"]
    all_clusters = client.execute(
        "SELECT cluster_id, unique_channels FROM public.clusters "
        "WHERE run_id = %s ORDER BY cluster_id ASC",
        [AUTHORITATIVE_RUN_ID],
    )
    rows = client.execute(
        "SELECT cv.cluster_id, cv.video_id, v.channel_id, "
        "o.is_strong_outlier, o.is_major_outlier, o.is_extreme_outlier, "
        "o.small_channel_outlier FROM public.cluster_videos cv "
        "JOIN public.videos v ON v.video_id = cv.video_id "
        "JOIN public.video_outlier_analyses o ON o.run_id = cv.run_id AND o.video_id = cv.video_id "
        "WHERE cv.run_id = %s ORDER BY cv.cluster_id ASC, cv.video_id ASC",
        [AUTHORITATIVE_RUN_ID],
    )
    by_cluster = {int(row["cluster_id"]): [] for row in all_clusters}
    for row in rows:
        by_cluster[int(row["cluster_id"])].append(row)
    metrics = []
    for cluster in all_clusters:
        cluster_id = int(cluster["cluster_id"])
        members = by_cluster[cluster_id]
        metric = {
            "cluster_id": cluster_id,
            "video_count": len(members),
            "outlier_count": sum(bool(r["is_strong_outlier"] or r["is_major_outlier"] or r["is_extreme_outlier"]) for r in members),
            "small_channel_outliers": sum(bool(r["small_channel_outlier"]) for r in members),
            "channel_count": len({r["channel_id"] for r in members}),
        }
        assert metric["channel_count"] == int(cluster["unique_channels"])
        metrics.append(metric)
    ranked = sorted(
        metrics,
        key=lambda row: (row["outlier_count"], row["small_channel_outliers"], row["channel_count"]),
        reverse=True,
    )

    assert len(metrics) == 35
    assert items == [{"rank": rank, **row} for rank, row in enumerate(ranked[:30], 1)]
    assert ranking_hash([row["cluster_id"] for row in items]) == EXPECTED_TOP30_HASH
    assert len({(r["outlier_count"], r["small_channel_outliers"], r["channel_count"]) for r in metrics}) == 35
    assert (ranked[29]["outlier_count"], ranked[29]["small_channel_outliers"], ranked[29]["channel_count"]) != (
        ranked[30]["outlier_count"], ranked[30]["small_channel_outliers"], ranked[30]["channel_count"]
    )


def test_semantic_metrics_provenance_labels_and_top20_validation():
    client = PostgresClient()
    reconstruction = reconstruct_gate1(client, AUTHORITATIVE_RUN_ID)
    top20 = reconstruction["top20"]["items"]
    top30_ids = {row["cluster_id"] for row in reconstruction["top30"]["items"]}
    persisted_definitions = {
        row["definition_id"]: row
        for row in client.execute(
            "SELECT * FROM public.gate7_semantic_definitions WHERE run_id = %s",
            [AUTHORITATIVE_RUN_ID],
        )
    }
    ordered_definitions = sorted(
        persisted_definitions.values(), key=lambda row: int(row["analytical_ordinal"])
    )
    persisted_top20 = client.execute(
        "SELECT definition_id, ranking_hash FROM public.gate7_top20_definitions "
        "WHERE run_id = %s ORDER BY rank ASC",
        [AUTHORITATIVE_RUN_ID],
    )

    assert [row["normalized_intent"] for row in ordered_definitions] == sorted(
        row["normalized_intent"] for row in ordered_definitions
    )
    assert [row["definition_id"] for row in top20] == EXPECTED_TOP20_IDS
    assert [row["definition_id"] for row in persisted_top20] == EXPECTED_TOP20_IDS
    assert {row["ranking_hash"] for row in persisted_top20} == {EXPECTED_TOP20_HASH}
    assert ranking_hash(EXPECTED_TOP20_IDS) == EXPECTED_TOP20_HASH
    assert reconstruction["top20"]["matches_persisted"] is True

    for row in top20:
        persisted = persisted_definitions[row["definition_id"]]
        assert set(row["parent_cluster_ids"]).issubset(top30_ids)
        assert row["parent_cluster_id"] in row["parent_cluster_ids"]
        for field in (
            "video_count", "outlier_count", "small_channel_outliers",
            "channel_count", "distinct_intents_count", "content_depth",
        ):
            assert row[field] == persisted[field]

    assert any(len(row["parent_cluster_ids"]) > 1 for row in top20)
    assert any(row["niche"] == "20 Overview" for row in top20)
    assert any(row["subniche"] == "2025 & In" for row in top20)


def test_generated_artifacts_match_a_fresh_reconstruction():
    reconstruction = reconstruct_gate1(PostgresClient(), AUTHORITATIVE_RUN_ID)
    funnel = json.loads(
        (ROOT_DIR / "data" / "processed" / "sprint13_gate1_canonical_funnel.json").read_text(encoding="utf-8")
    )
    review = json.loads(
        (ROOT_DIR / "data" / "processed" / "sprint13_gate1_top20.json").read_text(encoding="utf-8")
    )

    assert funnel == reconstruction
    review_ids = [row["candidate_id"] for row in review]
    assert review_ids == EXPECTED_TOP20_IDS
    assert ranking_hash(review_ids) == EXPECTED_TOP20_HASH
    assert len(review_ids) == len(set(review_ids)) == 20


def test_top20_score_ranges_and_evidence_linkage():
    client = PostgresClient()
    repo = YouTubeRepository(client)
    run_row = repo.get_analytical_run(AUTHORITATIVE_RUN_ID)
    mapping = {row["definition_id"]: row for row in json.loads(run_row.notes)["top20_evaluation_mapping"]}
    reconstruction = reconstruct_gate1(client, AUTHORITATIVE_RUN_ID)

    tables = {
        "validation": "cluster_validation_analyses",
        "profitability": "cluster_profitability_analyses",
        "market": "market_structure_analyses",
        "production": "production_risk_analyses",
    }
    evidence = {
        key: {row["cluster_id"]: row for row in client.execute(
            f"SELECT * FROM public.{table} WHERE source_cluster_run_id = %s",
            [AUTHORITATIVE_RUN_ID],
        )}
        for key, table in tables.items()
    }

    for definition in reconstruction["top20"]["items"]:
        evaluation_id = mapping[definition["definition_id"]]["evaluation_cluster_id"]
        validation = evidence["validation"][evaluation_id]
        profitability = evidence["profitability"][evaluation_id]
        market = evidence["market"][evaluation_id]
        production = evidence["production"][evaluation_id]
        metrics = profitability["metrics"] if isinstance(profitability["metrics"], dict) else json.loads(profitability["metrics"] or "{}")

        for value in (
            profitability["profitability_score"], metrics["outlier_score"],
            metrics["revenue_potential_score"], market["competition_score"],
            market["evergreen_score"], production["overall_risk_score"],
            validation["validation_confidence"],
        ):
            assert 0.0 <= float(value) <= 100.0
        assert all(
            row["source_cluster_run_id"] == AUTHORITATIVE_RUN_ID
            for row in (validation, profitability, market, production)
        )
