"""Create and verify the Sprint 8 schema in PostgreSQL."""
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.postgres_client import PostgresClient

MIGRATION_VERSION = "20260904000100"
MIGRATION_NAME = "complete-sprint8-production-risk-schema"
MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS public.production_risk_analyses (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id TEXT NOT NULL,
    source_market_structure_run_id TEXT,
    source_cluster_run_id TEXT,
    cluster_id INTEGER NOT NULL,
    analyzed_at TIMESTAMPTZ NOT NULL,
    config JSONB NOT NULL,
    quality JSONB NOT NULL,
    metrics JSONB NOT NULL,
    microniche TEXT NOT NULL DEFAULT '',
    production_cost_score DOUBLE PRECISION NOT NULL CHECK (production_cost_score BETWEEN 0 AND 100),
    estimated_hours_low DOUBLE PRECISION CHECK (estimated_hours_low >= 0),
    estimated_hours_high DOUBLE PRECISION CHECK (estimated_hours_high >= 0),
    production_complexity TEXT NOT NULL CHECK (production_complexity IN ('LOW', 'MEDIUM', 'HIGH', 'UNKNOWN')),
    overall_risk_score DOUBLE PRECISION CHECK (overall_risk_score BETWEEN 0 AND 100),
    risk_level TEXT NOT NULL CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'UNKNOWN')),
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT production_risk_hour_bounds CHECK (
        estimated_hours_low IS NULL OR estimated_hours_high IS NULL
        OR estimated_hours_low <= estimated_hours_high
    ),
    CONSTRAINT production_risk_run_cluster_key UNIQUE (run_id, cluster_id)
);

CREATE INDEX IF NOT EXISTS production_risk_run_id_idx
    ON public.production_risk_analyses (run_id);
CREATE INDEX IF NOT EXISTS production_risk_source_market_run_idx
    ON public.production_risk_analyses (source_market_structure_run_id);
CREATE INDEX IF NOT EXISTS production_risk_source_cluster_run_idx
    ON public.production_risk_analyses (source_cluster_run_id);
""".strip()


def execute_migration(client: PostgresClient) -> Dict[str, Any]:
    client.execute(MIGRATION_SQL)
    return {"version": MIGRATION_VERSION, "name": MIGRATION_NAME, "message": "Migration applied"}


def verify_tables(client: PostgresClient) -> List[str]:
    table = "production_risk_analyses"
    client.execute(f"SELECT 1 FROM public.{table} LIMIT 1")
    return [table]


def main() -> None:
    client = PostgresClient()
    result = execute_migration(client)
    print(result["message"])
    for table in verify_tables(client):
        print(f"{table}: EXISTS")


if __name__ == "__main__":
    main()
