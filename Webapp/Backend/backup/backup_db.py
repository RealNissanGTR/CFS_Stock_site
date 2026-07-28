import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent

DB_FILE = BACKEND_DIR / "stock.db"
QUICK_BACKUP_FILE = SCRIPT_DIR / "stock.quick.db"
WEEKLY_DIR = SCRIPT_DIR / "db_backups" / "weekly"


def _ensure_dirs():
    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)


def _copy_sqlite(src: Path, dest: Path):
    if not src.exists():
        raise FileNotFoundError(f"Database not found: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(src) as source_conn, sqlite3.connect(dest) as dest_conn:
        source_conn.backup(dest_conn)


def quick_backup():
    """Make a fast overwrite backup after every edit."""
    _copy_sqlite(DB_FILE, QUICK_BACKUP_FILE)
    return QUICK_BACKUP_FILE


def weekly_backup():
    """Save a timestamped backup once per week."""
    _ensure_dirs()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = WEEKLY_DIR / f"stock-weekly-{timestamp}.db"
    _copy_sqlite(DB_FILE, dest)
    return dest


def restore_backup(backup_path: Path, target_db: Path = DB_FILE):
    """Restore the chosen backup into the live database file."""
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")
    _copy_sqlite(backup_path, target_db)
    return target_db


def restore_quick_backup():
    return restore_backup(QUICK_BACKUP_FILE)


def restore_latest_weekly():
    _ensure_dirs()
    backups = sorted(WEEKLY_DIR.glob("stock-weekly-*.db"))
    if not backups:
        raise FileNotFoundError("No weekly backups found")
    return restore_backup(backups[-1])


def main():
    parser = argparse.ArgumentParser(description="SQLite backup helper for CFS Stock")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("quick", help="Create/overwrite the quick backup")
    subparsers.add_parser("weekly", help="Create a timestamped weekly backup")
    subparsers.add_parser("restore-quick", help="Restore the quick overwrite backup")
    subparsers.add_parser("restore-latest-weekly", help="Restore the latest weekly backup")

    restore_file = subparsers.add_parser("restore-file", help="Restore a specific backup file")
    restore_file.add_argument("file", type=Path, help="Path to the backup file")

    args = parser.parse_args()

    if args.command == "quick":
        dest = quick_backup()
        print(f"Quick backup saved to: {dest}")
    elif args.command == "weekly":
        dest = weekly_backup()
        print(f"Weekly backup saved to: {dest}")
    elif args.command == "restore-quick":
        dest = restore_quick_backup()
        print(f"Restored quick backup to: {dest}")
    elif args.command == "restore-latest-weekly":
        dest = restore_latest_weekly()
        print(f"Restored latest weekly backup to: {dest}")
    elif args.command == "restore-file":
        dest = restore_backup(args.file)
        print(f"Restored backup to: {dest}")


if __name__ == "__main__":
    main()



#run this through task scheduler to run weekly and create a backup of the database.

#cd "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend"
#.\venv\Scripts\Activate.ps1
#python backup_db.py weekly



#task scheduler command to run weekly backup of the database
#-NoProfile -ExecutionPolicy Bypass -File "D:\CFS_WEBAPP\CFS_Stock_site\Webapp\Backend\backup_db.py" weekly