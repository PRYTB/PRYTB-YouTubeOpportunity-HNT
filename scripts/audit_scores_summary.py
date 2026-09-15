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
eval_mapping = notes['top20_evaluation_mapping']

top20_defs = repo.get_gate7_top20_definitions(run_id)

print("GATE 1A SCORES AUDIT:")
for row in top20_defs:
    def_id = row['definition_id']
    m_item = next(m for m in eval_mapping if m['definition_id'] == def_id)
    eval_id = m_item['evaluation_cluster_id']

    prof = client.execute('SELECT * FROM public.cluster_profitability_analyses WHERE source_cluster_run_id = %s AND cluster_id = %s', [run_id, eval_id])[0]
    mkt = client.execute('SELECT * FROM public.market_structure_analyses WHERE source_cluster_run_id = %s AND cluster_id = %s', [run_id, eval_id])[0]
    prd = client.execute('SELECT * FROM public.production_risk_analyses WHERE source_cluster_run_id = %s AND cluster_id = %s', [run_id, eval_id])[0]
    val = client.execute('SELECT * FROM public.cluster_validation_analyses WHERE source_cluster_run_id = %s AND cluster_id = %s', [run_id, eval_id])[0]

    prof_m = prof['metrics'] if isinstance(prof['metrics'], dict) else json.loads(prof['metrics'] or '{}')
    mkt_m = mkt['metrics'] if isinstance(mkt['metrics'], dict) else json.loads(mkt['metrics'] or '{}')
    prd_m = prd['metrics'] if isinstance(prd['metrics'], dict) else json.loads(prd['metrics'] or '{}')
    val_m = val['metrics'] if isinstance(val['metrics'], dict) else json.loads(val['metrics'] or '{}')

    prof_score = prof['profitability_score']
    outlier_score = prof_m['outlier_score']
    rev_score = prof_m['revenue_potential_score']
    risk_score = prd['overall_risk_score']
    conf_score = val['validation_confidence']

    r = row['rank']
    print(f"Rank {r:02d} ({def_id}) | Prof: {prof_score:.2f} | True ViralScore: {outlier_score:.2f} | Rev: {rev_score:.2f} | Risk: {risk_score:.2f} | Conf: {conf_score:.2f}%")
