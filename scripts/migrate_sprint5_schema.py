"""Create and verify the Sprint 5 schema through the InsForge migration API."""
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.insforge_client import InsForgeClient, InsForgeClientError

MIGRATION_VERSION = "20260902000100"
MIGRATION_NAME = "create-sprint5-niche-schema"
MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS public.clusters (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id TEXT NOT NULL,
    cluster_id INTEGER NOT NULL,
    algorithm TEXT NOT NULL,
    semantic_provider TEXT NOT NULL,
    parameters JSONB NOT NULL,
    video_count INTEGER NOT NULL,
    unique_channels INTEGER NOT NULL,
    dominant_channel_share DOUBLE PRECISION NOT NULL,
    semantic_quality DOUBLE PRECISION NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    signal_score DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT clusters_run_cluster_key UNIQUE (run_id, cluster_id)
);

CREATE TABLE IF NOT EXISTS public.subniches (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id TEXT NOT NULL,
    cluster_id INTEGER NOT NULL,
    niche TEXT NOT NULL,
    subniche TEXT NOT NULL,
    microniche TEXT NOT NULL,
    summary TEXT NOT NULL,
    label_confidence DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT subniches_run_cluster_key UNIQUE (run_id, cluster_id),
    CONSTRAINT subniches_cluster_fk FOREIGN KEY (run_id, cluster_id)
        REFERENCES public.clusters (run_id, cluster_id)
);

CREATE TABLE IF NOT EXISTS public.cluster_videos (
    run_id TEXT NOT NULL,
    cluster_id INTEGER NOT NULL,
    video_id TEXT NOT NULL,
    distance_to_centroid DOUBLE PRECISION,
    CONSTRAINT cluster_videos_run_video_key UNIQUE (run_id, video_id),
    CONSTRAINT cluster_videos_cluster_fk FOREIGN KEY (run_id, cluster_id)
        REFERENCES public.clusters (run_id, cluster_id),
    CONSTRAINT cluster_videos_video_fk FOREIGN KEY (video_id)
        REFERENCES public.videos (video_id)
);

CREATE INDEX IF NOT EXISTS clusters_run_id_idx ON public.clusters (run_id);
CREATE INDEX IF NOT EXISTS subniches_run_id_idx ON public.subniches (run_id);
CREATE INDEX IF NOT EXISTS cluster_videos_run_id_idx ON public.cluster_videos (run_id);
""".strip()


def execute_migration(client: InsForgeClient) -> Dict[str, Any]:
    if not client.url:
        raise InsForgeClientError("INSFORGE_URL is not configured.")
    response = httpx.post(
        f"{client.url}/api/database/migrations",
        headers=client._get_headers(),
        json={"version": MIGRATION_VERSION, "name": MIGRATION_NAME, "sql": MIGRATION_SQL},
        timeout=client.timeout,
    )
    if response.status_code != 201:
        raise InsForgeClientError(
            f"Sprint 5 migration failed (HTTP {response.status_code}): {response.text}"
        )
    body = response.json()
    if body.get("version") != MIGRATION_VERSION or not body.get("statements") or not body.get("message"):
        raise InsForgeClientError(f"Invalid Sprint 5 migration response: {body}")
    return body


def verify_tables(client: InsForgeClient) -> List[str]:
    existing = []
    for table in ("clusters", "subniches", "cluster_videos"):
        response = httpx.get(
            f"{client.url}/api/database/records/{table}",
            headers=client._get_headers(),
            params={"limit": 1},
            timeout=client.timeout,
        )
        if response.status_code != 200:
            raise InsForgeClientError(
                f"Sprint 5 table {table} is not accessible (HTTP {response.status_code}): {response.text}"
            )
        existing.append(table)
    return existing


def main() -> None:
    client = InsForgeClient()
    result = execute_migration(client)
    print(f"Migration HTTP 201: {result['message']}")
    for table in verify_tables(client):
        print(f"{table}: EXISTS")


if __name__ == "__main__":
    main()
