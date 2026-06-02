"""Active disk space watchdog with LRU database cleanup.

Monitors local storage and enforces disk quotas by deleting oldest
processed records when space exceeds limits.
"""

from __future__ import annotations

import logging
import shutil
import threading
from pathlib import Path
from typing import Any

from nexus_agent.training.data.ingestion import WALDatabase

logger = logging.getLogger(__name__)


class DiskWatchdog:
    """Active watchdog that monitors disk space and enforces quotas.

    When disk usage exceeds the target limit, the watchdog queries and
    deletes the oldest processed records, followed by a database VACUUM.

    Args:
        db: WAL database instance.
        cache_dir: Directory to monitor for disk usage.
        target_bytes: Target disk usage in bytes (default 30GB).
        max_bytes: Maximum allowed disk usage before forced cleanup (default 50GB).
        check_interval: Seconds between disk checks.
    """

    def __init__(
        self,
        db: WALDatabase,
        cache_dir: str | Path,
        target_bytes: int = 30 * 1024 * 1024 * 1024,
        max_bytes: int = 50 * 1024 * 1024 * 1024,
        check_interval: float = 60.0,
    ):
        self._db = db
        self._cache_dir = Path(cache_dir)
        self._target_bytes = target_bytes
        self._max_bytes = max_bytes
        self._check_interval = check_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def target_bytes(self) -> int:
        return self._target_bytes

    @target_bytes.setter
    def target_bytes(self, value: int) -> None:
        self._target_bytes = value

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    def get_disk_usage(self) -> int:
        """Get current disk usage of the cache directory in bytes."""
        if not self._cache_dir.exists():
            return 0
        total = 0
        for item in self._cache_dir.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
        return total

    def get_disk_free(self) -> int:
        """Get free disk space in bytes."""
        usage = shutil.disk_usage(str(self._cache_dir))
        return usage.free

    def cleanup_processed_records(self, target_freed: int) -> int:
        """Delete oldest processed records until target_freed bytes are reclaimed.

        Returns:
            Number of records deleted.
        """
        total_deleted = 0
        bytes_freed = 0

        while bytes_freed < target_freed:
            # Query oldest processed records
            rows = self._db.execute(
                """
                SELECT id, sample_uid, content, token_count
                FROM samples
                WHERE status = 'processed'
                ORDER BY created_at ASC
                LIMIT 100
                """
            ).fetchall()

            if not rows:
                break

            uids_to_delete = []
            for row in rows:
                uids_to_delete.append(row["sample_uid"])
                # Estimate bytes freed (content + overhead)
                bytes_freed += row["token_count"] * 4 + 200
                total_deleted += 1

            # Delete batch
            placeholders = ",".join("?" for _ in uids_to_delete)
            self._db.execute(
                f"DELETE FROM samples WHERE sample_uid IN ({placeholders})",
                tuple(uids_to_delete),
            )
            self._db.commit()

            logger.info(f"Deleted {len(uids_to_delete)} records, freed ~{bytes_freed / 1024 / 1024:.1f}MB")

        return total_deleted

    def check_and_cleanup(self) -> dict[str, Any]:
        """Check disk usage and perform cleanup if needed.

        Returns:
            Dict with cleanup statistics.
        """
        usage = self.get_disk_usage()
        free = self.get_disk_free()
        stats = {
            "usage_bytes": usage,
            "free_bytes": free,
            "target_bytes": self._target_bytes,
            "max_bytes": self._max_bytes,
            "cleaned": False,
            "records_deleted": 0,
        }

        if usage > self._max_bytes or free < self._target_bytes:
            # Calculate how much to free
            target_free = max(self._target_bytes, self._max_bytes - usage)
            target_free = min(target_free, usage)  # Can't free more than we have

            logger.warning(
                f"Disk quota exceeded: usage={usage / 1024 / 1024 / 1024:.1f}GB, "
                f"free={free / 1024 / 1024 / 1024:.1f}GB. Cleaning up..."
            )

            records_deleted = self.cleanup_processed_records(target_free)
            stats["cleaned"] = True
            stats["records_deleted"] = records_deleted

            # VACUUM to reclaim space
            try:
                self._db.vacuum()
            except (OSError, ValueError) as e:
                logger.warning(f"VACUUM failed: {e}")

            logger.info(f"Cleanup complete: deleted {records_deleted} records")

        return stats

    def start(self) -> None:
        """Start the watchdog in a background thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Disk watchdog started")

    def stop(self) -> None:
        """Stop the watchdog."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("Disk watchdog stopped")

    def _run_loop(self) -> None:
        """Main watchdog loop."""
        while not self._stop_event.is_set():
            try:
                self.check_and_cleanup()
            except (OSError, ValueError, RuntimeError) as e:
                logger.error(f"Watchdog error: {e}")
            self._stop_event.wait(self._check_interval)

    def __enter__(self) -> DiskWatchdog:
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()
