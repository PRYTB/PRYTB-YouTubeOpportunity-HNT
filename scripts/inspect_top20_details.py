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

print("MAPPING & SCORES FOR TOP 20:")
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

    print(f"Rank {rank:02d} | DefID: {def_id} | EvalID: {eval_id} | Subniche: {sd['subniche']} | Intent: {sd['normalized_intent']}")
    print(f"   ProfitabilityScore: {prof.get('profitability_score')} | BaseScore: {prof.get('base_score')} | RiskPenalty: {prof.get('risk_penalty')}")
    print(f"   MarketCompScore: {mkt.get('competition_score')} | EvergreenScore: {mkt.get('evergreen_score')}")
    print(f"   ProdOverallRiskScore: {prd.get('overall_risk_score')} | RiskLevel: {prd.get('risk_level')}")
    print(f"   Depth: {sd['content_depth']} ({sd['distinct_intents_count']} intents) | Confidence: {val.get('validation_confidence')}")
    print(f"   ProfMetrics: {prof_m}")
    print(f"   ValMetrics: {val_m}")
