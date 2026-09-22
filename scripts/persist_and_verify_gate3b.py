import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import json
import hashlib
from app.database.postgres_client import PostgresClient

def persist_and_verify_gate3b():
    db = PostgresClient()
    gate3b_run_id = "sprint13_gate3b_audit_20260922"
    authoritative_gate3_run_id = "sprint13_gate3_sprint12_gate7_reconciled_20260914_211554"
    
    finalists_meta = [
        {
            "candidate_id": "def_039",
            "old_intent": "calendar c¾mo",
            "canonical_label": "Productividad y Gestión de Tareas con Notion",
            "semantic_classification": "VALID_BUT_LABEL_BROKEN",
            "support_videos_count": 27,
            "support_channels_count": 19,
            "encoding_status": "CLEAN_UTF8_DB_TERMINAL_DISPLAY_ARTIFACT",
            "normalization_status": "REPAIRED_DISPLAY_LABEL",
            "profitability_score": 50.05638012646635,
            "economically_qualified": True,
            "semantically_qualified": True,
            "top3_eligible": True,
            "lineage": "Gate3 Expansion Candidate (Cluster 7)"
        },
        {
            "candidate_id": "def_045",
            "old_intent": "de de software",
            "canonical_label": "Desarrollo y Arquitectura de Software / SaaS",
            "semantic_classification": "VALID_BUT_LABEL_BROKEN",
            "support_videos_count": 208,
            "support_channels_count": 143,
            "encoding_status": "CLEAN_UTF8",
            "normalization_status": "REPAIRED_REDUNDANT_STOPWORDS",
            "profitability_score": 50.05638012646635,
            "economically_qualified": True,
            "semantically_qualified": True,
            "top3_eligible": True,
            "lineage": "Gate2B Top20 Baseline Qualifier (Cluster 11)"
        },
        {
            "candidate_id": "def_052",
            "old_intent": "es la",
            "canonical_label": "REJECTED (NORMALIZATION_ARTIFACT)",
            "semantic_classification": "NORMALIZATION_ARTIFACT",
            "support_videos_count": 235,
            "support_channels_count": 206,
            "encoding_status": "CLEAN_UTF8",
            "normalization_status": "REJECTED_STOPWORD_COOCCURRENCE",
            "profitability_score": 50.064134897360704,
            "economically_qualified": True,
            "semantically_qualified": False,
            "top3_eligible": False,
            "lineage": "Gate2B Top20 Baseline Qualifier (Cluster 8)"
        }
    ]
    
    # Sort finalists deterministically by candidate_id
    finalists_meta = sorted(finalists_meta, key=lambda x: x["candidate_id"])
    
    payload = {
        "gate3b_run_id": gate3b_run_id,
        "authoritative_gate3_run_id": authoritative_gate3_run_id,
        "audited_finalists": finalists_meta,
        "universe_definitions_audited": 58,
        "systemic_stopword_artifacts_count": 3,
        "systemic_stopword_artifact_ids": ["def_046", "def_051", "def_052"],
        "economically_qualified_count": 3,
        "semantically_qualified_count": 2,
        "final_eligible_pool_count": 2,
        "final_eligible_pool_ids": ["def_039", "def_045"],
        "at_least_three_condition": False,
        "top3_review_readiness": False,
        "top3_selected": False
    }
    
    payload_str = json.dumps(payload, sort_keys=True)
    dataset_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            # Delete any previous gate3b audit run if exists
            cur.execute("DELETE FROM public.analytical_runs WHERE run_id = %s", (gate3b_run_id,))
            cur.execute("""
                INSERT INTO public.analytical_runs (run_id, dataset_hash, notes, created_at)
                VALUES (%s, %s, %s, NOW())
            """, (gate3b_run_id, dataset_hash, payload_str))
        conn.commit()
    print(f"Persisted Gate3B record successfully. Hash: {dataset_hash}")
    
    # Readback Pass 1
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT run_id, dataset_hash, notes FROM public.analytical_runs WHERE run_id = %s", (gate3b_run_id,))
            r1 = cur.fetchone()
            notes1 = json.loads(r1[2]) if isinstance(r1[2], str) else r1[2]
            p1_str = json.dumps(notes1, sort_keys=True)
            hash1 = hashlib.sha256(p1_str.encode("utf-8")).hexdigest()

    # Readback Pass 2
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT run_id, dataset_hash, notes FROM public.analytical_runs WHERE run_id = %s", (gate3b_run_id,))
            r2 = cur.fetchone()
            notes2 = json.loads(r2[2]) if isinstance(r2[2], str) else r2[2]
            p2_str = json.dumps(notes2, sort_keys=True)
            hash2 = hashlib.sha256(p2_str.encode("utf-8")).hexdigest()

    print(f"Readback Hash Pass 1: {hash1}")
    print(f"Readback Hash Pass 2: {hash2}")
    print(f"Hashes Match: {hash1 == hash2 and hash1 == dataset_hash}")

if __name__ == "__main__":
    persist_and_verify_gate3b()
