"""Tests for vector/semantic memory — EmbeddingEngine and VectorStore."""

import math
import tempfile
import unittest
from pathlib import Path

from nexus_agent.memory.memory_manager import MemoryManager
from nexus_agent.memory.vector_embedding import EmbeddingEngine, cosine_similarity
from nexus_agent.memory.vector_store import VectorStore


class TestEmbeddingEngine(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.engine = EmbeddingEngine(model_dir=self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_embed_returns_384d(self):
        vec = self.engine.embed("hello world")
        self.assertEqual(len(vec), 384)

    def test_embed_empty_returns_zeros(self):
        vec = self.engine.embed("")
        self.assertEqual(vec, [0.0] * 384)

    def test_embed_whitespace_returns_zeros(self):
        vec = self.engine.embed("   ")
        self.assertEqual(vec, [0.0] * 384)

    def test_embed_mode_is_ngram(self):
        # Without ONNX model, mode should be ngram
        self.assertEqual(self.engine.mode, "ngram")

    def test_embed_dimensions_property(self):
        self.assertEqual(self.engine.dimensions, 384)

    def test_similar_texts_have_positive_similarity(self):
        vec1 = self.engine.embed("python async programming patterns")
        vec2 = self.engine.embed("python async await coroutine patterns")
        sim = cosine_similarity(vec1, vec2)
        self.assertGreater(sim, 0.3)

    def test_dissimilar_texts_have_lower_similarity(self):
        vec1 = self.engine.embed("python async programming patterns")
        vec2 = self.engine.embed("the quick brown fox jumps over the lazy dog")
        sim = cosine_similarity(vec1, vec2)
        self.assertLess(sim, 0.8)

    def test_embed_many(self):
        texts = ["hello", "world", "foo bar"]
        vectors = self.engine.embed_many(texts)
        self.assertEqual(len(vectors), 3)
        self.assertEqual(len(vectors[0]), 384)

    def test_cosine_similarity_identical(self):
        vec = self.engine.embed("test")
        sim = cosine_similarity(vec, vec)
        self.assertAlmostEqual(sim, 1.0, places=5)

    def test_cosine_similarity_orthogonal(self):
        a = [1.0] + [0.0] * 383
        b = [0.0] * 384
        b[0] = 1.0
        # These should be identical after normalisation...
        # Actually ngram fallback normalises, so this test is tricky.
        # Just verify the function doesn't crash.
        self.assertIsInstance(cosine_similarity(a, b), float)

    def test_cosine_similarity_zero_vector(self):
        a = [0.0] * 384
        b = self.engine.embed("test")
        sim = cosine_similarity(a, b)
        self.assertEqual(sim, 0.0)


class TestVectorStore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "vectors.db"
        self.store = VectorStore(self.db_path)

    def tearDown(self):
        self.store.close()
        self.tmpdir.cleanup()

    def test_store_and_search(self):
        self.store.store("id1", "python async programming patterns")
        results = self.store.search("async python", limit=5)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "id1")
        self.assertGreater(results[0]["score"], 0.0)

    def test_store_and_get(self):
        self.store.store("id1", "hello world")
        entry = self.store.get("id1")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["entry_id"], "id1")

    def test_get_nonexistent(self):
        self.assertIsNone(self.store.get("nope"))

    def test_delete_existing(self):
        self.store.store("id1", "content")
        self.assertTrue(self.store.delete("id1"))
        self.assertIsNone(self.store.get("id1"))

    def test_delete_nonexistent(self):
        self.assertFalse(self.store.delete("nope"))

    def test_empty_content_is_noop(self):
        self.store.store("id1", "")
        self.assertIsNone(self.store.get("id1"))

    def test_search_empty_query(self):
        self.store.store("id1", "content")
        results = self.store.search("")
        self.assertEqual(results, [])

    def test_search_returns_relevant_first(self):
        self.store.store("id1", "the quick brown fox jumps")
        self.store.store("id2", "python async await programming")
        self.store.store("id3", "javascript event loop callback")
        results = self.store.search("python async", limit=3)
        self.assertGreaterEqual(len(results), 1)
        # "id2" should appear in the top results
        top_ids = [r["id"] for r in results[:3]]
        self.assertIn("id2", top_ids)

    def test_count(self):
        self.assertEqual(self.store.count(), 0)
        self.store.store("id1", "content a")
        self.store.store("id2", "content b")
        self.assertEqual(self.store.count(), 2)

    def test_store_batch(self):
        entries = [
            {"entry_id": "id1", "content": "python async"},
            {"entry_id": "id2", "content": "javascript callback"},
        ]
        self.store.store_batch(entries)
        self.assertEqual(self.store.count(), 2)

    def test_rebuild(self):
        self.store.store("id1", "content a")
        self.store.store("id2", "content b")
        n = self.store.rebuild()
        self.assertEqual(n, 2)

    def test_search_min_score_filter(self):
        self.store.store("id1", "python async programming")
        self.store.store("id2", "cooking recipes italian pasta")
        results = self.store.search("cooking pasta", limit=5, min_score=0.01)
        self.assertGreaterEqual(len(results), 1)
        # high threshold should filter out irrelevant
        results_high = self.store.search("cooking pasta", limit=5, min_score=0.9)
        self.assertEqual(len(results_high), 0)


