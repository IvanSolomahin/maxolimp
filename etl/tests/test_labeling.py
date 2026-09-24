import argparse
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from labeling import label_difficulty as label


class LabelDifficultyTests(unittest.TestCase):
    def test_score_mapping_and_rejection(self):
        for score, expected in [(0, 1), (4.49, 5), (4.5, 6), (9, 10)]:
            body = {"answers": {"difficulty": {"type": "score", "score": score}}}
            self.assertEqual(label.parse_difficulty(body), expected)
        with self.assertRaises(ValueError):
            label.parse_difficulty({"answers": {"difficulty": {"type": "score", "score": 10}}})

    def test_request_uses_local_proxy_and_olympiad_rubric(self):
        row = {"subject": "math", "grade": "9", "statement": " Условие ", "solution": " Решение "}

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"answers": {"difficulty": {"type": "score", "score": 6.2}}}

        class FakeSession:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def post(self, url, **kwargs):
                if url != label.API_URL:
                    raise AssertionError(url)
                if kwargs["proxies"]["https"] != "http://127.0.0.1:12334":
                    raise AssertionError(kwargs["proxies"])
                if len(kwargs["json"]["questions"]["difficulty"]["criteria"]) != 10:
                    raise AssertionError("Incorrect rubric size")
                if kwargs["json"]["state"]["statement"] != "Условие":
                    raise AssertionError(kwargs["json"]["state"])
                return FakeResponse()

        with patch.object(label.requests, "Session", FakeSession):
            self.assertEqual(label.label_one(row, "test-key", "http://127.0.0.1:12334"), 7)

    def test_adds_column_and_resumes_only_missing_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "problems.sqlite3"
            connection = sqlite3.connect(db)
            connection.execute(
                "CREATE TABLE problems (subject TEXT, problem_id INTEGER, grade TEXT, "
                "statement TEXT, solution TEXT, PRIMARY KEY(subject, problem_id))"
            )
            connection.executemany(
                "INSERT INTO problems VALUES (?, ?, ?, ?, ?)",
                [("math", 1, "9", "Задача 1", "Решение 1"),
                 ("math", 2, "9", "Задача 2", "Решение 2"),
                 ("math", 3, "9", "", "")],
            )
            connection.commit()
            connection.close()
            args = argparse.Namespace(
                db=db, api_key_file=None, proxy="http://127.0.0.1:12334",
                batch_size=2, workers=2, limit=1, subject=None,
            )
            with patch.dict(label.os.environ, {"OPENROUTER_API_KEY": "test-key"}):
                with patch.object(label, "label_one", return_value=6) as mocked:
                    self.assertEqual(label.run(args), 0)
                    self.assertEqual(mocked.call_count, 1)
                    args.limit = None
                    self.assertEqual(label.run(args), 0)
                    self.assertEqual(mocked.call_count, 2)
            connection = sqlite3.connect(db)
            self.assertEqual(
                connection.execute("SELECT difficulty FROM problems ORDER BY problem_id").fetchall(),
                [(6,), (6,), (None,)],
            )
            connection.close()


if __name__ == "__main__":
    unittest.main()
