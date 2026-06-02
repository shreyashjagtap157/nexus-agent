"""PyTorch iterable dataset with stratified category-aware sampling.

Provides an iterable dataset wrapper over the WAL database with stratified
and category-specific queries for proportional representation of training data.
"""

from __future__ import annotations

import json
import logging
import random
import time
from collections.abc import Iterator
from typing import Any

import torch
from torch.utils.data import IterableDataset, get_worker_info

from nexus_agent.training.data.ingestion import WALDatabase

logger = logging.getLogger(__name__)


class StratifiedDataset(IterableDataset):
    """Iterable dataset with stratified category sampling from SQLite.

    Supports dynamic filtering by category tags and proportional
    representation of different dataset categories.

    Args:
        db: WAL database instance.
        batch_size: Number of samples per batch.
        max_seq_length: Maximum sequence length for tokenization.
        categories: Optional list of categories to include. None = all.
        category_weights: Optional dict mapping category → sampling weight.
        shuffle: Whether to shuffle within each category.
    """

    def __init__(
        self,
        db: WALDatabase,
        batch_size: int = 32,
        max_seq_length: int = 2048,
        categories: list[str] | None = None,
        category_weights: dict[str, float] | None = None,
        shuffle: bool = True,
    ):
        self._db = db
        self._batch_size = batch_size
        self._max_seq_length = max_seq_length
        self._categories = categories
        self._category_weights = category_weights or {}
        self._shuffle = shuffle
        self._worker_id = 0
        self._num_workers = 1

    def __iter__(self) -> Iterator[dict[str, Any]]:
        """Iterate over stratified batches."""
        worker_info = get_worker_info()
        if worker_info is not None:
            self._worker_id = worker_info.id
            self._num_workers = worker_info.num_workers

        category_batches = self._fetch_category_batches()
        if not category_batches:
            return

        # Interleave category batches proportionally
        all_batches: list[dict[str, Any]] = []
        for category, batch in category_batches:
            weight = self._category_weights.get(category, 1.0)
            # Add batch multiple times proportional to weight
            repeat_count = max(1, int(weight * 10))
            for _ in range(repeat_count):
                all_batches.append(batch)

        if self._shuffle:
            random.shuffle(all_batches)

        # Distribute across workers
        per_worker = len(all_batches) // self._num_workers
        start = self._worker_id * per_worker
        end = start + per_worker
        for batch in all_batches[start:end]:
            yield batch

    def _fetch_category_batches(self) -> list[tuple[str, dict[str, Any]]]:
        """Fetch batches stratified by category."""
        query = """
            SELECT sample_uid, content, token_count, category, dataset_name, metadata
            FROM samples
            WHERE status = 'unprocessed'
        """
        params: list[Any] = []

        if self._categories:
            placeholders = ",".join("?" for _ in self._categories)
            query += f" AND category IN ({placeholders})"
            params.extend(self._categories)

        query += " ORDER BY category, created_at"

        rows = self._db.execute(query, tuple(params)).fetchall()
        if not rows:
            return []

        # Group by category
        by_category: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            cat = row["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append({
                "sample_uid": row["sample_uid"],
                "content": row["content"],
                "token_count": row["token_count"],
                "category": row["category"],
                "dataset_name": row["dataset_name"],
                "metadata": json.loads(row["metadata"] or "{}"),
            })

        # Create batches from each category
        result: list[tuple[str, dict[str, Any]]] = []
        for category, samples in by_category.items():
            if self._shuffle:
                random.shuffle(samples)

            # Truncate sequences
            for sample in samples:
                tokens = sample["content"][:self._max_seq_length]
                sample["content"] = tokens
                sample["token_count"] = len(tokens)

            # Create batches
            for i in range(0, len(samples), self._batch_size):
                batch_samples = samples[i:i + self._batch_size]
                if len(batch_samples) > 0:
                    batch = self._collate_batch(batch_samples)
                    result.append((category, batch))

        return result

    def _collate_batch(self, samples: list[dict[str, Any]]) -> dict[str, Any]:
        """Collate samples into a batch tensor dict."""
        contents = [s["content"] for s in samples]
        token_counts = [s["token_count"] for s in samples]
        categories = [s["category"] for s in samples]
        uids = [s["sample_uid"] for s in samples]

        # Pad contents to max length in batch
        max_len = max(token_counts) if token_counts else 0
        max_len = min(max_len, self._max_seq_length)

        padded_contents = []
        attention_masks = []
        for content in contents:
            padded = content.ljust(max_len)[:max_len]
            mask = [1] * len(padded) + [0] * (max_len - len(padded))
            padded_contents.append(padded)
            attention_masks.append(mask[:max_len])

        return {
            "input_ids": padded_contents,
            "attention_mask": torch.tensor(attention_masks, dtype=torch.bool),
            "token_counts": torch.tensor(token_counts, dtype=torch.long),
            "categories": categories,
            "sample_uids": uids,
            "batch_size": len(samples),
        }

    def mark_processed(self, sample_uids: list[str]) -> None:
        """Mark samples as processed in the database."""
        if not sample_uids:
            return
        placeholders = ",".join("?" for _ in sample_uids)
        query = f"""
            UPDATE samples
            SET status = 'processed', updated_at = ?
            WHERE sample_uid IN ({placeholders})
        """
        params = [time.time()] + list(sample_uids)
        self._db.execute(query, tuple(params))
        self._db.commit()

    def get_category_stats(self) -> dict[str, int]:
        """Get count of unprocessed samples per category."""
        query = """
            SELECT category, COUNT(*) as cnt
            FROM samples
            WHERE status = 'unprocessed'
            GROUP BY category
        """
        rows = self._db.execute(query).fetchall()
        return {row["category"]: row["cnt"] for row in rows}

    def get_total_unprocessed(self) -> int:
        """Get total count of unprocessed samples."""
        query = "SELECT COUNT(*) as cnt FROM samples WHERE status = 'unprocessed'"
        row = self._db.execute(query).fetchone()
        return row["cnt"] if row else 0
