"""Rule-only retrieval checks; no embedding provider or model request."""
import tempfile
import unittest
from pathlib import Path

from kp_agent.retrieval import RetrievalService


class RuleRetrievalV2Tests(unittest.TestCase):
    def setUp(self):
        self.retrieval = RetrievalService()

    def topic(self, query, title):
        results = self.retrieval.search(query)
        return next(item for item in results if item["title"] == title)

    def test_library_skill_has_verified_source_for_archive_actions(self):
        result = self.topic("图馆 查资料", "图书馆使用：查书、报刊和档案")
        self.assertEqual((57, 49), (result["pdf_page"], result["printed_page"]))
        self.assertIn("资料确实存在", result["text"])

    def test_first_aid_does_not_turn_the_story_item_into_a_core_rule(self):
        result = self.topic("急救 包扎", "急救：基础恢复效果")
        self.assertEqual(103, result["pdf_page"])
        self.assertIn("恢复 1 HP", result["text"])
        self.assertIn("场景约定", result["text"])

    def test_damage_and_mp_sources_are_present(self):
        damage = self.topic("重伤 HP", "HP伤害、重伤和归零")
        mana = self.topic("魔法值 MP", "MP：魔法值的作用与自然恢复")
        self.assertEqual(102, damage["pdf_page"])
        self.assertEqual(154, mana["pdf_page"])

    def test_default_corpus_contains_rules_and_no_authored_secrets(self):
        self.assertEqual(17, len(self.retrieval.store))
        corpus = "\n".join(chunk.text for chunk in self.retrieval.store.chunks.values())
        for secret in ("17号柜", "封存铜片", "scholar_statement", "archive_route"):
            self.assertNotIn(secret, corpus)
        self.assertEqual([], self.retrieval.search(""))

    def test_cache_reload_preserves_evidence_identifiers(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "rules.json"
            first = RetrievalService(cache_path=cache).search("图书馆使用")
            second = RetrievalService(cache_path=cache).search("图书馆使用")
            self.assertEqual([item["evidence_id"] for item in first],
                             [item["evidence_id"] for item in second])


if __name__ == "__main__":
    unittest.main()
