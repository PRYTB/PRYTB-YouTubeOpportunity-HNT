"""Create and verify the Sprint 5 schema in PostgreSQL."""
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.postgres_client import PostgresClient

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
    CONSTRAINT subniches_cluster_fk FOREIGN KEY (run_id, cluster_id) REFERENCES public.clusters (run_id, cluster_id)
);
CREATE TABLE IF NOT EXISTS public.cluster_videos (
    run_id TEXT NOT NULL,
    cluster_id INTEGER NOT NULL,
    video_id TEXT NOT NULL,
    distance_to_centroid DOUBLE PRECISION,
    CONSTRAINT cluster_videos_run_video_key UNIQUE (run_id, video_id),
    CONSTRAINT cluster_videos_cluster_fk FOREIGN KEY (run_id, cluster_id) REFERENCES public.clusters (run_id, cluster_id),
    CONSTRAINT cluster_videos_video_fk FOREIGN KEY (video_id) REFERENCES public.videos (video_id)
);
CREATE INDEX IF NOT EXISTS clusters_run_id_idx ON public.clusters (run_id);
CREATE INDEX IF NOT EXISTS subniches_run_id_idx ON public.subniches (run_id);
CREATE INDEX IF NOT EXISTS cluster_videos_run_id_idx ON public.cluster_videos (run_id);
""".strip()


def execute_migration(client: PostgresClient) -> dict:
    client.execute(MIGRATION_SQL)
    return {"version": MIGRATION_VERSION, "name": MIGRATION_NAME, "message": "Migration applied"}


def verify_tables(client: PostgresClient) -> List[str]:
    tables = ["clusters", "subniches", "cluster_videos"]
    for table in tables:
        client.execute(f"SELECT 1 FROM public.{table} LIMIT 1")
    return tables


def main() -> None:
    client = PostgresClient()
    result = execute_migration(client)
    print(result["message"])
    for table in verify_tables(client):
        print(f"{table}: EXISTS")


if __name__ == "__main__":
    main()
