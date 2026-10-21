"""Regression checks for evidence provenance, offline retrieval and embedding caches."""
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

from kp_agent.embeddings import (EmbeddingCallError, EmbeddingConfigurationError,
                                  OpenAIEmbedder, retrieval_from_env)

from kp_agent.retrieval import RetrievalService
from trpg.rules_store import RuleStore, chunk_text


class TestAgentRuleRetrieval(unittest.TestCase):
    def setUp(self):
        self.service = RetrievalService()

    def test_colloquial_player_actions_find_the_matching_rule(self):
        cases = {
            "我想偷偷绕到管家身后，不让他发现": "潜行",
            "我把耳朵贴在门上听听里面的声音": "聆听",
            "我仔细听房间里有没有动静": "聆听",
            "我检查书桌抽屉，仔细找找有没有线索": "侦查",
            "失败了，我想再试一次": "孤注一骰",
        }
        for query, title in cases.items():
            with self.subTest(query=query):
                results = self.service.search(query, top_k=1)
                self.assertTrue(results)
                self.assertIn(title, results[0]["title"])

    def test_evidence_has_real_provenance_and_stable_id(self):
        evidence = self.service.search("潜行", top_k=1)[0]
        self.assertEqual(evidence["source"], "COC7th核心规则书v1.2.1.pdf")
        self.assertEqual(evidence["pdf_page"], 66)
        self.assertEqual(evidence["printed_page"], 58)
        self.assertEqual(evidence["edition"], "COC7 中文 v1.2.1")
        self.assertTrue(evidence["evidence_id"].startswith("rule_"))
        self.assertEqual(evidence["evidence_id"], RetrievalService().search("潜行", 1)[0]["evidence_id"])
        self.assertIsInstance(evidence["score"], float)

    def test_no_match_and_empty_query_return_no_evidence(self):
        self.assertEqual(self.service.search(""), [])
        self.assertEqual(self.service.search("天气预报纽约股票"), [])
        self.assertEqual(self.service.search("图书馆使用"), [])
        self.assertEqual(self.service.search("帮我查一下规则"), [])
        self.assertEqual(self.service.search("潜行", top_k=0), [])

    def test_temporary_insanity_rule_is_not_reversed(self):
        evidence = self.service.search("临时性疯狂 智力检定", top_k=1)[0]
        self.assertIn("INT 成功意味着理解恐怖", evidence["text"])
        self.assertIn("INT 失败则压抑记忆", evidence["text"])
        colloquial = self.service.search("一次掉了六点理智怎么办", top_k=1)[0]
        self.assertIn("临时性疯狂", colloquial["title"])

    def test_daily_loss_uses_stored_start_of_day_baseline(self):
        evidence = self.service.search("不定性疯狂 日初SAN 一天累计", top_k=1)[0]
        self.assertIn("day_start_san", evidence["text"])
        self.assertIn("day_san_loss", evidence["text"])
        self.assertIn("实现约定", evidence["text"])


class TestMetadataAndDeduplication(unittest.TestCase):
    def test_pages_are_not_invented_for_plain_text(self):
        chunk = chunk_text("# 潜行\n\n安静移动。", source="notes.md")[0]
        self.assertIsNone(chunk.pdf_page)
        self.assertIsNone(chunk.printed_page)
        self.assertEqual(chunk.source, "notes.md")

    def test_metadata_is_scoped_to_its_section(self):
        text = '# A\n<!-- rule_meta: {"pdf_page":66,"printed_page":58,"edition":"COC7"} -->\n\n潜行\n\n# B\n\n聆听'
        chunks = chunk_text(text, source="test.md")
        self.assertEqual(chunks[0].pdf_page, 66)
        self.assertIsNone(chunks[1].pdf_page)
        self.assertNotIn("rule_meta", chunks[0].text)

    def test_invalid_page_and_zero_chunk_length_are_rejected(self):
        with self.assertRaises(ValueError):
            chunk_text('# A\n<!-- rule_meta: {"pdf_page":0} -->\ntext')
        with self.assertRaises(ValueError):
            chunk_text("text", max_chars=0)

    def test_repeated_import_of_same_source_does_not_duplicate_evidence(self):
        store = RuleStore()
        self.assertEqual(store.add_text("# 潜行\n\n安静移动。", source="rules"), 1)
        self.assertEqual(store.add_text("# 潜行\n\n安静移动。", source="rules"), 0)
        self.assertEqual(len(store), 1)


