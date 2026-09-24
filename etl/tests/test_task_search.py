import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

import task_search as search


class FakeTokenizer:
    def encode(self, text):
        return type("Encoding", (), {"ids": text.split()})()


class FakeResponse:
    status_code = 200

    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class FakeSession:
    def post(self, url, headers, json, timeout):
        vectors = []
        for index, value in enumerate(json["input"]):
            text = value.lower()
            vector = [float("геометр" in text), float("энерги" in text), 1.0]
            vectors.append({"index": index, "embedding": vector})
        return FakeResponse({"data": vectors[::-1], "model": json["model"], "usage": {"total_tokens": 3}})


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.db = root / "source.db"
        self.config = search.Config(db=self.db, index_dir=root / "indexes", dimensions=3, max_tokens=5, api_key="fake")
        self.conn = sqlite3.connect(self.db)
        self.conn.execute("CREATE TABLE problems (subject TEXT, problem_id INTEGER, grade TEXT, year TEXT, url TEXT, statement TEXT, classifier TEXT, solution TEXT, PRIMARY KEY(subject,problem_id))")
        self.put("math", 1, "8-9", "2020", "Геометрия: треугольник", "геометрия", "Проведём высоту")
        self.put("math", 2, "9", "2020", "Геометрия: треугольник", "геометрия", "Другое решение")
        self.put("physics", 3, "10", "2021", "Найдите энергию", "механика", "закон сохранения энергии")
        self.put("physics", 4, "10", "2021", "Длинная задача", "", "раз два три четыре пять шесть")
        self.conn.commit()
        self.patcher = patch.object(search, "get_tokenizer", return_value=FakeTokenizer())
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.conn.close()
        self.temporary.cleanup()

    def put(self, subject, problem_id, grade, year, statement, classifier, solution):
        self.conn.execute("INSERT OR REPLACE INTO problems VALUES (?,?,?,?,?,?,?,?)",
                          (subject, problem_id, grade, year, f"https://example/{problem_id}", statement, classifier, solution))

    def test_incremental_search_filters_duplicates_and_model_isolation(self):
        session = FakeSession()
        progress = []
        report = search.build_index(self.config, session=session, batch_size=2,
                                    workers=2, progress=progress.append)
        self.assertEqual(report["embedded"], 7)
        self.assertEqual(progress[0]["scanned"], 0)
        self.assertEqual(progress[-1]["scanned"], 4)
        self.assertTrue(progress[-1]["final"])
        self.assertEqual([(x["problem_id"], x["kind"]) for x in report["skipped"]], [(4, "solution")])
        again = search.build_index(self.config, session=session)
        self.assertEqual(again["embedded"], 0)
        self.assertEqual(again["unchanged"], 8)
        index = search.open_index(self.config)
        index.execute("DELETE FROM vectors WHERE subject='math' AND problem_id=1 AND kind='topic'")
        index.commit()
        index.close()
        recovered = search.build_index(self.config, session=session)
        self.assertEqual(recovered["embedded"], 1)
        results = search.search("геометрия", mode="topic", subject="math", grade="8", year="2020", method="hybrid", config=self.config, session=session)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["problem_id"], 1)
        self.assertEqual(results[0]["duplicates"], [])  # grade filter excludes task 2
        results = search.search("геометрия", mode="topic", subject="math", method="fts", config=self.config)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0]["duplicates"]), 1)
        self.assertEqual(set([results[0]["problem_id"], *results[0]["duplicates"]]), {1, 2})
        results = search.search("энергии", mode="solution", subject="physics", method="vector", config=self.config, session=session)
        self.assertEqual(results[0]["problem_id"], 3)
        lexical = search.search("шесть", mode="solution", subject="physics", method="fts", config=self.config)
        self.assertEqual(lexical[0]["problem_id"], 4)
        self.put("physics", 3, "10", "2021", "Найдите энергию", "механика", "геометрическое построение")
        self.conn.commit()
        changed = search.build_index(self.config, session=session)
        self.assertEqual(changed["embedded"], 1)
        self.conn.execute("DELETE FROM problems WHERE subject='math' AND problem_id=2")
        self.conn.commit()
        deleted = search.build_index(self.config, session=session)
        self.assertEqual(deleted["deleted"], 1)
        other = search.Config(db=self.db, index_dir=self.config.index_dir, model="another/model", dimensions=3,
                              max_tokens=5, tokenizer=Path("unused"), api_key="fake")
        self.assertNotEqual(search.index_path(other.index_dir, other.model, 3), search.index_path(self.config.index_dir, self.config.model, 3))
        self.assertEqual(search.build_index(other, limit=1, session=session)["embedded"], 2)
        self.assertEqual(search.build_index(self.config, session=session)["embedded"], 0)

    def test_invalid_embedding_response(self):
        class BadSession:
            def post(self, *args, **kwargs):
                return FakeResponse({"data": [{"index": 0, "embedding": [1, 2]}]})
        with self.assertRaisesRegex(ValueError, "размерность"):
            search.embed(["a"], self.config, BadSession())

    def test_proxy_disconnect_is_retried_and_concurrency_reduces(self):
        class DisconnectingSession(FakeSession):
            calls = 0

            def post(self, *args, **kwargs):
                self.calls += 1
                if self.calls < 3:
                    raise requests.exceptions.ProxyError("RemoteDisconnected")
                return super().post(*args, **kwargs)

        session = DisconnectingSession()
        gate = search.RequestGate(32)
        with patch.object(search.time, "sleep"), patch.object(search.random, "uniform", return_value=0):
            vectors, tokens = search.embed(["геометрия"], self.config, session, gate)
        self.assertEqual(session.calls, 3)
        self.assertEqual(len(vectors[0]), 3)
        self.assertEqual(tokens, 3)
        self.assertEqual(gate.snapshot(), (0, 2, 2))


if __name__ == "__main__":
    unittest.main()
