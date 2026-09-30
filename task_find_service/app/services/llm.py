from gigachat import GigaChat
from app.config import settings
import json

def check_solution(file_path: str | None, prompt: str) -> dict:
    with GigaChat(
        base_url="https://api.giga.chat/v1",
        credentials=settings.gigachat_credentials,
        scope=settings.gigachat_scope,
    ) as client:
        message = {"role": "user", "content": prompt}
        if file_path is not None:
            with open(file_path, "rb") as f:
                uploaded = client.upload_file(f, purpose="general")
            message["attachments"] = [uploaded.id_]

        result = client.chat({
            "model": "GigaChat-2-Pro",
            "messages": [message],
            "temperature": 0.1,
        })

        content = (result.choices[0].message.content or "").strip()
        if content.startswith("```") and content.endswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return {"text": content or "", "verdict": 1}
