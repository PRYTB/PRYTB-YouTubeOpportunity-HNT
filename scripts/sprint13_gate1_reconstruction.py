import hashlib
import json
import re
from collections import defaultdict
from typing import Any, Dict, List

from app.analytics.text_normalizer import clean_text_for_embedding
from app.database.postgres_client import PostgresClient

AUTHORITATIVE_RUN_ID = "sprint12_gate7_reconciled_20260914_211554"
PRIOR_GATE4_RUN_ID = "sprint12_gate4_subniche_20260910_184255"
TOP100_RANKING_BASIS = "outlier_rank_score descending; stable source id order breaks ties"
TOP30_RANKING_BASIS = "outlier_count, small_channel_outliers, channel_count descending; ascending cluster_id production order breaks ties"
TOP20_RANKING_BASIS = "outlier_count, small_channel_outliers, distinct_intents_count, video_count descending; ascending analytical_ordinal production order breaks ties"


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


def _json_value(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else json.loads(value or "{}")


def _actual_outlier(row: Dict[str, Any]) -> bool:
    return bool(row["is_strong_outlier"] or row["is_major_outlier"] or row["is_extreme_outlier"])


def _outlier_classification(row: Dict[str, Any]) -> str:
    if row["is_extreme_outlier"]:
        return "EXTREME"
    if row["is_major_outlier"]:
        return "MAJOR"
    return "STRONG"


def _semantic_classification(niche: str, subniche: str, normalized_intent: str) -> Dict[str, Any]:
    label = f"{niche} {subniche}".lower()
    reasons = []
    if "overview" in label:
        reasons.append("generic_overview_template")
    if re.search(r"(^|\s)\d{2,4}(\s|$)", label):
        reasons.append("numeric_token_label")
    tokens = re.findall(r"[a-záéíóúñ]+", label)
    if tokens and sum(token in {"de", "en", "in", "and"} for token in tokens) >= 2:
        reasons.append("stopword_dominated_label")
    normalized_label = normalize_intent_string(f"{niche} {subniche}")
    intent_tokens = set(normalized_intent.lower().split())
    label_tokens = set(normalized_label.lower().split())
    if intent_tokens and not intent_tokens.intersection(label_tokens):
        reasons.append("label_intent_token_mismatch")
    return {
        "status": "SUSPICIOUS_GENERATED_LABEL" if reasons else "SEMANTICALLY_DESCRIPTIVE",
        "reasons": reasons,
        "basis": "Deterministic lexical audit only; suspicious rows require human semantic review and are not relabeled.",
    }


def _load_prior_set(client: PostgresClient) -> Dict[str, Any]:
    rows = client.execute(
        "SELECT cluster_id, niche, subniche, microniche, summary, label_confidence "
        "FROM public.subniches WHERE run_id = %s",
        [PRIOR_GATE4_RUN_ID],
    )
    items = []
    for row in rows:
        summary = _json_value(row["summary"])
        if summary.get("is_top20") is not True:
            continue
        items.append({
            "rank": int(summary["top20_rank"]),
            "stable_id": summary["subniche_id"],
            "parent_cluster_id": int(row["cluster_id"]),
            "niche": row["niche"],
            "subniche": row["subniche"],
            "normalized_intent": row["microniche"],
            "evidence_count": int(summary["evidence_count"]),
            "source_run_id": PRIOR_GATE4_RUN_ID,
            "dataset_hash": summary.get("dataset_hash"),
            "assignment_hash": summary.get("assignment_hash"),
            "gate3_run_id": summary.get("gate3_run_id"),
        })
    return {"source_run_id": PRIOR_GATE4_RUN_ID, "items": sorted(items, key=lambda row: row["rank"])}


def reconstruct_gate1(client: PostgresClient | None = None, run_id: str = AUTHORITATIVE_RUN_ID) -> Dict[str, Any]:
    client = client or PostgresClient()
    run_rows = client.execute(
        "SELECT dataset_hash, source_collection_run, methodology_version, notes "
        "FROM public.analytical_runs WHERE run_id = %s", [run_id]
    )
    if len(run_rows) != 1:
        raise ValueError(f"Expected one analytical run for {run_id}, found {len(run_rows)}")
    run_row = run_rows[0]
    run_notes = _json_value(run_row["notes"])

    outliers = client.execute(
        "SELECT * FROM public.video_outlier_analyses WHERE run_id = %s ORDER BY id ASC", [run_id]
    )
    actual_outliers = [row for row in outliers if _actual_outlier(row)]
    ranked_outliers = sorted(actual_outliers, key=lambda row: row["outlier_rank_score"], reverse=True)
    top100_source = ranked_outliers[:100]
    top100_ids = [row["video_id"] for row in top100_source]
    top100_hash = ranking_hash(top100_ids)
    top100_items = [
        {
            "rank": rank,
            "video_id": row["video_id"],
            "channel_id": row["channel_id"],
            "classification": _outlier_classification(row),
            "score": float(row["outlier_rank_score"]),
            "source_run_id": run_id,
        }
        for rank, row in enumerate(top100_source, 1)
    ]
    persisted_top100 = client.execute(
        "SELECT * FROM public.gate7_top100_outliers WHERE run_id = %s ORDER BY outlier_rank ASC", [run_id]
    )

    label_rows = {
        int(row["cluster_id"]): row
        for row in client.execute(
            "SELECT cluster_id, niche, subniche, microniche, summary, label_confidence "
            "FROM public.subniches WHERE run_id = %s ORDER BY cluster_id ASC", [run_id]
        )
    }
    cluster_rows = client.execute(
        "SELECT c.cluster_id, cv.video_id, v.channel_id FROM public.clusters c "
        "JOIN public.cluster_videos cv ON cv.run_id = c.run_id AND cv.cluster_id = c.cluster_id "
        "JOIN public.videos v ON v.video_id = cv.video_id "
        "WHERE c.run_id = %s ORDER BY c.cluster_id ASC, cv.video_id ASC", [run_id]
    )
    outlier_by_video = {row["video_id"]: row for row in outliers}
    cluster_members = defaultdict(list)
    for row in cluster_rows:
        cluster_members[int(row["cluster_id"])].append(row)
    top100_id_set = set(top100_ids)
    clusters = []
    for cluster_id in sorted(cluster_members):
        members = cluster_members[cluster_id]
        member_outliers = [outlier_by_video[row["video_id"]] for row in members]
        labels = label_rows[cluster_id]
        top100_support = sorted(
            (row["video_id"] for row in members if row["video_id"] in top100_id_set),
            key=top100_ids.index,
        )
        clusters.append({
            "cluster_id": cluster_id,
            "labels": {
                "niche": labels["niche"],
                "subniche": labels["subniche"],
                "microniche": labels["microniche"],
                "summary": labels["summary"],
                "label_confidence": float(labels["label_confidence"]),
            },
            "membership_counts": {
                "videos": len(members),
                "channels": len({row["channel_id"] for row in members}),
                "actual_outliers": sum(_actual_outlier(row) for row in member_outliers),
                "small_channel_outliers": sum(bool(row["small_channel_outlier"]) for row in member_outliers),
            },
            "top100_support": {"count": len(top100_support), "video_ids": top100_support},
            "ranking_basis": TOP30_RANKING_BASIS,
            "source_run_id": run_id,
        })
    ranked_clusters = sorted(
        clusters,
        key=lambda row: (
            row["membership_counts"]["actual_outliers"],
            row["membership_counts"]["small_channel_outliers"],
            row["membership_counts"]["channels"],
        ),
        reverse=True,
    )
    top30_items = [{"rank": rank, **row} for rank, row in enumerate(ranked_clusters[:30], 1)]
    top30_ids = [row["cluster_id"] for row in top30_items]

    definitions = client.execute(
        "SELECT * FROM public.gate7_semantic_definitions WHERE run_id = %s ORDER BY analytical_ordinal ASC", [run_id]
    )
    memberships = client.execute(
        "SELECT m.definition_id, m.video_id, m.parent_cluster_id, v.channel_id, v.title "
        "FROM public.gate7_semantic_memberships m JOIN public.videos v ON v.video_id = m.video_id "
        "WHERE m.run_id = %s ORDER BY m.definition_id ASC, m.video_id ASC", [run_id]
    )
    memberships_by_definition = defaultdict(list)
    for row in memberships:
        memberships_by_definition[row["definition_id"]].append(row)
    top30_id_set = set(top30_ids)
    reconstructed_definitions = []
    for definition in definitions:
        evidence = _json_value(definition["evidence_payload"])
        parent_cluster_ids = sorted(int(value) for value in evidence.get("parent_cluster_ids", [definition["parent_cluster_id"]]))
        if not parent_cluster_ids or not set(parent_cluster_ids).issubset(top30_id_set):
            continue
        members = memberships_by_definition[definition["definition_id"]]
        member_outliers = [outlier_by_video[row["video_id"]] for row in members]
        supporting_videos = [row["video_id"] for row in members]
        supporting_outliers = [row["video_id"] for row in members if _actual_outlier(outlier_by_video[row["video_id"]])]
        title_intents = {normalize_intent_string(str(row["title"] or "")) for row in members if row["title"]}
        title_intents.discard("")
        reconstructed_definitions.append({
            "stable_id": definition["definition_id"],
            "analytical_ordinal": int(definition["analytical_ordinal"]),
            "niche": definition["niche"],
            "subniche": definition["subniche"],
            "normalized_intent": definition["normalized_intent"],
            "supporting_cluster_ids": parent_cluster_ids,
            "supporting_video_ids": supporting_videos,
            "supporting_outlier_ids": supporting_outliers,
            "semantic_membership_count": len(members),
            "evidence_count": len(title_intents),
            "membership_counts": {
                "videos": len(members),
                "channels": len({row["channel_id"] for row in members}),
                "actual_outliers": len(supporting_outliers),
                "small_channel_outliers": sum(bool(row["small_channel_outlier"]) for row in member_outliers),
                "distinct_title_intents": len(title_intents),
            },
            "content_depth": content_depth(len(title_intents)),
            "semantic_classification": _semantic_classification(definition["niche"], definition["subniche"], definition["normalized_intent"]),
            "ranking_basis": TOP20_RANKING_BASIS,
            "source_run_id": run_id,
            "provenance": {
                "root_run_id": run_id,
                "dataset_hash": run_row["dataset_hash"],
                "source_collection_run": run_row["source_collection_run"],
                "methodology_version": run_row["methodology_version"],
                "definition_id": definition["definition_id"],
                "definition_parent_cluster_id": int(definition["parent_cluster_id"]),
                "evidence_payload": evidence,
            },
        })
    ranked_definitions = sorted(
        reconstructed_definitions,
        key=lambda row: (
            row["membership_counts"]["actual_outliers"],
            row["membership_counts"]["small_channel_outliers"],
            row["membership_counts"]["distinct_title_intents"],
            row["membership_counts"]["videos"],
        ),
        reverse=True,
    )
    top20_items = [{"rank": rank, **row} for rank, row in enumerate(ranked_definitions[:20], 1)]
    top20_ids = [row["stable_id"] for row in top20_items]
    persisted_top20 = client.execute(
        "SELECT * FROM public.gate7_top20_definitions WHERE run_id = %s ORDER BY rank ASC", [run_id]
    )

    prior = _load_prior_set(client)
    prior_intents = {row["normalized_intent"].lower(): row for row in prior["items"]}
    current_intents = {row["normalized_intent"].lower(): row for row in top20_items}
    shared_intents = sorted(set(prior_intents).intersection(current_intents))
    prior["comparison"] = {
        "basis": "Case-insensitive exact normalized-intent equality; stable IDs are run-specific and are not equated.",
        "prior_count": len(prior["items"]),
        "current_count": len(top20_items),
        "shared_normalized_intents": shared_intents,
        "shared_count": len(shared_intents),
        "prior_only_count": len(prior_intents) - len(shared_intents),
        "current_only_count": len(current_intents) - len(shared_intents),
    }

    persisted_top100_ids = [row["video_id"] for row in persisted_top100]
    persisted_top20_ids = [row["definition_id"] for row in persisted_top20]
    return {
        "run_id": run_id,
        "dataset_hash": run_row["dataset_hash"],
        "source_counts": {
            "outlier_analyses": len(outliers), "actual_outliers": len(actual_outliers),
            "small_channel_outliers": sum(bool(row["small_channel_outlier"]) for row in outliers),
            "clusters": len(clusters), "cluster_memberships": len(cluster_rows),
            "semantic_definitions": len(definitions), "eligible_semantic_definitions": len(reconstructed_definitions),
            "semantic_memberships": len(memberships),
        },
        "provenance": {
            "root_run_id": run_id,
            "dataset_hash": run_row["dataset_hash"],
            "source_collection_run": run_row["source_collection_run"],
            "methodology_version": run_row["methodology_version"],
            "assignments_hash": run_notes.get("assignments_hash"),
            "sprint_run_ids": run_notes.get("sprint_run_ids", {}),
        },
        "top100": {
            "ranking_hash": top100_hash,
            "persisted_ranking_hash": next(iter({row["ranking_hash"] for row in persisted_top100}), None),
            "matches_persisted": top100_ids == persisted_top100_ids,
            "ranking_basis": TOP100_RANKING_BASIS,
            "items": top100_items,
        },
        "top30": {"ranking_hash": ranking_hash(top30_ids), "ranking_basis": TOP30_RANKING_BASIS, "items": top30_items},
        "top20": {
            "ranking_hash": ranking_hash(top20_ids),
            "persisted_ranking_hash": next(iter({row["ranking_hash"] for row in persisted_top20}), None),
            "matches_persisted": top20_ids == persisted_top20_ids,
            "ranking_basis": TOP20_RANKING_BASIS,
            "items": top20_items,
        },
        "prior_set": prior,
    }
