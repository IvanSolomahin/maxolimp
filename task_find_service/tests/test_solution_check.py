import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, UploadFile

from app.routers.tasks import check_task_solution


class SolutionCheckTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.task_id = uuid.uuid4()
        self.db = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(statement="Найдите x")))

    async def test_text_only_is_sent_without_attachment(self):
        with patch("app.routers.tasks.check_solution", return_value={"text": "Верно", "verdict": 0}) as check:
            result = await check_task_solution(self.task_id, self.db, file=None, answer_text="  x = 2  ")
        self.assertEqual(result["verdict"], 0)
        self.assertIsNone(result["filename"])
        self.assertIsNone(check.call_args.args[0])
        self.assertIn("x = 2", check.call_args.args[1])

    async def test_file_and_text_are_sent_together(self):
        from io import BytesIO

        file = UploadFile(filename="solution.png", file=BytesIO(b"image"))
        with patch("app.routers.tasks.check_solution", return_value={"text": "Разбор", "verdict": 1}) as check:
            result = await check_task_solution(self.task_id, self.db, file=file, answer_text="Мой ответ")
            self.assertEqual(result["filename"], "solution.png")
            self.assertIn("Мой ответ", check.call_args.args[1])
            self.assertIsNotNone(check.call_args.args[0])

    async def test_file_only_remains_supported(self):
        from io import BytesIO

        file = UploadFile(filename="solution.jpg", file=BytesIO(b"image"))
        with patch("app.routers.tasks.check_solution", return_value={"text": "Разбор", "verdict": 1}) as check:
            result = await check_task_solution(self.task_id, self.db, file=file, answer_text=None)
        self.assertEqual(result["filename"], "solution.jpg")
        self.assertIn("текст не предоставлен", check.call_args.args[1])

    async def test_empty_submission_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            await check_task_solution(self.task_id, self.db, file=None, answer_text="  ")
        self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