class TestEmbeddingCache(unittest.TestCase):
    def test_documents_are_embedded_once_queries_each_time(self):
        calls = []
        def embed(text):
            calls.append(text)
            return [float("潜行" in text), float("理智" in text)]
        store = RuleStore()
        store.add_text("潜行安静移动", source="a")
        store.add_text("理智损失", source="b")
        store.set_embedder(embed, model_id="test-v1")
        self.assertEqual(len(calls), 2)  # eager document indexing
        store.search("潜行")
        store.search("理智")
        self.assertEqual(len(calls), 4)  # only the two queries are new
        store.add_text("潜行安静移动", source="a")
        self.assertEqual(len(calls), 4)

    def test_named_vectors_survive_disk_roundtrip_and_model_change_rebuilds(self):
        calls = []
        def embed(text):
            calls.append(text)
            return [1.0, 0.5]
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            store = RuleStore()
            store.add_text("潜行", source="a")
            store.set_embedder(embed, model_id="provider/model-v1/2")
            store.save(str(cache))
            restored = RuleStore.load(str(cache))
            restored.set_embedder(embed, model_id="provider/model-v1/2")
            self.assertEqual(len(calls), 1)
            restored.search("潜行")
            self.assertEqual(len(calls), 2)
            restored.set_embedder(embed, model_id="provider/model-v2/2")
            self.assertEqual(len(calls), 3)

    def test_mismatched_or_nonfinite_vectors_fail_clearly(self):
        store = RuleStore()
        store.add_text("潜行")
        store.set_embedder(lambda text: [1, 2] if text == "潜行" else [1], model_id="bad-provider")
        with self.assertRaisesRegex(ValueError, "dimensions"):
            store.search("理智")
        with self.assertRaisesRegex(ValueError, "finite"):
            RuleStore()._validate_vector([float("nan")])

    def test_source_edit_invalidates_service_disk_cache(self):
        calls = []
        def embed(text):
            calls.append(text)
            return [1.0, 0.0]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "rules.md"
            cache = Path(directory) / "index.json"
            source.write_text("# 潜行\n\n安静移动。", encoding="utf-8")
            first = RetrievalService(source, cache, embed, "test-v1")
            self.assertEqual(len(calls), 1)
            second = RetrievalService(source, cache, embed, "test-v1")
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(second.store), 1)
            source.write_text("# 潜行\n\n安静移动，修改过。", encoding="utf-8")
            third = RetrievalService(source, cache, embed, "test-v1")
            self.assertEqual(len(calls), 2)
            self.assertIn("修改过", third.search("潜行")[0]["text"])
            self.assertEqual(first.search("潜行")[0]["pdf_page"], None)

    def test_corrupt_cache_is_rebuilt(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "index.json"
            cache.write_text("{broken", encoding="utf-8")
            service = RetrievalService(cache_path=cache)
            self.assertGreater(len(service.store), 5)
            self.assertIn("chunks", json.loads(cache.read_text(encoding="utf-8")))


class TestRuleIndexCacheBoundaries(unittest.TestCase):
    def test_valid_json_with_invalid_cache_structure_is_rebuilt(self):
        malformed = (
            [],
            {"chunks": [], "embeddings": []},
            {"chunks": [], "cache_metadata": []},
            {"chunks": [], "embedding_dimension": True},
            {"chunks": [], "embedding_dimension": 0},
        )
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "index.json"
            for data in malformed:
                with self.subTest(data=data):
                    cache.write_text(json.dumps(data), encoding="utf-8")
                    service = RetrievalService(cache_path=cache)
                    self.assertTrue(service.search("潜行"))
                    self.assertGreater(len(service.store), 5)

    def test_concurrent_saves_do_not_share_a_temporary_filename(self):
        store = RuleStore()
        store.add_text("# 潜行\n\n安静移动。", source="test.md")
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "index.json"
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda _: store.save(str(cache)), range(12)))
            restored = RuleStore.load(str(cache))
            self.assertEqual(len(restored), 1)
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_unknown_queries_remain_empty_after_disk_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "index.json"
            RetrievalService(cache_path=cache)
            restored = RetrievalService(cache_path=cache)
            self.assertEqual(restored.search("我要买苹果股票"), [])
            self.assertEqual(restored.search("图书馆使用"), [])
            self.assertEqual(restored.search("帮我查一下规则"), [])


