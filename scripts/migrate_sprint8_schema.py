"""Create and verify the Sprint 8 schema through the InsForge migration API."""
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.insforge_client import InsForgeClient, InsForgeClientError

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


def execute_migration(client: InsForgeClient) -> Dict[str, Any]:
    if not client.url:
        raise InsForgeClientError("INSFORGE_URL is not configured.")
    try:
        response = httpx.post(
            f"{client.url}/api/database/migrations",
            headers=client._get_headers(),
            json={"version": MIGRATION_VERSION, "name": MIGRATION_NAME, "sql": MIGRATION_SQL},
            timeout=client.timeout,
        )
    except httpx.RequestError as exc:
        raise InsForgeClientError(f"Sprint 8 migration network error: {exc}") from exc
    if response.status_code != 201:
        raise InsForgeClientError(
            f"Sprint 8 migration failed (HTTP {response.status_code}): {response.text}"
        )
    try:
        body = response.json()
    except ValueError as exc:
        raise InsForgeClientError("Invalid Sprint 8 migration JSON response.") from exc
    if (
        not isinstance(body, dict)
        or body.get("version") != MIGRATION_VERSION
        or not body.get("statements")
        or not body.get("message")
    ):
        raise InsForgeClientError(f"Invalid Sprint 8 migration response: {body}")
    return body


def verify_tables(client: InsForgeClient) -> List[str]:
    if not client.url:
        raise InsForgeClientError("INSFORGE_URL is not configured.")
    table = "production_risk_analyses"
    try:
        response = httpx.get(
            f"{client.url}/api/database/records/{table}",
            headers=client._get_headers(),
            params={"limit": 1},
            timeout=client.timeout,
        )
    except httpx.RequestError as exc:
        raise InsForgeClientError(
            f"Sprint 8 table verification network error: {exc}"
        ) from exc
    if response.status_code != 200:
        raise InsForgeClientError(
            f"Sprint 8 table {table} is not accessible (HTTP {response.status_code}): {response.text}"
        )
    return [table]


def main() -> None:
    client = InsForgeClient()
    result = execute_migration(client)
    print(f"Migration HTTP 201: {result['message']}")
    for table in verify_tables(client):
        print(f"{table}: EXISTS")


if __name__ == "__main__":
    main()
