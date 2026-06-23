"""
Management command: backup_db

Creates a gzip-compressed pg_dump of the configured DATABASE_URL.
Saves backups to BACKUP_DIR (default: BASE_DIR/backups/).
Keeps the most recent BACKUP_KEEP files (default: 7).

Usage:
    python manage.py backup_db
    BACKUP_DIR=/mnt/backups python manage.py backup_db

To run daily on Railway: add a Cron service in your Railway project with
    start command:  python manage.py backup_db
    schedule:       0 2 * * *   (daily at 02:00 UTC)
"""

import gzip
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Backup the PostgreSQL database to a gzip-compressed .sql.gz file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep",
            type=int,
            default=int(os.getenv("BACKUP_KEEP", "7")),
            help="Number of backup files to retain (default: 7 or BACKUP_KEEP env var).",
        )
        parser.add_argument(
            "--output-dir",
            default=os.getenv("BACKUP_DIR", ""),
            help="Directory to store backups (default: <BASE_DIR>/backups/ or BACKUP_DIR env var).",
        )

    def handle(self, *args, **options):
        backup_dir = Path(options["output_dir"] or (settings.BASE_DIR / "backups"))
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = backup_dir / f"db_backup_{timestamp}.sql.gz"

        db_url = os.getenv("DATABASE_URL", "")
        if not db_url:
            # Try Django DATABASES setting
            db_cfg = settings.DATABASES.get("default", {})
            host = db_cfg.get("HOST", "localhost")
            port = db_cfg.get("PORT", "5432")
            name = db_cfg.get("NAME", "")
            user = db_cfg.get("USER", "")
            password = db_cfg.get("PASSWORD", "")
        else:
            parsed = urlparse(db_url)
            host = parsed.hostname or "localhost"
            port = str(parsed.port or 5432)
            name = parsed.path.lstrip("/")
            user = parsed.username or ""
            password = parsed.password or ""

        if not name:
            self.stderr.write(
                self.style.ERROR("No database name found. Check DATABASE_URL or DATABASES setting.")
            )
            return

        pg_dump = shutil.which("pg_dump")
        if not pg_dump:
            self.stderr.write(
                self.style.ERROR("pg_dump not found on PATH. Install postgresql-client.")
            )
            return

        env = os.environ.copy()
        if password:
            env["PGPASSWORD"] = password

        cmd = [pg_dump, "-h", host, "-p", str(port), "-U", user, "--no-password", name]
        self.stdout.write(f"Starting backup of database '{name}' to {filename} ...")

        try:
            proc = subprocess.run(cmd, capture_output=True, env=env, check=True)
        except subprocess.CalledProcessError as exc:
            self.stderr.write(self.style.ERROR(f"pg_dump failed: {exc.stderr.decode()[:500]}"))
            return

        with gzip.open(filename, "wb") as gz:
            gz.write(proc.stdout)

        size_kb = filename.stat().st_size // 1024
        self.stdout.write(self.style.SUCCESS(f"Backup saved: {filename} ({size_kb} KB)"))

        # Rotation: keep only the most recent N backups
        keep = options["keep"]
        backups = sorted(backup_dir.glob("db_backup_*.sql.gz"))
        for old_file in backups[:-keep]:
            old_file.unlink()
            self.stdout.write(f"Removed old backup: {old_file.name}")
