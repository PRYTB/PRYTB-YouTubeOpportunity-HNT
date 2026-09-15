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

print('POSTGRESQL CONNECTION: OK')
run_row = repo.get_analytical_run(run_id)
print('Run Status:', run_row.status)

top20_defs = repo.get_gate7_top20_definitions(run_id)
sem_defs = {d['definition_id']: d for d in repo.get_gate7_semantic_definitions(run_id)}
eval_mapping = json.loads(run_row.notes)['top20_evaluation_mapping']

for row in top20_defs[:3]:
    def_id = row['definition_id']
    m_item = next(m for m in eval_mapping if m['definition_id'] == def_id)
    eval_id = m_item['evaluation_cluster_id']
    sd = sem_defs[def_id]

    print(f"=== {def_id} (eval_cluster: {eval_id}) ===")
    print("  Outlier Count (sd):", sd.get('outlier_count'))
    print("  Outliers List len:", len(sd.get('outliers', [])))

    val = client.execute('SELECT * FROM public.cluster_validation_analyses WHERE source_cluster_run_id = %s AND cluster_id = %s', [run_id, eval_id])
    if val:
        print("  Validation Confidence:", val[0]['validation_confidence'])
        val_m = val[0]['metrics'] if isinstance(val[0]['metrics'], dict) else json.loads(val[0]['metrics'] or '{}')
        print("  Validation Metrics:", val_m)

    prof = client.execute('SELECT * FROM public.cluster_profitability_analyses WHERE source_cluster_run_id = %s AND cluster_id = %s', [run_id, eval_id])
    if prof:
        print("  Profitability Score:", prof[0]['profitability_score'])
        prof_m = prof[0]['metrics'] if isinstance(prof[0]['metrics'], dict) else json.loads(prof[0]['metrics'] or '{}')
        print("  Profitability Metrics:", prof_m)
