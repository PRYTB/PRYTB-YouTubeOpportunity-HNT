import hashlib
from collections import defaultdict
from typing import Any, Dict, List

from app.analytics.text_normalizer import clean_text_for_embedding
from app.database.postgres_client import PostgresClient

AUTHORITATIVE_RUN_ID = "sprint12_gate7_reconciled_20260914_211554"


def ranking_hash(ids: List[Any]) -> str:
    return hashlib.sha256("\n".join(str(value) for value in ids).encode("utf-8")).hexdigest()


def normalize_intent_string(text: str) -> str:
    cleaned = clean_text_for_embedding(text)
    return " ".join(word for word in cleaned.split() if len(word) > 1)


def content_depth(distinct_intents_count: int) -> str:
    if distinct_intents_count >= 100:
        return "100_PLUS"
    if distinct_intents_count >= 50:
        return "50_TO_99"
    if distinct_intents_count >= 20:
        return "20_TO_49"
    return "SHALLOW"


def _actual_outlier(row: Dict[str, Any]) -> bool:
    return bool(
        row["is_strong_outlier"]
        or row["is_major_outlier"]
        or row["is_extreme_outlier"]
    )


def reconstruct_gate1(
    client: PostgresClient | None = None,
    run_id: str = AUTHORITATIVE_RUN_ID,
) -> Dict[str, Any]:
    client = client or PostgresClient()

    run_rows = client.execute(
        "SELECT dataset_hash FROM public.analytical_runs WHERE run_id = %s", [run_id]
    )
    if len(run_rows) != 1:
        raise ValueError(f"Expected one analytical run for {run_id}, found {len(run_rows)}")

    outliers = client.execute(
        "SELECT * FROM public.video_outlier_analyses "
        "WHERE run_id = %s ORDER BY id ASC",
        [run_id],
    )
    actual_outliers = [row for row in outliers if _actual_outlier(row)]
    ranked_outliers = sorted(
        actual_outliers,
        key=lambda row: row["outlier_rank_score"],
        reverse=True,
    )
    top100_rows = ranked_outliers[:100]
    top100_ids = [row["video_id"] for row in top100_rows]
    top100_hash = ranking_hash(top100_ids)

    persisted_top100 = client.execute(
        "SELECT * FROM public.gate7_top100_outliers "
        "WHERE run_id = %s ORDER BY outlier_rank ASC",
        [run_id],
    )
    persisted_top100_ids = [row["video_id"] for row in persisted_top100]
    persisted_top100_hashes = sorted({row["ranking_hash"] for row in persisted_top100})

    cluster_rows = client.execute(
        "SELECT c.cluster_id, cv.video_id, v.channel_id "
        "FROM public.clusters c "
        "JOIN public.cluster_videos cv "
        "ON cv.run_id = c.run_id AND cv.cluster_id = c.cluster_id "
        "JOIN public.videos v ON v.video_id = cv.video_id "
        "WHERE c.run_id = %s ORDER BY c.cluster_id ASC, cv.video_id ASC",
        [run_id],
    )
    outlier_by_video = {row["video_id"]: row for row in outliers}
    cluster_members = defaultdict(list)
    for row in cluster_rows:
        cluster_members[int(row["cluster_id"])].append(row)

    clusters = []
    for cluster_id in sorted(cluster_members):
        members = cluster_members[cluster_id]
        member_outliers = [outlier_by_video[row["video_id"]] for row in members]
        clusters.append(
            {
                "cluster_id": cluster_id,
                "video_count": len(members),
                "outlier_count": sum(_actual_outlier(row) for row in member_outliers),
                "small_channel_outliers": sum(
                    bool(row["small_channel_outlier"]) for row in member_outliers
                ),
                "channel_count": len({row["channel_id"] for row in members}),
            }
        )
    ranked_clusters = sorted(
        clusters,
        key=lambda row: (
            row["outlier_count"],
            row["small_channel_outliers"],
            row["channel_count"],
        ),
        reverse=True,
    )
    top30 = [{"rank": rank, **row} for rank, row in enumerate(ranked_clusters[:30], 1)]
    top30_ids = [row["cluster_id"] for row in top30]

    definitions = client.execute(
        "SELECT * FROM public.gate7_semantic_definitions "
        "WHERE run_id = %s ORDER BY analytical_ordinal ASC",
        [run_id],
    )
    memberships = client.execute(
        "SELECT m.definition_id, m.video_id, m.parent_cluster_id, "
        "v.channel_id, v.title "
        "FROM public.gate7_semantic_memberships m "
        "JOIN public.videos v ON v.video_id = m.video_id "
        "WHERE m.run_id = %s ORDER BY m.definition_id ASC, m.video_id ASC",
        [run_id],
    )
    memberships_by_definition = defaultdict(list)
    for row in memberships:
        memberships_by_definition[row["definition_id"]].append(row)

    top30_id_set = set(top30_ids)
    reconstructed_definitions = []
    for definition in definitions:
        evidence = definition["evidence_payload"]
        if isinstance(evidence, str):
            import json

            evidence = json.loads(evidence)
        parent_cluster_ids = sorted(
            int(value)
            for value in evidence.get(
                "parent_cluster_ids", [definition["parent_cluster_id"]]
            )
        )
        if not parent_cluster_ids or not set(parent_cluster_ids).issubset(top30_id_set):
            continue
        members = memberships_by_definition[definition["definition_id"]]
        member_outliers = [outlier_by_video[row["video_id"]] for row in members]
        title_intents = {
            normalize_intent_string(str(row["title"] or ""))
            for row in members
            if row["title"]
        }
        title_intents.discard("")
        distinct_intents_count = len(title_intents)
        reconstructed_definitions.append(
            {
                "definition_id": definition["definition_id"],
                "analytical_ordinal": int(definition["analytical_ordinal"]),
                "parent_cluster_id": int(definition["parent_cluster_id"]),
                "parent_cluster_ids": parent_cluster_ids,
                "niche": definition["niche"],
                "subniche": definition["subniche"],
                "microniche": definition["microniche"],
                "normalized_intent": definition["normalized_intent"],
                "video_count": len(members),
                "outlier_count": sum(_actual_outlier(row) for row in member_outliers),
                "small_channel_outliers": sum(
                    bool(row["small_channel_outlier"]) for row in member_outliers
                ),
                "channel_count": len({row["channel_id"] for row in members}),
                "distinct_intents_count": distinct_intents_count,
                "content_depth": content_depth(distinct_intents_count),
            }
        )

    ranked_definitions = sorted(
        reconstructed_definitions,
        key=lambda row: (
            row["outlier_count"],
            row["small_channel_outliers"],
            row["distinct_intents_count"],
            row["video_count"],
        ),
        reverse=True,
    )
    top20 = [
        {"rank": rank, **row} for rank, row in enumerate(ranked_definitions[:20], 1)
    ]
    top20_ids = [row["definition_id"] for row in top20]
    top20_hash = ranking_hash(top20_ids)

    persisted_top20 = client.execute(
        "SELECT * FROM public.gate7_top20_definitions "
        "WHERE run_id = %s ORDER BY rank ASC",
        [run_id],
    )
    persisted_top20_ids = [row["definition_id"] for row in persisted_top20]
    persisted_top20_hashes = sorted({row["ranking_hash"] for row in persisted_top20})

    return {
        "run_id": run_id,
        "dataset_hash": run_rows[0]["dataset_hash"],
        "source_counts": {
            "outlier_analyses": len(outliers),
            "actual_outliers": len(actual_outliers),
            "small_channel_outliers": sum(
                bool(row["small_channel_outlier"]) for row in outliers
            ),
            "clusters": len(clusters),
            "cluster_memberships": len(cluster_rows),
            "semantic_definitions": len(definitions),
            "eligible_semantic_definitions": len(reconstructed_definitions),
            "semantic_memberships": len(memberships),
        },
        "ordering_contracts": {
            "top100": "Python stable score-desc sort over outlier-analysis insertion identity order",
            "top30": "Python stable metric-desc sort over ascending cluster_id production order",
            "top20": "Python stable metric-desc sort over ascending analytical_ordinal production order",
        },
        "top100": {
            "ranking_hash": top100_hash,
            "persisted_ranking_hash": persisted_top100_hashes[0] if len(persisted_top100_hashes) == 1 else None,
            "matches_persisted": top100_ids == persisted_top100_ids,
            "items": [
                {
                    "rank": rank,
                    "video_id": row["video_id"],
                    "channel_id": row["channel_id"],
                    "outlier_rank_score": row["outlier_rank_score"],
                }
                for rank, row in enumerate(top100_rows, 1)
            ],
        },
        "top30": {
            "ranking_hash": ranking_hash(top30_ids),
            "items": top30,
        },
        "top20": {
            "ranking_hash": top20_hash,
            "persisted_ranking_hash": persisted_top20_hashes[0] if len(persisted_top20_hashes) == 1 else None,
            "matches_persisted": top20_ids == persisted_top20_ids,
            "items": top20,
        },
    }
