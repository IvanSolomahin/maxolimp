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
