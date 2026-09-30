from gigachat import GigaChat
from app.config import settings
import json

def generate_hint(statement: str, level: int) -> str:
    preview = statement.strip().replace("\n", " ")[:120]
    return (
        f"[stub LLM, уровень {level}] Подсказка к задаче: "
        f"попробуй выделить ключевые объекты в условии. Контекст: «{preview}…»"
    )


def generate_solution(statement: str, style: str, steps: bool) -> str:
    preview = statement.strip().replace("\n", " ")[:200]
    step_note = "пошагово" if steps else "кратко"
    return (
        f"[stub LLM, стиль={style}, {step_note}] Решение задачи:\n"
        f"1. Прочитать условие.\n2. Применить подходящий метод.\n"
        f"Условие (фрагмент): «{preview}…»"
    )

def check_solution(file_path: str, prompt: str) -> dict:
    with GigaChat(
        base_url="https://api.giga.chat/v1",
        credentials=settings.gigachat_credentials,
        scope=settings.gigachat_scope,
    ) as client:
        with open(file_path, "rb") as f:
            uploaded = client.upload_file(f, purpose="general")

        result = client.chat({
            "model": "GigaChat-2-Pro",
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "attachments": [uploaded.id_],
                }
            ],
            "temperature": 0.1,
        })

        content = result.choices[0].message.content
        content = content[7:-3]
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return {"text": content or "", "verdict": 1}