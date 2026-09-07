"""Script to generate deterministic Sprint 12 Dataset Contract from collected production videos."""

import json
import hashlib
import re
from pathlib import Path
from typing import Dict, Any, List
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw" / "sprint12"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
SEED_MANIFEST_PATH = ROOT_DIR / "config" / "sprint12_seed_manifest.json"

_TEST_ID_PATTERN = re.compile(r"(^|[_-])(test|fixture|mock)([_-]|$)", re.IGNORECASE)
_TEST_TEXT_MARKERS = ("integration test", "fixture data", "mock data", "test data")


def clean_text_for_embedding(title: str, description: str | None = None) -> str:
    text = title if description is None else f"{title} {description}"
    text = text.lower()
    text = re.sub(r"https?://\S+|www\.\S+", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    tokens = [t for t in text.split() if len(t) > 1 and not t.isdigit()]
    return " ".join(tokens)


def is_test_video(video: Dict[str, Any]) -> bool:
    video_id = str(video.get("video_id", "") or "")
    text = " ".join(
        (
            str(video.get("title", "") or ""),
            str(video.get("description", "") or ""),
        )
    ).lower()
    return bool(_TEST_ID_PATTERN.search(video_id)) or any(
        marker in text for marker in _TEST_TEXT_MARKERS
    )


def compute_seed_manifest_hash(manifest_path: Path) -> str:
    with open(manifest_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def compute_dataset_hash(rows: List[Dict[str, str]]) -> str:
    # Sort rows deterministically by video_id
    sorted_rows = sorted(rows, key=lambda row: row["video_id"])
    payload = "\n".join(
        f"{row['video_id']}||{row['semantic_text']}" for row in sorted_rows
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    videos_file = RAW_DIR / "sprint12_prod_run_01_videos.json"
    channels_file = RAW_DIR / "sprint12_prod_run_01_channels.json"

    with open(videos_file, "r", encoding="utf-8") as f:
        raw_videos = json.load(f)

    with open(channels_file, "r", encoding="utf-8") as f:
        raw_channels = json.load(f)

    print(f"Loaded {len(raw_videos)} raw videos and {len(raw_channels)} raw channels.")

    seen_video_ids = set()
    production_rows = []
    production_videos = []
    
    test_exclusions = 0
    duplicate_exclusions = 0
    invalid_exclusions = 0

    language_dist = {}
    channel_video_counts = {}

    for v in raw_videos:
        vid = v.get("video_id")
        if not vid or not v.get("title"):
            invalid_exclusions += 1
            continue

        if is_test_video(v):
            test_exclusions += 1
            continue

        if vid in seen_video_ids:
            duplicate_exclusions += 1
            continue

        seen_video_ids.add(vid)
        title = v.get("title", "")
        description = v.get("description", "")
        sem_text = clean_text_for_embedding(title, description)
        sem_text_title = clean_text_for_embedding(title, None)

        row = {
            "video_id": vid,
            "channel_id": v.get("channel_id", ""),
            "title": title,
            "semantic_text": sem_text,
            "semantic_text_title": sem_text_title,
        }
        production_rows.append(row)
        production_videos.append(v)

        lang = v.get("default_audio_language") or v.get("default_language") or "unknown"
        # Simplify language tags e.g. en-US -> en, es-ES -> es
        lang_code = lang.split("-")[0].lower() if lang != "unknown" else "unknown"
        language_dist[lang_code] = language_dist.get(lang_code, 0) + 1

        cid = v.get("channel_id")
        if cid:
            channel_video_counts[cid] = channel_video_counts.get(cid, 0) + 1

    production_rows.sort(key=lambda x: x["video_id"])
    sorted_video_ids = [r["video_id"] for r in production_rows]
    
    dataset_hash = compute_dataset_hash(production_rows)
    seed_manifest_hash = compute_seed_manifest_hash(SEED_MANIFEST_PATH)

    # Channel concentration metrics
    counts = list(channel_video_counts.values())
    total_vids = len(production_rows)
    unique_channels = len(channel_video_counts)

    if counts:
        median_vids = float(np.median(counts))
        p90_vids = float(np.percentile(counts, 90))
        sorted_counts = sorted(counts, reverse=True)
        largest_share = sorted_counts[0] / total_vids if total_vids > 0 else 0.0
        top10_share = sum(sorted_counts[:10]) / total_vids if total_vids > 0 else 0.0
        shares = [c / total_vids for c in counts]
        hhi = float(sum(s**2 for s in shares))
    else:
        median_vids = p90_vids = largest_share = top10_share = hhi = 0.0

    contract = {
        "run_id": "sprint12_prod_run_01",
        "methodology_version": "sprint12-v1",
        "video_count": total_vids,
        "channel_count": unique_channels,
        "sorted_video_ids": sorted_video_ids,
        "dataset_hash": dataset_hash,
        "seed_manifest_hash": seed_manifest_hash,
        "language_distribution": language_dist,
        "exclusions": {
            "test_records": test_exclusions,
            "duplicates": duplicate_exclusions,
            "invalid": invalid_exclusions,
            "raw_total": len(raw_videos),
        },
        "channel_diversity": {
            "unique_channels": unique_channels,
            "median_videos_per_channel": median_vids,
            "p90_videos_per_channel": p90_vids,
            "largest_channel_share": largest_share,
            "top10_channel_share": top10_share,
            "hhi": hhi,
        },
    }

    contract_path = PROCESSED_DIR / "sprint12_dataset_contract.json"
    with open(contract_path, "w", encoding="utf-8") as f:
        json.dump(contract, f, indent=2)

    # Save cleaned production dataset for analytics script use
    cleaned_videos_path = PROCESSED_DIR / "sprint12_production_videos.json"
    with open(cleaned_videos_path, "w", encoding="utf-8") as f:
        json.dump(production_videos, f, indent=2)

    print("\n--- SPRINT 12 DATASET CONTRACT CREATED ---")
    print(f"Contract file: {contract_path}")
    print(f"Cleaned production videos: {cleaned_videos_path}")
    print(f"Production Videos: {total_vids}")
    print(f"Unique Channels: {unique_channels}")
    print(f"Dataset Hash: {dataset_hash}")
    print(f"Seed Manifest Hash: {seed_manifest_hash}")
    print(f"Exclusions: {contract['exclusions']}")
    print(f"Language Dist: {language_dist}")
    print(f"Channel Diversity: Median={median_vids}, P90={p90_vids}, Largest Share={largest_share:.4f}, Top10 Share={top10_share:.4f}, HHI={hhi:.6f}")


if __name__ == "__main__":
    main()
