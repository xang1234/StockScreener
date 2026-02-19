"""
Database integrity check and repair script.

Checks SQLite database for corruption and optionally repairs it using
the sqlite3 CLI dump-and-reload method (most resilient) or Python
iterdump() as fallback.

Usage:
    cd backend
    python scripts/check_db_integrity.py              # Check only
    python scripts/check_db_integrity.py --quick       # Quick check (faster)
    python scripts/check_db_integrity.py --repair      # Check + repair if corrupt
    python scripts/check_db_integrity.py --repair --yes # Repair without confirmation
"""
import sys
import os
import argparse
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings


def get_db_path() -> str:
    """Extract database file path from the SQLAlchemy URL."""
    return settings.database_url.replace("sqlite:///", "")


def get_db_info(db_path: str) -> dict:
    """Gather database file information."""
    info = {}
    info["db_path"] = db_path
    info["db_exists"] = os.path.exists(db_path)

    if info["db_exists"]:
        info["db_size_mb"] = os.path.getsize(db_path) / (1024 * 1024)
    else:
        info["db_size_mb"] = 0

    wal_path = db_path + "-wal"
    info["wal_exists"] = os.path.exists(wal_path)
    info["wal_size_mb"] = os.path.getsize(wal_path) / (1024 * 1024) if info["wal_exists"] else 0

    shm_path = db_path + "-shm"
    info["shm_exists"] = os.path.exists(shm_path)
    info["shm_size_mb"] = os.path.getsize(shm_path) / (1024 * 1024) if info["shm_exists"] else 0

    return info


