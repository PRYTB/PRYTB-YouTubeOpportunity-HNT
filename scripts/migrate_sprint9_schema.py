"""Create and verify the Sprint 9 schema in PostgreSQL."""
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.postgres_client import PostgresClient

MIGRATION_VERSION = "20260907000100"
MIGRATION_NAME = "complete-sprint9-profitability-schema"
MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS public.cluster_profitability_analyses (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id TEXT NOT NULL,
    source_cluster_run_id TEXT,
    source_revenue_run_id TEXT,
    source_market_run_id TEXT,
    source_production_run_id TEXT,
    dataset_hash TEXT NOT NULL,
    assignments_hash TEXT NOT NULL,
    methodology_version TEXT NOT NULL DEFAULT 'sprint9-v1',
    cluster_id INTEGER NOT NULL,
    analyzed_at TIMESTAMPTZ NOT NULL,
    quality JSONB NOT NULL,
    metrics JSONB NOT NULL,
    microniche TEXT NOT NULL DEFAULT '',
    expected_views_base DOUBLE PRECISION NOT NULL CHECK (expected_views_base >= 0),
    rpm_available BOOLEAN NOT NULL DEFAULT FALSE,
    revenue_available BOOLEAN NOT NULL DEFAULT FALSE,
    cost_money_available BOOLEAN NOT NULL DEFAULT FALSE,
    profit_available BOOLEAN NOT NULL DEFAULT FALSE,
    base_score DOUBLE PRECISION NOT NULL CHECK (base_score BETWEEN 0 AND 100),
    risk_penalty DOUBLE PRECISION NOT NULL CHECK (risk_penalty BETWEEN 0 AND 100),
    profitability_score DOUBLE PRECISION NOT NULL CHECK (profitability_score BETWEEN 0 AND 100),
    classification TEXT NOT NULL CHECK (classification IN ('DISCARD', 'WATCH', 'INTERESTING', 'STRONG', 'EXCEPTIONAL')),
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    component_coverage DOUBLE PRECISION NOT NULL CHECK (component_coverage BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cluster_profitability_run_cluster_key UNIQUE (run_id, cluster_id)
);

CREATE INDEX IF NOT EXISTS cluster_profitability_run_id_idx
    ON public.cluster_profitability_analyses (run_id);
CREATE INDEX IF NOT EXISTS cluster_profitability_source_cluster_run_idx
    ON public.cluster_profitability_analyses (source_cluster_run_id);
""".strip()


def execute_migration(client: PostgresClient) -> Dict[str, Any]:
    client.execute(MIGRATION_SQL)
    return {"version": MIGRATION_VERSION, "name": MIGRATION_NAME, "message": "Migration applied"}


def verify_tables(client: PostgresClient) -> List[str]:
    table = "cluster_profitability_analyses"
    client.execute(f"SELECT 1 FROM public.{table} LIMIT 1")
    return [table]


if __name__ == "__main__":
    cli_client = PostgresClient()
    try:
        print("Executing Sprint 9 schema migration...")
        mig_result = execute_migration(cli_client)
        print(f"Migration successful: {mig_result.get('message')}")
        tables = verify_tables(cli_client)
        print(f"Verified tables: {tables}")
    except Exception as err:
        print(f"Migration error: {err}")
        sys.exit(1)
