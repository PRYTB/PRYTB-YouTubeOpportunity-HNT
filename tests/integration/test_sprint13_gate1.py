"""Sprint 13 Gate 1 deterministic funnel reconstruction integration tests."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.postgres_client import PostgresClient
from app.database.repositories import YouTubeRepository
from scripts.sprint12_reproducibility_constants import (
    EXPECTED_DATASET_HASH,
    EXPECTED_PROD_CHANNELS,
    EXPECTED_PROD_VIDEOS,
)
from scripts.sprint13_gate1_reconstruction import (
    AUTHORITATIVE_RUN_ID,
    PRIOR_GATE4_RUN_ID,
    TOP20_RANKING_BASIS,
    TOP30_RANKING_BASIS,
    TOP100_RANKING_BASIS,
    ranking_hash,
    reconstruct_gate1,
)

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
TOP100_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate1_top100_outliers.json"
TOP30_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate1_top30_clusters.json"
TOP20_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate1_top20_subniches.json"
REPORT_PATH = ROOT_DIR / "docs" / "sprint13_gate1_funnel_reconstruction.md"


@pytest.fixture(scope="module")
def reconstruction():
    return reconstruct_gate1(PostgresClient(), AUTHORITATIVE_RUN_ID)


@pytest.fixture(scope="module")
def artifacts():
    return {
        "top100": json.loads(TOP100_PATH.read_text(encoding="utf-8")),
        "top30": json.loads(TOP30_PATH.read_text(encoding="utf-8")),
        "top20": json.loads(TOP20_PATH.read_text(encoding="utf-8")),
    }


def test_01_postgres_connection():
    rows = PostgresClient().execute("SELECT current_database(), current_user;")
    assert rows == [{"current_database": "prytb", "current_user": "prytb_app"}]


def test_02_unique_authoritative_terminal_run():
    client = PostgresClient()
    terminal_rows = client.execute(
        "SELECT run_id FROM public.analytical_runs WHERE status = %s",
        [TERMINAL_STATUS],
    )
    assert terminal_rows == [{"run_id": AUTHORITATIVE_RUN_ID}]
    run = YouTubeRepository(client).get_analytical_run(AUTHORITATIVE_RUN_ID)
    assert run is not None and run.status == TERMINAL_STATUS


def test_03_authoritative_dataset_and_counts(reconstruction):
    run = YouTubeRepository(PostgresClient()).get_analytical_run(AUTHORITATIVE_RUN_ID)
    assert run.dataset_hash == reconstruction["dataset_hash"] == EXPECTED_DATASET_HASH
    assert run.video_count == EXPECTED_PROD_VIDEOS
    assert run.channel_count == EXPECTED_PROD_CHANNELS
    assert reconstruction["source_counts"] == EXPECTED_COUNTS


def test_04_two_independent_reconstructions_are_identical(reconstruction):
    independent = reconstruct_gate1(PostgresClient(), AUTHORITATIVE_RUN_ID)
    assert reconstruction == independent
    assert reconstruction["top100"]["ranking_hash"] == EXPECTED_TOP100_HASH
    assert reconstruction["top30"]["ranking_hash"] == EXPECTED_TOP30_HASH
    assert reconstruction["top20"]["ranking_hash"] == EXPECTED_TOP20_HASH


def test_05_closed_loop_payload_hashes(artifacts):
    loops = [artifact["closed_loop"] for artifact in artifacts.values()]
    assert loops[0] == loops[1] == loops[2]
    closed_loop = loops[0]
    assert closed_loop["read_count"] == 2
    assert closed_loop["independent_clients"] is True
    assert closed_loop["identical_reconstructions"] is True
    assert closed_loop["ranking_hashes_equal"] is True
    assert closed_loop["first_read_hash"] == closed_loop["second_read_hash"]
    assert len(closed_loop["first_read_hash"]) == 64


def test_06_top100_exact_artifact_filename():
    assert TOP100_PATH.is_file()
    assert TOP100_PATH.name == "sprint13_gate1_top100_outliers.json"


def test_07_top100_count_ranks_and_uniqueness(artifacts):
    items = artifacts["top100"]["items"]
    assert len(items) == 100
    assert [row["rank"] for row in items] == list(range(1, 101))
    assert len({row["video_id"] for row in items}) == 100
    assert ranking_hash([row["video_id"] for row in items]) == EXPECTED_TOP100_HASH


def test_08_top100_required_fields_and_source_run(artifacts):
    required = {"rank", "video_id", "channel_id", "classification", "score", "source_run_id"}
    for row in artifacts["top100"]["items"]:
        assert set(row) == required
        assert row["classification"] in {"STRONG", "MAJOR", "EXTREME"}
        assert isinstance(row["score"], float)
        assert row["source_run_id"] == AUTHORITATIVE_RUN_ID
    assert artifacts["top100"]["ranking_basis"] == TOP100_RANKING_BASIS


def test_09_top100_source_derivation_classification_and_persisted_match(artifacts):
    client = PostgresClient()
    source = client.execute(
        "SELECT id, video_id, channel_id, outlier_rank_score, is_strong_outlier, "
        "is_major_outlier, is_extreme_outlier FROM public.video_outlier_analyses "
        "WHERE run_id = %s ORDER BY id ASC",
        [AUTHORITATIVE_RUN_ID],
    )
    actual = [r for r in source if r["is_strong_outlier"] or r["is_major_outlier"] or r["is_extreme_outlier"]]
    expected = sorted(actual, key=lambda r: r["outlier_rank_score"], reverse=True)[:100]
    persisted = client.execute(
        "SELECT video_id FROM public.gate7_top100_outliers WHERE run_id = %s ORDER BY outlier_rank ASC",
        [AUTHORITATIVE_RUN_ID],
    )
    items = artifacts["top100"]["items"]
    assert [r["video_id"] for r in items] == [r["video_id"] for r in expected]
    assert [r["video_id"] for r in items] == [r["video_id"] for r in persisted]
    for item, row in zip(items, expected):
        classification = "EXTREME" if row["is_extreme_outlier"] else "MAJOR" if row["is_major_outlier"] else "STRONG"
        assert (item["channel_id"], item["classification"], item["score"]) == (
            row["channel_id"], classification, float(row["outlier_rank_score"])
        )
    assert artifacts["top100"]["matches_persisted"] is True


def test_10_top30_exact_artifact_filename():
    assert TOP30_PATH.is_file()
    assert TOP30_PATH.name == "sprint13_gate1_top30_clusters.json"


def test_11_top30_count_hash_and_ranking_basis(artifacts):
    payload = artifacts["top30"]
    items = payload["items"]
    assert len(items) == 30
    assert [r["rank"] for r in items] == list(range(1, 31))
    assert len({r["cluster_id"] for r in items}) == 30
    assert payload["ranking_hash"] == EXPECTED_TOP30_HASH
    assert ranking_hash([r["cluster_id"] for r in items]) == EXPECTED_TOP30_HASH
    assert payload["ranking_basis"] == TOP30_RANKING_BASIS
    metrics = [(
        r["membership_counts"]["actual_outliers"],
        r["membership_counts"]["small_channel_outliers"],
        r["membership_counts"]["channels"],
    ) for r in items]
    assert metrics == sorted(metrics, reverse=True)


def test_12_top30_labels_and_membership_counts(artifacts):
    client = PostgresClient()
    labels = {int(r["cluster_id"]): r for r in client.execute(
        "SELECT cluster_id, niche, subniche, microniche, summary, label_confidence "
        "FROM public.subniches WHERE run_id = %s", [AUTHORITATIVE_RUN_ID]
    )}
    for row in artifacts["top30"]["items"]:
        source = labels[row["cluster_id"]]
        assert row["labels"] == {
            "niche": source["niche"], "subniche": source["subniche"],
            "microniche": source["microniche"], "summary": source["summary"],
            "label_confidence": float(source["label_confidence"]),
        }
        counts = row["membership_counts"]
        assert counts["videos"] > 0 and counts["channels"] > 0
        assert counts["actual_outliers"] >= counts["small_channel_outliers"]
        assert row["source_run_id"] == AUTHORITATIVE_RUN_ID


def test_13_top30_top100_mapping_and_support(artifacts):
    top100_rank = {r["video_id"]: r["rank"] for r in artifacts["top100"]["items"]}
    supported = []
    for row in artifacts["top30"]["items"]:
        support = row["top100_support"]
        assert support["count"] == len(support["video_ids"])
        assert all(video_id in top100_rank for video_id in support["video_ids"])
        assert support["video_ids"] == sorted(support["video_ids"], key=top100_rank.get)
        supported.extend(support["video_ids"])
    assert len(supported) == len(set(supported))


def test_14_top20_exact_filename_ids_and_hash(artifacts):
    assert TOP20_PATH.is_file()
    assert TOP20_PATH.name == "sprint13_gate1_top20_subniches.json"
    payload = artifacts["top20"]
    ids = [r["stable_id"] for r in payload["items"]]
    assert ids == EXPECTED_TOP20_IDS
    assert payload["ranking_hash"] == ranking_hash(ids) == EXPECTED_TOP20_HASH
    assert payload["matches_persisted"] is True
    assert payload["ranking_basis"] == TOP20_RANKING_BASIS


def test_15_top20_support_evidence_and_complete_provenance(artifacts):
    required_provenance = {
        "root_run_id", "dataset_hash", "source_collection_run", "methodology_version",
        "definition_id", "definition_parent_cluster_id", "evidence_payload",
        "evaluation_cluster_id", "downstream_run_ids", "source_cluster_run_ids",
    }
    for row in artifacts["top20"]["items"]:
        assert row["source_run_id"] == AUTHORITATIVE_RUN_ID
        assert row["supporting_cluster_ids"]
        assert row["semantic_membership_count"] == len(row["supporting_video_ids"])
        assert row["membership_counts"]["videos"] == row["semantic_membership_count"]
        assert row["membership_counts"]["actual_outliers"] == len(row["supporting_outlier_ids"])
        assert row["evidence_count"] == row["membership_counts"]["distinct_title_intents"]
        assert set(row["supporting_outlier_ids"]).issubset(row["supporting_video_ids"])
        assert set(row["provenance"]) == required_provenance
        assert row["provenance"]["definition_id"] == row["stable_id"]
        assert row["provenance"]["dataset_hash"] == EXPECTED_DATASET_HASH
        assert set(row["provenance"]["downstream_run_ids"]) == {"validation", "profitability", "market", "production"}
        assert set(row["provenance"]["source_cluster_run_ids"].values()) == {AUTHORITATIVE_RUN_ID}


def test_16_prior_set_source_and_comparison(artifacts):
    prior = artifacts["top20"]["prior_set"]
    comparison = prior["comparison"]
    assert prior["source_run_id"] == PRIOR_GATE4_RUN_ID
    assert len(prior["items"]) == 20
    assert [r["rank"] for r in prior["items"]] == list(range(1, 21))
    assert all(r["source_run_id"] == PRIOR_GATE4_RUN_ID for r in prior["items"])
    assert all(r["dataset_hash"] and r["assignment_hash"] and r["gate3_run_id"] for r in prior["items"])
    assert comparison["prior_count"] == comparison["current_count"] == 20
    assert comparison["shared_count"] == 6
    assert comparison["prior_only_count"] == comparison["current_only_count"] == 14
    assert "stable IDs are run-specific" in comparison["basis"]


def test_17_suspicious_label_semantic_classification(artifacts):
    payload = artifacts["top20"]
    suspicious = [r for r in payload["items"] if r["semantic_classification"]["status"] == "SUSPICIOUS_GENERATED_LABEL"]
    assert payload["semantic_audit"]["suspicious_count"] == len(suspicious) > 0
    assert "preserved without fabricated replacements" in payload["semantic_audit"]["method"]
    assert all(r["semantic_classification"]["reasons"] for r in suspicious)
    assert all("not relabeled" in r["semantic_classification"]["basis"] for r in suspicious)


def test_18_exact_markdown_closed_loop_sections_and_final_table():
    assert REPORT_PATH.is_file()
    assert REPORT_PATH.name == "sprint13_gate1_funnel_reconstruction.md"
    report = REPORT_PATH.read_text(encoding="utf-8")
    for heading in (
        "## Mandatory two-read closed loop", "## Funnel validation",
        "## Prior-set comparison", "## Semantic classification of suspicious labels",
        "## Final Top20",
    ):
        assert heading in report
    assert "Full reconstruction equality: **True**" in report
    assert "Ranking-hash equality: **True**" in report
    assert "This audit does not invent corrected labels." in report
    assert "| Rank | ID | Niche | Subniche | Normalized Intent | Supporting Clusters | Supporting Outliers | Evidence Count |" in report
    assert sum(line.startswith("| ") and "`def_" in line for line in report.splitlines()[report.splitlines().index("## Final Top20"):]) == 20