def get_active_processes(db_path: str) -> list:
    """Check for processes that have the database file open."""
    active = []
    for suffix in ("", "-wal", "-shm"):
        fpath = db_path + suffix
        if not os.path.exists(fpath):
            continue
        try:
            result = subprocess.run(
                ["lsof", fpath],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.strip().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 2:
                    active.append(f"{parts[0]} (PID {parts[1]}) -> {fpath}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    return active


def check_journal_mode(db_path: str) -> str:
    """Check the current journal mode."""
    try:
        conn = sqlite3.connect(db_path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        return mode
    except Exception as e:
        return f"error: {e}"


def run_integrity_check(db_path: str, quick: bool = False) -> tuple[bool, str]:
    """
    Run SQLite integrity check.

    Returns:
        (is_ok, result_text)
    """
    pragma = "PRAGMA quick_check" if quick else "PRAGMA integrity_check"
    check_type = "quick_check" if quick else "integrity_check"

    print(f"\nRunning {check_type}...")
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA busy_timeout=30000")
        results = conn.execute(pragma).fetchall()
        conn.close()

        # integrity_check returns "ok" if everything is fine,
        # otherwise returns a list of problems
        if len(results) == 1 and results[0][0] == "ok":
            return True, "ok"
        else:
            problems = "\n".join(row[0] for row in results[:50])
            if len(results) > 50:
                problems += f"\n... and {len(results) - 50} more issues"
            return False, problems

    except Exception as e:
        return False, f"Error running {check_type}: {e}"


def repair_with_sqlite3_cli(db_path: str, recovered_path: str) -> bool:
    """
    Repair database using sqlite3 CLI .dump command.

    This is the most resilient method — the sqlite3 shell reads raw pages
    and can recover data from partially corrupted B-trees.

    Returns:
        True if repair succeeded
    """
    sqlite3_bin = shutil.which("sqlite3")
    if not sqlite3_bin:
        print("  sqlite3 CLI not found, falling back to Python iterdump()")
        return False

    print(f"  Using sqlite3 CLI: {sqlite3_bin}")
    print(f"  Dumping database to SQL...")

    try:
        # .dump outputs CREATE TABLE + INSERT statements as SQL text
        dump_proc = subprocess.run(
            [sqlite3_bin, db_path, ".dump"],
            capture_output=True, text=True, timeout=600,  # 10 min timeout
        )

        if not dump_proc.stdout:
            print(f"  ERROR: sqlite3 .dump produced no output")
            if dump_proc.stderr:
                print(f"  stderr: {dump_proc.stderr[:500]}")
            return False

        sql_size = len(dump_proc.stdout)
        print(f"  Dump complete: {sql_size / (1024*1024):.1f} MB of SQL")

        if dump_proc.stderr:
            # .dump may print warnings about corrupt rows but still produce output
            stderr_lines = dump_proc.stderr.strip().splitlines()
            print(f"  Warnings during dump ({len(stderr_lines)} lines):")
            for line in stderr_lines[:10]:
                print(f"    {line}")
            if len(stderr_lines) > 10:
                print(f"    ... and {len(stderr_lines) - 10} more")

        # Load the dump into a fresh database
        print(f"  Loading dump into recovered database...")
        load_proc = subprocess.run(
            [sqlite3_bin, recovered_path],
            input=dump_proc.stdout, capture_output=True, text=True, timeout=600,
        )

        if load_proc.returncode != 0:
            print(f"  ERROR: Failed to load dump into recovered DB")
            if load_proc.stderr:
                print(f"  stderr: {load_proc.stderr[:500]}")
            return False

        print(f"  Recovered database created successfully")
        return True

    except subprocess.TimeoutExpired:
        print(f"  ERROR: sqlite3 command timed out after 10 minutes")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def repair_with_iterdump(db_path: str, recovered_path: str) -> bool:
    """
    Repair database using Python's sqlite3.iterdump().

    Fallback method when sqlite3 CLI is not available. Less resilient
    than the CLI method but works in environments without the binary.

    Returns:
        True if repair succeeded
    """
    print(f"  Using Python iterdump() fallback...")

    try:
        source = sqlite3.connect(db_path)
        dest = sqlite3.connect(recovered_path)

        row_count = 0
        errors = 0
        for line in source.iterdump():
            try:
                dest.execute(line)
                row_count += 1
            except Exception as e:
                errors += 1
                if errors <= 10:
                    print(f"    Warning: skipped statement due to {e}")

        dest.commit()
        source.close()
        dest.close()

        print(f"  iterdump complete: {row_count} statements, {errors} errors")
        return errors == 0 or row_count > 0

    except Exception as e:
        print(f"  ERROR: iterdump failed: {e}")
        return False


def repair_database(db_path: str, skip_confirmation: bool = False) -> bool:
    """
    Repair a corrupted database.

    Steps:
    1. Create timestamped backup
    2. Try sqlite3 CLI dump, fall back to iterdump()
    3. Verify integrity of recovered DB
    4. Swap recovered DB into place
    5. Enable WAL mode on the new DB

    Returns:
        True if repair succeeded
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{timestamp}"
    recovered_path = f"{db_path}.recovered_{timestamp}"

    # Check for active processes
    active = get_active_processes(db_path)
    if active:
        print("\n  WARNING: Other processes have the database open:")
        for proc in active:
            print(f"    - {proc}")
        print("\n  For safest repair, stop all services first:")
        print("    docker-compose down  # or stop uvicorn + celery")

        if not skip_confirmation:
            response = input("\n  Continue anyway? (yes/no): ").strip().lower()
            if response != "yes":
                print("  Repair cancelled.")
                return False

    # Step 1: Backup
    print(f"\n  Step 1: Creating backup...")
    print(f"    {backup_path}")
    shutil.copy2(db_path, backup_path)
    # Also backup WAL/SHM if they exist
    for suffix in ("-wal", "-shm"):
        src = db_path + suffix
        if os.path.exists(src):
            shutil.copy2(src, backup_path + suffix)
            print(f"    {backup_path + suffix}")
    print(f"  Backup complete")

    # Step 2: Dump and reload
    print(f"\n  Step 2: Recovering data...")
    if not repair_with_sqlite3_cli(db_path, recovered_path):
        if not repair_with_iterdump(db_path, recovered_path):
            print("\n  REPAIR FAILED: Both recovery methods failed.")
            print(f"  Backup preserved at: {backup_path}")
            return False

    # Step 3: Verify recovered DB
    print(f"\n  Step 3: Verifying recovered database...")
    recovered_size = os.path.getsize(recovered_path) / (1024 * 1024)
    original_size = os.path.getsize(db_path) / (1024 * 1024)
    print(f"    Original size: {original_size:.1f} MB")
    print(f"    Recovered size: {recovered_size:.1f} MB")

    if recovered_size < original_size * 0.5:
        print(f"  WARNING: Recovered DB is less than 50% of original size!")
        print(f"  This may indicate significant data loss.")
        if not skip_confirmation:
            response = input("  Continue with swap? (yes/no): ").strip().lower()
            if response != "yes":
                print(f"  Recovered DB preserved at: {recovered_path}")
                print(f"  Backup preserved at: {backup_path}")
                return False

    is_ok, result = run_integrity_check(recovered_path, quick=False)
    if not is_ok:
        print(f"\n  REPAIR FAILED: Recovered database also has integrity issues:")
        print(f"    {result[:500]}")
        print(f"  Recovered DB preserved at: {recovered_path}")
        print(f"  Backup preserved at: {backup_path}")
        return False

    print(f"  Integrity check: ok")

    # Step 4: Enable WAL on recovered DB
    print(f"\n  Step 4: Enabling WAL mode on recovered database...")
    conn = sqlite3.connect(recovered_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.close()

    # Step 5: Swap
    print(f"\n  Step 5: Swapping databases...")
    if not skip_confirmation:
        response = input("  Replace original with recovered? (yes/no): ").strip().lower()
        if response != "yes":
            print(f"  Swap cancelled.")
            print(f"  Recovered DB at: {recovered_path}")
            print(f"  Backup at: {backup_path}")
            return False

    os.replace(recovered_path, db_path)
    # Remove old WAL/SHM files (new DB has its own)
    for suffix in ("-wal", "-shm"):
        old = db_path + suffix
        if os.path.exists(old):
            os.remove(old)

    print(f"  Swap complete!")
    print(f"\n  Backup preserved at: {backup_path}")
    print(f"  Restart services to pick up the new database.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Check and repair SQLite database integrity")
    parser.add_argument("--quick", action="store_true", help="Run quick_check instead of full integrity_check")
    parser.add_argument("--repair", action="store_true", help="Attempt repair if corruption is detected")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")
    args = parser.parse_args()

    db_path = get_db_path()

    print("=" * 80)
    print("DATABASE INTEGRITY CHECK")
    print("=" * 80)

    # Gather info
    info = get_db_info(db_path)
    print(f"\nDatabase: {info['db_path']}")
    print(f"  Exists: {info['db_exists']}")

    if not info["db_exists"]:
        print("\nERROR: Database file not found!")
        print(f"  Expected at: {db_path}")
        print(f"  Check DATABASE_URL in your .env file")
        sys.exit(1)

    print(f"  Size: {info['db_size_mb']:.1f} MB")
    print(f"  WAL file: {'yes' if info['wal_exists'] else 'no'} ({info['wal_size_mb']:.1f} MB)")
    print(f"  SHM file: {'yes' if info['shm_exists'] else 'no'}")

    # Journal mode
    journal_mode = check_journal_mode(db_path)
    print(f"  Journal mode: {journal_mode}")
    if journal_mode != "wal":
        print(f"  WARNING: Expected WAL mode. Concurrent writes may cause corruption.")

    # Active processes
    active = get_active_processes(db_path)
    if active:
        print(f"\n  Active processes ({len(active)}):")
        for proc in active:
            print(f"    - {proc}")
    else:
        print(f"  Active processes: none detected")

    # Run integrity check
    is_ok, result = run_integrity_check(db_path, quick=args.quick)

    if is_ok:
        print(f"\n{'='*80}")
        print(f"RESULT: Database integrity OK")
        print(f"{'='*80}")
        sys.exit(0)
    else:
        print(f"\n{'='*80}")
        print(f"RESULT: CORRUPTION DETECTED")
        print(f"{'='*80}")
        print(f"\nIssues found:")
        print(result)

        if args.repair:
            print(f"\n{'='*80}")
            print("STARTING REPAIR")
            print(f"{'='*80}")

            if not args.yes:
                response = input("\nProceed with repair? (yes/no): ").strip().lower()
                if response != "yes":
                    print("Repair cancelled.")
                    sys.exit(1)

            success = repair_database(db_path, skip_confirmation=args.yes)
            if success:
                print(f"\n{'='*80}")
                print("REPAIR SUCCESSFUL")
                print(f"{'='*80}")
                sys.exit(0)
            else:
                print(f"\n{'='*80}")
                print("REPAIR FAILED")
                print(f"{'='*80}")
                sys.exit(1)
        else:
            print(f"\nTo attempt repair, run:")
            print(f"  python scripts/check_db_integrity.py --repair")
            sys.exit(1)


if __name__ == "__main__":
    main()
