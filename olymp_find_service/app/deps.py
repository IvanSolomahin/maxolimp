from typing import Annotated

from fastapi import Header

from app.config import settings

BENEFIT_ALIASES = {
    "bvi": "no entrance exams",
    "no entrance exams": "no entrance exams",
    "no_entrance_exams": "no entrance exams",
    "100 points": "100 points",
    "100_points": "100 points",
    "additional_points": "additional_points",
    "additional points": "additional_points",
}

RESPONSE_BENEFIT_ALIASES = {
    "no entrance exams": "bvi",
}


def normalize_benefit_type(value: str | None) -> str | None:
    if value is None:
        return None
    key = value.strip().lower()
    return BENEFIT_ALIASES.get(key, value.strip())


def public_benefit_type(stored: str) -> str:
    return RESPONSE_BENEFIT_ALIASES.get(stored, stored)


def current_user_id(
    x_user_id: Annotated[int | None, Header()] = None,
) -> int:
    return x_user_id if x_user_id is not None else settings.default_user_id
