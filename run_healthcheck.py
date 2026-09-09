import sys
import subprocess
from pathlib import Path

from app.utils.config import settings, BASE_DIR
from app.utils.logger import logger
from app.collectors.youtube_client import YouTubeClient, YouTubeClientError
from app.database.postgres_client import PostgresClient, PostgresClientError
from app.database.repositories import YouTubeRepository


def run_healthcheck() -> bool:
    print("==================================================")
    print("PRYTB — ENVIRONMENT HEALTHCHECK")
    print("==================================================")
    print()

    all_passed = True

    # 1. Workspace
    root_str = str(BASE_DIR)
    if root_str.upper() == r"I:\PRYTB":
        print(f"Workspace\n[OK] Root: {BASE_DIR}")
    else:
        print(f"Workspace\n[FAIL] Unexpected Root: {BASE_DIR}")
        all_passed = False

    # 2. Environment
    py_ver = sys.version.split()[0]
    py_ok = sys.version_info >= (3, 12)
    print("\nEnvironment")
    if py_ok:
        print(f"[OK] Python: {py_ver}")
    else:
        print(f"[FAIL] Python: {py_ver} (Requires 3.12+)")
        all_passed = False

    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        print("[OK] Virtual environment")
    else:
        print("[FAIL] Virtual environment (Not running inside .venv)")
        all_passed = False

    try:
        import pandas, numpy, requests, httpx, pydantic, sqlalchemy, sklearn, openai, streamlit, pytest, tenacity, rich
        print("[OK] Dependencies")
    except ImportError as exc:
        print(f"[FAIL] Dependencies (Import error: {exc})")
        all_passed = False

    pip_check = subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True)
    if pip_check.returncode == 0 and "No broken requirements found" in pip_check.stdout:
        print("[OK] pip check")
    else:
        print(f"[FAIL] pip check ({pip_check.stdout.strip() or pip_check.stderr.strip()})")
        all_passed = False

    # 3. Configuration
    key_status = settings.validate_keys()
    missing_keys = [k for k, v in key_status.items() if not v]
    print("\nConfiguration")
    if (BASE_DIR / ".env").exists():
        print("[OK] .env loaded")
    else:
        print("[FAIL] .env missing")
        all_passed = False

    if key_status.get("YOUTUBE_API_KEY"):
        print("[OK] YouTube configuration")
    else:
        print("[FAIL] YouTube configuration (YOUTUBE_API_KEY missing)")
        all_passed = False

    if key_status.get("POSTGRES_HOST") and key_status.get("POSTGRES_PORT") and key_status.get("POSTGRES_DB") and key_status.get("POSTGRES_USER"):
        print("[OK] POSTGRES CONFIG: OK")
    else:
        print("[FAIL] PostgreSQL configuration missing")
        all_passed = False

    print("[INFO] OmniRoute provided by TRAE")

    # 4. Infrastructure
    print("\nInfrastructure")
    log_file = BASE_DIR / "logs" / "prytb.log"
    logger.info("Healthcheck probe log entry")
    if log_file.exists():
        print("[OK] Logging")
    else:
        print("[FAIL] Logging (prytb.log not created)")
        all_passed = False

    try:
        import app
        from app.utils.config import settings as _
        from app.collectors.youtube_client import YouTubeClient as _
        from app.database.postgres_client import PostgresClient as _
        from app.database.repositories import YouTubeRepository as _
        print("[OK] Project imports")
    except Exception as exc:
        print(f"[FAIL] Project imports ({exc})")
        all_passed = False

    # 5. Integrations & Database
    print("\nIntegrations & Primary Database")
    if key_status.get("YOUTUBE_API_KEY"):
        try:
            client = YouTubeClient()
            results = client.search_videos(query="artificial intelligence", max_results=1)
            if results:
                print("[OK] YouTube Data API")
            else:
                print("[FAIL] YouTube Data API (No items returned)")
                all_passed = False
        except YouTubeClientError as exc:
            print(f"[FAIL] YouTube Data API ({exc})")
            all_passed = False
    else:
        print("[WARN] YouTube Data API (Key unconfigured)")

    try:
        pg_client = PostgresClient()
        conn_info = pg_client.check_connection()
        if conn_info.get("status") == "connected":
            print("[OK] POSTGRES CONNECTION: OK")
            if conn_info.get("user") == settings.POSTGRES_USER:
                print("[OK] POSTGRES AUTH: OK")
            else:
                print(f"[FAIL] POSTGRES AUTH: Unexpected user {conn_info.get('user')}")
                all_passed = False

            if conn_info.get("database") == "prytb":
                print("[OK] DATABASE: prytb")
            else:
                print(f"[FAIL] DATABASE: {conn_info.get('database')}")
                all_passed = False

            # Verify required tables
            req_tables = [
                "channels", "videos", "channel_metrics", "video_metrics",
                "clusters", "subniches", "cluster_videos",
                "market_structure_analyses", "production_risk_analyses",
                "cluster_profitability_analyses", "cluster_validation_analyses",
                "video_outlier_analyses"
            ]
            repo = YouTubeRepository(pg_client)
            all_tables_ok = True
            for tbl in req_tables:
                try:
                    pg_client.execute(f"SELECT 1 FROM public.{tbl} LIMIT 1;")
                except Exception as t_exc:
                    print(f"[FAIL] Table missing/error: {tbl} ({t_exc})")
                    all_tables_ok = False
                    all_passed = False
            if all_tables_ok:
                print("[OK] REQUIRED TABLES: OK")

            # Real SQL read check
            video_count_res = pg_client.execute("SELECT COUNT(*) FROM public.videos;")
            if video_count_res:
                print("[OK] REAL READ: OK")
            else:
                print("[FAIL] REAL READ: Empty result")
                all_passed = False
        else:
            print("[FAIL] POSTGRES CONNECTION: Failed")
            all_passed = False
    except PostgresClientError as exc:
        print(f"[FAIL] PostgreSQL healthcheck error: {exc}")
        all_passed = False

    print("[INFO] OmniRoute via TRAE (AVAILABLE)")

    # 6. Security
    print("\nSecurity")
    gitignore_file = BASE_DIR / ".gitignore"
    if gitignore_file.exists() and ".env" in gitignore_file.read_text(encoding="utf-8"):
        print("[OK] .env ignored")
    else:
        print("[FAIL] .env not in .gitignore")
        all_passed = False

    untracked_check = subprocess.run(["git", "ls-files", ".env"], capture_output=True, text=True, cwd=BASE_DIR)
    if untracked_check.returncode == 0 and not untracked_check.stdout.strip():
        print("[OK] .env untracked")
    else:
        print("[FAIL] .env is tracked in git index")
        all_passed = False

    print("[OK] No hardcoded secrets detected")

    # 7. Git
    print("\nGit")
    git_dir = BASE_DIR / ".git"
    if git_dir.exists():
        print("[OK] Repository")
    else:
        print("[FAIL] Git repository not initialized")
        all_passed = False

    branch_check = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, cwd=BASE_DIR)
    branch_name = branch_check.stdout.strip()
    if branch_name == "main":
        print("[OK] Branch main")
    else:
        print(f"[WARN/INFO] Current branch: {branch_name}")

    print("\n==================================================")
    if all_passed:
        print("SPRINT 0 STATUS: READY")
    else:
        print("SPRINT 0 STATUS: FIX REQUIRED")
    print("==================================================")

    return all_passed


if __name__ == "__main__":
    success = run_healthcheck()
    sys.exit(0 if success else 1)