class TestOpenAIEmbeddingConfiguration(unittest.TestCase):
    def client_with_vector(self, vector):
        client = SimpleNamespace(embeddings=SimpleNamespace(create=Mock()))
        client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=vector)])
        return client

    def test_keyword_is_default_even_if_credentials_exist(self):
        client = self.client_with_vector([1, 2])
        service = retrieval_from_env(client=client, environ={
            "OPENAI_API_KEY": "test-not-a-real-key", "OPENAI_EMBEDDING_MODEL": "explicit-test-model"})
        self.assertTrue(service.search("潜行"))
        client.embeddings.create.assert_not_called()

    def test_explicit_mode_requires_key_and_model_without_paid_calls(self):
        client = self.client_with_vector([1, 2])
        for values in ({"KP_RETRIEVAL_MODE": "openai_embeddings"},
                       {"KP_RETRIEVAL_MODE": "openai_embeddings", "OPENAI_EMBEDDING_MODEL": "chosen"},
                       {"KP_RETRIEVAL_MODE": "not-a-mode"}):
            with self.subTest(values=values):
                with self.assertRaises(EmbeddingConfigurationError):
                    retrieval_from_env(client=client, environ=values)
        client.embeddings.create.assert_not_called()

    def test_request_uses_explicit_model_and_validates_actual_dimensions(self):
        client = self.client_with_vector([0.5, 1.0])
        embedder = OpenAIEmbedder(model="chosen-by-user", dimensions=2, client=client)
        self.assertEqual(embedder("潜行"), [0.5, 1.0])
        client.embeddings.create.assert_called_once_with(
            input="潜行", model="chosen-by-user", dimensions=2, encoding_format="float")
        client.embeddings.create.return_value.data[0].embedding = [1.0]
        with self.assertRaisesRegex(EmbeddingCallError, "维度"):
            embedder("侦查")

    def test_provider_errors_are_sanitized_and_do_not_fall_back(self):
        client = self.client_with_vector([1.0, 0.5])
        client.embeddings.create.side_effect = RuntimeError("test-secret-key")
        with self.assertRaises(EmbeddingCallError) as raised:
            OpenAIEmbedder(model="chosen", client=client)("潜行")
        self.assertNotIn("test-secret-key", str(raised.exception))
        self.assertIn("未改用关键词", str(raised.exception))
        self.assertEqual(client.embeddings.create.call_count, 1)

    def test_invalid_provider_vectors_are_rejected(self):
        for vector in ([], [float("nan")], [float("inf")], [0.0, 0.0], "bad"):
            with self.subTest(vector=vector):
                with self.assertRaises(EmbeddingCallError):
                    OpenAIEmbedder(model="chosen", client=self.client_with_vector(vector))("潜行")

    def test_explicit_vector_mode_reuses_cache_and_only_embeds_new_query(self):
        client = self.client_with_vector([1.0, 0.5])
        values = {"KP_RETRIEVAL_MODE": "openai_embeddings", "OPENAI_API_KEY": "test-not-a-real-key",
                  "OPENAI_EMBEDDING_MODEL": "chosen", "OPENAI_EMBEDDING_DIMENSIONS": "2"}
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "rules.md"
            source.write_text("# 潜行\n\n安静移动。", encoding="utf-8")
            cache = Path(directory) / "index.json"
            retrieval_from_env(cache, client=client, environ=values, rule_path=source)
            self.assertEqual(client.embeddings.create.call_count, 1)
            service = retrieval_from_env(cache, client=client, environ=values, rule_path=source)
            self.assertEqual(client.embeddings.create.call_count, 1)
            service.search("潜行")
            self.assertEqual(client.embeddings.create.call_count, 2)

    def test_cache_identity_distinguishes_model_endpoint_and_dimensions(self):
        client = self.client_with_vector([1.0, 0.5])
        basic = OpenAIEmbedder(model="chosen", client=client)
        changed_model = OpenAIEmbedder(model="other", client=client)
        changed_endpoint = OpenAIEmbedder(model="chosen", base_url="https://test.invalid/v1", client=client)
        changed_dimensions = OpenAIEmbedder(model="chosen", dimensions=2, client=client)
        self.assertEqual(len({item.cache_key for item in (
            basic, changed_model, changed_endpoint, changed_dimensions)}), 4)
        for value in ("abc", "0", "-1"):
            with self.subTest(value=value):
                with self.assertRaises(EmbeddingConfigurationError):
                    retrieval_from_env(client=client, environ={
                        "KP_RETRIEVAL_MODE": "openai_embeddings", "OPENAI_API_KEY": "fake",
                        "OPENAI_EMBEDDING_MODEL": "chosen", "OPENAI_EMBEDDING_DIMENSIONS": value})


if __name__ == "__main__":
    unittest.main()
