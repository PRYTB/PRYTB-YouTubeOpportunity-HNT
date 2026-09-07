"""Create and verify the Sprint 9 schema through the InsForge migration API."""
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.insforge_client import InsForgeClient, InsForgeClientError

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
        raise InsForgeClientError(f"Sprint 9 migration network error: {exc}") from exc
    if response.status_code != 201:
        raise InsForgeClientError(
            f"Sprint 9 migration failed (HTTP {response.status_code}): {response.text}"
        )
    try:
        body = response.json()
    except ValueError as exc:
        raise InsForgeClientError("Invalid Sprint 9 migration JSON response.") from exc
    if (
        not isinstance(body, dict)
        or body.get("version") != MIGRATION_VERSION
        or not body.get("statements")
        or not body.get("message")
    ):
        raise InsForgeClientError(f"Invalid Sprint 9 migration response: {body}")
    return body


def verify_tables(client: InsForgeClient) -> List[str]:
    if not client.url:
        raise InsForgeClientError("INSFORGE_URL is not configured.")
    table = "cluster_profitability_analyses"
    try:
        response = httpx.get(
            f"{client.url}/api/database/records/{table}",
            headers=client._get_headers(),
            params={"limit": 1},
            timeout=client.timeout,
        )
    except httpx.RequestError as exc:
        raise InsForgeClientError(
            f"Sprint 9 table verification network error: {exc}"
        ) from exc
    if response.status_code != 200:
        raise InsForgeClientError(
            f"Sprint 9 table {table} is not accessible (HTTP {response.status_code}): {response.text}"
        )
    return [table]


if __name__ == "__main__":
    cli_client = InsForgeClient()
    try:
        print("Executing Sprint 9 schema migration...")
        mig_result = execute_migration(cli_client)
        print(f"Migration successful: {mig_result.get('message')}")
        tables = verify_tables(cli_client)
        print(f"Verified tables: {tables}")
    except Exception as err:
        print(f"Migration error: {err}")
        sys.exit(1)
