import json
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.models.youtube import YouTubeVideo, YouTubeChannel, CollectionResult
from app.database.repositories import YouTubeRepository
from app.utils.logger import logger

def main():
    raw_dir = BASE_DIR / "data/raw/sprint12"
    v_path = raw_dir / "sprint12_prod_run_01_videos.json"
    c_path = raw_dir / "sprint12_prod_run_01_channels.json"

    with open(v_path, "r", encoding="utf-8") as f:
        videos_data = json.load(f)
    with open(c_path, "r", encoding="utf-8") as f:
        channels_data = json.load(f)

    # Clean & exclude synthetic test items
    videos = [
        YouTubeVideo(**item) for item in videos_data
        if item.get("video_id") not in ("VID_TEST_INTEGRATION_99", "TEST_VID_001", "TEST_VID_002")
        and "test" not in item.get("video_id", "").lower()
    ]
    channels = [
        YouTubeChannel(**item) for item in channels_data
        if item.get("channel_id") not in ("CH_TEST_99",)
        and "test" not in item.get("channel_id", "").lower()
    ]

    repo = YouTubeRepository()

    v_db_before_records = repo.get_all_videos()
    c_db_before_records = repo.get_all_channels()

    v_db_before = len(v_db_before_records)
    c_db_before = len(c_db_before_records)

    v_db_before_ids = {r["video_id"] for r in v_db_before_records if "video_id" in r}
    c_db_before_ids = {r["channel_id"] for r in c_db_before_records if "channel_id" in r}

    exp_v_ids = {v.video_id for v in videos}
    exp_c_ids = {c.channel_id for c in channels}

    print(f"Expected canonical videos: {len(exp_v_ids)}")
    print(f"Expected canonical channels: {len(exp_c_ids)}")
    print(f"DB Videos total before: {v_db_before}")
    print(f"DB Channels total before: {c_db_before}")

    # Chunked upsert to InsForge (CHANNELS FIRST due to FK constraint on videos.channel_id)
    batch_size = 500
    for i in range(0, len(channels), batch_size):
        batch = channels[i:i + batch_size]
        repo.upsert_channels(batch)
        repo.insert_channel_metrics(batch)

    for i in range(0, len(videos), batch_size):
        batch = videos[i:i + batch_size]
        repo.upsert_videos(batch)
        repo.insert_video_metrics(batch)

    v_db_after_records = repo.get_all_videos()
    c_db_after_records = repo.get_all_channels()

    v_db_after = len(v_db_after_records)
    c_db_after = len(c_db_after_records)

    v_db_after_ids = {r["video_id"] for r in v_db_after_records if "video_id" in r}
    c_db_after_ids = {r["channel_id"] for r in c_db_after_records if "channel_id" in r}

    found_v = exp_v_ids.intersection(v_db_after_ids)
    missing_v = exp_v_ids - v_db_after_ids

    found_c = exp_c_ids.intersection(c_db_after_ids)
    missing_c = exp_c_ids - c_db_after_ids

    v_created = len(exp_v_ids - v_db_before_ids)
    v_updated = len(exp_v_ids.intersection(v_db_before_ids))

    c_created = len(exp_c_ids - c_db_before_ids)
    c_updated = len(exp_c_ids.intersection(c_db_before_ids))

    print("--- SYNC SUMMARY ---")
    print(f"Videos expected: {len(exp_v_ids)}")
    print(f"Videos DB before: {v_db_before}")
    print(f"Videos created: {v_created}")
    print(f"Videos updated/existing: {v_updated}")
    print(f"Videos DB after: {v_db_after}")
    print(f"Videos Sprint12 found: {len(found_v)}")
    print(f"Videos missing: {len(missing_v)}")

    print("--- CHANNELS SUMMARY ---")
    print(f"Channels expected: {len(exp_c_ids)}")
    print(f"Channels DB before: {c_db_before}")
    print(f"Channels created: {c_created}")
    print(f"Channels updated/existing: {c_updated}")
    print(f"Channels DB after: {c_db_after}")
    print(f"Channels Sprint12 found: {len(found_c)}")
    print(f"Channels missing: {len(missing_c)}")

if __name__ == "__main__":
    main()
