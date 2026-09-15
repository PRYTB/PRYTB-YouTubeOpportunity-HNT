import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.postgres_client import PostgresClient
from app.database.repositories import YouTubeRepository
from scripts.sprint13_gate1_reconstruction import (
    AUTHORITATIVE_RUN_ID,
    reconstruct_gate1,
)


def _json_value(value):
    return value if isinstance(value, dict) else json.loads(value or "{}")


def build_top20_review_data(client, reconstruction):
    repo = YouTubeRepository(client)
    run_row = repo.get_analytical_run(AUTHORITATIVE_RUN_ID)
    notes = json.loads(run_row.notes)
    mapping = {
        row["definition_id"]: row for row in notes["top20_evaluation_mapping"]
    }
    validations = {
        row["cluster_id"]: row
        for row in client.execute(
            "SELECT * FROM public.cluster_validation_analyses "
            "WHERE source_cluster_run_id = %s",
            [AUTHORITATIVE_RUN_ID],
        )
    }
    profitabilities = {
        row["cluster_id"]: row
        for row in client.execute(
            "SELECT * FROM public.cluster_profitability_analyses "
            "WHERE source_cluster_run_id = %s",
            [AUTHORITATIVE_RUN_ID],
        )
    }
    markets = {
        row["cluster_id"]: row
        for row in client.execute(
            "SELECT * FROM public.market_structure_analyses "
            "WHERE source_cluster_run_id = %s",
            [AUTHORITATIVE_RUN_ID],
        )
    }
    production_risks = {
        row["cluster_id"]: row
        for row in client.execute(
            "SELECT * FROM public.production_risk_analyses "
            "WHERE source_cluster_run_id = %s",
            [AUTHORITATIVE_RUN_ID],
        )
    }

    result = []
    for definition in reconstruction["top20"]["items"]:
        definition_id = definition["definition_id"]
        evaluation_cluster_id = mapping[definition_id]["evaluation_cluster_id"]
        validation = validations[evaluation_cluster_id]
        profitability = profitabilities[evaluation_cluster_id]
        market = markets[evaluation_cluster_id]
        production_risk = production_risks[evaluation_cluster_id]
        validation_metrics = _json_value(validation["metrics"])
        profitability_metrics = _json_value(profitability["metrics"])
        positive = validation_metrics.get("positive_evidence", [])
        negative = validation_metrics.get("contradictory_evidence", [])
        negative += validation_metrics.get("missing_evidence", [])
        result.append(
            {
                "rank": definition["rank"],
                "candidate_id": definition_id,
                "evaluation_cluster_id": evaluation_cluster_id,
                "parent_cluster_id": definition["parent_cluster_id"],
                "parent_cluster_ids": definition["parent_cluster_ids"],
                "niche": definition["niche"],
                "subniche": definition["subniche"],
                "normalized_intent": definition["normalized_intent"],
                "market": "Global/English",
                "language": "en",
                "profitability_score": profitability["profitability_score"],
                "viral_score": profitability_metrics.get("outlier_score"),
                "outlier_count": definition["outlier_count"],
                "small_channel_outliers": definition["small_channel_outliers"],
                "video_count": definition["video_count"],
                "channel_count": definition["channel_count"],
                "revenue_score": profitability_metrics.get("revenue_potential_score"),
                "competition_score": market["competition_score"],
                "evergreen_score": market["evergreen_score"],
                "production_score": profitability_metrics.get("production_score"),
                "risk_score": production_risk["overall_risk_score"],
                "risk_level": production_risk["risk_level"],
                "content_depth_status": definition["content_depth"],
                "distinct_intents_count": definition["distinct_intents_count"],
                "confidence": validation["validation_confidence"],
                "expected_views_range": profitability_metrics.get(
                    "expected_views_range", "NOT AVAILABLE"
                ),
                "rpm_range": profitability_metrics.get("rpm_range", "NOT AVAILABLE"),
                "expected_revenue_range": profitability_metrics.get(
                    "revenue_scenarios", "NOT AVAILABLE"
                ),
                "expected_cost_range": profitability_metrics.get(
                    "production_cost", "NOT AVAILABLE"
                ),
                "expected_profit_range": profitability_metrics.get(
                    "profit_scenarios", "NOT AVAILABLE"
                ),
                "evidence_summary": positive or ["NOT AVAILABLE"],
                "counter_evidence": negative or ["NONE"],
                "recommendation": validation["validation_status"],
                "source_run_linkage": {
                    "root_run_id": AUTHORITATIVE_RUN_ID,
                    "profitability_run_id": profitability["run_id"],
                    "market_run_id": market["run_id"],
                    "production_run_id": production_risk["run_id"],
                    "validation_run_id": validation["run_id"],
                },
            }
        )
    return result


