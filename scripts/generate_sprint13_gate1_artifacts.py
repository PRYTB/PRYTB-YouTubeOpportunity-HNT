import hashlib
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.postgres_client import PostgresClient
from app.database.repositories import YouTubeRepository
from scripts.sprint13_gate1_reconstruction import AUTHORITATIVE_RUN_ID, reconstruct_gate1

TOP100_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate1_top100_outliers.json"
TOP30_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate1_top30_clusters.json"
TOP20_PATH = ROOT_DIR / "data" / "processed" / "sprint13_gate1_top20_subniches.json"
REPORT_PATH = ROOT_DIR / "docs" / "sprint13_gate1_funnel_reconstruction.md"


def _json_value(value):
    return value if isinstance(value, dict) else json.loads(value or "{}")


def _payload_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def add_downstream_provenance(client, reconstruction):
    run_row = YouTubeRepository(client).get_analytical_run(AUTHORITATIVE_RUN_ID)
    mapping = {row["definition_id"]: row for row in json.loads(run_row.notes)["top20_evaluation_mapping"]}
    table_names = {
        "validation": "cluster_validation_analyses",
        "profitability": "cluster_profitability_analyses",
        "market": "market_structure_analyses",
        "production": "production_risk_analyses",
    }
    evidence = {
        name: {
            int(row["cluster_id"]): row
            for row in client.execute(
                f"SELECT * FROM public.{table} WHERE source_cluster_run_id = %s",
                [AUTHORITATIVE_RUN_ID],
            )
        }
        for name, table in table_names.items()
    }
    for item in reconstruction["top20"]["items"]:
        evaluation_id = int(mapping[item["stable_id"]]["evaluation_cluster_id"])
        item["provenance"]["evaluation_cluster_id"] = evaluation_id
        item["provenance"]["downstream_run_ids"] = {
            name: rows[evaluation_id]["run_id"] for name, rows in evidence.items()
        }
        item["provenance"]["source_cluster_run_ids"] = {
            name: rows[evaluation_id]["source_cluster_run_id"] for name, rows in evidence.items()
        }
    return reconstruction


def build_artifacts(reconstruction, second_read):
    closed_loop = {
        "read_count": 2,
        "independent_clients": True,
        "identical_reconstructions": reconstruction == second_read,
        "first_read_hash": _payload_hash(reconstruction),
        "second_read_hash": _payload_hash(second_read),
        "ranking_hashes_equal": all(
            reconstruction[name]["ranking_hash"] == second_read[name]["ranking_hash"]
            for name in ("top100", "top30", "top20")
        ),
    }
    common = {
        "source_run_id": AUTHORITATIVE_RUN_ID,
        "dataset_hash": reconstruction["dataset_hash"],
        "provenance": reconstruction["provenance"],
        "closed_loop": closed_loop,
    }
    top100 = {**common, **reconstruction["top100"]}
    top30 = {**common, **reconstruction["top30"]}
    top20 = {
        **common,
        **reconstruction["top20"],
        "prior_set": reconstruction["prior_set"],
        "semantic_audit": {
            "method": "Deterministic lexical classification; source labels are preserved without fabricated replacements.",
            "suspicious_count": sum(
                row["semantic_classification"]["status"] == "SUSPICIOUS_GENERATED_LABEL"
                for row in reconstruction["top20"]["items"]
            ),
        },
    }
    return top100, top30, top20, closed_loop


