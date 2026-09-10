"""Create and verify the Sprint 10 schema in PostgreSQL."""
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.postgres_client import PostgresClient

MIGRATION_VERSION = "20260907000200"
MIGRATION_NAME = "complete-sprint10-validator-schema"
MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS public.cluster_validation_analyses (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id TEXT NOT NULL,
    source_profitability_run_id TEXT NOT NULL,
    source_cluster_run_id TEXT NOT NULL,
    source_revenue_run_id TEXT NOT NULL,
    source_market_run_id TEXT NOT NULL,
    source_production_run_id TEXT NOT NULL,
    dataset_hash TEXT NOT NULL,
    assignments_hash TEXT NOT NULL,
    methodology_version TEXT NOT NULL DEFAULT 'sprint10-v1',
    cluster_id INTEGER NOT NULL,
    analyzed_at TIMESTAMPTZ NOT NULL,
    quality JSONB NOT NULL,
    metrics JSONB NOT NULL,
    microniche TEXT NOT NULL DEFAULT '',
    profitability_score DOUBLE PRECISION NOT NULL CHECK (profitability_score BETWEEN 0 AND 100),
    validation_score DOUBLE PRECISION NOT NULL CHECK (validation_score BETWEEN 0 AND 100),
    validation_status TEXT NOT NULL CHECK (validation_status IN ('PASS', 'PASS_WITH_WARNINGS', 'WATCH', 'FAIL', 'INSUFFICIENT_EVIDENCE')),
    validation_confidence DOUBLE PRECISION NOT NULL CHECK (validation_confidence BETWEEN 0 AND 100),
    false_positive_risk DOUBLE PRECISION NOT NULL CHECK (false_positive_risk BETWEEN 0 AND 100),
    fragility_score DOUBLE PRECISION NOT NULL CHECK (fragility_score BETWEEN 0 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cluster_validation_run_cluster_key UNIQUE (run_id, cluster_id)
);

CREATE INDEX IF NOT EXISTS cluster_validation_run_id_idx
    ON public.cluster_validation_analyses (run_id);
CREATE INDEX IF NOT EXISTS cluster_validation_source_profitability_run_idx
    ON public.cluster_validation_analyses (source_profitability_run_id);
""".strip()


def execute_migration(client: PostgresClient) -> Dict[str, Any]:
    client.execute(MIGRATION_SQL)
    return {"version": MIGRATION_VERSION, "name": MIGRATION_NAME, "message": "Migration applied"}


def verify_tables(client: PostgresClient) -> List[str]:
    table = "cluster_validation_analyses"
    client.execute(f"SELECT 1 FROM public.{table} LIMIT 1")
    return [table]


def main() -> None:
    client = PostgresClient()
    print("Executing Sprint 10 PostgreSQL migration...")
    res = execute_migration(client)
    print(f"Migration response: {res['message']}")
    tables = verify_tables(client)
    print(f"Verified tables: {tables}")


if __name__ == "__main__":
    main()