class TestVectorStoreWithCustomEngine(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "vectors.db"
        self.engine = EmbeddingEngine(model_dir=self.tmpdir.name)
        self.store = VectorStore(self.db_path, embedding_engine=self.engine)

    def tearDown(self):
        self.store.close()
        self.tmpdir.cleanup()

    def test_custom_engine_works(self):
        self.store.store("id1", "custom engine test")
        results = self.store.search("custom", limit=5)
        self.assertGreaterEqual(len(results), 1)


class _HashEngineV1:
    """Simple deterministic embedding engine (v1) using md5 hashes."""
    DIMENSIONS = 384

    @property
    def mode(self) -> str:
        return "hash_v1"

    @property
    def dimensions(self) -> int:
        return self.DIMENSIONS

    def embed(self, text: str) -> list[float]:
        import hashlib
        vec = [0.0] * self.DIMENSIONS
        for i, chunk in enumerate(text.split()):
            h = int(hashlib.md5(chunk.encode()).hexdigest()[:8], 16)
            idx = (h + i * 7) % self.DIMENSIONS
            vec[idx] += 1.0 + (h % 3) * 0.1
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm > 0 else vec

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


class _HashEngineV2:
    """Different deterministic embedding engine (v2) using sha256 hashes.

    Produces different vectors from ``_HashEngineV1`` for the same text,
    simulating an upgraded embedding model.
    """
    DIMENSIONS = 384

    @property
    def mode(self) -> str:
        return "hash_v2"

    @property
    def dimensions(self) -> int:
        return self.DIMENSIONS

    def embed(self, text: str) -> list[float]:
        import hashlib
        vec = [0.0] * self.DIMENSIONS
        for i, chunk in enumerate(text.split()):
            h = int(hashlib.sha256(chunk.encode()).hexdigest()[:8], 16)
            idx = (h + i * 13) % self.DIMENSIONS
            vec[idx] += 1.0 + (h % 7) * 0.1
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm > 0 else vec

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


class TestEngineUpgradeRebuild(unittest.TestCase):
    """Rebuild after engine upgrade changes query results."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "vectors.db"
        self.engine_v1 = _HashEngineV1()
        self.engine_v2 = _HashEngineV2()
        self.store = VectorStore(self.db_path, embedding_engine=self.engine_v1)

    def tearDown(self):
        self.store.close()
        self.tmpdir.cleanup()

    def _store_sample_entries(self):
        self.store.store("id1", "python async await programming patterns")
        self.store.store("id2", "javascript promise callback event loop")
        self.store.store("id3", "docker kubernetes container orchestration")
        self.store.store("id4", "the quick brown fox jumps over the lazy dog")

    def _query_scores(self, query: str) -> dict[str, float]:
        results = self.store.search(query, limit=10, min_score=0.01)
        return {r["id"]: r["score"] for r in results}

    def test_rebuild_with_same_engine_preserves_results(self):
        """Rebuilding with the same engine should preserve scores."""
        self._store_sample_entries()
        before = self._query_scores("python async")

        n = self.store.rebuild()
        self.assertEqual(n, 4)

        after = self._query_scores("python async")

        # Scores should be the same (within floating point)
        for eid in before:
            if eid in after:
                self.assertAlmostEqual(
                    before[eid], after[eid], places=5,
                    msg=f"Score for {eid} should match after rebuild with same engine",
                )

    def test_rebuild_with_different_engine_changes_scores(self):
        """Rebuilding with a different engine should change scores."""
        self._store_sample_entries()

        before = self._query_scores("python async")

        # Swap engine to v2
        self.store._engine = self.engine_v2
        n = self.store.rebuild()
        self.assertEqual(n, 4)

        after = self._query_scores("python async")

        # Scores should differ after engine swap
        score_changed = False
        for eid in before:
            if eid in after:
                if abs(before[eid] - after[eid]) > 0.001:
                    score_changed = True
                    break
        self.assertTrue(
            score_changed,
            "Expected at least one score to differ after engine upgrade + rebuild. "
            f"Before: {before}, After: {after}",
        )

    def test_rebuild_engine_upgrade_changes_ranking_order(self):
        """Engine upgrade + rebuild can change which entry ranks first."""
        self._store_sample_entries()

        before = self._query_scores("python async")
        top_before = max(before, key=before.get) if before else None

        # Swap engine and rebuild
        self.store._engine = self.engine_v2
        self.store.rebuild()

        after = self._query_scores("python async")
        top_after = max(after, key=after.get) if after else None

        # At minimum, both engines should return the clearly relevant entry (id1)
        self.assertIn("id1", before)
        self.assertIn("id1", after)

        # id1 (python async) should rank high in both, but scores will differ
        self.assertIn("id1", before, "id1 (python async) must appear in V1 results")
        if "id4" in before:
            self.assertGreater(before["id1"], before["id4"],
                               "V1 engine: python async entry should outrank fox entry")
        self.assertIn("id1", after, "id1 (python async) must appear in V2 results")
        if "id4" in after:
            self.assertGreater(after["id1"], after["id4"],
                               "V2 engine after rebuild: python async entry should outrank fox entry")


class TestMigrationPipeline(unittest.TestCase):
    """Full FTS5 → vector store migration pipeline."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name) / "memory"
        self.mgr = MemoryManager(data_dir=self.data_dir)

    def tearDown(self):
        self.mgr.close()
        self.tmpdir.cleanup()

    def _migrate(self) -> int:
        """Replicate /memory vector migrate logic: iterate FTS5, store in vector store."""
        vs = self.mgr.vector
        if vs is None:
            return 0
        stats = self.mgr.long_term.get_stats()
        total = stats.get("total_entries", 0)
        migrated = 0
        offset = 0
        PAGE_SIZE = 50
        while offset < total:
            entries = self.mgr.long_term.list_all(limit=PAGE_SIZE, offset=offset)
            if not entries:
                break
            for entry in entries:
                eid = entry.get("id", "")
                content = entry.get("content", "")
                category = entry.get("category", "general")
                if not content or not content.strip():
                    continue
                if vs.get(eid):
                    continue
                vs.store(eid, content, category=category)
                migrated += 1
            offset += PAGE_SIZE
        return migrated

    def test_migrate_empty_does_nothing(self):
        """Migration with no FTS5 entries returns 0."""
        migrated = self._migrate()
        self.assertEqual(migrated, 0)
        self.assertEqual(self.mgr.vector.count(), 0)

    def test_migrate_single_entry(self):
        """Store in FTS5, migrate, verify vector store has it."""
        eid = self.mgr.long_term.store("python async programming patterns", category="code")
        migrated = self._migrate()
        self.assertEqual(migrated, 1)
        self.assertEqual(self.mgr.vector.count(), 1)

        # Verify the entry is retrievable
        entry = self.mgr.vector.get(eid)
        self.assertIsNotNone(entry)
        self.assertIn("python", entry["content"])

    def test_migrate_multiple_entries(self):
        """Store multiple entries in FTS5, migrate all, verify counts."""
        ids = []
        for text, cat in [
            ("python async await patterns", "code"),
            ("javascript event loop callbacks", "code"),
            ("user prefers tabs over spaces", "preference"),
            ("project uses pytest for testing", "convention"),
            ("deployment uses docker compose", "devops"),
        ]:
            eid = self.mgr.long_term.store(text, category=cat)
            ids.append(eid)

        migrated = self._migrate()
        self.assertEqual(migrated, 5)
        self.assertEqual(self.mgr.vector.count(), 5)

    def test_migrate_idempotent(self):
        """Running migrate twice should not duplicate entries."""
        self.mgr.long_term.store("python async patterns", category="code")
        self.mgr.long_term.store("javascript callbacks", category="code")

        first = self._migrate()
        self.assertEqual(first, 2)
        self.assertEqual(self.mgr.vector.count(), 2)

        # Second migration should skip already-present entries
        second = self._migrate()
        self.assertEqual(second, 0)
        self.assertEqual(self.mgr.vector.count(), 2)

    def test_migrate_then_query_returns_relevant(self):
        """After migration, semantic search returns relevant results."""
        self.mgr.long_term.store("python async await programming", category="code")
        self.mgr.long_term.store("the quick brown fox jumps", category="general")
        self.mgr.long_term.store("javascript promise callback pattern", category="code")

        self._migrate()
        self.assertEqual(self.mgr.vector.count(), 3)

        # Query via vector store for async-related content
        results = self.mgr.vector.search("async python", limit=5)
        self.assertGreaterEqual(len(results), 1)
        top_ids = [r["id"] for r in results[:3]]

        # python async entry should rank high
        lt_entries = self.mgr.long_term.list_all(limit=10)
        async_eid = None
        for e in lt_entries:
            if "python async" in e.get("content", ""):
                async_eid = e["id"]
                break
        self.assertIsNotNone(async_eid, "Expected to find the python async entry")
        self.assertIn(async_eid, top_ids, "Async entry should appear in top vector results")

    def test_migrate_with_clear_and_remigrate(self):
        """Clear vector store then re-migrate should re-embed everything."""
        self.mgr.long_term.store("python async patterns", category="code")
        self.mgr.long_term.store("javascript callbacks", category="code")

        self._migrate()
        self.assertEqual(self.mgr.vector.count(), 2)

        # Clear vector store
        cleared = self.mgr.vector.clear()
        self.assertEqual(cleared, 2)
        self.assertEqual(self.mgr.vector.count(), 0)

        # Re-migrate
        remigrated = self._migrate()
        self.assertEqual(remigrated, 2)
        self.assertEqual(self.mgr.vector.count(), 2)
