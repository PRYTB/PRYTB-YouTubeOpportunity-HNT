import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import json
from app.database.postgres_client import PostgresClient
from app.analytics.text_normalizer import validate_intent_semantic_quality, normalize_intent_string

def run_revalidation():
    db = PostgresClient()
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT definition_id, parent_cluster_id, niche, subniche, microniche, normalized_intent, video_count
                FROM public.gate7_semantic_definitions
                WHERE run_id = 'sprint12_gate7_reconciled_20260914_211554'
                ORDER BY definition_id
            """)
            rows = cur.fetchall()

    print(f"TOTAL DEFINITIONS AUDITED: {len(rows)}")
    valid_list = []
    invalid_list = []

    for r in rows:
        did, p_clust, niche, subniche, microniche, intent, v_count = r
        is_valid, reason = validate_intent_semantic_quality(intent)
        norm_deduped = normalize_intent_string(intent)
        
        item = {
            "definition_id": did,
            "parent_cluster_id": p_clust,
            "raw_intent": intent,
            "normalized_deduped_intent": norm_deduped,
            "is_valid": is_valid,
            "rejection_reason": reason,
            "video_count": v_count
        }
        
        if is_valid:
            valid_list.append(item)
        else:
            invalid_list.append(item)

    print(f"VALID DEFINITIONS COUNT: {len(valid_list)}")
    print(f"INVALID DEFINITIONS COUNT: {len(invalid_list)}")
    print("\n--- INVALID DEFINITIONS DETAILS ---")
    for inv in invalid_list:
        print(f"  {inv['definition_id']}: raw='{inv['raw_intent']}', deduped='{inv['normalized_deduped_intent']}', reason={inv['rejection_reason']}")

if __name__ == "__main__":
    run_revalidation()
