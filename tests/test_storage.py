"""Tests for library storage functions (sorting, slug collisions, deletion)."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scholardex.models import Paper, SummaryResult
from scholardex import storage


class TestStorageLibrary(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = TemporaryDirectory()
        self.lib_dir = Path(self.tmp_dir.name) / "library"
        self.index_path = self.lib_dir / "index.json"
        
        # Patch LIBRARY_DIR and _INDEX_PATH
        self.patcher1 = patch("scholardex.storage.LIBRARY_DIR", self.lib_dir)
        self.patcher2 = patch("scholardex.storage._INDEX_PATH", self.index_path)
        self.patcher1.start()
        self.patcher2.start()

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        self.tmp_dir.cleanup()

    def test_slug_collision_handling(self):
        p1 = Paper(title="Same Title", year=2023)
        p2 = Paper(title="Same Title", year=2023)
        res = SummaryResult(summary="Summary text", model="test-model")

        path1 = storage.save_paper(p1, res)
        path2 = storage.save_paper(p2, res)

        self.assertEqual(path1.stem, "2023-same-title")
        self.assertEqual(path2.stem, "2023-same-title-1")
        
        index = storage._load_index()
        self.assertIn("2023-same-title", index)
        self.assertIn("2023-same-title-1", index)

    def test_list_papers_sorting_by_added_desc(self):
        p1 = Paper(title="Paper A", year=2020)
        p2 = Paper(title="Paper B", year=2021)
        res = SummaryResult(summary="Summary", model="test-model")

        # Mock datetime to control added timestamps
        with patch("scholardex.storage.datetime") as mock_dt:
            mock_dt.now().strftime.return_value = "2026-01-01 10:00"
            storage.save_paper(p1, res)

            mock_dt.now().strftime.return_value = "2026-01-02 12:00"
            storage.save_paper(p2, res)

        papers = storage.list_papers()
        self.assertEqual(len(papers), 2)
        # Newest added ("2026-01-02 12:00") should be first
        self.assertEqual(papers[0]["title"], "Paper B")
        self.assertEqual(papers[1]["title"], "Paper A")

    def test_delete_paper(self):
        p1 = Paper(title="To Be Deleted", year=2022)
        res = SummaryResult(summary="Summary", model="test-model")
        path1 = storage.save_paper(p1, res)

        self.assertTrue(path1.exists())
        index = storage._load_index()
        slug = "2022-to-be-deleted"
        self.assertIn(slug, index)

        # Delete non-existent
        self.assertFalse(storage.delete_paper("non-existent"))

        # Delete existent
        self.assertTrue(storage.delete_paper(slug))
        self.assertFalse(path1.exists())
        self.assertNotIn(slug, storage._load_index())


if __name__ == "__main__":
    unittest.main()
