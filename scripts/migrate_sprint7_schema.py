"""Create and verify the Sprint 7 schema in PostgreSQL."""
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.postgres_client import PostgresClient

MIGRATION_VERSION = "20260903000200"
MIGRATION_NAME = "complete-sprint7-market-structure-schema"
MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS public.market_structure_analyses (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id TEXT NOT NULL,
    source_cluster_run_id TEXT,
    cluster_id INTEGER NOT NULL,
    analyzed_at TIMESTAMPTZ NOT NULL,
    config JSONB NOT NULL,
    quality JSONB NOT NULL,
    metrics JSONB NOT NULL,
    competition_score DOUBLE PRECISION NOT NULL CHECK (competition_score BETWEEN 0 AND 100),
    accessibility_score DOUBLE PRECISION NOT NULL CHECK (accessibility_score BETWEEN 0 AND 100),
    content_depth_score DOUBLE PRECISION NOT NULL CHECK (content_depth_score BETWEEN 0 AND 100),
    evergreen_score DOUBLE PRECISION NOT NULL CHECK (evergreen_score BETWEEN 0 AND 100),
    market_structure_class TEXT NOT NULL CHECK (market_structure_class IN (
        'VIRAL_SATURATED', 'CONTENT_CONSTRAINED',
        'SUSTAINABLE_ACCESSIBLE', 'UNCERTAIN'
    )),
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT market_structure_run_cluster_key UNIQUE (run_id, cluster_id)
);

CREATE INDEX IF NOT EXISTS market_structure_run_id_idx
    ON public.market_structure_analyses (run_id);
CREATE INDEX IF NOT EXISTS market_structure_source_run_idx
    ON public.market_structure_analyses (source_cluster_run_id);

ALTER TABLE public.market_structure_analyses
    ADD COLUMN IF NOT EXISTS microniche TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS top_5_rank INTEGER CHECK (top_5_rank BETWEEN 1 AND 5),
    ADD COLUMN IF NOT EXISTS market_structure_score DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (market_structure_score BETWEEN 0 AND 100),
    ADD COLUMN IF NOT EXISTS trend_score DOUBLE PRECISION CHECK (trend_score BETWEEN 0 AND 100),
    ADD COLUMN IF NOT EXISTS evergreen_class TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (evergreen_class IN (
        'TREND', 'SEMI_EVERGREEN', 'EVERGREEN', 'UNKNOWN'
    ));
""".strip()


def execute_migration(client: PostgresClient) -> Dict[str, Any]:
    client.execute(MIGRATION_SQL)
    return {"version": MIGRATION_VERSION, "name": MIGRATION_NAME, "message": "Migration applied"}


def verify_tables(client: PostgresClient) -> List[str]:
    table = "market_structure_analyses"
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
