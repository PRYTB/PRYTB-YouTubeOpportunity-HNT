import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.postgres_client import PostgresClient
from app.database.repositories import YouTubeRepository

client = PostgresClient()
repo = YouTubeRepository(client)
run_id = 'sprint12_gate7_reconciled_20260914_211554'

run_row = repo.get_analytical_run(run_id)
notes = json.loads(run_row.notes)
mapping = notes['top20_evaluation_mapping']

top20_defs = repo.get_gate7_top20_definitions(run_id)
sem_defs = repo.get_gate7_semantic_definitions(run_id)
sem_map = {d['definition_id']: d for d in sem_defs}

validations = {v['cluster_id']: v for v in client.execute('SELECT * FROM public.cluster_validation_analyses WHERE source_cluster_run_id = %s', [run_id])}
profitabilities = {p['cluster_id']: p for p in client.execute('SELECT * FROM public.cluster_profitability_analyses WHERE source_cluster_run_id = %s', [run_id])}
markets = {m['cluster_id']: m for m in client.execute('SELECT * FROM public.market_structure_analyses WHERE source_cluster_run_id = %s', [run_id])}
prods = {pr['cluster_id']: pr for pr in client.execute('SELECT * FROM public.production_risk_analyses WHERE source_cluster_run_id = %s', [run_id])}

top20_data = []

for row in top20_defs:
    rank = row['rank']
    def_id = row['definition_id']
    m_item = next(m for m in mapping if m['definition_id'] == def_id)
    eval_id = m_item['evaluation_cluster_id']

    sd = sem_map[def_id]
    val = validations.get(eval_id, {})
    prof = profitabilities.get(eval_id, {})
    mkt = markets.get(eval_id, {})
    prd = prods.get(eval_id, {})

    val_m = val.get('metrics', {})
    if isinstance(val_m, str):
        val_m = json.loads(val_m or '{}')
    prof_m = prof.get('metrics', {})
    if isinstance(prof_m, str):
        prof_m = json.loads(prof_m or '{}')
    mkt_m = mkt.get('metrics', {})
    if isinstance(mkt_m, str):
        mkt_m = json.loads(mkt_m or '{}')
    prd_m = prd.get('metrics', {})
    if isinstance(prd_m, str):
        prd_m = json.loads(prd_m or '{}')

    ev_pos = val_m.get('positive_evidence', [])
    ev_neg = val_m.get('contradictory_evidence', []) + val_m.get('missing_evidence', [])

    item = {
        "rank": rank,
        "candidate_id": def_id,
        "evaluation_cluster_id": eval_id,
        "niche": sd.get("niche"),
        "subniche": sd.get("subniche"),
        "normalized_intent": sd.get("normalized_intent"),
        "market": "Global/English",
        "language": "en",
        "profitability_score": prof.get("profitability_score"),
        "viral_score": sd.get("outlier_count"),
        "revenue_score": prof_m.get("revenue_potential_score"),
        "competition_score": mkt.get("competition_score"),
        "evergreen_score": mkt.get("evergreen_score"),
        "production_score": prof_m.get("production_score"),
        "risk_score": prd.get("overall_risk_score"),
        "risk_level": prd.get("risk_level"),
        "content_depth_status": sd.get("content_depth"),
        "distinct_intents_count": sd.get("distinct_intents_count"),
        "confidence": val.get("validation_confidence"),
        "expected_views_range": prof_m.get("expected_views_range", "NOT AVAILABLE"),
        "rpm_range": prof_m.get("rpm_range", "NOT AVAILABLE"),
        "expected_revenue_range": prof_m.get("revenue_scenarios", "NOT AVAILABLE"),
        "expected_cost_range": prof_m.get("production_cost", "NOT AVAILABLE"),
        "expected_profit_range": prof_m.get("profit_scenarios", "NOT AVAILABLE"),
        "evidence_summary": ev_pos if ev_pos else ["NOT AVAILABLE"],
        "counter_evidence": ev_neg if ev_neg else ["NONE"],
        "recommendation": val.get("validation_status"),
        "source_run_linkage": {
            "root_run_id": run_id,
            "profitability_run_id": prof.get("run_id"),
            "market_run_id": mkt.get("run_id"),
            "production_run_id": prd.get("run_id"),
            "validation_run_id": val.get("run_id")
        }
    }
    top20_data.append(item)

# Output JSON
json_path = Path("data/processed/sprint13_gate1_top20.json")
json_path.parent.mkdir(parents=True, exist_ok=True)
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(top20_data, f, indent=2, ensure_ascii=False)
print(f"Wrote {len(top20_data)} candidates to {json_path}")

# Output Markdown
md_path = Path("docs/sprint13_gate1_top20_review.md")
md_path.parent.mkdir(parents=True, exist_ok=True)

with open(md_path, "w", encoding="utf-8") as f:
    f.write("# SPRINT 13 — GATE 1: CANONICAL TOP 20 CANDIDATE REVIEW\n\n")
    f.write(f"**Authoritative Run ID:** `{run_id}`\n\n")
    f.write("| Rank | Candidate ID | Subniche | Normalized Intent | Market | Profitability | Outliers | Revenue | Risk | Depth | Confidence |\n")
    f.write("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
    for d in top20_data:
        prof_s = f"{d['profitability_score']:.1f}" if d['profitability_score'] is not None else "N/A"
        rev_s = f"{d['revenue_score']:.1f}" if d['revenue_score'] is not None else "N/A"
        risk_s = f"{d['risk_score']:.1f}" if d['risk_score'] is not None else "N/A"
        conf_s = f"{d['confidence']:.1f}%" if d['confidence'] is not None else "N/A"
        f.write(f"| {d['rank']} | `{d['candidate_id']}` | {d['subniche']} | `{d['normalized_intent']}` | {d['market']} | {prof_s} | {d['viral_score']} | {rev_s} | {risk_s} ({d['risk_level']}) | {d['content_depth_status']} | {conf_s} |\n")
    
    f.write("\n\n## Detailed Candidate Evidence Breakdown\n\n")
    for d in top20_data:
        f.write(f"### Rank {d['rank']}: {d['candidate_id']} — {d['subniche']} (`{d['normalized_intent']}`)\n")
        f.write(f"- **Niche:** {d['niche']}\n")
        f.write(f"- **Validation Status:** {d['recommendation']}\n")
        f.write(f"- **Confidence:** {d['confidence']:.2f}%\n")
        f.write(f"- **Scores:** Profitability={d['profitability_score']:.2f}, Revenue={d['revenue_score']}, Risk={d['risk_score']} ({d['risk_level']}), Evergreen={d['evergreen_score']}, Competition={d['competition_score']}\n")
        f.write(f"- **Content Depth:** {d['content_depth_status']} ({d['distinct_intents_count']} distinct intents)\n")
        f.write(f"- **Evidence Summary:** {', '.join(d['evidence_summary'])}\n")
        f.write(f"- **Counter-Evidence:** {', '.join(d['counter_evidence'])}\n\n")

print(f"Wrote review markdown to {md_path}")
