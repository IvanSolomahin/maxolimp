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
        scope=settings.gigachat_scope
    ) as client:
        with open(file_path, "rb") as f:
            uploaded = client.upload_file(f, purpose="general")

        result = client.chat(
            {
                "model": "GigaChat-2-Pro",
                "function_call": "auto",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "attachments": [uploaded.id_],
                    }
                ],
                "temperature": 0.1,
                "response_format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": (
                                    "Подробный разбор решения: вердикт, "
                                    "правильные шаги, ошибки, как исправить, "
                                    "итоговый правильный ответ."
                                )
                            },
                            "verdict": {
                                "type": "integer",
                                "enum": [0, 1],
                                "description": (
                                    "0 — задача зачтена (решение и ответ верные), "
                                    "1 — задача не зачтена (решение или ответ неверные)."
                                )
                            }
                        },
                        "required": ["text", "verdict"],
                        "additionalProperties": False
                    },
                    "strict": True
                }
            }
        )

        content = result.choices[0].message.content
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return {"text": content or "", "verdict": 1}