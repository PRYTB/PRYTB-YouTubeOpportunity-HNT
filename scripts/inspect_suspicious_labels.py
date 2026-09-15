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

sem_defs = repo.get_gate7_semantic_definitions(run_id)
print("ALL SEMANTIC DEFINITIONS SUSPICIOUS LABELS INSPECTION:")
for d in sem_defs:
    def_id = d['definition_id']
    niche = d['niche']
    subniche = d['subniche']
    intent = d['normalized_intent']
    if any(k in niche or k in subniche or k in intent for k in ['20', '2025', 'Overview', 'In']):
        print(f"ID: {def_id} | Niche: {niche} | Subniche: {subniche} | Intent: {intent}")