def write_markdown(path, reconstruction, top20_data):
    counts = reconstruction["source_counts"]
    with path.open("w", encoding="utf-8") as output:
        output.write("# SPRINT 13 — GATE 1: CANONICAL FUNNEL RECONSTRUCTION\n\n")
        output.write(f"**Authoritative Run ID:** `{AUTHORITATIVE_RUN_ID}`\n\n")
        output.write("## Reconstruction validation\n\n")
        output.write(
            f"- Source outlier analyses: {counts['outlier_analyses']} "
            f"({counts['actual_outliers']} actual; {counts['small_channel_outliers']} small-channel)\n"
        )
        output.write(
            f"- Source clusters/memberships: {counts['clusters']}/{counts['cluster_memberships']}\n"
        )
        output.write(
            f"- Source semantic definitions/memberships: "
            f"{counts['semantic_definitions']}/{counts['semantic_memberships']}\n"
        )
        output.write(
            f"- Top100 SHA-256: `{reconstruction['top100']['ranking_hash']}` "
            f"(persisted match: {reconstruction['top100']['matches_persisted']})\n"
        )
        output.write(
            f"- Top30 SHA-256: `{reconstruction['top30']['ranking_hash']}`\n"
        )
        output.write(
            f"- Top20 SHA-256: `{reconstruction['top20']['ranking_hash']}` "
            f"(persisted match: {reconstruction['top20']['matches_persisted']})\n\n"
        )
        output.write("## Canonical Top 20 semantic candidates\n\n")
        output.write(
            "| Rank | Candidate | Subniche | Outliers | Small-channel | Intents | Videos | Channels | Parents |\n"
        )
        output.write("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |\n")
        for row in top20_data:
            parents = ", ".join(str(value) for value in row["parent_cluster_ids"])
            output.write(
                f"| {row['rank']} | `{row['candidate_id']}` | {row['subniche']} | "
                f"{row['outlier_count']} | {row['small_channel_outliers']} | "
                f"{row['distinct_intents_count']} | {row['video_count']} | "
                f"{row['channel_count']} | {parents} |\n"
            )


def main():
    client = PostgresClient()
    reconstruction = reconstruct_gate1(client)
    if not reconstruction["top100"]["matches_persisted"]:
        raise RuntimeError("Reconstructed Top100 differs from persisted Gate 7 validation")
    if not reconstruction["top20"]["matches_persisted"]:
        raise RuntimeError("Reconstructed Top20 differs from persisted Gate 7 validation")

    top20_data = build_top20_review_data(client, reconstruction)
    funnel_path = ROOT_DIR / "data" / "processed" / "sprint13_gate1_canonical_funnel.json"
    top20_path = ROOT_DIR / "data" / "processed" / "sprint13_gate1_top20.json"
    markdown_path = ROOT_DIR / "docs" / "sprint13_gate1_top20_review.md"
    funnel_path.write_text(
        json.dumps(reconstruction, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    top20_path.write_text(
        json.dumps(top20_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_markdown(markdown_path, reconstruction, top20_data)
    print(f"Wrote canonical funnel to {funnel_path}")
    print(f"Wrote {len(top20_data)} candidates to {top20_path}")
    print(f"Wrote review markdown to {markdown_path}")


if __name__ == "__main__":
    main()
