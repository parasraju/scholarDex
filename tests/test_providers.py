"""Tests for provider search concurrency, ranking, and error handling."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from scholardex.models import Paper
from scholardex.providers import search_all, _rank, _dedupe


class DummyProvider:
    def __init__(self, name: str, papers: list[Paper], fail: bool = False):
        self.name = name
        self._papers = papers
        self._fail = fail

    def search(self, query: str, limit: int = 5) -> list[Paper]:
        if self._fail:
            raise RuntimeError(f"Provider {self.name} failed")
        return self._papers[:limit]

    def can_resolve(self, ref) -> bool:
        return False

    def resolve(self, ref):
        return None


class TestProviderSearchAndRanking(unittest.TestCase):
    def test_ranking(self):
        p1 = Paper(title="A", citations=10, year=2020)
        p2 = Paper(title="B", citations=20, year=2019)
        p3 = Paper(title="C", citations=20, year=2021)
        p4 = Paper(title="D", citations=5, year=2022)
        p5 = Paper(title="E", citations=0, year=2023)

        ranked = _rank([p1, p2, p3, p4, p5])
        # Sorted by citations desc, then year desc:
        # p3 (20, 2021)
        # p2 (20, 2019)
        # p1 (10, 2020)
        # p4 (5, 2022)
        # p5 (0, 2023)
        self.assertEqual([p.title for p in ranked], ["C", "B", "A", "D", "E"])

    def test_search_all_concurrent_and_graceful_failure(self):
        import scholardex.providers as prov_mod

        # Temporarily override registry for test
        old_registry = prov_mod._REGISTRY.copy()
        try:
            prov_mod._REGISTRY.clear()

            p1 = Paper(title="Paper One", citations=5, year=2020)
            p2 = Paper(title="Paper Two", citations=50, year=2023)
            p3 = Paper(title="Paper One Duplicate", citations=10, year=2020)

            prov_mod.register(DummyProvider("provA", [p1]))
            prov_mod.register(DummyProvider("provB", [p2, p3]))
            prov_mod.register(DummyProvider("provC", [], fail=True))

            results = search_all("test query", limit=10)
            # Should succeed despite provC failing, dedupe "Paper One" (if matching key), and rank by citations/year.
            # p2 has 50 citations, p1 has 5 citations.
            self.assertTrue(len(results) >= 2)
            self.assertEqual(results[0].title, "Paper Two")
        finally:
            prov_mod._REGISTRY.clear()
            prov_mod._REGISTRY.update(old_registry)


if __name__ == "__main__":
    unittest.main()
