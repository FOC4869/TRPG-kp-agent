import os
import tempfile
import unittest

from trpg.rules_store import RuleChunk, RuleStore, chunk_text, tokenize

_DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "rules_core.md")

TEXT = """# 测试规则

## 伤害加值

伤害加值由力量与体型决定，见伤害加值表。

## 理智与疯狂

单次理智损失达到 5 点需做智力检定；单日损失达到当前理智的 1/5 进入不定期疯狂。
"""


class TestChunking(unittest.TestCase):
    def test_split_by_heading(self):
        chunks = chunk_text(TEXT, source="test")
        titles = {c.title for c in chunks}
        self.assertIn("伤害加值", titles)
        self.assertIn("理智与疯狂", titles)
        self.assertTrue(all(c.text for c in chunks))

    def test_order_is_sequential(self):
        chunks = chunk_text(TEXT)
        self.assertEqual([c.order for c in chunks], list(range(len(chunks))))


class TestTokenize(unittest.TestCase):
    def test_cjk_bigrams_and_ascii(self):
        toks = tokenize("理智损失 HP 10")
        self.assertIn("理智", toks)
        self.assertIn("hp", toks)


class TestKeywordSearch(unittest.TestCase):
    def test_search_returns_relevant_chunk(self):
        store = RuleStore()
        store.add_text(TEXT, source="test")
        results = store.search("理智损失", top_k=2)
        self.assertTrue(results)
        self.assertIn("理智", results[0].chunk.text)

    def test_add_file(self):
        store = RuleStore()
        n = store.add_file(_DATA_FILE)
        self.assertGreater(n, 0)
        self.assertIn("rules_core.md", store.sources())

    def test_add_dir(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("a.md", "b.txt"):
                with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                    f.write(f"# 规则 {name}\n\n这是 {name} 的内容。\n")
            store = RuleStore()
            n = store.add_dir(d)
        self.assertEqual(n, 2)
        self.assertEqual(set(store.sources()), {"a.md", "b.txt"})

    def test_empty_query(self):
        store = RuleStore()
        store.add_text(TEXT)
        self.assertEqual(store.search("   "), [])


class TestVectorSearch(unittest.TestCase):
    def test_with_fake_embedder(self):
        vocab = ["理智", "伤害", "成长", "移动"]
        store = RuleStore()
        store.add_text("伤害加值由力量与体型决定", source="a")
        store.add_text("理智损失达到 5 点进入临时疯狂", source="b")
        store.set_embedder(lambda t: [1.0 if w in t else 0.0 for w in vocab])
        results = store.search("理智")
        self.assertTrue(results)
        self.assertIn("理智", results[0].chunk.text)
        self.assertTrue(all(isinstance(r.score, float) for r in results))


class TestPersist(unittest.TestCase):
    def test_save_load_roundtrip(self):
        store = RuleStore()
        store.add_text(TEXT, source="test")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "rules.json")
            store.save(path)
            store2 = RuleStore.load(path)
        self.assertEqual(len(store2), len(store))
        self.assertEqual(store2.sources(), store.sources())
        self.assertEqual(store2.search("理智")[0].chunk.text, store.search("理智")[0].chunk.text)


if __name__ == "__main__":
    unittest.main()