def write_markdown(path, reconstruction, top20_artifact, closed_loop):
    counts = reconstruction["source_counts"]
    comparison = reconstruction["prior_set"]["comparison"]
    suspicious = [
        row for row in top20_artifact["items"]
        if row["semantic_classification"]["status"] == "SUSPICIOUS_GENERATED_LABEL"
    ]
    lines = [
        "# SPRINT 13 — GATE 1: FUNNEL RECONSTRUCTION",
        "",
        f"**Authoritative source run:** `{AUTHORITATIVE_RUN_ID}`",
        "",
        f"**Dataset hash:** `{reconstruction['provenance']['dataset_hash']}`",
        "",
        "## Mandatory two-read closed loop",
        "",
        "Two full PostgreSQL reconstructions were performed with separate clients before artifact writing.",
        "",
        f"- Read count: {closed_loop['read_count']}",
        f"- Full reconstruction equality: **{closed_loop['identical_reconstructions']}**",
        f"- Ranking-hash equality: **{closed_loop['ranking_hashes_equal']}**",
        f"- Read 1 payload SHA-256: `{closed_loop['first_read_hash']}`",
        f"- Read 2 payload SHA-256: `{closed_loop['second_read_hash']}`",
        "",
        "## Funnel validation",
        "",
        f"- Source outlier analyses: {counts['outlier_analyses']} ({counts['actual_outliers']} actual; {counts['small_channel_outliers']} small-channel)",
        f"- Source clusters/memberships: {counts['clusters']}/{counts['cluster_memberships']}",
        f"- Source semantic definitions/memberships: {counts['semantic_definitions']}/{counts['semantic_memberships']}",
        f"- Top100 ranking SHA-256: `{reconstruction['top100']['ranking_hash']}` (persisted match: {reconstruction['top100']['matches_persisted']})",
        f"- Top30 ranking SHA-256: `{reconstruction['top30']['ranking_hash']}`",
        f"- Top20 ranking SHA-256: `{reconstruction['top20']['ranking_hash']}` (persisted match: {reconstruction['top20']['matches_persisted']})",
        "",
        "## Prior-set comparison",
        "",
        f"The prior set is read from PostgreSQL run `{reconstruction['prior_set']['source_run_id']}`. {comparison['basis']}",
        "",
        f"- Prior/current counts: {comparison['prior_count']}/{comparison['current_count']}",
        f"- Shared normalized intents: {comparison['shared_count']} ({', '.join(comparison['shared_normalized_intents']) or 'none'})",
        f"- Prior-only/current-only: {comparison['prior_only_count']}/{comparison['current_only_count']}",
        "",
        "The run-specific stable IDs are intentionally not compared as identities. Dataset and assignment lineage for every prior item is retained in the Top20 JSON.",
        "",
        "## Semantic classification of suspicious labels",
        "",
        "This audit does not invent corrected labels. It flags generic templates, numeric/token-derived labels, stopword-dominated labels, and label/intent token mismatches for human review.",
        "",
        "| ID | Niche | Subniche | Normalized Intent | Classification | Reasons |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in suspicious:
        lines.append(
            f"| `{row['stable_id']}` | {row['niche']} | {row['subniche']} | {row['normalized_intent']} | "
            f"{row['semantic_classification']['status']} | {', '.join(row['semantic_classification']['reasons'])} |"
        )
    lines.extend([
        "",
        "## Final Top20",
        "",
        "| Rank | ID | Niche | Subniche | Normalized Intent | Supporting Clusters | Supporting Outliers | Evidence Count |",
        "| ---: | --- | --- | --- | --- | --- | ---: | ---: |",
    ])
    for row in top20_artifact["items"]:
        lines.append(
            f"| {row['rank']} | `{row['stable_id']}` | {row['niche']} | {row['subniche']} | "
            f"{row['normalized_intent']} | {', '.join(map(str, row['supporting_cluster_ids']))} | "
            f"{len(row['supporting_outlier_ids'])} | {row['evidence_count']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    first = add_downstream_provenance(PostgresClient(), reconstruct_gate1(PostgresClient()))
    second = add_downstream_provenance(PostgresClient(), reconstruct_gate1(PostgresClient()))
    top100, top30, top20, closed_loop = build_artifacts(first, second)
    if not closed_loop["identical_reconstructions"]:
        raise RuntimeError("Two independent PostgreSQL reconstructions differ")
    if not first["top100"]["matches_persisted"] or not first["top20"]["matches_persisted"]:
        raise RuntimeError("Reconstruction differs from persisted Gate 7 validation")
    TOP100_PATH.write_text(json.dumps(top100, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    TOP30_PATH.write_text(json.dumps(top30, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    TOP20_PATH.write_text(json.dumps(top20, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(REPORT_PATH, first, top20, closed_loop)
    for path in (TOP100_PATH, TOP30_PATH, TOP20_PATH, REPORT_PATH):
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
