"""Create and verify the Sprint 10 schema through the InsForge migration API."""
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.insforge_client import InsForgeClient, InsForgeClientError

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
        raise InsForgeClientError(f"Sprint 10 migration network error: {exc}") from exc
    if response.status_code != 201:
        raise InsForgeClientError(
            f"Sprint 10 migration failed (HTTP {response.status_code}): {response.text}"
        )
    try:
        body = response.json()
    except ValueError as exc:
        raise InsForgeClientError("Invalid Sprint 10 migration JSON response.") from exc
    if (
        not isinstance(body, dict)
        or body.get("version") != MIGRATION_VERSION
        or not body.get("statements")
        or not body.get("message")
    ):
        raise InsForgeClientError(f"Invalid Sprint 10 migration response: {body}")
    return body


def verify_tables(client: InsForgeClient) -> List[str]:
    if not client.url:
        raise InsForgeClientError("INSFORGE_URL is not configured.")
    table = "cluster_validation_analyses"
    try:
        response = httpx.get(
            f"{client.url}/api/database/records/{table}",
            headers=client._get_headers(),
            params={"limit": 1},
            timeout=client.timeout,
        )
    except httpx.RequestError as exc:
        raise InsForgeClientError(
            f"Sprint 10 table verification network error: {exc}"
        ) from exc
    if response.status_code != 200:
        raise InsForgeClientError(
            f"Sprint 10 table {table} is not accessible (HTTP {response.status_code}): {response.text}"
        )
    return [table]


def main() -> None:
    client = InsForgeClient()
    print("Executing Sprint 10 InsForge migration...")
    try:
        res = execute_migration(client)
        print(f"Migration response: {res['message']}")
    except InsForgeClientError as err:
        if "409" in str(err) or "ALREADY_EXISTS" in str(err):
            print("Migration version already applied on InsForge. Verifying tables...")
        else:
            raise err
    tables = verify_tables(client)
    print(f"Verified tables: {tables}")


if __name__ == "__main__":
    main()
