import argparse
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent

DB_FILE = BACKEND_DIR / "stock.db"
QUICK_BACKUP_FILE = SCRIPT_DIR / "stock.quick.db"
MONTHLY_DIR = SCRIPT_DIR / "db_backups" / "monthly"
LOG_RETENTION_DAYS = 30


def _ensure_dirs():
    MONTHLY_DIR.mkdir(parents=True, exist_ok=True)


def _copy_sqlite(src: Path, dest: Path):
    if not src.exists():
        raise FileNotFoundError(f"Database not found: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(src) as source_conn, sqlite3.connect(dest) as dest_conn:
        source_conn.backup(dest_conn)


def _prune_logs_to_retention(dest: Path, retention_days: int = LOG_RETENTION_DAYS):
    cutoff = (datetime.utcnow() - timedelta(days=retention_days)).isoformat()
    with sqlite3.connect(dest) as conn:
        conn.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff,))
        conn.commit()


def quick_backup():
    """Make a fast overwrite backup after every edit."""
    _copy_sqlite(DB_FILE, QUICK_BACKUP_FILE)
    return QUICK_BACKUP_FILE


def monthly_backup():
    """Save a timestamped backup once every 30 days."""
    _ensure_dirs()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = MONTHLY_DIR / f"stock-monthly-{timestamp}.db"
    _copy_sqlite(DB_FILE, dest)
    _prune_logs_to_retention(dest)
    return dest


def weekly_backup():
    """Backward-compatible alias for the monthly backup command."""
    return monthly_backup()


def restore_backup(backup_path: Path, target_db: Path = DB_FILE):
    """Restore the chosen backup into the live database file."""
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")
    _copy_sqlite(backup_path, target_db)
    return target_db


def restore_quick_backup():
    return restore_backup(QUICK_BACKUP_FILE)


def restore_latest_monthly():
    _ensure_dirs()
    backups = sorted(MONTHLY_DIR.glob("stock-monthly-*.db"))
    if not backups:
        raise FileNotFoundError("No monthly backups found")
    return restore_backup(backups[-1])


def restore_latest_weekly():
    """Backward-compatible alias for the monthly restore command."""
    return restore_latest_monthly()


def main():
    parser = argparse.ArgumentParser(description="SQLite backup helper for CFS Stock")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("quick", help="Create/overwrite the quick backup")
    subparsers.add_parser("monthly", help="Create a timestamped monthly backup")
    subparsers.add_parser("weekly", help=argparse.SUPPRESS)
    subparsers.add_parser("restore-quick", help="Restore the quick overwrite backup")
    subparsers.add_parser("restore-latest-monthly", help="Restore the latest monthly backup")
    subparsers.add_parser("restore-latest-weekly", help=argparse.SUPPRESS)

    restore_file = subparsers.add_parser("restore-file", help="Restore a specific backup file")
    restore_file.add_argument("file", type=Path, help="Path to the backup file")

    args = parser.parse_args()

    if args.command == "quick":
        dest = quick_backup()
        print(f"Quick backup saved to: {dest}")
    elif args.command in {"monthly", "weekly"}:
        dest = monthly_backup()
        print(f"Monthly backup saved to: {dest}")
    elif args.command == "restore-quick":
        dest = restore_quick_backup()
        print(f"Restored quick backup to: {dest}")
    elif args.command in {"restore-latest-monthly", "restore-latest-weekly"}:
        dest = restore_latest_monthly()
        print(f"Restored latest monthly backup to: {dest}")
    elif args.command == "restore-file":
        dest = restore_backup(args.file)
        print(f"Restored backup to: {dest}")


if __name__ == "__main__":
    main()



#run this through task scheduler to run every 30 days and create a monthly backup of the database.

#cd "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend"
#.\venv\Scripts\Activate.ps1
#python backup_db.py monthly



#task scheduler command to run monthly backup of the database
# -NoProfile -ExecutionPolicy Bypass -Command "cd 'D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend'; .\venv\Scripts\python.exe backup\backup_db.py monthly"