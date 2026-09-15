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
top20_defs = repo.get_gate7_top20_definitions(run_id)
sem_defs = {d['definition_id']: d for d in repo.get_gate7_semantic_definitions(run_id)}
eval_mapping = json.loads(run_row.notes)['top20_evaluation_mapping']

print("AUDIT OF ALL 20 CANDIDATES:")
print("Rank | DefID | EvalID | OutlierCount (sd) | OutlierScore (prof) | OutlierDiversityVal (val)")
for row in top20_defs:
    def_id = row['definition_id']
    m_item = next(m for m in eval_mapping if m['definition_id'] == def_id)
    eval_id = m_item['evaluation_cluster_id']
    sd = sem_defs[def_id]

    prof = client.execute('SELECT * FROM public.cluster_profitability_analyses WHERE source_cluster_run_id = %s AND cluster_id = %s', [run_id, eval_id])
    prof_m = prof[0]['metrics'] if isinstance(prof[0]['metrics'], dict) else json.loads(prof[0]['metrics'] or '{}')
    
    val = client.execute('SELECT * FROM public.cluster_validation_analyses WHERE source_cluster_run_id = %s AND cluster_id = %s', [run_id, eval_id])
    val_m = val[0]['metrics'] if isinstance(val[0]['metrics'], dict) else json.loads(val[0]['metrics'] or '{}')

    outlier_cnt = sd.get('outlier_count')
    outlier_score = prof_m.get('outlier_score')
    outlier_div_val = val_m.get('outlier_diversity_validation')

    print(f"{row['rank']:2d}   | {def_id:7s} | {eval_id:6d} | {outlier_cnt:17d} | {outlier_score:19.4f} | {outlier_div_val}")
